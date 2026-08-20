"""Guard against MIDI-constant drift between the 4 implementations.

Before the refactor, each implementation defined its own copy of the 39
constants. ``CONTROL_BANK_USER2`` had silently drifted to ``0x18`` in
pygame + TUI mocks (computed via ``FIELD_BASE | FIELD_USER2``) while the
hardware and testing mock had the correct ``0x03``. ``CONTROL_BANK_ALL_OFF``
similarly drifted to ``0x00`` in two places.

These tests assert every implementation now pulls its constants from
:mod:`akai_fire.constants` and therefore cannot drift again.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from akai_fire import AkaiFire
from akai_fire import constants as C
from akai_fire_testing import MockAkaiFire as TestingMock

try:
    from mock_gui_tui import MockAkaiFire as TuiMock

    HAS_TUI = True
except ImportError:
    HAS_TUI = False

from mock_gui_pygame import MockAkaiFire as PygameMock

# Four live implementations share this contract.
IMPLS = [AkaiFire, PygameMock, TestingMock]
if HAS_TUI:
    IMPLS.append(TuiMock)

# The specific values that had drifted historically — every one of these
# must match the authoritative module value.
REGRESSION_CONSTANTS = [
    "CONTROL_BANK_USER2",  # was 0x18 in pygame + TUI; should be 0x03
    "CONTROL_BANK_ALL_OFF",  # was 0x00 in pygame + TUI; should be 0x10
    "CONTROL_BANK_ALL_ON",
    "BUTTON_PLAY",
    "BUTTON_SHIFT",
    "BUTTON_ALT",
    "ROTARY_VOLUME",
    "ROTARY_SELECT",
    "RECTANGLE_LED_HIGH_RED",
    "LED_HIGH_GREEN",
    "FIELD_BASE",
    "NOTE_ON",
    "NOTE_OFF",
    "CC",
]


class TestConstantsMatchAuthoritativeModule(unittest.TestCase):
    """Every implementation must agree with ``akai_fire.constants``."""

    def test_each_impl_matches_authoritative(self):
        for name in REGRESSION_CONSTANTS:
            expected = getattr(C, name)
            for cls in IMPLS:
                with self.subTest(constant=name, impl=cls.__name__):
                    self.assertEqual(
                        getattr(cls, name),
                        expected,
                        f"{cls.__name__}.{name} != akai_fire.constants.{name}",
                    )

    def test_solo_buttons_mapping_matches(self):
        for cls in IMPLS:
            with self.subTest(impl=cls.__name__):
                self.assertEqual(cls.SOLO_BUTTONS, C.SOLO_BUTTONS)

    def test_control_bank_user2_is_03_not_18(self):
        """Named regression — the hardware-documented oddball value."""
        for cls in IMPLS:
            self.assertEqual(cls.CONTROL_BANK_USER2, 0x03, cls.__name__)

    def test_control_bank_all_off_is_10_not_00(self):
        """Named regression — FIELD_BASE must be set for the 'off' state."""
        for cls in IMPLS:
            self.assertEqual(cls.CONTROL_BANK_ALL_OFF, 0x10, cls.__name__)


if __name__ == "__main__":
    unittest.main()
