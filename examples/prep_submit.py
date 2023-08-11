import datetime
import pathlib

from aiida import common, engine, orm

from aiida_c2sm import spice


def get_params() -> orm.JsonableData:
    try:
        params = orm.load_node(label="spice-prep-example-params")
        return params
    except common.NotExistent:
        src_dir = pathlib.Path("/scratch/snx3000/mjaehn/sandbox_workflow/spice/src")
        return orm.JsonableData(
            spice.data.PrepParams(
                date=datetime.datetime(year=1979, month=1, day=1),
                next_date=datetime.datetime(year=1979, month=2, day=1),
                n_parallel_tasks=12,
                utils_bindir=src_dir / "utils" / "bin",
                cfu_bindir=src_dir / "cfu" / "bin",
                hincbound=6,
                gcm_prefix="caf",
            ),
            label="spice-prep-example-params",
        ).store()


computer = orm.load_computer("Daint")
code = orm.load_code("spice-prep-installed")
params = get_params()
gcm_data = spice.data.get_gcm_data()

builder = code.get_builder()
builder.gcm_data = gcm_data
builder.parameters = params
builder.metadata.description = "Test prep job submission."
builder.metadata.computer = computer
builder.metadata.options.account = "csstaff"
builder.metadata.options.max_wallclock_seconds = 1800
builder.metadata.options.queue_name = "normal"
builder.metadata.options.custom_scheduler_commands = "#SBATCH -C gpu"
builder.metadata.options.max_memory_kb = int(64e6)

print(
    f"""
Submitting prep with:
code: {builder.code}
gcm_data: {builder.gcm_data}
paramters: {builder.parameters}
computer: {builder.metadata.computer}
"""
)

proc = engine.submit(builder)
print(proc.pk)
