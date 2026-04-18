"""Tests for the pygame-backed MockAkaiFire.

Uses SDL's "dummy" video driver so it runs in headless CI. Events are
synthesized as minimal stand-ins for pygame.event objects — we only
need ``pos``/``rel``/``buttons`` attributes for the mock's handlers.
"""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mock_gui_pygame import MockAkaiFire  # noqa: E402


def _evt(**kwargs) -> SimpleNamespace:
    """Minimal pygame-event stand-in."""
    return SimpleNamespace(**kwargs)


class TestPygameMockInputDispatch(unittest.TestCase):
    """Clicks on pads/buttons/rotaries must fire the same handlers the real device does."""

    def setUp(self) -> None:
        self.fire = MockAkaiFire()

    def tearDown(self) -> None:
        self.fire.close()

    def test_pad_click_fires_pad_handler(self):
        calls = []

        @self.fire.on_pad()
        def handler(idx, velocity):
            calls.append((idx, velocity))

        rect = self.fire.pad_rects[5]
        self.fire._handle_mouse_down(_evt(pos=rect.center))
        self.assertEqual(calls, [(5, 100)])

    def test_specific_pad_handler_is_called(self):
        calls = []

        @self.fire.on_pad(10)
        def handler(velocity):
            calls.append(velocity)

        rect = self.fire.pad_rects[10]
        self.fire._handle_mouse_down(_evt(pos=rect.center))
        self.assertEqual(calls, [100])

    def test_button_press_and_release(self):
        events = []

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler(event):
            events.append(event)

        pos = self.fire.button_rects[self.fire.BUTTON_PLAY].center
        self.fire._handle_mouse_down(_evt(pos=pos))
        self.fire._handle_mouse_up(_evt(pos=pos))
        self.assertEqual(events, ["press", "release"])

    def test_global_button_handler_sees_every_button(self):
        seen = []

        @self.fire.on_button()
        def handler(button_id, event):
            seen.append((button_id, event))

        for bid in (self.fire.BUTTON_PLAY, self.fire.BUTTON_STOP, self.fire.BUTTON_REC):
            pos = self.fire.button_rects[bid].center
            self.fire._handle_mouse_down(_evt(pos=pos))
            self.fire._handle_mouse_up(_evt(pos=pos))

        self.assertEqual(
            seen,
            [
                (self.fire.BUTTON_PLAY, "press"),
                (self.fire.BUTTON_PLAY, "release"),
                (self.fire.BUTTON_STOP, "press"),
                (self.fire.BUTTON_STOP, "release"),
                (self.fire.BUTTON_REC, "press"),
                (self.fire.BUTTON_REC, "release"),
            ],
        )

    def test_modifier_buttons_latch_via_mouse(self):
        # Covered at the parity level in test_testing_module; this is the
        # direct, exhaustive version.
        self.assertFalse(self.fire.is_shift_pressed())
        self.assertFalse(self.fire.is_alt_pressed())

        shift_pos = self.fire.button_rects[self.fire.BUTTON_SHIFT].center
        alt_pos = self.fire.button_rects[self.fire.BUTTON_ALT].center

        self.fire._handle_mouse_down(_evt(pos=shift_pos))
        self.assertTrue(self.fire.is_shift_pressed())
        self.fire._handle_mouse_down(_evt(pos=alt_pos))
        self.assertTrue(self.fire.is_alt_pressed())

        self.fire._handle_mouse_up(_evt(pos=shift_pos))
        self.assertFalse(self.fire.is_shift_pressed())
        self.fire._handle_mouse_up(_evt(pos=alt_pos))
        self.assertFalse(self.fire.is_alt_pressed())

    def test_rotary_drag_fires_turn_handler(self):
        turns = []

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handler(direction, velocity):
            turns.append((direction, velocity))

        # _handle_mouse_motion expects event.buttons[0] == 1 (left held),
        # a position inside a 25px radius of the rotary, and event.rel.
        pos = self.fire.rotary_data[self.fire.ROTARY_VOLUME]["pos"]
        # delta = -event.rel[1]; rel=(0, -5) -> delta=+5 -> clockwise
        self.fire._handle_mouse_motion(
            _evt(pos=pos, rel=(0, -5), buttons=(1, 0, 0))
        )
        self.fire._handle_mouse_motion(
            _evt(pos=pos, rel=(0, 3), buttons=(1, 0, 0))
        )
        self.assertEqual(
            turns, [("clockwise", 5), ("counterclockwise", 3)]
        )

    def test_rotary_drag_ignored_without_left_button(self):
        turns = []

        @self.fire.on_rotary_turn()
        def handler(rotary_id, direction, velocity):
            turns.append((rotary_id, direction, velocity))

        pos = self.fire.rotary_data[self.fire.ROTARY_PAN]["pos"]
        self.fire._handle_mouse_motion(
            _evt(pos=pos, rel=(0, -5), buttons=(0, 0, 0))
        )
        self.assertEqual(turns, [])


class TestPygameMockVisualState(unittest.TestCase):
    """Pad/LED setters queue updates that apply on process_events()."""

    def setUp(self) -> None:
        self.fire = MockAkaiFire()

    def tearDown(self) -> None:
        self.fire.close()

    def _flush(self) -> None:
        """Drain the setter queue and paint one frame."""
        self.fire.process_events()

    def test_set_pad_color_updates_state(self):
        self.fire.set_pad_color(0, 127, 64, 0)
        self._flush()
        self.assertEqual(self.fire.pad_colors[0], [127, 64, 0])

    def test_set_multiple_pad_colors_updates_state(self):
        colors = [(i, i * 2, 0, 127 - i * 2) for i in range(4)]
        self.fire.set_multiple_pad_colors(colors)
        self._flush()
        for i, r, g, b in colors:
            self.assertEqual(self.fire.pad_colors[i], [r, g, b])

    def test_clear_all_pads_zeroes_state(self):
        for i in range(64):
            self.fire.set_pad_color(i, 127, 127, 127)
        self._flush()
        self.fire.clear_all_pads()
        self._flush()
        self.assertTrue(all(c == [0, 0, 0] for c in self.fire.pad_colors))

    def test_set_button_led_updates_state(self):
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
        self._flush()
        self.assertEqual(
            self.fire.button_leds.get(self.fire.BUTTON_PLAY),
            self.fire.LED_HIGH_GREEN,
        )

    def test_set_track_led_updates_state(self):
        self.fire.set_track_led(1, self.fire.RECTANGLE_LED_HIGH_GREEN)
        self._flush()
        self.assertEqual(self.fire.track_leds[0], self.fire.RECTANGLE_LED_HIGH_GREEN)


class TestPygameMockLifecycle(unittest.TestCase):
    """Init, render, close cycles must not crash."""

    def test_render_to_display_accepts_optional_canvas(self):
        # API parity with AkaiFire.render_to_display(canvas=None): the
        # mock must accept both the zero-arg and canvas-arg forms.
        fire = MockAkaiFire()
        try:
            canvas = fire.get_canvas()
            canvas.draw_text("hello", 10, 10)
            fire.render_to_display()             # zero-arg
            other = fire.new_canvas()
            other.draw_text("world", 10, 10)
            fire.render_to_display(other)        # explicit canvas
            self.assertIs(fire.get_canvas(), other)
        finally:
            fire.close()

    def test_process_events_runs_one_frame(self):
        fire = MockAkaiFire()
        try:
            result = fire.process_events()
            # Returns True while the window is alive
            self.assertIn(result, (True, False))
        finally:
            fire.close()

    def test_close_is_idempotent(self):
        fire = MockAkaiFire()
        fire.close()
        fire.close()  # second call must not raise


if __name__ == "__main__":
    unittest.main()
