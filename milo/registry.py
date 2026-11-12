"""Load every @tool in milo.tools without editing main.py."""

from __future__ import annotations

import importlib
import os
import pkgutil
from collections.abc import Callable

import milo.tools


def _collect(module) -> list[Callable[..., str]]:
    found = []
    for obj in vars(module).values():
        if not getattr(obj, "_milo_tool", False):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        found.append(obj)
    return found


def load_tools() -> list[Callable[..., str]]:
    """Import tool modules and return their @tool functions in stable order.

    Extra modules can be added with the MILO_TOOL_MODULES environment variable,
    a comma-separated list of importable module names.
    """
    discovered: list[Callable[..., str]] = []
    prefix = milo.tools.__name__ + "."
    for module_info in pkgutil.iter_modules(milo.tools.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(prefix + module_info.name)
        discovered.extend(_collect(module))

    extra = os.getenv("MILO_TOOL_MODULES", "")
    for module_name in extra.split(","):
        module_name = module_name.strip()
        if not module_name:
            continue
        module = importlib.import_module(module_name)
        discovered.extend(_collect(module))

    discovered.sort(key=lambda fn: (fn.__module__, fn.__name__))
    if not discovered:
        raise RuntimeError("No Milo tools found. Decorate functions with @tool.")
    return discovered
