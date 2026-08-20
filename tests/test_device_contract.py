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

import inspect
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


def _pygame_font_available() -> bool:
    """True when pygame's font module actually works (see test_pygame_mock)."""
    try:
        import pygame

        pygame.font.init()
        pygame.font.Font(None, 10)
        return True
    except Exception:
        return False


HAS_PYGAME = _pygame_font_available()

if HAS_PYGAME:
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
    with (
        patch("rtmidi.MidiIn", return_value=_StubMidiPort()),
        patch("rtmidi.MidiOut", return_value=_StubMidiPort()),
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
    ("TestingMock", TestingMock, _make_testing_mock),
]
if HAS_PYGAME:
    _IMPLS.insert(1, ("PygameMock", PygameMock, _make_pygame_mock))
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
            "CONTROL_BANK_USER2",  # historical drift: 0x18 vs 0x03
            "CONTROL_BANK_ALL_OFF",  # historical drift: 0x00 vs 0x10
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

    def test_led_setters_return_bool(self):
        """LED setters report success as a real bool on every implementation."""
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                with self.subTest(impl=name):
                    self.assertIs(fire.set_pad_color(0, 1, 2, 3), True)
                    self.assertIs(fire.set_button_led(fire.BUTTON_PLAY, 1), True)
                    self.assertIs(fire.set_track_led(1, 0), True)
                    self.assertIs(fire.set_control_bank_leds(0x11), True)
                    self.assertIs(fire.clear_all_pads(), True)
                    self.assertIs(fire.clear_all_button_leds(), True)
                    self.assertIs(fire.clear_all_track_leds(), True)
            finally:
                fire.close()

    def test_invalid_indices_raise_like_hardware(self):
        """Bad pad/button arguments raise InvalidParameterError everywhere."""
        import inspect

        from akai_fire.errors import InvalidParameterError

        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                with self.subTest(impl=name):
                    for bad_index in (-1, 64):
                        with self.assertRaises(InvalidParameterError):
                            fire.set_pad_color(bad_index, 0, 0, 0)
                    with self.assertRaises(InvalidParameterError):
                        fire.set_button_led(0x77, 1)  # not an LED button
            finally:
                fire.close()

    def test_track_led_accepts_full_rectangle_range(self):
        """Track LEDs take RECTANGLE_LED_* values 0-4 (not the button 0-2 range).

        Regression: hardware clamped to 2, silently degrading
        RECTANGLE_LED_HIGH_GREEN (4) to dull green on the device.
        """
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                with self.subTest(impl=name):
                    self.assertTrue(fire.set_track_led(1, C.RECTANGLE_LED_HIGH_GREEN))
                    # The pygame mock applies setters on process_events().
                    if hasattr(fire, "process_events"):
                        fire.process_events()
                    if hasattr(fire, "track_leds"):
                        # Storage shape differs (list on pygame/TUI,
                        # dict keyed 1-4 on the testing mock).
                        if isinstance(fire.track_leds, list):
                            state = fire.track_leds[0]
                        else:
                            state = fire.track_leds.get(1)
                        expected = C.RECTANGLE_LED_HIGH_GREEN
                        self.assertEqual(
                            state,
                            expected,
                            f"{name}: HIGH_GREEN degraded to {state}",
                        )
            finally:
                fire.close()

    def test_pad_position_uses_row_col_convention(self):
        """pad_position returns (row, col) — same as GridMixin and the apps."""
        from akai_fire_framework.grid import GridMixin

        for name, cls, _factory in _IMPLS:
            with self.subTest(impl=name):
                self.assertEqual(cls.pad_position(15), (0, 15))  # row 0, col 15
                self.assertEqual(cls.pad_position(16), (1, 0))  # row 1, col 0
                self.assertEqual(cls.pad_position(63), (3, 15))
        # The framework mixin must agree with the device base.
        self.assertEqual(
            GridMixin.pad_position(GridMixin, 16), AkaiFireDevice.pad_position(16)
        )

    def test_mock_canvas_matches_real_canvas_signatures(self):
        """MockCanvas high-level methods accept the real Canvas's arguments."""
        from akai_fire.canvas import Canvas
        from akai_fire_testing.mocks import MockCanvas

        shared_methods = (
            "clear",
            "set_pixel",
            "get_pixel",
            "draw_text",
            "draw_rect",
            "fill_rect",
            "draw_page",
            "draw_value_page",
            "draw_menu",
            "draw_grid_info",
            "draw_split_screen",
        )
        for method_name in shared_methods:
            real_params = list(
                inspect.signature(getattr(Canvas, method_name)).parameters
            )
            mock_params = list(
                inspect.signature(getattr(MockCanvas, method_name)).parameters
            )
            # MockCanvas uses width/height instance attrs but the
            # argument lists must still line up.
            self.assertEqual(
                real_params,
                mock_params,
                f"MockCanvas.{method_name} signature drifts from Canvas",
            )

    def test_remove_listener_stops_dispatch(self):
        """Removed listeners no longer fire; removal inside a handler is safe."""
        for name, _cls, factory in _IMPLS:
            fire = factory()
            try:
                calls = []

                def handler(velocity):
                    calls.append("specific")
                    fire.remove_listener(0, handler)  # remove from inside

                fire.add_listener(0, handler)
                fire._dispatch_pad(0, 100)
                fire._dispatch_pad(0, 100)  # already removed

                with self.subTest(impl=name):
                    self.assertEqual(calls, ["specific"])
            finally:
                fire.close()


if __name__ == "__main__":
    unittest.main()
