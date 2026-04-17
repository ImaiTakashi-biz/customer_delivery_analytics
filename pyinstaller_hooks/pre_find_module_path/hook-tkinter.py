"""Override PyInstaller's tkinter pre-find hook.

The local Python installation is usable for tkinter at runtime once the
Tcl/Tk data directories are bundled, but PyInstaller's default availability
probe can incorrectly treat it as broken and exclude the package entirely.
This hook intentionally does nothing so the standard module path resolution
can proceed.
"""

from __future__ import annotations


def pre_find_module_path(hook_api) -> None:
    del hook_api
