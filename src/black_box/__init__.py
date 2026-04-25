# SPDX-License-Identifier: MIT
"""Black Box — forensic copilot for robots."""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("black-box")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
