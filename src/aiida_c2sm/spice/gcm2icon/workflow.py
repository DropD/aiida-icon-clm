import coolname
import pendulum
from aiida import engine, orm
from aiida.engine.processes.workchains import workchain
from typing_extensions import Self

from aiida_c2sm import spice


class Gcm2Icon(engine.WorkChain):
    """SPICE gcm2icon workflow."""

    @classmethod
    def define(cls: type[Self], spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input(
            "experiment_id",
            valid_type=orm.Str,
            serializer=orm.to_aiida_type,
            default=lambda: orm.Str(coolname.generate_slug(2)),
        )
        spec.input("parameters", valid_type=orm.JsonableData, help="SPICE params")
        spec.input(
            "computer_options", valid_type=orm.Dict, serializer=orm.to_aiida_type
        )
        spec.input(
            "prep.computer_options",
            valid_type=orm.Dict,
            serializer=orm.to_aiida_type,
        )
        spec.input(
            "conv.computer_options",
            valid_type=orm.Dict,
            serializer=orm.to_aiida_type,
        )
        spec.input(
            "icon.computer_options",
            valid_type=orm.Dict,
            serializer=orm.to_aiida_type,
        )
        spec.expose_inputs(
            spice.prep.GCM2IconPrep, exclude=["parameters", "code", "metadata"]
        )
        spec.expose_inputs(spice.prep.GCM2IconPrep, include=["code"], namespace="prep")
        spec.expose_inputs(
            spice.conv2icon.Conv2Icon, include=["code"], namespace="conv"
        )
        spec.expose_inputs(
            spice.icon_wc.IconWorkChain,
            exclude=[
                "gcm_converted",
                "lam_grid_relpath",
                "parent_grid_relpath",
                "extpar_relpath",
                "ghg_file_relpath",
                "expid",
                "code",
                "metadata",
                "options",
                "parameters",
                "restart_file_dir",
                "restart_file_name",
            ],
        )
        spec.expose_inputs(
            spice.icon_wc.IconWorkChain, include=["code"], namespace="icon"
        )

        spec.expose_outputs(spice.icon_wc.IconWorkChain)

        spec.outline(
            cls.check_inputs,
            cls.init_iterations,
            engine.while_(cls.should_run)(
                cls.prep,
                cls.conv,
                cls.wait_for_previous_icon,
                cls.icon,
                cls.incr_iteration,
            ),
            cls.wait_for_previous_icon,
            cls.finalize,
        )

    def check_inputs(self: Self) -> None:
        self.report("Checking inputs.")
        self.ctx.params = self.inputs.parameters.obj
        self.ctx.expid = self.inputs.experiment_id.value

    def init_iterations(self: Self) -> None:
        self.report("Initializing iteration variables.")
        self.ctx.current_date = self.ctx.params.start_date
        self.ctx.next_date = next_date(self.ctx.current_date)
        self.ctx.iter_num = 0

    def incr_iteration(self: Self) -> None:
        self.report("Updating iteration variables.")
        self.report(
            "Current date: {current} -> {next}".format(
                current=self.ctx.current_date.to_datetime_string(),
                next=self.ctx.next_date.to_datetime_string(),
            )
        )
        self.ctx.current_date = self.ctx.next_date
        self.ctx.next_date = next_date(self.ctx.current_date)
        self.ctx.iter_num += 1

    def should_run(self: Self) -> bool:
        should_run = self.ctx.current_date < self.ctx.params.stop_date
        if not should_run:
            self.report("Stop date is reached, stopping.")
        return should_run

    def prep(self: Self) -> None:
        self.report(
            "Starting Preparation run for date {current}.".format(
                current=self.ctx.current_date.to_datetime_string()
            )
        )
        builder = self.inputs.prep.code.get_builder()
        builder.metadata.label = (
            f"prep:{self.ctx.expid}@{self.ctx.current_date.isoformat()}"
        )
        builder.metadata.description = " ".join(
            (
                f"Preparation job for experiment {self.ctx.expid},",
                "launched from Gcm2Icon workflow.",
            )
        )
        builder.metadata.computer = builder.code.computer
        options = (
            self.inputs.computer_options.get_dict()
            | self.inputs.prep.computer_options.get_dict()
        )
        for key, value in options.items():
            builder.metadata.options[key] = value
        builder.gcm_data = self.inputs.gcm_data
        builder.parameters = orm.JsonableData(
            spice.data.PrepParams(
                date=self.ctx.current_date,
                next_date=self.ctx.next_date,
                n_parallel_tasks=self.ctx.params.prep_n_parallel_tasks,
                utils_bindir=self.ctx.params.utils_bindir,
                cfu_bindir=self.ctx.params.cfu_bindir,
                hincbound=self.ctx.params.hincbound,
                gcm_prefix=self.ctx.params.gcm_prefix,
            ),
            label=f"prep:params:{self.ctx.expid}@{self.ctx.current_date.isoformat()}",
        )
        self.to_context(preps=engine.append_(self.submit(builder)))

    def conv(self: Self) -> None:
        self.report(
            "Starting Conv2Icon run for date {current}.".format(
                current=self.ctx.current_date.to_datetime_string()
            )
        )
        builder = self.inputs.conv.code.get_builder()
        builder.metadata.label = (
            f"conv:{self.ctx.expid}@{self.ctx.current_date.isoformat()}"
        )
        builder.metadata.description = " ".join(
            (
                f"Conversion job for experiment {self.ctx.expid},",
                "launched from Gcm2Icon workflow.",
            )
        )
        builder.metadata.computer = builder.code.computer
        options = (
            self.inputs.computer_options.get_dict()
            | self.inputs.conv.computer_options.get_dict()
        )
        for key, value in options.items():
            builder.metadata.options[key] = value
        builder.gcm_prepared = self.ctx.preps[self.ctx.iter_num].outputs.gcm_prepared
        builder.ini_basedir = self.inputs.ini_basedir
        builder.boundary_data = self.inputs.boundary_data
        builder.parameters = orm.JsonableData(
            spice.conv2icon.Conv2IconParams(
                start_date=self.ctx.params.start_date,
                date=self.ctx.current_date,
                n_parallel_tasks=self.ctx.params.prep_n_parallel_tasks,
                gcm_prefix=self.ctx.params.gcm_prefix,
                omp_threads=self.ctx.params.prep_omp_threads,
                gcm_remap=self.ctx.params.gcm_remap,
                icon_input_optional=self.ctx.params.icon_input_optional,
                cleanup_previous=False,
            ),
            label=f"conv:params:{self.ctx.expid}@{self.ctx.current_date.isoformat()}",
        )
        self.to_context(convs=engine.append_(self.submit(builder)))

    def wait_for_previous_icon(self: Self) -> None:
        self.report("Making the next step wait for the previous Icon run.")
        if self.ctx.iter_num > 0:
            self.to_context(
                icons=engine.append_(orm.load_node(uuid=self.ctx.last_icon_id))
            )

    def icon(self: Self) -> None:
        self.report(
            "Starting Icon run for date {current}.".format(
                current=self.ctx.current_date.to_datetime_string()
            )
        )
        builder = spice.icon_wc.IconWorkChain.get_builder()
        builder.metadata.label = (
            f"icon:{self.ctx.expid}@{self.ctx.current_date.isoformat()}"
        )
        builder.metadata.description = " ".join(
            (
                f"Icon run for experiment {self.ctx.expid}, ",
                "launched from Gcm2Icon workflow.",
            )
        )
        builder.code = self.inputs.icon.code
        builder.options = (
            self.inputs.computer_options.get_dict()
            | self.inputs.icon.computer_options.get_dict()
        )
        builder.expid = self.inputs.experiment_id
        builder.gcm_converted = self.ctx.convs[self.ctx.iter_num].outputs.converted
        builder.boundary_data = self.inputs.boundary_data
        builder.ini_basedir = self.inputs.ini_basedir
        builder.inidata = self.inputs.inidata
        builder.ecraddir = self.inputs.ecraddir
        builder.lam_grid_relpath = self.ctx.params.lam_grid_relpath
        builder.parent_grid_relpath = self.ctx.params.parent_grid_relpath
        builder.extpar_relpath = self.ctx.params.extpar_relpath
        builder.ghg_file_relpath = self.ctx.params.ghg_file_relpath
        if self.ctx.iter_num > 0:
            prev_icon = self.ctx.icons[self.ctx.iter_num - 1]
            builder.restart_file_dir = prev_icon.outputs.restart_file_dir
            builder.restart_file_name = prev_icon.outputs.restart_file_name
        builder.parameters = orm.JsonableData(
            spice.icon_wc.IconParams(
                start_date=self.ctx.params.start_date,
                stop_date=self.ctx.params.stop_date,
                date=self.ctx.current_date,
                num_io_procs=self.ctx.params.icon_num_io_procs,
                num_restart_procs=self.ctx.params.icon_num_restart_procs,
                num_prefetch_proc=self.ctx.params.icon_num_prefetch_proc,
                hincbound=self.ctx.params.hincbound,
                gcm_prefix=self.ctx.params.gcm_prefix,
                precip_interval=self.ctx.params.precip_interval,
                runoff_interval=self.ctx.params.runoff_interval,
                sunshine_interval=self.ctx.params.sunshine_interval,
                maxt_interval=self.ctx.params.maxt_interval,
                gust_interval=self.ctx.params.gust_interval,
                melt_interval=self.ctx.params.melt_interval,
                hout_inc=self.ctx.params.hout_inc,
                operation=self.ctx.params.operation,
                dtime=self.ctx.params.dtime,
                zml_soil=self.ctx.params.zml_soil,
                ndyn_substeps=self.ctx.params.ndyn_substeps,
            ),
            label=f"icon:params:{self.ctx.expid}@{self.ctx.current_date.isoformat()}",
        )
        self.ctx.last_icon_id = self.submit(builder).uuid

    def finalize(self: Self) -> None:
        self.report(
            "Setting outputs from last Icon run (for date {current}).".format(
                current=self.ctx.icons[
                    -1
                ].inputs.parameters.obj.date.to_datetime_string()
            )
        )
        self.out_many(
            self.exposed_outputs(self.ctx.icons[-1], spice.icon_wc.IconWorkChain)
        )


def next_date(current_date: pendulum.DateTime) -> pendulum.DateTime:
    return (current_date + pendulum.duration(months=1)).start_of("month")
