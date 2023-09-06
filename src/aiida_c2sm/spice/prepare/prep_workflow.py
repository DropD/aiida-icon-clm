import pathlib

import aiida_shell
import pendulum
from aiida import engine, orm
from aiida.engine.processes.workchains import workchain


class PreparationWorkflow(engine.WorkChain):
    """Workchain for SPICE ICON preparations."""

    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("computer_uuid", valid_type=orm.Str, help="Computer to run on.")
        #  spec.input("parameters", valid_type=orm.JsonableData, help="Parameters.")
        spec.input("iso_current_date", valid_type=orm.Str)
        spec.input("gcm_dir", valid_type=orm.RemoteData)
        spec.input(
            "gcm_relpath_template", valid_type=orm.Str, serializer=orm.to_aiida_type
        )

        spec.outline(cls.check_inputs, cls.untar)

    def check_inputs(self) -> None:
        #  self.ctx.parameters = self.inputs.parameters.obj
        self.ctx.current_date = pendulum.DateTime.fromisoformat(
            self.inputs.iso_current_date.value
        )
        self.ctx.gcm_relpath = self.inputs.gcm_relpath_template.value.format(
            current_date=self.ctx.current_date
        )
        self.ctx.gcm_fullpath = (
            pathlib.Path(self.inputs.gcm_dir.get_remote_path()) / self.ctx.gcm_relpath
        )
        test_gcm_subdir = self.inputs.gcm_dir.clone()
        test_gcm_subdir.set_remote_path(str(self.ctx.gcm_fullpath.parent))
        assert self.ctx.gcm_fullpath.name in test_gcm_subdir.listdir()

    def untar(self) -> None:
        results, node = aiida_shell.launch_shell_job(
            "tar",
            arguments="-C gcm_data -xf {gcm_path}",
            nodes={
                "gcm_path": orm.Str(str(self.ctx.gcm_fullpath)),
            },
            metadata={
                "options": {
                    "computer": orm.load_computer(uuid=self.inputs.computer_uuid.value),
                    "account": "csstaff",
                    "max_wallclock_seconds": 600,
                    "queue_name": "normal",
                    "custom_scheduler_commands": "$SBATCH -C gpu",
                    "max_memory_kb": int(64e6),
                }
            },
        )
