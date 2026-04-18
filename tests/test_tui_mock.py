"""Tests for the terminal-UI MockAkaiFire (scaffold coverage — commit 1).

Uses ``headless=True`` so no TTY is needed and neither the render nor the
input thread runs. Later commits add keyboard-input and render tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import rich  # noqa: F401
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


@unittest.skipUnless(HAS_RICH, "rich is required for the TUI mock")
class TestTuiMockScaffold(unittest.TestCase):
    """The scaffold surface: constructor, setters, decorators, close."""

    def setUp(self) -> None:
        from mock_gui_tui import MockAkaiFire

        self.MockAkaiFire = MockAkaiFire
        self.fire = MockAkaiFire(headless=True)

    def tearDown(self) -> None:
        self.fire.close()

    # -- lifecycle -----------------------------------------------------

    def test_headless_close_is_clean(self):
        self.fire.close()  # already closed in tearDown; just verify idempotent

    def test_double_close_is_idempotent(self):
        self.fire.close()
        self.fire.close()

    def test_context_manager(self):
        with self.MockAkaiFire(headless=True) as fire:
            fire.set_pad_color(0, 127, 0, 0)
        # After exit the canvas is cleared and close() has run; asserts that
        # no exception is raised is enough for this scaffold test.

    def test_process_events_returns_true_while_open(self):
        self.assertTrue(self.fire.process_events())

    def test_start_listening_is_noop(self):
        self.fire.start_listening()  # must not raise

    # -- pad/LED setters ----------------------------------------------

    def test_set_pad_color_updates_state(self):
        self.fire.set_pad_color(5, 127, 64, 0)
        self.assertEqual(self.fire.pad_colors[5], [127, 64, 0])

    def test_set_pad_color_clamps_values(self):
        self.fire.set_pad_color(0, 500, -5, 255)
        self.assertEqual(self.fire.pad_colors[0], [127, 0, 127])

    def test_set_pad_color_rejects_out_of_range_index(self):
        self.assertFalse(self.fire.set_pad_color(64, 127, 0, 0))
        self.assertFalse(self.fire.set_pad_color(-1, 127, 0, 0))

    def test_set_multiple_pad_colors(self):
        self.fire.set_multiple_pad_colors([(0, 1, 2, 3), (1, 4, 5, 6), (2, 7, 8, 9)])
        self.assertEqual(self.fire.pad_colors[0], [1, 2, 3])
        self.assertEqual(self.fire.pad_colors[1], [4, 5, 6])
        self.assertEqual(self.fire.pad_colors[2], [7, 8, 9])

    def test_set_all_pads(self):
        self.fire.set_all_pads((10, 20, 30))
        for c in self.fire.pad_colors:
            self.assertEqual(c, [10, 20, 30])

    def test_clear_all_pads(self):
        self.fire.set_all_pads((100, 50, 25))
        self.fire.clear_all_pads()
        self.assertTrue(all(c == [0, 0, 0] for c in self.fire.pad_colors))

    def test_clear_pad(self):
        self.fire.set_pad_color(0, 127, 127, 127)
        self.fire.clear_pad(0)
        self.assertEqual(self.fire.pad_colors[0], [0, 0, 0])

    def test_set_button_led(self):
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
        self.assertEqual(
            self.fire.button_leds[self.fire.BUTTON_PLAY],
            self.fire.LED_HIGH_GREEN,
        )

    def test_clear_all_button_leds(self):
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)
        self.fire.clear_all_button_leds()
        self.assertEqual(self.fire.button_leds, {})

    def test_set_track_led(self):
        self.fire.set_track_led(2, self.fire.RECTANGLE_LED_HIGH_GREEN)
        self.assertEqual(self.fire.track_leds[1], self.fire.RECTANGLE_LED_HIGH_GREEN)

    def test_set_track_led_out_of_range(self):
        self.assertFalse(self.fire.set_track_led(0, 1))
        self.assertFalse(self.fire.set_track_led(5, 1))

    def test_clear_all_track_leds(self):
        for i in range(1, 5):
            self.fire.set_track_led(i, 1)
        self.fire.clear_all_track_leds()
        self.assertEqual(self.fire.track_leds, [0, 0, 0, 0])

    def test_set_control_bank_leds(self):
        self.fire.set_control_bank_leds(self.fire.CONTROL_BANK_CHANNEL)
        self.assertEqual(self.fire.control_bank_state, self.fire.CONTROL_BANK_CHANNEL)

    def test_clear_all(self):
        self.fire.set_pad_color(0, 127, 127, 127)
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)
        self.fire.set_track_led(1, 1)
        self.fire.clear_all()
        self.assertEqual(self.fire.pad_colors[0], [0, 0, 0])
        self.assertEqual(self.fire.button_leds, {})
        self.assertEqual(self.fire.track_leds, [0, 0, 0, 0])
        self.assertEqual(self.fire.control_bank_state, 0)

    # -- OLED canvas --------------------------------------------------

    def test_get_canvas_returns_same_instance(self):
        canvas = self.fire.get_canvas()
        self.assertIs(canvas, self.fire.canvas)

    def test_render_to_display_swaps_canvas(self):
        original = self.fire.canvas
        from akai_fire import Canvas

        new_canvas = Canvas()
        self.fire.render_to_display(new_canvas)
        self.assertIs(self.fire.canvas, new_canvas)
        self.assertIsNot(self.fire.canvas, original)

    def test_render_to_display_no_arg_keeps_canvas(self):
        before = self.fire.canvas
        self.fire.render_to_display()
        self.assertIs(self.fire.canvas, before)

    def test_new_canvas_returns_fresh_instance(self):
        before = self.fire.canvas
        fresh = self.fire.new_canvas()
        self.assertIs(self.fire.canvas, fresh)
        self.assertIsNot(fresh, before)

    def test_render_to_bmp_writes_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.bmp")
            self.fire.render_to_bmp(path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)

    # -- decorators + listener adders ---------------------------------

    def test_on_pad_global(self):
        calls = []

        @self.fire.on_pad()
        def h(pad, vel):
            calls.append((pad, vel))

        self.assertEqual(len(self.fire.global_pad_listeners), 1)
        self.assertIs(self.fire.global_pad_listeners[0], h)

    def test_on_pad_specific(self):
        @self.fire.on_pad(5)
        def h(vel):
            pass

        self.assertIn(h, self.fire.pad_listeners[5])

    def test_on_pad_list(self):
        @self.fire.on_pad([1, 2, 3])
        def h(vel):
            pass

        for idx in (1, 2, 3):
            self.assertIn(h, self.fire.pad_listeners[idx])

    def test_on_button_global_and_specific(self):
        @self.fire.on_button()
        def g(bid, event):
            pass

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def s(event):
            pass

        self.assertIn(g, self.fire.global_button_listeners)
        self.assertIn(s, self.fire.button_listeners[self.fire.BUTTON_PLAY])

    def test_on_rotary_turn_and_touch(self):
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def turn(direction, velocity):
            pass

        @self.fire.on_rotary_touch(self.fire.ROTARY_PAN)
        def touch(event):
            pass

        self.assertIn(turn, self.fire.rotary_listeners[self.fire.ROTARY_VOLUME])
        self.assertIn(touch, self.fire.rotary_touch_listeners[self.fire.ROTARY_PAN])

    def test_on_solo(self):
        @self.fire.on_solo(1)
        def s1(event):
            pass

        self.assertIn(s1, self.fire.button_listeners[self.fire.BUTTON_SOLO_1])

    def test_add_listener_variants(self):
        def cb(*args):
            pass

        self.fire.add_listener(0, cb)
        self.fire.add_listener([1, 2], cb)
        self.fire.add_global_listener(cb)
        self.fire.add_button_listener(self.fire.BUTTON_PLAY, cb)
        self.fire.add_rotary_listener(self.fire.ROTARY_VOLUME, cb)
        self.fire.add_rotary_touch_listener(self.fire.ROTARY_PAN, cb)

        self.assertIn(cb, self.fire.pad_listeners[0])
        self.assertIn(cb, self.fire.pad_listeners[1])
        self.assertIn(cb, self.fire.pad_listeners[2])
        self.assertIn(cb, self.fire.global_pad_listeners)
        self.assertIn(cb, self.fire.button_listeners[self.fire.BUTTON_PLAY])
        self.assertIn(cb, self.fire.rotary_listeners[self.fire.ROTARY_VOLUME])
        self.assertIn(cb, self.fire.rotary_touch_listeners[self.fire.ROTARY_PAN])

    # -- utility ------------------------------------------------------

    def test_pad_position(self):
        self.assertEqual(self.fire.pad_position(0), (0, 0))
        self.assertEqual(self.fire.pad_position(15), (15, 0))
        self.assertEqual(self.fire.pad_position(16), (0, 1))
        self.assertEqual(self.fire.pad_position(63), (15, 3))

    def test_get_pad_column_and_row(self):
        # 1-indexed, matching real hardware (column 1..16, row 1..4).
        self.assertEqual(self.fire.get_pad_column(17), 2)
        self.assertEqual(self.fire.get_pad_row(17), 2)

    def test_pad_position_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            self.fire.pad_position(64)

    def test_get_solo_index(self):
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_1), 1)
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_4), 4)
        self.assertIsNone(self.fire.get_solo_index(0x99))

    def test_list_midi_ports_returns_empty(self):
        self.assertEqual(self.fire.list_midi_ports(), {"input": [], "output": []})

    # -- modifier state (latching is filled in by commit 3) -----------

    def test_modifier_state_defaults_to_false(self):
        self.assertFalse(self.fire.is_shift_pressed())
        self.assertFalse(self.fire.is_alt_pressed())
        self.assertFalse(self.fire.shift_pressed)
        self.assertFalse(self.fire.alt_pressed)


@unittest.skipUnless(HAS_RICH, "rich is required for the TUI mock")
class TestTuiMockInput(unittest.TestCase):
    """Key dispatch via inject_key + set_focus — no TTY required."""

    def setUp(self) -> None:
        from mock_gui_tui import MockAkaiFire

        self.fire = MockAkaiFire(headless=True)

    def tearDown(self) -> None:
        self.fire.close()

    # -- focus navigation ---------------------------------------------

    def test_tab_cycles_regions(self):
        self.fire.set_focus("rotary", 0)
        self.fire.inject_key("tab")
        self.assertEqual(self.fire._focus[0], "btn_bank")
        self.fire.inject_key("tab")
        self.assertEqual(self.fire._focus[0], "btn_mode")

    def test_arrow_keys_move_within_pad_grid(self):
        self.fire.set_focus("pad", 0)
        self.fire.inject_key("right")
        self.assertEqual(self.fire._focus, ("pad", 1))
        self.fire.inject_key("down")
        self.assertEqual(self.fire._focus, ("pad", 17))
        self.fire.inject_key("left")
        self.assertEqual(self.fire._focus, ("pad", 16))
        self.fire.inject_key("up")
        self.assertEqual(self.fire._focus, ("pad", 0))

    def test_arrow_keys_clamp_at_pad_edges(self):
        self.fire.set_focus("pad", 0)
        self.fire.inject_key("left")
        self.fire.inject_key("up")
        self.assertEqual(self.fire._focus, ("pad", 0))
        self.fire.set_focus("pad", 63)
        self.fire.inject_key("right")
        self.fire.inject_key("down")
        self.assertEqual(self.fire._focus, ("pad", 63))

    def test_set_focus_rejects_unknown_region(self):
        with self.assertRaises(ValueError):
            self.fire.set_focus("not_a_region")

    # -- activation dispatches listeners ------------------------------

    def test_enter_on_pad_fires_handler(self):
        calls = []

        @self.fire.on_pad()
        def h(idx, vel):
            calls.append((idx, vel))

        self.fire.set_focus("pad", 37)
        self.fire.inject_key("enter")
        self.assertEqual(calls, [(37, 100)])

    def test_enter_on_transport_button_fires_press_then_release(self):
        events = []

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def h(event):
            events.append(event)

        self.fire.set_focus("btn_transport", 1)  # PLAY is index 1
        self.fire.inject_key("enter")
        # press fires synchronously; release is scheduled. Wait briefly.
        import time

        time.sleep(0.2)
        self.assertEqual(events, ["press", "release"])

    def test_space_fires_play_button(self):
        events = []

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def h(event):
            events.append(event)

        self.fire.inject_key("space")
        self.assertIn("press", events)

    def test_period_fires_stop_button(self):
        events = []

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def h(event):
            events.append(event)

        self.fire.inject_key(".")
        self.assertIn("press", events)

    # -- modifier toggles ---------------------------------------------

    def test_s_toggles_shift_state_and_fires_button(self):
        events = []

        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def h(event):
            events.append(event)

        self.fire.inject_key("s")
        self.assertTrue(self.fire.is_shift_pressed())
        self.fire.inject_key("s")
        self.assertFalse(self.fire.is_shift_pressed())
        self.assertEqual(events, ["press", "release"])

    def test_a_toggles_alt_state(self):
        self.fire.inject_key("a")
        self.assertTrue(self.fire.is_alt_pressed())
        self.fire.inject_key("a")
        self.assertFalse(self.fire.is_alt_pressed())

    def test_shift_modifier_observable_in_pad_handler(self):
        """Modifier-first invariant: pad handler sees latched shift."""
        observations = []

        @self.fire.on_pad()
        def h(idx, vel):
            observations.append(self.fire.is_shift_pressed())

        self.fire.set_focus("pad", 0)
        self.fire.inject_key("enter")  # no shift
        self.fire.inject_key("s")
        self.fire.inject_key("enter")  # shift latched
        self.assertEqual(observations, [False, True])

    # -- rotary dispatch ----------------------------------------------

    def test_plus_minus_turn_focused_rotary(self):
        turns = []

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def h(direction, velocity):
            turns.append((direction, velocity))

        self.fire.set_focus("rotary", 0)  # VOLUME
        self.fire.inject_key("+")
        self.fire.inject_key("-")
        self.assertEqual(
            turns, [("clockwise", 1), ("counterclockwise", 1)]
        )

    def test_rotary_turn_no_focus_does_nothing(self):
        turns = []

        @self.fire.on_rotary_turn()
        def h(rid, direction, velocity):
            turns.append((rid, direction, velocity))

        self.fire.set_focus("pad", 0)
        self.fire.inject_key("+")
        self.assertEqual(turns, [])

    def test_enter_on_rotary_fires_touch(self):
        touches = []

        @self.fire.on_rotary_touch(self.fire.ROTARY_PAN)
        def h(event):
            touches.append(event)

        self.fire.set_focus("rotary", 1)  # PAN
        self.fire.inject_key("enter")
        self.assertEqual(touches, ["touch"])

    # -- quit ---------------------------------------------------------

    def test_ctrl_q_sets_stop_flag(self):
        self.fire.inject_key("ctrl_q")
        self.assertTrue(self.fire._stop_flag.is_set())


@unittest.skipUnless(HAS_RICH, "rich is required for the TUI mock")
class TestTuiMockRendering(unittest.TestCase):
    """Glyph conversion + live-thread lifecycle."""

    def test_braille_oled_all_blank_is_spaces(self):
        from PIL import Image

        from mock_gui_tui import _braille_from_oled

        # mode "1" with fill=1 = off (white background in PIL)
        img = Image.new("1", (128, 64), 1)
        text = _braille_from_oled(img)
        # Every non-newline cell should be a space (no lit dots)
        body = str(text).replace("\n", "")
        self.assertEqual(len(body), 64 * 16)
        self.assertTrue(all(c == " " for c in body))

    def test_braille_oled_all_lit_is_full_dot_cells(self):
        from PIL import Image

        from mock_gui_tui import _braille_from_oled

        img = Image.new("1", (128, 64), 0)  # 0 = black = all lit
        text = _braille_from_oled(img)
        body = str(text).replace("\n", "")
        # 0x2800 | 0xFF = 0x28FF "⣿" (all eight dots lit)
        self.assertTrue(all(c == "\u28ff" for c in body))

    def test_build_view_returns_renderable(self):
        import io

        from mock_gui_tui import MockAkaiFire

        fire = MockAkaiFire(headless=True)
        try:
            view = fire._build_view()
            from rich.console import Console

            # Send output to an in-memory buffer so it doesn't pollute the
            # test runner's stdout.
            buf = io.StringIO()
            console = Console(file=buf, record=True, width=160, force_terminal=True)
            console.print(view)
            self.assertGreater(len(buf.getvalue()), 0)
        finally:
            fire.close()

    # Live-render-thread lifecycle is manually verified via
    # examples/run_tui_mock.py — we can't capture rich.live's console
    # cleanly in a test, and the thread-start/join plumbing is already
    # exercised by the scaffold's close() idempotency test.


@unittest.skipUnless(HAS_RICH, "rich is required for the TUI mock")
class TestGetAkaiFireWithTuiString(unittest.TestCase):
    """The new ``use_mock='tui'`` branch on ``get_akai_fire``."""

    def test_returns_tui_mock_class(self):
        from akai_fire import get_akai_fire
        from mock_gui_tui import MockAkaiFire as TuiMock

        fire = get_akai_fire(use_mock="tui", headless=True)
        try:
            self.assertIsInstance(fire, TuiMock)
        finally:
            fire.close()

    def test_pygame_string_alias_still_works(self):
        # `use_mock="pygame"` should be equivalent to `use_mock=True`.
        from akai_fire import get_akai_fire
        from mock_gui_pygame import MockAkaiFire as PygameMock

        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        fire = get_akai_fire(use_mock="pygame")
        try:
            self.assertIsInstance(fire, PygameMock)
        finally:
            fire.close()


if __name__ == "__main__":
    unittest.main()
