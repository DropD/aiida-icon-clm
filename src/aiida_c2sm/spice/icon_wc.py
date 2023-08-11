from __future__ import annotations

import dataclasses
import datetime
import io
import pathlib
import tempfile
import textwrap
import typing

import jinja2
import netCDF4 as nc
import pendulum
import tabulate
from aiida import engine, orm
from aiida.engine.processes.workchains import workchain

from aiida_c2sm import spice


class IconWorkChain(engine.WorkChain):
    """Workchain for SPICE ICON runs."""

    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.expose_inputs(
            spice.icon.Icon,
            exclude=[
                "master_namelist",
                "model_namelist",
                "ifs2icon_filename",
                "metadata",
            ],
        )
        spec.input("parameters", valid_type=orm.JsonableData, help="Parameters.")
        spec.input(
            "options",
            valid_type=orm.Dict,
            serializer=orm.to_aiida_type,
            help="Computer options.",
        )
        spec.expose_outputs(spice.icon.Icon)

        spec.outline(cls.prepare_namelists, cls.launch_icon, cls.finalize)

    def prepare_namelists(self) -> None:
        params = self.inputs.parameters.obj
        ystartdate = params.start_date.strftime("%Y%m%d%H")
        nmlvars: dict[str, typing.Any] = {}
        next_date_full = (
            pendulum.instance(params.date).naive() + pendulum.duration(months=1)
        ).naive()
        next_date = next_date_full.start_of("month").naive()
        if params.start_date == params.date:
            nmlvars["lrestart"] = ".FALSE."
            nmlvars["check_uuid_gracefully"] = ".FALSE."
            nmlvars["ifs2icon_filename"] = f"{params.gcm_prefix}{ystartdate}_ini.nc"
        else:
            nmlvars["lrestart"] = ".TRUE."
            nmlvars["check_uuid_gracefully"] = ".TRUE."
            nmlvars["ifs2icon_filename"] = ""

        if params.num_restart_procs == 0:
            nmlvars["restart_write_mode"] = "sync"
        else:
            nmlvars["restart_write_mode"] = "dedicated procs multifile"

        self.ctx.ifs2icon_filename = nmlvars["ifs2icon_filename"]

        self.ctx.master_namelist = str_to_namelist(
            make_master_namelists(
                params,
                lrestart=nmlvars["lrestart"],
                expid=self.inputs.expid.value,
                next_date=next_date,
            )
        )

        self.ctx.model_namelist = str_to_namelist(
            make_model_namelists(
                params,
                gcm_converted=self.inputs.gcm_converted,
                ini_basedir=self.inputs.ini_basedir,
                lam_grid_path=self.inputs.lam_grid_relpath.value,
                parent_grid_path=self.inputs.parent_grid_relpath.value,
                extpar_path=self.inputs.extpar_relpath.value,
                ghg_file_path=str(
                    pathlib.Path(self.inputs.ini_basedir.get_remote_path())
                    / self.inputs.ghg_file_relpath.value
                ),
                ecraddir=self.inputs.ecraddir,
                ifs2icon_filename=nmlvars["ifs2icon_filename"],
                check_uuid_gracefully=nmlvars["check_uuid_gracefully"],
                restart_write_mode=nmlvars["restart_write_mode"],
                next_date=next_date,
            )
        )

    def launch_icon(self) -> None:
        icon_builder = self.inputs.code.get_builder()
        icon_builder.metadata.computer = self.inputs.code.computer
        icon_builder.metadata.options.account = self.inputs.options["account"]
        icon_builder.metadata.options.max_wallclock_seconds = self.inputs.options[
            "max_wallclock_seconds"
        ]
        icon_builder.metadata.options.queue_name = self.inputs.options["queue_name"]
        icon_builder.metadata.options.custom_scheduler_commands = self.inputs.options[
            "custom_scheduler_commands"
        ]
        icon_builder.metadata.options.max_memory_kb = self.inputs.options[
            "max_memory_kb"
        ]
        #  for key, value in self.inputs.options["environment_variables"].items():
        #      icon_builder.metadata.options.environment_variables[key] = value

        self.to_context(
            icon=self.submit(
                icon_builder,
                master_namelist=self.ctx.master_namelist,
                model_namelist=self.ctx.model_namelist,
                ifs2icon_filename=self.ctx.ifs2icon_filename,
                **self.exposed_inputs(spice.icon.Icon),
            ),
        )

    def finalize(self) -> None:
        self.out_many(self.exposed_outputs(self.ctx.icon, spice.icon.Icon))


@engine.calcfunction
def dict_to_namelist(namelists: orm.Dict) -> orm.SinglefileData:
    namelists_lines: list[str] = []
    for namelist, data in namelists.items():
        namelists_lines.append(f"&{namelist}")
        namelists_lines += textwrap.indent(
            tabulate.tabulate(
                [(key, "=", value) for key, value in data.items()], tablefmt="plain"
            ),
            prefix="  ",
        ).splitlines()
        namelists_lines.append("/")
    namelists_str = "\n".join(namelists_lines) + "\n"

    return orm.SinglefileData(
        file=io.BytesIO(initial_bytes=namelists_str.encode("utf-8"))
    )


@engine.calcfunction
def str_to_namelist(namelists: orm.Str) -> orm.SinglefileData:
    return orm.SinglefileData(
        file=io.BytesIO(initial_bytes=namelists.value.encode("utf-8"))
    )


def make_master_namelists(
    params: spice.icon.IconParams,
    *,
    lrestart: str,
    expid: str,
    next_date: pendulum.DateTime,
) -> str:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("aiida_c2sm.spice", "templates")
    )
    template = env.get_template("icon_master.namelist")

    def to_utc(dt: datetime.datetime) -> pendulum.DateTime:
        utc = pendulum.timezone("Utc")
        return pendulum.instance(dt).astimezone(utc)

    dt_restart = (
        pendulum.period(to_utc(params.date), to_utc(next_date)).in_hours() + 1
    ) * 3600.0

    return template.render(
        lrestart=lrestart,
        ini_datetime_string=to_utc(params.start_date).to_iso8601_string(),
        dt_restart=f"{dt_restart:.1f}",
        expid=expid,
        experiment_start_date=to_utc(params.start_date).to_iso8601_string(),
        experiment_stop_date=to_utc(params.stop_date).to_iso8601_string(),
    )

    #  return {
    #      "master_nml": {
    #          "lrestart": lrestart,
    #          "lrestart_write_last": ".TRUE.",
    #      },
    #      "time_nml": {
    #          "ini_datetime_string": params.start_date.isoformat(),
    #          "dt_restart": str(
    #              pendulum.period(
    #                  pendulum.instance(params.date).naive(), next_date.naive()
    #              ).in_hours()
    #              * 3600
    #          ),  # hincrestart
    #          "is_relative_time": ".TRUE.",
    #      },
    #      "master_model_nml": {
    #          "model_type": "1",
    #          "model_name": '"ATMO"',
    #          "model_namelist_filename": f"NAMELIST_{expid}",
    #          "model_min_rank": "1",
    #          "model_max_rank": "65536",
    #          "model_inc_rank": "1",
    #      },
    #      "master_time_control_nml": {
    #          "calendar": "proleptic gregorian",
    #          "experiment_start_date": params.start_date.isoformat(),
    #          "experiment_stop_date": params.stop_date.isoformat(),
    #      },
    #  }


def make_model_namelists(
    params: spice.icon.IconParams,
    *,
    gcm_converted: orm.RemoteData,
    ini_basedir: orm.RemoteData,
    lam_grid_path: str,
    parent_grid_path: str,
    extpar_path: str,
    ghg_file_path: str,
    ecraddir: orm.RemoteData,
    ifs2icon_filename: str,
    check_uuid_gracefully: str,
    restart_write_mode: str,
    next_date: pendulum.DateTime,
) -> str:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("aiida_c2sm.spice", "templates")
    )
    template = env.get_template("model_namelists.nml")

    return template.render(
        gcm_converted_path=gcm_converted.get_remote_path(),
        num_io_procs=params.num_io_procs,
        num_restart_procs=params.num_restart_procs,
        num_prefetch_proc=params.num_prefetch_proc,
        dynamics_grid_filename=f"'{pathlib.Path(lam_grid_path).name}',",
        radiation_grid_filename=f"'{pathlib.Path(parent_grid_path).name}',",
        ifs2icon_filename=ifs2icon_filename,
        dtime_latbc=params.hincbound * 3600.0,
        latbc_path=gcm_converted.get_remote_path(),
        gcm_prefix=params.gcm_prefix,
        precip_interval=to_iso_8601_period(params.precip_interval),
        runoff_interval=to_iso_8601_period(params.runoff_interval),
        sunshine_interval=to_iso_8601_period(params.sunshine_interval),
        maxt_interval=to_iso_8601_period(params.maxt_interval),
        gust_interval=params.gust_interval.in_seconds(),
        melt_interval=to_iso_8601_period(params.melt_interval),
        restart_write_mode=restart_write_mode,
        sstart=pendulum.period(params.start_date, params.date).in_hours() * 3600,
        snext=pendulum.period(
            pendulum.instance(params.start_date).naive(), next_date
        ).in_hours()
        * 3600,
        sout_inc=[inc.in_seconds() for inc in params.hout_inc],
        check_uuid_gracefully=check_uuid_gracefully,
        **get_dtimes(params, ini_basedir, lam_grid_path),
        year=params.date.year,
        month=f"{params.date.month:02}",
        zml_soil=params.zml_soil,
        ecrad_data_path=pathlib.Path(ecraddir.get_remote_path()).name,
        ghg_filename=ghg_file_path,
        ndyn_substeps=params.ndyn_substeps,
        extpar_filename=pathlib.Path(extpar_path).name,
        operation=params.operation,
    )


def to_iso_8601_period(dt: pendulum.duration) -> str:
    years = f"{dt.years:02}Y" if dt.years != 0 else ""
    months = f"{dt.months:02}M" if dt.months != 0 else ""
    weeks = f"{dt.weeks:02}W" if dt.weeks != 0 else ""
    days = f"{dt.remaining_days:02}D" if dt.remaining_days != 0 else ""
    hours = f"{dt.hours:02}H" if dt.hours != 0 else ""
    minutes = f"{dt.minutes:02}M" if dt.minutes else ""
    seconds = f"{dt.remaining_seconds:02}S" if dt.remaining_seconds else ""
    return f"P{years}{months}{weeks}{days}T{hours}{minutes}{seconds}"


def get_dtimes(
    params: IconParams, ini_basedir: orm.RemoteData, lam_grid_path: str
) -> dict[str, int]:
    #! smallest value of the increment in output_bounds of the output_nml namelists
    base_output_interval = 3600
    #! number of short time steps per basic timestep dtime.
    #! Default: 5. Should not exceed the default
    params.ndyn_substeps = 5
    #! time step factor for convective and cloud cover.
    #! Integer number, setting the multiple of dtime
    nt_conv = 2
    #! time step factor for radiation.
    #! Integer number, setting the multiple of dt_conv
    nt_rad = 3
    #! time step factor for orographic gravity wave drag (SSO).
    #! Integer number, setting the multiple of dtime
    nt_sso = 4
    #! time step factor for non-orographic gravity wave drag.
    #! Integer number, setting the multiple of dtime
    nt_gwd = 4

    if params.dtime is not None:
        dtime = params.dtime
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_grid_path = pathlib.Path(temp_dir) / "grid.nc"
            ini_basedir.getfile(lam_grid_path, temp_grid_path)
            lam_grid_data = nc.Dataset(temp_grid_path, mode="r")

        grid_root = lam_grid_data.grid_root
        grid_level = lam_grid_data.grid_level
        dtime = int(params.ndyn_substeps * 9090.0 / (grid_root * 2.0**grid_level))

        # DTIME modified such that it fits into `base_output_interval`.
        # Therefore the following calculations are only valid
        # if the increment in output_bounds is a multiple of `base_output_interval`.
        while base_output_interval % dtime > 0:
            dtime -= 1

    return {
        "dtime": dtime,
        "dt_conv": (dt_conv := dtime * nt_conv),
        "dt_rad": dt_conv * nt_rad,
        "dt_sso": dtime * nt_sso,
        "dt_gwd": dtime * nt_gwd,
    }


@dataclasses.dataclass
class IconParams:
    start_date: pendulum.DateTime
    stop_date: pendulum.DateTime
    date: pendulum.DateTime
    num_io_procs: int = 1
    num_restart_procs: int = 1
    num_prefetch_proc: int = 1
    hincbound: int = 6
    gcm_prefix: str = "caf"
    precip_interval: pendulum.duration = pendulum.duration(hours=1)
    runoff_interval: pendulum.duration = pendulum.duration(hours=1)
    sunshine_interval: pendulum.duration = pendulum.duration(hours=24)
    maxt_interval: pendulum.duration = pendulum.duration(hours=24)
    gust_interval: pendulum.duration = pendulum.duration(hours=1)
    melt_interval: pendulum.duration = pendulum.duration(hours=1)
    hout_inc: tuple[pendulum.duration, ...] = tuple(
        pendulum.duration(hours=i) for i in [3, 24, 1, 24, 6, 6, 1, 1, 1, 1]
    )
    operation: tuple[str, ...] = ("", "", "", "", "", "", "", "mean", "", "")
    dtime: typing.Optional[int] = None
    zml_soil: str = "0.005,0.02,0.06,0.18,0.54,1.62,4.86,14.58"
    #! number of short time steps per basic timestep dtime.
    #! Default: 5. Should not exceed the default
    ndyn_substeps: int = 5

    def as_dict(self) -> dict[str, str | int | bool]:
        data = dataclasses.asdict(self)
        data["start_date"] = self.start_date.isoformat()
        data["stop_date"] = self.stop_date.isoformat()
        data["date"] = self.date.isoformat()
        data |= {
            "precip_interval": self.precip_interval.total_seconds(),
            "runoff_interval": self.runoff_interval.total_seconds(),
            "sunshine_interval": self.sunshine_interval.total_seconds(),
            "maxt_interval": self.maxt_interval.total_seconds(),
            "gust_interval": self.gust_interval.total_seconds(),
            "melt_interval": self.melt_interval.total_seconds(),
            "hout_inc": tuple(dur.total_seconds() for dur in self.hout_inc),
        }

        return data

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> IconParams:
        return cls(
            **data
            | {
                "start_date": pendulum.DateTime.fromisoformat(data["start_date"]),
                "stop_date": pendulum.DateTime.fromisoformat(data["stop_date"]),
                "date": pendulum.DateTime.fromisoformat(data["date"]),
                "precip_interval": pendulum.duration(seconds=data["precip_interval"]),
                "runoff_interval": pendulum.duration(seconds=data["runoff_interval"]),
                "sunshine_interval": pendulum.duration(
                    seconds=data["sunshine_interval"]
                ),
                "maxt_interval": pendulum.duration(seconds=data["maxt_interval"]),
                "gust_interval": pendulum.duration(seconds=data["gust_interval"]),
                "melt_interval": pendulum.duration(seconds=data["melt_interval"]),
                "hout_inc": tuple(
                    pendulum.duration(seconds=s) for s in data["hout_inc"]
                ),
            }
        )
