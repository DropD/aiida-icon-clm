from __future__ import annotations

import dataclasses
import datetime
import pathlib
from typing import Callable

import pendulum
from aiida import orm

from aiida_c2sm import exceptions

_GROUP_LABEL = "spice-exp"

_GCM_DATA_LABEL = "gcm_data"
_GCM_DATA_PATH = "/store/c2sm/c2sme/reanalyses_dkrz/ERAInterim"

_INIDATA_LABEL = "inidata"
_INIDATA_PATH = (
    "/scratch/snx3000/mjaehn/sandbox_workflow/spice/chain/work/sp001/inidata"
)

_INIBASEDIR_LABEL = "ini_basedir"
_INIBASEDIR_PATH = "/scratch/snx3000/mjaehn/sandbox_workflow/spice/data/rcm/"


__all__ = ["get_gcm_data", "get_inidata", "get_inibasedir"]


@dataclasses.dataclass
class PrepParams:
    date: pendulum.DateTime
    next_date: pendulum.DateTime
    n_parallel_tasks: int
    utils_bindir: pathlib.Path
    cfu_bindir: pathlib.Path
    hincbound: int
    gcm_prefix: str

    def as_dict(self) -> dict[str, str | int]:
        data = dataclasses.asdict(self)
        data["date"] = self.date.isoformat()
        data["next_date"] = self.next_date.isoformat()
        data["utils_bindir"] = str(self.utils_bindir)
        data["cfu_bindir"] = str(self.cfu_bindir)
        return data

    @classmethod
    def from_dict(cls, data) -> PrepParams:
        kwargs = data.copy()
        kwargs["date"] = datetime.datetime.fromisoformat(data["date"])
        kwargs["next_date"] = datetime.datetime.fromisoformat(data["next_date"])
        kwargs["utils_bindir"] = pathlib.Path(data["utils_bindir"])
        kwargs["cfu_bindir"] = pathlib.Path(data["cfu_bindir"])
        return cls(**kwargs)


def get_data(label: str, initializer: Callable[[], orm.RemoteData]) -> orm.RemoteData:
    """Get a singleton spice data node, create if it doesn't exist."""
    query = orm.QueryBuilder()
    query.append(orm.Group, filters={"label": _GROUP_LABEL}, tag="group")
    query.append(orm.RemoteData, filters={"label": label}, with_group="group")
    n_candidates = query.count()
    if n_candidates < 1:
        node = initializer().store()
        group = orm.load_group(_GROUP_LABEL)
        group.add_nodes([node])
        return node
    elif n_candidates > 1:
        raise exceptions.DatabaseAmbiguityError(
            f"Multiple remote data nodes found with the {_GCM_DATA_LABEL} label. "
            f"PKs: {[c.pk for c in query.all()]}. Please relable all but one."
        )
    return query.one()[0]


def get_inidata() -> orm.RemoteData:
    """Get the inidata node, create if it doesn't exist."""
    return get_data(label=_INIDATA_LABEL, initializer=__inidata_initializer)


def get_gcm_data() -> orm.RemoteData:
    """Get the gcm data node, create if it doesn't exist."""
    return get_data(label=_GCM_DATA_LABEL, initializer=__gcm_data_initializer)


def get_inibasedir() -> orm.RemoteData:
    """Get the gcm data node, create if it doesn't exist."""
    return get_data(label=_INIBASEDIR_LABEL, initializer=__inibasedir_initializer)


def __gcm_data_initializer() -> orm.RemoteData:
    return orm.RemoteData(
        label=_GCM_DATA_LABEL,
        remote_path=_GCM_DATA_PATH,
        description="Initial boundary data.",
        computer=orm.load_computer("Daint"),
    )


def __inidata_initializer() -> orm.RemoteData:
    return orm.RemoteData(
        label=_INIDATA_LABEL,
        remote_path=_INIDATA_PATH,
        description="Some initial data.",
        computer=orm.load_computer("Daint"),
    )


def __inibasedir_initializer() -> orm.RemoteData:
    return orm.RemoteData(
        label=_INIBASEDIR_LABEL,
        remote_path=_INIBASEDIR_PATH,
        description="Some initial data.",
        computer=orm.load_computer("Daint"),
    )
