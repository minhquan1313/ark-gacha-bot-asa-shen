"""Shen GBot launcher UI package."""

import sys
from importlib import import_module

_COMPATIBILITY_MODULES = {
    "helper_window": "source.launcher.components.helper_window",
    "deposit_helper_capture": "source.launcher.utils.deposit_helper_capture",
    "system": "source.launcher.utils.system",
}


def __getattr__(name: str):
    """Load legacy module aliases on demand so config imports do not initialize UI."""
    if name not in _COMPATIBILITY_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_COMPATIBILITY_MODULES[name])
    globals()[name] = module
    sys.modules.setdefault(f"{__name__}.{name}", module)
    return module
