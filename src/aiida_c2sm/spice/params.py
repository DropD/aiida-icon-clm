import dataclasses
import pathlib
from typing import Any, Optional

import pendulum
from typing_extensions import Self


def datetimefield(**kwargs):
    return dataclasses.field(
        metadata={
            "to_json": pendulum.DateTime.isoformat,
            "from_json": pendulum.DateTime.fromisoformat,
        },
        **kwargs,
    )


def duration_from_seconds(seconds: int | float) -> pendulum.Duration:
    return pendulum.duration(seconds=seconds)


def durationfield(**kwargs):
    return dataclasses.field(
        metadata={
            "to_json": pendulum.Duration.total_seconds,
            "from_json": duration_from_seconds,
        },
        **kwargs,
    )


def pathfield(**kwargs):
    return dataclasses.field(metadata={"to_json": str, "from_json": pathlib.Path})


@dataclasses.dataclass(kw_only=True)
class SpiceParams:
    start_date: pendulum.DateTime = datetimefield()
    stop_date: pendulum.DateTime = datetimefield()
    utils_bindir: pathlib.Path = pathfield()
    cfu_bindir: pathlib.Path = pathfield()
    lam_grid_relpath: pathlib.Path = pathfield()
    parent_grid_relpath: pathlib.Path = pathfield()
    extpar_relpath: pathlib.Path = pathfield()
    ghg_file_relpath: pathlib.Path = pathfield()
    hincbound: int = 6
    gcm_prefix: str = "caf"
    gcm_remap: str = "remaplaf"
    precip_interval: pendulum.duration = durationfield(
        default=pendulum.duration(hours=1)
    )
    runoff_interval: pendulum.duration = durationfield(
        default=pendulum.duration(hours=1)
    )
    sunshine_interval: pendulum.duration = durationfield(
        default=pendulum.duration(hours=24)
    )
    maxt_interval: pendulum.duration = durationfield(
        default=pendulum.duration(hours=24)
    )
    gust_interval: pendulum.duration = durationfield(default=pendulum.duration(hours=1))
    melt_interval: pendulum.duration = durationfield(default=pendulum.duration(hours=1))
    hout_inc: tuple[pendulum.duration, ...] = dataclasses.field(
        metadata={
            "to_json": lambda durations: tuple(d.total_seconds() for d in durations),
            "from_json": lambda second_values: tuple(
                duration_from_seconds(sec) for sec in second_values
            ),
        },
        default=tuple(
            pendulum.duration(hours=i) for i in [3, 24, 1, 24, 6, 6, 1, 1, 1, 1]
        ),
    )
    operation: tuple[str, ...] = ("", "", "", "", "", "", "", "mean", "", "")
    dtime: Optional[int] = None
    zml_soil: str = "0.005,0.02,0.06,0.18,0.54,1.62,4.86,14.58"
    #! number of short time steps per basic timestep dtime.
    #! Default: 5. Should not exceed the default
    ndyn_substeps: int = 5
    prep_n_parallel_tasks: int = 12
    prep_omp_threads: int = 1
    icon_input_optional: str = ""
    icon_num_io_procs: int = 1
    icon_num_restart_procs: int = 1
    icon_num_prefetch_proc: int = 1

    def as_dict(self) -> dict[str, str | int | bool]:
        data = dataclasses.asdict(self)
        for field in dataclasses.fields(self):
            if "to_json" in field.metadata:
                data[field.name] = field.metadata["to_json"](data[field.name])

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        for field in dataclasses.fields(cls):
            if "from_json" in field.metadata:
                data[field.name] = field.metadata["from_json"](data[field.name])
        return cls(**data)
