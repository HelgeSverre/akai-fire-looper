"""Check real font extents: no text overlaps or silently leaves the OLED."""

import subprocess
import sys
import unittest
from itertools import combinations
from unittest.mock import Mock, patch

from PIL import ImageFont

from akai_fire import Canvas
from akai_fire_framework import ScreenMixin
from akai_fire_testing import MockAkaiFire
from examples.apps.circuit.ui.screen_manager import Mode, ScreenManager
from examples.apps.midi_scope import MidiScopeApp
from examples.apps.snake.app import SnakeApp
from examples.apps.snake.game import State
from examples.apps.synth_editor.app import SynthEditorApp
from examples.apps.synth_editor.parameters import PARAMETERS
from screen_manager import MenuScreen, TextScreen


class MeasuredCanvas(Canvas):
    def __init__(self):
        super().__init__()
        self.text_boxes = []

    def clear(self, color=1):
        super().clear(color)
        self.text_boxes = []

    def draw_text(self, text, x, y, font=None, color=0):
        font = font or ImageFont.load_default()
        left, top, right, bottom = self.draw.textbbox((x, y), text, font=font)
        if text.strip():
            self.text_boxes.append((text, (left, top, right, bottom)))
        super().draw_text(text, x, y, font, color)


class OledLayouts(unittest.TestCase):
    def assert_readable(self, canvas):
        self.assertTrue(canvas.text_boxes, "No visible text was drawn")
        for text, (left, top, right, bottom) in canvas.text_boxes:
            self.assertTrue(
                0 <= left < right <= 128 and 0 <= top < bottom <= 64,
                f"Clipped {text!r}: {(left, top, right, bottom)}",
            )
        for (a, ra), (b, rb) in combinations(canvas.text_boxes, 2):
            overlaps = max(ra[0], rb[0]) < min(ra[2], rb[2]) and max(
                ra[1], rb[1]
            ) < min(ra[3], rb[3])
            self.assertFalse(overlaps, f"Overlapping {a!r} {ra} and {b!r} {rb}")

    def test_page_limits_rows_and_split_limits_columns(self):
        canvas = MeasuredCanvas()
        canvas.draw_page("A very long title that does not fit", ["Wide line " * 8] * 10)
        self.assert_readable(canvas)
        self.assertEqual(len(canvas.text_boxes), 4)  # Header plus three full rows.
        canvas.clear()
        canvas.draw_split_screen(
            "Split", ["WWWWWWWWWWWWWWWW"] * 10, ["Right column"] * 10
        )
        self.assert_readable(canvas)
        for _, box in canvas.text_boxes[1:5]:
            self.assertLess(box[2], 64)

    def test_menu_last_item_remains_visible_on_real_and_testing_canvas(self):
        from akai_fire_testing import MockCanvas

        for canvas in (MeasuredCanvas(), MockCanvas()):
            canvas.draw_menu("Settings", [f"Item {i}" for i in range(10)], 9)
            if isinstance(canvas, MeasuredCanvas):
                self.assert_readable(canvas)
                labels = [text for text, _ in canvas.text_boxes]
            else:
                labels = [text for text, _, _ in canvas.text_drawn]
            self.assertIn("Item 9", labels)
            self.assertEqual(len(labels), 4)

    def test_fitted_text_preserves_raw_scrolling_api(self):
        canvas = MeasuredCanvas()
        canvas.draw_text_fitted("W" * 100, 4, 2, width=35)
        self.assert_readable(canvas)
        self.assertLessEqual(canvas.text_boxes[0][1][2], 39)
        self.assertTrue(canvas.text_boxes[0][0].endswith("..."))
        self.assertEqual(Canvas.fit_text("abc", 0), "")
        self.assertEqual(Canvas.fit_text("abc", 1), "")
        canvas.draw_text("Scrolling text", -10, 20)
        self.assertLess(canvas.text_boxes[-1][1][0], 0)

    def test_framework_headers_menus_and_root_screens(self):
        canvas = MeasuredCanvas()
        mixin = ScreenMixin()
        mixin.canvas = canvas
        mixin.draw_header("A long application name", "RECORDING 300 BPM")
        mixin.draw_content_lines(["Long content " * 10] * 8)
        self.assert_readable(canvas)
        mixin.draw_menu("Settings", ["A wide menu item " * 4] * 10, 9)
        self.assert_readable(canvas)
        TextScreen(canvas, "Console", ["A long log line " * 5] * 20).render()
        self.assert_readable(canvas)
        menu = MenuScreen(canvas, "Menu")
        for i in range(10):
            menu.add_item(f"Item {i}")
        menu.selected_index = 9
        menu.render()
        self.assert_readable(canvas)
        self.assertIn("Item 9", [text for text, _ in canvas.text_boxes])

    def test_header_text_keeps_both_edges_clear_in_rendered_pixels(self):
        for screen_type in (ScreenMixin, ScreenManager):
            for status in ("STOP 120", "PLAY 300", "RECORDING 300 BPM"):
                with self.subTest(screen=screen_type.__name__, status=status):
                    canvas = Canvas()
                    screen = (
                        ScreenManager(canvas)
                        if screen_type is ScreenManager
                        else ScreenMixin()
                    )
                    screen.canvas = canvas
                    screen.draw_header("NOTE T2", status)
                    for y in range(screen.HEADER_HEIGHT):
                        for x in (*range(4), *range(124, 128)):
                            self.assertEqual(
                                canvas.image.getpixel((x, y)),
                                0,
                                f"Header text entered the inset at {(x, y)}",
                            )

    def test_all_circuit_modes_with_long_dynamic_values(self):
        canvas = MeasuredCanvas()
        screen = ScreenManager(canvas)
        status = {
            "timing": {"bpm": 300, "swing": 0.75, "quantization": "1/32"},
            "transport_state": "RECORDING",
            "current_track": 2,
            "tracks": [
                {
                    "name": "Very long synthesizer name",
                    "midi_channel": 16,
                    "pattern_chain": list(range(1, 17)),
                }
            ]
            * 4,
        }
        for mode in Mode:
            with self.subTest(mode=mode):
                screen.set_mode(mode)
                screen.update_display(
                    status,
                    current_notes=[48, 52, 55, 60, 64, 67],
                    step_info={
                        "step": 32,
                        "track_name": "Long track name",
                        "notes": [60, 64, 67],
                        "gate": 4,
                    },
                    edit_parameter="velocity",
                    menu_title="Track configuration menu",
                    menu_items=["MIDI channel: 16"] * 9,
                    selected_index=8,
                )
                self.assert_readable(canvas)
        screen.draw_startup_screen()
        self.assert_readable(canvas)
        screen.draw_error_screen(
            "A very long instrument port name that does not fit the screen"
        )
        self.assert_readable(canvas)

    def make_fire(self):
        fire = MockAkaiFire()
        fire.canvas = MeasuredCanvas()
        self.addCleanup(fire.close)
        return fire

    def test_synth_pages_overview_detail_and_long_notice(self):
        fire = self.make_fire()
        output = Mock(port_name=None, channel=16)
        with SynthEditorApp(fire, output=output) as app:
            app.values = dict.fromkeys(PARAMETERS, 127)
            app.notice = "A very long snapshot filename was saved"
            for page in range(4):
                for detail in (False, True):
                    with self.subTest(page=page, detail=detail):
                        app.page, app.detail = page, detail
                        app.on_update(0.04)
                        self.assert_readable(fire.canvas)

    def test_scope_views_and_snake_states(self):
        fire = self.make_fire()
        with MidiScopeApp(fire) as app:
            for i in range(8):
                fire.simulate_button_press(fire.BUTTON_GRID_RIGHT)
                fire.simulate_rotary_turn(fire.ROTARY_VOLUME, "counterclockwise", 127)
            for log in (True, False):
                app.show_log = log
                app.notice = "Long diagnostic message " * 4
                app.on_update(0.04)
                self.assert_readable(fire.canvas)
        with SnakeApp(fire) as app:
            for state in State:
                app.game.state = state
                app.game.score = app.game.best = 61
                app.on_update(0)
                self.assert_readable(fire.canvas)

    def test_modal_and_looper_views(self):
        from examples.apps.looper.looper_app import LooperApp
        from examples.apps.modal_demo import ModalDemoApp

        for app_class in (LooperApp, ModalDemoApp):
            fire = self.make_fire()
            with app_class(fire) as app:
                for button in (fire.BUTTON_NOTE, fire.BUTTON_BROWSER):
                    fire.simulate_button_press(button)
                    app.on_update(0.04)
                    self.assert_readable(fire.canvas)

    def test_oled_page_catalog(self):
        from examples.oled_pages import ScreenDemo, ScreenLayoutDemo

        fire = self.make_fire()
        # Avoid constructing a controller or writing the demo's preview files.
        demo = ScreenLayoutDemo.__new__(ScreenLayoutDemo)
        demo.fire, demo.canvas = fire, fire.canvas
        demo.setup_demo_data()
        with patch.object(fire, "render_to_bmp"):
            for screen in ScreenDemo:
                demo.current_screen = screen
                demo.draw_current_screen()
                self.assert_readable(fire.canvas)

    def test_gallery_polarity_and_animation_frames(self):
        from examples import oled_gallery

        canvas = Canvas()
        oled_gallery.draw_matrix_rain(canvas, 4)
        self.assertEqual(canvas.get_pixel(0, 8), 0)
        oled_gallery.draw_tron_humanoid(canvas, 0)
        self.assertEqual(canvas.get_pixel(64, 26), 0)
        for name in dir(oled_gallery):
            if not name.startswith("draw_"):
                continue
            draw = getattr(oled_gallery, name)
            for frame in (0, 25, 100):
                with self.subTest(animation=name, frame=frame):
                    draw(canvas, frame)
                    self.assertEqual(canvas.image.size, (128, 64))
                    self.assertEqual(
                        {color for _, color in canvas.image.getcolors()}, {0, 1}
                    )

    def test_legacy_oled_views_and_refresh_cleanup(self):
        from examples.legacy import circuit_standalone as circuit
        from examples.legacy import groovebox_standalone as groovebox
        from examples.legacy import looper_standalone as looper

        for module, app_class in (
            (circuit, circuit.CircuitTracks),
            (groovebox, groovebox.Groovebox),
            (looper, looper.MidiLooper),
        ):
            fire = self.make_fire()
            port = Mock(get_ports=list)
            with (
                patch.object(module, "get_akai_fire", return_value=fire),
                patch("rtmidi.MidiIn", return_value=port),
                patch("rtmidi.MidiOut", return_value=port),
            ):
                app = app_class()
                if module is circuit:
                    for mode in circuit.ViewMode:
                        with self.subTest(app="legacy Circuit", mode=mode):
                            app.view_mode = mode
                            app.canvas.clear()
                            app.update_grid()
                            self.assert_readable(app.canvas)
                    with patch.object(fire, "render_to_display") as render:
                        app.draw_fx_view()
                        render.assert_called_once()
                elif module is groovebox:
                    app.selected_track = app.selected_clip = 0
                    clip = app.tracks[0][0]
                    clip.step_sequence = groovebox.StepSequence(
                        [groovebox.StepParameters() for _ in range(16)]
                    )
                    clip.euclidean = groovebox.EuclideanPattern()
                    clip.generative = groovebox.GenerativePattern()
                    for mode in groovebox.EditMode:
                        with self.subTest(app="legacy Groovebox", mode=mode):
                            app.edit_mode = mode
                            app.update_display()
                            self.assert_readable(app.canvas)
                    app.edit_mode = groovebox.EditMode.CLIP
                    app.update_display()
                    before = app.canvas.image.tobytes()
                    app.update_display()
                    self.assertEqual(before, app.canvas.image.tobytes())
                else:
                    app.midi_inputs = app.midi_outputs = [
                        "Long instrument port name"
                    ] * 6
                    app.midi_monitor_messages = ["note on channel 16 velocity 127"] * 4
                    app.last_pressed_pad = 63
                    for mode in looper.ScreenMode:
                        with self.subTest(app="legacy Looper", mode=mode):
                            app.screen_mode = mode
                            app._update_display()
                            self.assert_readable(app.canvas)
                    with (
                        patch.object(app, "_handle_pad") as pad,
                        patch.object(app, "_handle_solo") as solo,
                    ):
                        fire.simulate_pad_press(31, 100)
                        fire.simulate_pad_release(31)
                        pad.assert_called_once_with(31)
                        fire.simulate_button_press(fire.BUTTON_SOLO_3)
                        solo.assert_called_once_with(2, "press")


class CircuitMidiRegression(unittest.TestCase):
    def test_connected_note_output_does_not_deadlock_activity_tracking(self):
        # Isolate the potential lock hang so a regression cannot stall discovery.
        code = """
from unittest.mock import Mock, patch
from examples.apps.circuit.core.midi_manager import MidiManager
port = Mock()
port.get_ports.return_value = []
port.is_port_open.return_value = True
with patch("rtmidi.MidiIn", return_value=Mock(get_ports=list)), patch("rtmidi.MidiOut", return_value=port):
    midi = MidiManager()
    midi.send_note_on(3, 60, 100)
    port.send_message.assert_called_with([0x92, 60, 100])
    assert midi.channel_velocities[3] == 100
    assert (3, 60) in midi.active_notes
    midi.send_note_off(3, 60)
    assert not midi.active_notes
    midi.cleanup()
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
