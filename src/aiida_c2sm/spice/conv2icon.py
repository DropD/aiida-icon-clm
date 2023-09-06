from __future__ import annotations

import dataclasses
import pathlib

import pendulum
from aiida import engine, orm
from aiida.common import datastructures, folders
from aiida.engine.processes.calcjobs import calcjob
from aiida.parsers import parser


class Conv2Icon(engine.CalcJob):
    """AiiDA calculation to convert boundary data to ICON."""

    @classmethod
    def define(cls, spec: calcjob.CalcJobProcessSpec) -> None:
        super().define(spec)
        spec.input("gcm_prepared", valid_type=orm.RemoteData, help="Prepared GCM data.")
        spec.input(
            "boundary_data",
            valid_type=orm.RemoteData,
            help="Base directory for boundary data.",
        )
        spec.input("ini_basedir", valid_type=orm.RemoteData)
        spec.input("parameters", valid_type=orm.JsonableData, help="Input parameters.")
        spec.output("converted")
        spec.output("boundary_data")
        options = spec.inputs["metadata"]["options"]
        options["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        options["parser_name"].default = "c2sm.spice_conv"
        spec.exit_code(
            300,
            "ERROR_MISSING_OUTPUT_FILES",
            message="Conv2Icon prep did not create all expected output files!",
        )

    def prepare_for_submission(self, folder: folders.Folder) -> datastructures.CalcInfo:
        params = self.inputs.parameters.obj
        ini_basedir = pathlib.Path(self.inputs.ini_basedir.get_remote_path())
        variables = {
            "ydate_start": params.start_date.strftime("%Y%m%d%H"),
            "current_date": params.date.strftime("%Y%m%d%H"),
            "yyyy": params.date.strftime("%Y"),
            "mm": params.date.strftime("%m"),
            "max_pp": params.n_parallel_tasks,
            "gcm_prefix": params.gcm_prefix,
            "extpar": str(
                ini_basedir
                / "europe044"
                / "external_parameter_icon_europe044_DOM01_tiles.nc"
            ),
            "lam_grid": str(ini_basedir / "europe044" / "europe044_DOM01.nc"),
            "omp_threads_conv2icon": params.omp_threads,
            "gcm_remap": params.gcm_remap,
            "icon_input_optional": params.icon_input_optional,
            "cleanup_previous": 1 if params.cleanup_previous else 0,
        }

        with folder.open("inputs.sh", "w", encoding="utf8") as handle:
            handle.write(
                "\n".join(
                    [f"{key.upper()}={value}" for key, value in variables.items()]
                )
            )

        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid

        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.remote_symlink_list = [
            (
                self.inputs.gcm_prepared.computer.uuid,
                self.inputs.gcm_prepared.get_remote_path(),
                "gcm_prepared",
            ),
        ]
        calcinfo.remote_copy_list = [
            (
                self.inputs.boundary_data.computer.uuid,
                self.inputs.boundary_data.get_remote_path(),
                "boundary_data",
            ),
        ]
        return calcinfo


class Conv2IconParser(parser.Parser):
    """Parser for conv2icon calculations."""

    def parse(self, **kwargs):
        """Add the remote outfiles subdirectory to outputs."""
        remote_path = self.node.outputs.remote_folder.get_remote_path()

        outfiles = orm.RemoteData(
            computer=self.node.outputs.remote_folder.computer,
            remote_path=str(pathlib.Path(remote_path) / "outfiles"),
        )
        if outfiles.is_empty:
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES
        self.out("converted", outfiles)

        boundary_data = orm.RemoteData(
            computer=self.node.outputs.remote_folder.computer,
            remote_path=str(pathlib.Path(remote_path) / "boundary_data"),
        )
        self.out("boundary_data", boundary_data)
        return engine.ExitCode(0)


@dataclasses.dataclass
class Conv2IconParams:
    start_date: pendulum.DateTime
    date: pendulum.DateTime
    hincbound: int = 6
    n_parallel_tasks: int = 12
    gcm_prefix: str = "caf"
    omp_threads: int = 1
    gcm_remap: str = "remaplaf"
    icon_input_optional: str = ""
    cleanup_previous: bool = False

    def as_dict(self) -> dict[str, str | int | bool]:
        data = dataclasses.asdict(self)
        data["start_date"] = self.start_date.isoformat()
        data["date"] = self.date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, str | int | bool]) -> Conv2IconParams:
        return cls(
            **data
            | {
                "start_date": pendulum.DateTime.fromisoformat(data["start_date"]),
                "date": pendulum.DateTime.fromisoformat(data["date"]),
            }
        )
