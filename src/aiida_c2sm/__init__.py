"""
AiiDA Workflows for climate and weather simulations.
"""
from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

from . import example_flow

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "aiida-c2sm"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

__all__ = ["__version__", "example_flow"]
