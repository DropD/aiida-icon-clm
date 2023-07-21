from typing import Callable

from aiida import orm

from aiida_c2sm import exceptions

_GROUP_LABEL = "spice-exp"

_GCM_DATA_LABEL = "gcm_data"
_GCM_DATA_PATH = "/store/c2sm/c2sme/reanalyses_dkrz/ERAInterim"

_INIDATA_LABEL = "inidata"
_INIDATA_PATH = (
    "/scratch/snx3000/mjaehn/sandbox_workflow/spice/chain/work/sp001/inidata"
)


__all__ = ["get_gcm_data", "get_inidata"]


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


def __gcm_data_initializer() -> orm.RemoteData:
    return orm.RemoteData(
        label=_GCM_DATA_LABEL,
        remote_path=_GCM_DATA_PATH,
        description="Initial boundary data.",
    )


def __inidata_initializer() -> orm.RemoteData:
    return orm.RemoteData(
        label=_INIDATA_LABEL,
        remote_path=_INIDATA_PATH,
        description="Some initial data.",
    )
