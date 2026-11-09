"""Tests for the pygame-backed MockAkaiFire.

Uses SDL's "dummy" video driver so it runs in headless CI. Events are
synthesized as minimal stand-ins for pygame.event objects — we only
need ``pos``/``rel``/``buttons`` attributes for the mock's handlers.
"""

import os
import sys
import unittest
from itertools import pairwise
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pygame_font_available() -> bool:
    """True when pygame's font module actually works.

    pygame 2.6.1 predates Python 3.14; there ``pygame.font.Font``
    raises NotImplementedError, which took whole test files down with
    environmental errors masking real regressions. Skip instead.
    """
    try:
        import pygame

        pygame.font.init()
        pygame.font.Font(None, 10)
        return True
    except Exception:
        return False


HAS_PYGAME = _pygame_font_available()

if HAS_PYGAME:
    from mock_gui_pygame import MockAkaiFire  # noqa: E402


def _evt(**kwargs) -> SimpleNamespace:
    """Minimal pygame-event stand-in."""
    return SimpleNamespace(**kwargs)


@unittest.skipUnless(
    HAS_PYGAME,
    "pygame.font not available (pygame 2.6.1 is incompatible with Python >= 3.14)",
)
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
        self.fire._handle_mouse_motion(_evt(pos=pos, rel=(0, -5), buttons=(1, 0, 0)))
        self.fire._handle_mouse_motion(_evt(pos=pos, rel=(0, 3), buttons=(1, 0, 0)))
        self.assertEqual(turns, [("clockwise", 5), ("counterclockwise", 3)])

    def test_rotary_drag_ignored_without_left_button(self):
        turns = []

        @self.fire.on_rotary_turn()
        def handler(rotary_id, direction, velocity):
            turns.append((rotary_id, direction, velocity))

        pos = self.fire.rotary_data[self.fire.ROTARY_PAN]["pos"]
        self.fire._handle_mouse_motion(_evt(pos=pos, rel=(0, -5), buttons=(0, 0, 0)))
        self.assertEqual(turns, [])

    def test_drag_keeps_its_encoder_after_leaving_the_knob(self):
        turns, touches = [], []
        rotary = self.fire.ROTARY_FILTER
        self.fire.add_rotary_listener(
            rotary, lambda direction, velocity: turns.append((direction, velocity))
        )
        self.fire.add_rotary_touch_listener(rotary, touches.append)
        start = self.fire.rotary_data[rotary]["pos"]
        self.fire._handle_mouse_down(_evt(pos=start))
        self.fire._handle_mouse_motion(
            _evt(pos=(start[0], 300), rel=(0, -40), buttons=(1, 0, 0))
        )
        self.fire._handle_mouse_up(_evt(pos=(start[0], 300)))
        self.assertEqual(turns, [("clockwise", 40)])
        self.assertEqual(touches, ["touch", "release"])
        self.assertIsNone(self.fire._drag_rotary)

    def test_select_click_presses_switch_but_drag_only_turns(self):
        events, turns = [], []
        self.fire.add_button_listener(self.fire.BUTTON_SELECT, events.append)
        self.fire.add_rotary_listener(
            self.fire.ROTARY_SELECT, lambda *args: turns.append(args)
        )
        pos = self.fire.rotary_data[self.fire.ROTARY_SELECT]["pos"]
        self.fire._handle_mouse_down(_evt(pos=pos))
        self.fire._handle_mouse_up(_evt(pos=pos))
        self.assertEqual(events, ["press", "release"])
        events.clear()
        self.fire._handle_mouse_down(_evt(pos=pos))
        self.fire._handle_mouse_motion(_evt(pos=pos, rel=(0, -5), buttons=(1, 0, 0)))
        self.fire._handle_mouse_up(_evt(pos=pos))
        self.assertEqual(events, [])
        self.assertEqual(turns, [("clockwise", 5)])

    def test_release_outside_button_clears_modifier(self):
        pos = self.fire.button_rects[self.fire.BUTTON_SHIFT].center
        self.fire._handle_mouse_down(_evt(pos=pos))
        self.assertTrue(self.fire.is_shift_pressed())
        self.fire._handle_mouse_up(_evt(pos=(0, 0)))
        self.assertFalse(self.fire.is_shift_pressed())

    def test_focus_loss_releases_captured_input(self):
        import pygame

        self.fire._handle_mouse_down(
            _evt(pos=self.fire.button_rects[self.fire.BUTTON_ALT].center)
        )
        self.fire._handle_mouse_down(
            _evt(pos=self.fire.rotary_data[self.fire.ROTARY_PAN]["pos"])
        )
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.fire.process_events()
        self.assertFalse(self.fire.is_alt_pressed())
        self.assertIsNone(self.fire._drag_rotary)

    def test_scroll_turns_only_the_hovered_encoder(self):
        turns = []
        self.fire.add_rotary_listener(
            self.fire.ROTARY_VOLUME, lambda *args: turns.append(args)
        )
        with patch(
            "pygame.mouse.get_pos",
            return_value=self.fire.rotary_data[self.fire.ROTARY_VOLUME]["pos"],
        ):
            self.fire._handle_mouse_wheel(_evt(y=-2))
        with patch("pygame.mouse.get_pos", return_value=self.fire.pad_rects[0].center):
            self.fire._handle_mouse_wheel(_evt(y=3))
        self.assertEqual(turns, [("counterclockwise", 2)])

    def test_every_visible_button_and_pad_is_reachable(self):
        buttons, pads = [], []
        self.fire.on_button()(lambda button, event: buttons.append((button, event)))
        self.fire.on_pad()(lambda index, velocity: pads.append(index))
        for button, rect in self.fire.button_rects.items():
            self.fire._handle_mouse_down(_evt(pos=rect.center))
            self.fire._handle_mouse_up(_evt(pos=rect.center))
            self.assertEqual(buttons[-2:], [(button, "press"), (button, "release")])
        for rect in self.fire.pad_rects:
            self.fire._handle_mouse_down(_evt(pos=rect.center))
            self.fire._handle_mouse_up(_evt(pos=rect.center))
        self.assertEqual(pads, list(range(64)))


@unittest.skipUnless(
    HAS_PYGAME,
    "pygame.font not available (pygame 2.6.1 is incompatible with Python >= 3.14)",
)
class TestPygameMockVisualState(unittest.TestCase):
    """Pad/LED setters queue updates that apply on process_events()."""

    def setUp(self) -> None:
        self.fire = MockAkaiFire()

    def tearDown(self) -> None:
        self.fire.close()

    def _flush(self) -> None:
        """Drain the setter queue and paint one frame."""
        self.fire.process_events()

    def test_controls_fit_panel_without_overlapping_hit_targets(self):
        rects = self.fire.pad_rects + list(self.fire.button_rects.values())
        for index, rect in enumerate(rects):
            self.assertTrue(self.fire.panel_rect.contains(rect))
            self.assertEqual(rect.collidelist(rects[index + 1 :]), -1)
            self.assertFalse(rect.colliderect(self.fire.oled_rect))
        for row in range(4):
            pads = self.fire.pad_rects[row * 16 : (row + 1) * 16]
            self.assertEqual(len({p.top for p in pads}), 1)
            self.assertEqual(len({b.left - a.right for a, b in pairwise(pads)}), 1)
            self.assertEqual(self.fire.track_led_rects[row].centery, pads[0].centery)

    def test_button_led_hues_and_track_led_values_are_visible(self):
        for button in (
            self.fire.BUTTON_PLAY,
            self.fire.BUTTON_REC,
            self.fire.BUTTON_STEP,
        ):
            self.fire.set_button_led(button, self.fire.DUAL_LED_BRIGHT_PRIMARY)
        self.fire.set_button_led(self.fire.BUTTON_STEP, self.fire.DUAL_LED_BRIGHT_AMBER)
        self.fire.set_track_led(1, self.fire.RECTANGLE_LED_HIGH_RED)
        self.fire.set_track_led(2, self.fire.RECTANGLE_LED_HIGH_GREEN)
        self._flush()
        play = self.fire.screen.get_at(
            self.fire.button_rects[self.fire.BUTTON_PLAY].center
        )
        rec = self.fire.screen.get_at(
            self.fire.button_rects[self.fire.BUTTON_REC].center
        )
        step = self.fire.screen.get_at(
            self.fire.button_rects[self.fire.BUTTON_STEP].center
        )
        red_track = self.fire.screen.get_at(self.fire.track_led_rects[0].center)
        green_track = self.fire.screen.get_at(self.fire.track_led_rects[1].center)
        self.assertGreater(play.g, play.r)
        self.assertGreater(rec.r, rec.g)
        self.assertGreater(step.r, step.b)
        self.assertGreater(step.g, step.b)
        self.assertGreater(red_track.r, red_track.g)
        self.assertGreater(green_track.g, green_track.r)

    def test_dual_button_colors_and_brightness_match_hardware(self):
        for button in self.fire.DUAL_COLOR_BUTTON_IDS:
            colors = {}
            for value in range(1, 5):
                self.fire.set_button_led(button, value)
                self._flush()
                colors[value] = self.fire.screen.get_at(
                    self.fire.button_rects[button].center
                )
            with self.subTest(button=button):
                for value in (1, 3):
                    color = colors[value]
                    if button in (self.fire.BUTTON_PLAY, self.fire.BUTTON_PATTERN):
                        self.assertGreater(color.g, color.r)
                    else:
                        self.assertGreater(color.r, color.g)
                for value in (2, 4):
                    self.assertGreater(colors[value].r, colors[value].b)
                    self.assertGreater(colors[value].g, colors[value].b)
                self.assertGreater(sum(colors[3][:3]), sum(colors[1][:3]))
                self.assertGreater(sum(colors[4][:3]), sum(colors[2][:3]))

    def test_bank_zero_selects_channel_and_clear_turns_all_indicators_off(self):
        self.fire.set_control_bank_leds(0)
        self._flush()
        channel = self.fire.screen.get_at((54, 51))
        self.assertGreater(channel.r, channel.g)
        self.fire.clear_control_bank_leds()
        self._flush()
        for y in (51, 71, 91, 111):
            color = self.fire.screen.get_at((54, y))
            self.assertLess(color.r, color.g)

    def test_user2_bank_value_does_not_light_channel_and_mixer(self):
        self.fire.set_control_bank_leds(self.fire.CONTROL_BANK_USER2)
        self._flush()
        channel = self.fire.screen.get_at((54, 51))
        mixer = self.fire.screen.get_at((54, 71))
        user2 = self.fire.screen.get_at((54, 111))
        self.assertLess(channel.r, channel.g)
        self.assertLess(mixer.r, mixer.g)
        self.assertGreater(user2.r, user2.g)

    def test_oled_keeps_all_native_pixels_and_polarity(self):
        self.fire.canvas.clear(1)
        self.fire.canvas.image.putpixel((127, 63), 0)
        self._flush()
        rect = self.fire.oled_rect
        lit = self.fire.screen.get_at((rect.right - 1, rect.bottom - 1))
        unlit = self.fire.screen.get_at(rect.topleft)
        self.assertGreater(lit.r, 200)
        self.assertLess(unlit.r, 20)

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


@unittest.skipUnless(
    HAS_PYGAME,
    "pygame.font not available (pygame 2.6.1 is incompatible with Python >= 3.14)",
)
class TestPygameMockLifecycle(unittest.TestCase):
    """Init, render, close cycles must not crash."""

    def test_render_to_display_accepts_optional_canvas(self):
        # API parity with AkaiFire.render_to_display(canvas=None): the
        # mock must accept both the zero-arg and canvas-arg forms.
        fire = MockAkaiFire()
        try:
            canvas = fire.get_canvas()
            canvas.draw_text("hello", 10, 10)
            fire.render_to_display()  # zero-arg
            other = fire.new_canvas()
            other.draw_text("world", 10, 10)
            fire.render_to_display(other)  # explicit canvas
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
