import textwrap

import pendulum
import tabulate
from aiida import common, engine, orm
from aiida.engine.processes import builder

from aiida_c2sm.spice import data, icon_wc


def get_params(conv_node: orm.CalcJobNode) -> orm.JsonableData:
    try:
        params = orm.load_node(label="spice-icon-example-params")
        return params
    except common.NotExistent:
        utc = pendulum.timezone("Utc")
        return orm.JsonableData(
            icon_wc.IconParams(
                start_date=pendulum.datetime(year=1979, month=1, day=1, tz=utc),
                stop_date=pendulum.datetime(year=1979, month=3, day=1, tz=utc),
                date=pendulum.instance(conv_node.inputs.parameters.obj.date, tz=utc),
            ),
            label="spice-icon-example-params",
        ).store()


def get_ecraddir() -> orm.RemoteData:
    try:
        params = orm.load_node(label="spice-ecraddir")
        return params
    except common.NotExistent:
        return orm.RemoteData(
            label="spice-ecraddir",
            computer=orm.load_computer("Daint"),
            remote_path="/scratch/snx3000/mjaehn/sandbox_workflow/spice/icon-nwp-gpu/externals/ecrad/data",
        ).store()


def prepare(conv_node: orm.CalcJobNode) -> builder.ProcessBuilder:
    code = orm.load_code("spice-icon")
    builder = icon_wc.IconWorkChain.get_builder()

    builder.code = code
    builder.expid = "aii001"
    builder.gcm_converted = conv_node.outputs.converted
    builder.boundary_data = data.get_inidata()
    builder.parameters = get_params(conv_node)
    builder.ini_basedir = data.get_inibasedir()
    builder.inidata = data.get_inidata()
    builder.lam_grid_relpath = "europe044/europe044_DOM01.nc"
    builder.parent_grid_relpath = "europe044/europe044_DOM01.parent.nc"
    builder.extpar_relpath = (
        "europe044/external_parameter_icon_europe044_DOM01_tiles.nc"
    )
    builder.ghg_file_relpath = "greenhouse_gases/bc_greenhouse_rcp45_1765-2500.nc"
    builder.ecraddir = get_ecraddir()
    #  builder.metadata = {"description": "Test icon job submission."}
    builder.options = {
        "account": "csstaff",
        "max_wallclock_seconds": 3600,
        "queue_name": "normal",
        "custom_scheduler_commands": "#SBATCH -C gpu",
        "max_memory_kb": int(64e6),
        #  "environment_variables": {
        #      "CURRENT_DATE": builder.parameters.obj.date.strftime("%Y%m%d%H"),
        #      "EXPID": builder.expid,
        #  },
    }

    return builder


if __name__ == "__main__":
    conv_node = orm.load_node(label="spice-conv-successful")
    builder = prepare(conv_node)
    print(
        textwrap.dedent(
            f"""
        Submitting ICON with:
        {tabulate.tabulate(builder._data.items())}

        This will use the output of the prep calculation: {conv_node}.
    """
        )
    )
    proc = engine.submit(builder)
    print(proc.pk)
