"""AKAI Fire library — public surface.

This module is intentionally lightweight: it re-exports the pure-Python
:mod:`akai_fire.errors` eagerly and defers :class:`AkaiFire` / :class:`Canvas`
to module-level ``__getattr__`` so importing ``akai_fire`` (or
``akai_fire.device`` from the headless testing package) does not pull in
``rtmidi`` or Pillow unless the caller actually dereferences them.
"""

from akai_fire.errors import (
    AkaiFireError,
    HardwareError,
    InvalidParameterError,
    MIDIConnectionError,
    MIDISendError,
    StateError,
)

__all__ = [
    # Errors (always available)
    "AkaiFireError",
    "HardwareError",
    "InvalidParameterError",
    "MIDIConnectionError",
    "MIDISendError",
    "StateError",
    # Lazy-loaded (resolved via __getattr__)
    "AkaiFire",
    "Canvas",
    "discover_akai_fire",
    "get_akai_fire",
]

# name -> (submodule, attribute). Resolved on first access.
_LAZY = {
    "AkaiFire": ("akai_fire.hardware", "AkaiFire"),
    "discover_akai_fire": ("akai_fire.hardware", "discover_akai_fire"),
    "get_akai_fire": ("akai_fire.hardware", "get_akai_fire"),
    "Canvas": ("akai_fire.canvas", "Canvas"),
}


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod_name, attr = _LAZY[name]
        value = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = value  # cache on the module for subsequent lookups
        return value
    raise AttributeError(f"module 'akai_fire' has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
