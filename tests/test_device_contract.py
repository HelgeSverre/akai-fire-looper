"""Drift-prevention contract tests for every AkaiFire implementation.

Every subclass of :class:`AkaiFireDevice` (real hardware, pygame mock,
TUI mock, headless testing mock) must expose the same public surface
and honour the same invariants. These tests run against all four
implementations and assert:

- They all inherit from :class:`AkaiFireDevice`
- Critical constants match the authoritative module (regression for the
  ``CONTROL_BANK_USER2`` / ``CONTROL_BANK_ALL_OFF`` drift bugs)
- Every instance exposes the base's public method surface
- Listener registries have the expected ``defaultdict(list)`` shape
- Raising one handler does not silence sibling handlers
- Modifier-first latching: a pad handler reading ``is_shift_pressed()``
  after a ``BUTTON_SHIFT`` press observes ``True``

These tests would have caught every drift incident in recent git
history (commits 37e853d, fefc85e, the CONTROL_BANK_USER2 bug).
"""

import os
import sys
import unittest
from collections import defaultdict
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from akai_fire import AkaiFire
from akai_fire import constants as C
from akai_fire.device import AkaiFireDevice
from akai_fire_testing import MockAkaiFire as TestingMock
from mock_gui_pygame import MockAkaiFire as PygameMock

try:
    from mock_gui_tui import MockAkaiFire as TuiMock
    _HAS_TUI = True
except ImportError:
    _HAS_TUI = False


# ---------------------------------------------------------------------------
# MockMidiPort reused from tests/test_akai_fire.py for constructing a real
# AkaiFire without plugging in hardware.
# ---------------------------------------------------------------------------


class _StubMidiPort:
    def __init__(self):
        self.messages = []
        self.port_name = None
        self.is_port_open = False

    def send_message(self, message):
        self.messages.append(message)

    def get_message(self):
        return None if not self.messages else (self.messages.pop(0), 0)

    def open_port(self, port):
        self.is_port_open = True
        self.port_name = port

    def close_port(self):
        self.is_port_open = False

    def get_ports(self):
        return ["FL STUDIO FIRE", "Other"]


def _make_akai_fire():
    """Build a real :class:`AkaiFire` with MIDI ports mocked out."""
    with patch("rtmidi.MidiIn", return_value=_StubMidiPort()), patch(
        "rtmidi.MidiOut", return_value=_StubMidiPort()
    ):
        return AkaiFire(async_handlers=False)


def _make_pygame_mock():
    return PygameMock()


def _make_tui_mock():
    return TuiMock(headless=True)


def _make_testing_mock():
    return TestingMock()


# Table of (name, factory) used to parameterize every test below.
_IMPLS = [
    ("AkaiFire", AkaiFire, _make_akai_fire),
    ("PygameMock", PygameMock, _make_pygame_mock),
    ("TestingMock", TestingMock, _make_testing_mock),
]
if _HAS_TUI:
    _IMPLS.append(("TuiMock", TuiMock, _make_tui_mock))


class TestDeviceContract(unittest.TestCase):
    """Every live AkaiFire implementation must obey the shared contract."""

    def test_every_impl_inherits_device_base(self):
        for name, cls, _factory in _IMPLS:
            with self.subTest(impl=name):
                self.assertTrue(
                    issubclass(cls, AkaiFireDevice),
                    f"{name} is not a subclass of AkaiFireDevice",
                )

    def test_every_impl_has_authoritative_constant_values(self):
        """No class may shadow a constant away from the authoritative value."""
        # Sample a handful — any one of these drifting would fail the suite.
        for const_name in (
            "CONTROL_BANK_USER2",       # historical drift: 0x18 vs 0x03
            "CONTROL_BANK_ALL_OFF",     # historical drift: 0x00 vs 0x10
            "BUTTON_PLAY",
            "BUTTON_SHIFT",
            "BUTTON_ALT",
            "ROTARY_VOLUME",
            "ROTARY_SELECT",
            "RECTANGLE_LED_HIGH_RED",
            "LED_HIGH_GREEN",
            "NOTE_ON",
            "NOTE_OFF",
            "CC",
            "PAD_COUNT",
        ):
            expected = getattr(C, const_name)
            for name, cls, _factory in _IMPLS:
                with self.subTest(impl=name, constant=const_name):
                    self.assertEqual(
                        getattr(cls, const_name),
                        expected,
                        f"{name}.{const_name} diverges from "
                        f"akai_fire.constants.{const_name}",
                    )

    def test_every_impl_exposes_the_base_public_surface(self):
        """Subclasses may add methods but must never drop base ones."""
        base_public = {
            name
            for name in dir(AkaiFireDevice)
            if not name.startswith("_") and callable(getattr(AkaiFireDevice, name))
        }
        for name, cls, _factory in _IMPLS:
            with self.subTest(impl=name):
                cls_public = {
                    n
                    for n in dir(cls)
                    if not n.startswith("_") and callable(getattr(cls, n))
                }
                missing = base_public - cls_public
                self.assertFalse(
                    missing,
                    f"{name} is missing base public methods: {sorted(missing)}",
                )

    def test_every_impl_has_defaultdict_listener_registries(self):
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                for attr in (
                    "pad_listeners",
                    "button_listeners",
                    "rotary_listeners",
                    "rotary_touch_listeners",
                ):
                    reg = getattr(fire, attr)
                    with self.subTest(impl=name, registry=attr):
                        self.assertIsInstance(reg, defaultdict)
                        self.assertIs(reg.default_factory, list)
            finally:
                fire.close()

    def test_raising_handler_does_not_block_siblings(self):
        """One bad pad handler cannot silence sibling handlers."""
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                calls = []

                @fire.on_pad()
                def bad(pad, vel):
                    calls.append("bad")
                    raise RuntimeError("boom")

                @fire.on_pad()
                def good(pad, vel):
                    calls.append("good")

                fire._dispatch_pad(0, 100)

                with self.subTest(impl=name):
                    self.assertIn("good", calls)
            finally:
                fire.close()

    def test_modifier_latched_before_pad_handler_runs(self):
        """After a SHIFT press, a pad handler sees ``is_shift_pressed() == True``."""
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                observed = []

                @fire.on_pad()
                def handler(pad, vel):
                    observed.append(fire.is_shift_pressed())

                fire._dispatch_button(fire.BUTTON_SHIFT, "press")
                fire._dispatch_pad(0, 100)

                with self.subTest(impl=name):
                    self.assertEqual(observed, [True])
            finally:
                fire.close()


if __name__ == "__main__":
    unittest.main()
