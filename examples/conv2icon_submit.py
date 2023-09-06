import textwrap

import pendulum
from aiida import common, engine, orm
from aiida.engine.processes import builder

from aiida_c2sm.spice import conv2icon, data


def get_params(prep_node: orm.CalcJobNode) -> orm.JsonableData:
    try:
        params = orm.load_node(label="spice-conv-example-params")
        return params
    except common.NotExistent:
        return orm.JsonableData(
            conv2icon.Conv2IconParams(
                start_date=pendulum.DateTime(year=1979, month=1, day=1, tz="utc"),
                date=prep_node.inputs.parameters.obj.date,
                cleanup_previous=False,
            ),
            label="spice-conv-example-params",
        ).store()


def prepare(prep_node: orm.CalcJobNode) -> builder.ProcessBuilder:
    code = orm.load_code("spice-conv-installed")
    builder = code.get_builder()

    builder.gcm_prepared = prep_node.outputs.gcm_prepared
    builder.boundary_data = data.get_inidata()
    builder.parameters = get_params(prep_node)
    builder.ini_basedir = data.get_inibasedir()
    builder.metadata.description = "Test conv2icon job submission."
    builder.metadata.computer = code.computer
    builder.metadata.options.account = "csstaff"
    builder.metadata.options.max_wallclock_seconds = 1800
    builder.metadata.options.queue_name = "normal"
    builder.metadata.options.custom_scheduler_commands = "#SBATCH -C gpu"
    builder.metadata.options.max_memory_kb = int(64e6)

    return builder


if __name__ == "__main__":
    prep_node = orm.load_node(label="spice-prep-successful")
    builder = prepare(prep_node)
    print(
        textwrap.dedent(
            f"""
        Submitting conv2icon with:
        code: {builder.code}
        gcm_prepared: {builder.gcm_prepared}
        boundary_data: {builder.boundary_data}
        ini_basedir: {builder.ini_basedir}
        parameters: {builder.parameters}
        computer: {builder.metadata.computer}

        This will use the output of the prep calculation: {prep_node}.
        Will it delete the prep calculation's output?: {builder.parameters.obj.cleanup_previous}
    """
        )
    )
    proc = engine.submit(builder)
    print(proc.pk)
