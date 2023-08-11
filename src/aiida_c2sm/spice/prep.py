import pathlib

from aiida import engine, orm
from aiida.common import datastructures, folders
from aiida.engine.processes.calcjobs import calcjob
from aiida.parsers import parser


def get_script_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "scripts" / "prep"


class GCM2IconPrep(engine.CalcJob):
    """AiiDA calculation to decompress and convert gcm data for ICON."""

    @classmethod
    def define(cls, spec: calcjob.CalcJobProcessSpec) -> None:
        super().define(spec)
        spec.input(
            "gcm_data", valid_type=orm.RemoteData, help="Base directory for GCM data."
        )
        spec.input("parameters", valid_type=orm.JsonableData, help="Input parameters.")
        spec.output("gcm_prepared")
        spec.exit_code(
            300,
            "ERROR_MISSING_OUTPUT_FILES",
            message="GCM2Icon prep did not create all expected output files!",
        )
        options = spec.inputs["metadata"]["options"]
        options["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        options["parser_name"].default = "c2sm.spice_prep"

    def prepare_for_submission(self, folder: folders.Folder) -> datastructures.CalcInfo:
        params = self.inputs.parameters.obj
        variables = {
            "yyyy": params.date.strftime("%Y"),
            "mm": params.date.strftime("%m"),
            "current_date": params.date.strftime("%Y%m%d%H"),
            "next_date": params.next_date.strftime("%Y%m%d%H"),
            "max_pp": params.n_parallel_tasks,
            "utils_bindir": params.utils_bindir,
            "cfu_bindir": params.cfu_bindir,
            "hincbound": params.hincbound,
            "gcm_prefix": params.gcm_prefix,
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
                self.inputs.gcm_data.computer.uuid,
                self.inputs.gcm_data.get_remote_path(),
                "gcm_data",
            ),
        ]
        return calcinfo


class PrepParser(parser.Parser):
    """Parser for prep calculations."""

    def parse(self, **kwargs):
        """Add the remote outfiles subdirectory to outputs."""
        remote_path = self.node.outputs.remote_folder.get_remote_path()
        outfiles = orm.RemoteData(
            computer=self.node.outputs.remote_folder.computer,
            remote_path=str(pathlib.Path(remote_path) / "outfiles"),
        )
        if outfiles.is_empty:
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES
        self.out("gcm_prepared", outfiles)
        return engine.ExitCode(0)
