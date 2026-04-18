"""Abstract base class for AKAI Fire implementations.

Four implementations share this base: the real hardware (:class:`AkaiFire`),
the interactive pygame mock, the terminal-UI mock, and the headless
testing mock. All inherit MIDI constants via the ``@install_constants``
decorator and share state for modifier keys + a lock for registry guarding.

Later commits extend the base with the shared listener registries,
decorators, and dispatch helpers. For now it owns the utilities that
never needed duplicating in the first place — pad geometry, solo-button
lookup, modifier state, and the ``list_midi_ports()`` stub.
"""

from __future__ import annotations

import abc
import logging
import threading
from typing import Dict, List, Optional, Tuple

from akai_fire.constants import install as _install_constants


logger = logging.getLogger(__name__)


@_install_constants
class AkaiFireDevice(abc.ABC):
    """Shared base for every AKAI Fire implementation.

    MIDI constants (``BUTTON_*``, ``ROTARY_*``, ``LED_*``, ``FIELD_*``,
    ``CONTROL_BANK_*``, ``SOLO_BUTTONS``, ``NOTE_ON``/``NOTE_OFF``/``CC``,
    ``PAD_COUNT``, ``PAD_NOTE_BASE``) are installed from
    :mod:`akai_fire.constants` at class-definition time. Subclasses
    inherit them automatically — do not redefine.

    Subclasses MUST call ``super().__init__()`` to set up ``_lock`` and
    the modifier flags.
    """

    def __init__(self) -> None:
        # Guards the listener registries + modifier state. Held only
        # during the snapshot portion of dispatch; never while a user
        # handler is executing.
        self._lock = threading.RLock()

        # Modifier latch state. Updated inline during button dispatch so
        # any pad/button/rotary handler sees coherent state for the
        # SAME event.
        self._shift_pressed: bool = False
        self._alt_pressed: bool = False

    # --------------------------------------------------------------
    # Modifier-key state
    # --------------------------------------------------------------

    def is_shift_pressed(self) -> bool:
        """True while SHIFT is currently latched."""
        return self._shift_pressed

    def is_alt_pressed(self) -> bool:
        """True while ALT is currently latched."""
        return self._alt_pressed

    @property
    def shift_pressed(self) -> bool:
        return self._shift_pressed

    @property
    def alt_pressed(self) -> bool:
        return self._alt_pressed

    # --------------------------------------------------------------
    # Pad geometry utilities
    # --------------------------------------------------------------

    @staticmethod
    def pad_position(pad_index: int) -> Tuple[int, int]:
        """Return ``(column, row)`` 0-indexed for a pad index 0-63.

        Column is 0..15, row is 0..3.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return pad_index % 16, pad_index // 16

    @staticmethod
    def get_pad_column(pad_index: int) -> int:
        """Column number (1..16) for a pad index 0-63.

        One-indexed, matching the real hardware's documented coordinate
        system. ``pad_index`` is still 0-indexed.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index % 16) + 1

    @staticmethod
    def get_pad_row(pad_index: int) -> int:
        """Row number (1..4) for a pad index 0-63.

        One-indexed, matching the real hardware's documented coordinate
        system.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index // 16) + 1

    # --------------------------------------------------------------
    # Button utilities
    # --------------------------------------------------------------

    @classmethod
    def get_solo_index(cls, button_id: int) -> Optional[int]:
        """Convert a SOLO button ID to its 1..4 index, or None."""
        for index, bid in cls.SOLO_BUTTONS.items():
            if bid == button_id:
                return index
        return None

    # --------------------------------------------------------------
    # MIDI port listing — base returns empty; real AkaiFire overrides
    # --------------------------------------------------------------

    @staticmethod
    def list_midi_ports() -> Dict[str, List[str]]:
        """List available MIDI input/output ports.

        Base implementation returns empty lists (mocks don't have real
        ports). The hardware :class:`AkaiFire` subclass overrides this
        to enumerate ports via rtmidi.
        """
        return {"input": [], "output": []}
