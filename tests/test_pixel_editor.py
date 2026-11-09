"""Tutorial contracts through real app input, file storage and OLED drawing."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from akai_fire import Canvas
from akai_fire_testing import MockAkaiFire
from examples.apps.pixel_editor.__main__ import main
from examples.apps.pixel_editor.app import PixelEditorApp, View
from examples.apps.pixel_editor.first_light import FirstLight
from examples.apps.pixel_editor.model import BLACK, PALETTE, Picture
from tests import test_oled_layouts as oled_layouts


class PictureTests(unittest.TestCase):
    def test_paint_recolors_toggles_and_erases(self):
        picture = Picture()
        picture.paint(17)
        self.assertEqual(picture.pixels[17], (0, 127, 0))
        picture.brush = 1
        picture.paint(17)
        self.assertEqual(picture.pixels[17], (127, 0, 0))
        picture.paint(17)
        self.assertEqual(picture.pixels[17], BLACK)
        picture.paint(17)
        picture.brush = 6
        picture.paint(17, erase=True)
        self.assertEqual(picture.pixels[17], BLACK)
        picture.paint(63)
        picture.clear()
        self.assertEqual(picture.pixels, [BLACK] * 64)
        self.assertEqual((picture.brush, picture.brightness), (6, 75))

    def test_file_roundtrip_and_failed_replace_preserve_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "picture.json"
            picture = Picture(brush=6, brightness=50)
            picture.paint(63)
            picture.save(path)
            self.assertEqual(Picture.load(path), picture)
            original = path.read_bytes()
            picture.paint(0)
            with (
                patch.object(Path, "replace", side_effect=OSError("disk error")),
                self.assertRaises(OSError),
            ):
                picture.save(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_snapshots_are_rejected(self):
        valid = {"version": 1, "pixels": [0] * 64, "brush": 4, "brightness": 75}
        invalid = [None, [], {}, {**valid, "version": True}, {**valid, "version": 3}]
        invalid += [
            {**valid, key: value}
            for key, values in (
                ("pixels", [[0], [9] * 64, [True] * 64, "0" * 64]),
                ("brush", [0, 9, True, "4"]),
                ("brightness", [9, 101, False, 75.5]),
            )
            for value in values
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "picture.json"
            for payload in invalid:
                with self.subTest(payload=payload):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        Picture.load(path)

    def test_legacy_picture_migrates_without_changing_pad_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "picture.json"
            old = {
                "version": 1,
                "pixels": [i % 9 for i in range(64)],
                "brush": 7,
                "brightness": 35,
            }
            path.write_text(json.dumps(old))
            picture = Picture.load(path)
            self.assertEqual(picture.pixels, [PALETTE[i % 9][1] for i in range(64)])
            self.assertEqual(picture.brush_color, PALETTE[7][1])
            for pad, *rgb in picture.pad_colors():
                self.assertEqual(rgb, [round(c * 0.35) for c in PALETTE[pad % 9][1]])
            picture.adjust_channel(0, -10)
            picture.paint(0)
            picture.save(path)
            self.assertEqual(json.loads(path.read_text())["version"], 2)
            self.assertEqual(Picture.load(path), picture)

    def test_rgb_snapshot_rejects_invalid_channels_and_custom_brush(self):
        valid = {
            "version": 2,
            "pixels": [[0, 0, 0]] * 64,
            "brush": 4,
            "brightness": 75,
            "custom_color": [4, 5, 6],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "picture.json"
            for bad in (
                True,
                0,
                [0, 0],
                [0, 0, 0, 0],
                [-1, 0, 0],
                [128, 0, 0],
                [True, 0, 0],
                [1.5, 0, 0],
            ):
                for field in ("pixels", "custom_color"):
                    payload = {
                        **valid,
                        field: [bad] + valid["pixels"][1:]
                        if field == "pixels"
                        else bad,
                    }
                    with self.subTest(field=field, bad=bad):
                        path.write_text(json.dumps(payload))
                        with self.assertRaises(ValueError):
                            Picture.load(path)
            path.write_text(json.dumps(valid))
            picture = Picture.load(path)
            self.assertEqual(picture.custom_color, (4, 5, 6))
            self.assertTrue(all(isinstance(color, tuple) for color in picture.pixels))


class PixelEditorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fire = MockAkaiFire()
        self.app = PixelEditorApp(
            self.fire, path=Path(self.directory.name) / "picture.json"
        )
        self.addCleanup(self.fire.close)
        self.addCleanup(self.app.shutdown)

    def frame(self):
        self.app.tick(1 / 30)

    def press(self, button):
        self.fire.simulate_button_press(button)
        self.fire.simulate_button_release(button)
        self.frame()

    def turn(self, delta, encoder=None):
        self.fire.simulate_rotary_turn(
            self.fire.ROTARY_SELECT if encoder is None else encoder,
            "clockwise" if delta >= 0 else "counterclockwise",
            abs(delta),
        )
        self.frame()

    def test_input_waits_for_frame_and_one_batch_renders_both_views(self):
        self.app.canvas = Canvas()
        with patch.object(
            self.fire,
            "set_multiple_pad_colors",
            wraps=self.fire.set_multiple_pad_colors,
        ) as batch:
            self.fire.simulate_pad_press(0)
            self.fire.simulate_pad_press(63)
            self.assertEqual(self.app.picture.pixels, [BLACK] * 64)
            self.frame()
            self.assertEqual(batch.call_count, 1)
            self.assertEqual(len(batch.call_args.args[0]), 64)
            self.fire.assert_pad_color(0, (0, 95, 0))
            self.fire.assert_pad_color(63, (0, 95, 0))
            for pad in (0, 63):
                row, col = divmod(pad, 16)
                self.assertEqual(
                    self.app.canvas.image.getpixel((8 + col * 7, 20 + row * 7)), 0
                )
            self.assertEqual(self.app.canvas.image.getpixel((15, 20)), 1)
            self.frame()
            self.assertEqual(batch.call_count, 1)

    def test_modifier_snapshot_survives_release_before_frame(self):
        self.app.picture.pixels[5] = (127, 0, 0)
        self.fire.simulate_button_press(self.fire.BUTTON_SHIFT)
        self.fire.simulate_pad_press(5)
        self.fire.simulate_button_release(self.fire.BUTTON_SHIFT)
        self.frame()
        self.assertEqual(self.app.picture.pixels[5], BLACK)

    def test_main_knobs_mix_brush_without_recoloring_existing_pixels(self):
        self.fire.simulate_pad_press(0)
        self.frame()
        self.turn(40, self.fire.ROTARY_VOLUME)
        self.turn(-27, self.fire.ROTARY_PAN)
        self.turn(80, self.fire.ROTARY_FILTER)
        self.assertEqual(self.app.picture.brush_color, (40, 100, 80))
        self.fire.simulate_pad_press(1)
        self.frame()
        self.assertEqual(self.app.picture.pixels[:2], [(0, 127, 0), (40, 100, 80)])
        self.turn(-5, self.fire.ROTARY_RESONANCE)
        self.assertEqual(self.app.picture.brightness, 50)
        self.fire.assert_pad_color(0, (0, 64, 0))
        self.fire.assert_pad_color(1, (20, 50, 40))
        self.press(self.fire.BUTTON_REC)
        self.assertEqual(Picture.load(self.app.path), self.app.picture)
        self.turn(1)
        self.assertIsNone(self.app.picture.custom_color)
        self.assertEqual(self.app.picture.brush_color, (0, 127, 127))
        self.assertEqual(self.app.picture.pixels[1], (40, 100, 80))

    def test_knob_bounds_black_erase_and_settings_shortcuts(self):
        self.fire.simulate_pad_press(0)
        self.frame()
        self.press(self.fire.BUTTON_BROWSER)
        self.press(self.fire.BUTTON_SELECT)
        self.turn(1000, self.fire.ROTARY_VOLUME)
        self.assertEqual(self.app.picture.brush_color, (127, 127, 0))
        self.assertTrue(self.app.menu.editing)
        for knob in (
            self.fire.ROTARY_VOLUME,
            self.fire.ROTARY_PAN,
            self.fire.ROTARY_FILTER,
        ):
            self.turn(-1000, knob)
        self.assertEqual(self.app.picture.brush_color, BLACK)
        self.turn(-1000, self.fire.ROTARY_RESONANCE)
        self.assertEqual(self.app.picture.brightness, 10)
        self.turn(1000, self.fire.ROTARY_RESONANCE)
        self.assertEqual(self.app.picture.brightness, 100)
        self.press(self.fire.BUTTON_NOTE)
        self.fire.simulate_pad_press(0)
        self.frame()
        self.assertEqual(self.app.picture.pixels[0], BLACK)
        self.assertIn("0/64*", [text for text, _, _ in self.app.canvas.text_drawn])

    def test_menu_edits_values_and_grid_preserves_edit_only_for_values(self):
        self.press(self.fire.BUTTON_BROWSER)
        self.press(self.fire.BUTTON_SELECT)
        self.turn(2)
        self.assertEqual(self.app.picture.brush, 6)
        self.press(self.fire.BUTTON_GRID_RIGHT)
        self.assertTrue(self.app.menu.editing)
        self.turn(-20)
        self.assertEqual(self.app.picture.brightness, 10)
        self.turn(30)
        self.assertEqual(self.app.picture.brightness, 100)
        self.press(self.fire.BUTTON_GRID_RIGHT)
        self.assertFalse(self.app.menu.editing)  # Save is an action, not a value.
        self.assertFalse(self.app.path.exists())
        self.press(self.fire.BUTTON_BROWSER)
        self.assertEqual(self.app.view, View.DRAW)

    def test_pads_in_settings_do_not_paint_and_leaving_ends_edit(self):
        self.press(self.fire.BUTTON_BROWSER)
        self.press(self.fire.BUTTON_SELECT)
        self.fire.simulate_pad_press(0)
        self.frame()
        self.assertEqual(self.app.picture.pixels, [BLACK] * 64)
        self.press(self.fire.BUTTON_NOTE)
        self.assertFalse(self.app.menu.editing)
        self.assertEqual(self.app.view, View.DRAW)

    def test_save_clear_load_and_invalid_load_keep_model_consistent(self):
        self.fire.simulate_pad_press(17)
        self.press(self.fire.BUTTON_REC)
        self.assertFalse(self.app.unsaved)
        self.assertEqual(
            json.loads(self.app.path.read_text())["pixels"][17], [0, 127, 0]
        )
        self.fire.simulate_button_press(self.fire.BUTTON_SHIFT)
        self.fire.simulate_button_press(self.fire.BUTTON_STOP)
        self.fire.simulate_button_release(self.fire.BUTTON_SHIFT)
        self.frame()
        self.assertEqual(self.app.picture.pixels[17], BLACK)
        self.press(self.fire.BUTTON_BROWSER)
        self.turn(3)
        self.press(self.fire.BUTTON_SELECT)
        self.assertEqual(self.app.picture.pixels[17], (0, 127, 0))
        before = self.app.picture
        self.app.path.write_text('{"version": 1}', encoding="utf-8")
        self.press(self.fire.BUTTON_SELECT)
        self.assertIs(self.app.picture, before)
        self.assertEqual(self.app.notice, "Load failed")

    def test_write_failure_keeps_dirty_state_and_reports_error(self):
        self.fire.simulate_pad_press(0)
        self.frame()
        self.press(self.fire.BUTTON_BROWSER)
        self.press(self.fire.BUTTON_SELECT)
        with patch.object(Picture, "save", side_effect=OSError("read-only")):
            self.press(self.fire.BUTTON_REC)
        self.assertTrue(self.app.unsaved)
        self.assertEqual(self.app.notice, "Save failed")
        self.assertIn(
            "Save failed", [text for text, _, _ in self.app.canvas.text_drawn]
        )

    def test_display_layouts_fit_for_every_menu_item_and_color(self):
        canvas = oled_layouts.MeasuredCanvas()
        self.app.canvas = canvas
        checker = oled_layouts.OledLayouts()
        for brush in range(1, len(PALETTE)):
            self.app.picture.brush = brush
            self.app._draw()
            checker.assert_readable(canvas)
        self.app.picture.custom_color = (127, 127, 127)
        self.app.picture.brightness = 100
        self.app._draw()
        checker.assert_readable(canvas)
        self.assertIn("R127 G127 B127 100%", [text for text, _ in canvas.text_boxes])
        self.press(self.fire.BUTTON_BROWSER)
        for index in range(len(self.app.menu.items)):
            self.app.menu.select(index)
            self.app._draw()
            checker.assert_readable(canvas)
            if index < 2:
                self.app.menu.press()
                self.app._draw()
                checker.assert_readable(canvas)
        self.app._notify("Load failed")
        self.app._draw()
        checker.assert_readable(canvas)

    def test_shutdown_removes_subscriptions_and_leaves_borrowed_device_open(self):
        self.app.run(duration=0)
        self.assertTrue(self.fire.is_connected())
        self.assertFalse(any(self.fire.pad_listeners.values()))
        self.assertFalse(any(self.fire.button_listeners.values()))
        self.assertFalse(any(self.fire.rotary_listeners.values()))

    def test_launcher_selects_backend_and_serial_hardware_delivery(self):
        for args, expected in (
            ([], {"use_mock": "pygame", "max_workers": 1}),
            (["--hardware"], {"use_mock": False, "max_workers": 1}),
        ):
            with (
                self.subTest(args=args),
                patch(
                    "examples.apps.pixel_editor.__main__.get_akai_fire",
                    return_value=MockAkaiFire(),
                ) as factory,
            ):
                main([*args, "--duration", "0"])
                factory.assert_called_once_with(**expected)

    def test_first_checkpoint_queues_toggles_and_stops(self):
        with MockAkaiFire() as fire, FirstLight(fire) as app:
            app.on_start()
            app.tick(0.04)
            self.assertIn("Lit pads: 0", [text for text, _, _ in app.canvas.text_drawn])
            fire.simulate_pad_press(7)
            self.assertEqual(app.lit, set())
            app.tick(0.04)
            fire.assert_pad_color(7, (0, 100, 0))
            fire.simulate_pad_press(7)
            app.tick(0.04)
            fire.assert_pad_color(7, (0, 0, 0))
            app.running = True
            fire.simulate_button_press(fire.BUTTON_STOP)
            app.tick(0.04)
            self.assertFalse(app.running)
