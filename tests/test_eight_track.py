"""Eight Track timing, decorated controls and measured OLED contracts."""

import os
import threading
import unittest
from unittest.mock import Mock, patch

from akai_fire_testing import MockAkaiFire
from examples.apps.eight_track.app import EightTrackApp
from examples.apps.eight_track.audio import PreviewSound
from examples.apps.eight_track.engine import Engine
from examples.apps.eight_track.model import Note, Part
from tests import test_oled_layouts as layouts


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.output = Mock()
        self.engine = Engine(self.output)
        self.addCleanup(self.engine.close)

    def phrase(self, notes):
        self.engine.parts = (Part("Test", (tuple(notes),) + ((),) * 7),)

    def test_note_duration_and_simultaneous_release_before_attack(self):
        self.phrase([Note(0, 60, 0.2), Note(0.2, 62, 0.1)])
        self.engine.play()
        self.output.note_on.assert_called_once_with(0, 60, 90)
        self.engine.advance(0.1)
        self.assertEqual(self.output.method_calls[-2][0], "note_off")
        self.assertEqual(self.output.method_calls[-1][0], "note_on")
        self.engine.advance(0.05)
        self.output.note_off.assert_called_with(0, 62)
        self.assertFalse(any(self.engine.snapshot().active))

    def test_overlapping_same_pitch_keeps_other_owner_alive(self):
        self.phrase([Note(0, 60, 0.3), Note(0.1, 60, 0.5)])
        self.engine.play()
        for _ in range(4):
            self.engine.advance(0.05)
        self.output.note_on.assert_called_once()
        self.output.note_off.assert_not_called()
        self.engine.toggle_mute(0)
        self.output.note_off.assert_called_once_with(0, 60)

    def test_part_queue_only_commits_at_boundary_and_can_cancel(self):
        self.engine.play()
        self.engine.select_part(1)
        self.assertEqual(
            (self.engine.snapshot().part, self.engine.snapshot().pending), (0, 1)
        )
        self.engine.select_part(0)
        self.assertIsNone(self.engine.snapshot().pending)
        self.engine.select_part(2)
        self.engine.advance(7.9)
        self.assertEqual(self.engine.snapshot().part, 0)
        self.engine.advance(0.1)
        self.assertEqual(self.engine.snapshot().part, 2)
        self.assertIsNone(self.engine.snapshot().pending)
        self.assertAlmostEqual(self.engine.snapshot().position, 0)

    def test_stop_resume_rewind_and_close_silence(self):
        self.engine.play()
        self.engine.advance(0.5)
        self.engine.stop()
        self.assertEqual(self.engine.snapshot().position, 1)
        self.assertFalse(any(self.engine.snapshot().active))
        self.engine.play()
        self.assertEqual(self.engine.snapshot().position, 1)
        self.engine.stop()
        self.engine.stop()
        self.assertEqual(self.engine.snapshot().position, 0)
        self.engine.close()
        self.engine.close()
        self.output.stop.assert_called_once()

    def test_late_clock_skips_expired_notes_and_stays_bounded(self):
        self.phrase([Note(0.1, 60, 0.1), Note(1, 64, 1.5)])
        self.engine.play()
        self.engine.advance(0.75)
        self.output.note_on.assert_called_once_with(0, 64, 90)
        self.engine.advance(10**9)
        self.assertLess(self.engine.snapshot().position, 16)
        for bad in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.engine.advance(bad)

    def test_transforms_preserve_material_and_snapshot_is_immutable(self):
        original = self.engine.parts
        self.engine.adjust("transpose", 100, 3)
        self.engine.adjust("tempo", 1000)
        self.engine.adjust("quantize", 1)
        self.engine.adjust("swing", 30)
        s = self.engine.snapshot()
        self.assertEqual(s.transpose[3], 24)
        self.assertEqual(s.bpm, 240)
        self.assertEqual(self.engine.parts, original)
        self.engine.toggle_mute(3)
        self.assertFalse(s.muted[3])
        self.assertTrue(self.engine.snapshot().muted[3])

    def test_clock_failure_is_visible_and_play_cannot_restart_dead_worker(self):
        stopped = threading.Event()
        self.output.note_off.side_effect = OSError("output disappeared")
        self.output.stop.side_effect = stopped.set
        self.phrase([Note(0, 60, 0.02)])
        self.engine.parts += self.engine.parts
        self.engine.play()
        self.engine.select_part(1)
        self.engine.start()
        self.assertTrue(stopped.wait(2), "Clock did not report output failure")
        s = self.engine.snapshot()
        self.assertIn("output disappeared", s.error)
        self.assertFalse(s.running)
        self.assertIsNone(s.pending)
        self.output.stop.assert_called_once()
        self.engine.play()
        self.assertFalse(self.engine.snapshot().running)

    def test_clock_releases_notes_without_any_gui_frames(self):
        released = threading.Event()
        self.output.note_off.side_effect = lambda *args: released.set()
        self.phrase([Note(0, 60, 0.02)])
        self.engine.play()
        self.engine.start()
        self.assertTrue(released.wait(2), "Playback depended on a UI frame")
        self.engine.close()
        self.assertFalse(self.engine._thread.is_alive())

    def test_foreground_output_errors_enter_the_same_visible_failure_state(self):
        for operation in ("play", "mute", "transpose"):
            with self.subTest(operation=operation):
                output = Mock()
                engine = Engine(output)
                self.addCleanup(engine.close)
                if operation == "play":
                    output.note_on.side_effect = OSError("audio gone")
                    engine.play()
                else:
                    engine.play()
                    engine.select_part(1)
                    output.note_off.side_effect = OSError("audio gone")
                    if operation == "mute":
                        engine.toggle_mute(0)
                    else:
                        engine.adjust("transpose", 1)
                s = engine.snapshot()
                self.assertFalse(s.running)
                self.assertFalse(any(s.active))
                self.assertIsNone(s.pending)
                self.assertIn("audio gone", s.error)
                output.stop.assert_called_once()

    def test_failed_output_cleanup_does_not_escape_or_prevent_close(self):
        self.output.note_on.side_effect = OSError("audio gone")
        self.output.stop.side_effect = OSError("cleanup gone")
        self.engine.play()
        self.engine.close()
        self.assertFalse(self.engine.snapshot().running)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.output = Mock()
        self.app = EightTrackApp(self.fire, output=self.output, threaded=False)
        self.addCleanup(self.fire.close)
        self.addCleanup(self.app.shutdown)
        self.app.canvas = layouts.MeasuredCanvas()
        self.app.on_start()

    def button(self, button):
        self.fire.simulate_button_press(button)
        self.fire.simulate_button_release(button)
        self.app.tick(0)

    def turn(self, encoder, delta):
        self.fire.simulate_rotary_turn(
            encoder, "clockwise" if delta > 0 else "counterclockwise", abs(delta)
        )
        self.app.tick(0)

    def test_all_bottom_pairs_select_and_mute_independently(self):
        for track in range(8):
            before = self.app.selected
            self.fire.simulate_pad_press(48 + track * 2)
            self.assertEqual(self.app.selected, before)
            self.app.tick(0)
            self.assertEqual(self.app.selected, track)
            self.assertFalse(self.app.engine.snapshot().muted[track])
            self.fire.simulate_pad_press(49 + track * 2)
            self.app.tick(0)
            self.assertEqual(self.app.selected, track)
            self.assertTrue(self.app.engine.snapshot().muted[track])
            self.fire.simulate_pad_press(49 + track * 2)
            self.app.tick(0)
        self.assertFalse(any(self.app.engine.snapshot().muted))

    def test_transport_parts_and_pending_display_through_decorators(self):
        self.button(self.fire.BUTTON_PATTERN)
        self.fire.simulate_pad_press(1)
        self.app.tick(0)
        self.assertEqual(self.app.engine.snapshot().part, 1)
        self.button(self.fire.BUTTON_PLAY)
        self.fire.simulate_pad_press(2)
        self.app.tick(0)
        self.button(self.fire.BUTTON_PERFORM)
        self.assertEqual(self.app.last_snapshot.pending, 2)
        self.assertTrue(
            any("NEXT P03" in text for text, _ in self.app.canvas.text_boxes)
        )
        self.button(self.fire.BUTTON_STOP)
        self.assertIsNone(self.app.last_snapshot.pending)
        self.assertFalse(self.app.last_snapshot.running)

    def test_knobs_and_select_edit_mode_and_view_exit(self):
        for encoder, delta in (
            (self.fire.ROTARY_VOLUME, 3),
            (self.fire.ROTARY_PAN, 1),
            (self.fire.ROTARY_FILTER, 12),
            (self.fire.ROTARY_RESONANCE, 2),
        ):
            self.turn(encoder, delta)
        s = self.app.engine.snapshot()
        self.assertEqual((s.bpm, s.quantize, s.swing, s.transpose[0]), (123, 1, 12, 2))
        self.button(self.fire.BUTTON_SELECT)
        self.button(self.fire.BUTTON_SELECT)
        self.assertTrue(self.app.menu.editing)
        self.turn(self.fire.ROTARY_SELECT, -3)
        self.assertEqual(self.app.engine.snapshot().transpose[0], -1)
        self.button(self.fire.BUTTON_PERFORM)
        self.assertFalse(self.app.menu.editing)
        self.turn(self.fire.ROTARY_SELECT, 7)
        self.assertEqual(self.app.selected, 7)

    def test_every_view_has_readable_text_including_extreme_values(self):
        self.app.engine.adjust("tempo", 999)
        self.app.engine.adjust("transpose", -999, 7)
        self.app.selected = 7
        for view in ("perform", "parts", "settings", "help"):
            self.app.view = view
            self.app.tick(0)
            layouts.OledLayouts.assert_readable(self, self.app.canvas)
        self.app.view = "settings"
        self.app.menu.press()
        self.app.tick(0)
        layouts.OledLayouts.assert_readable(self, self.app.canvas)

    def test_shutdown_closes_clock_but_not_borrowed_controller(self):
        self.button(self.fire.BUTTON_PLAY)
        self.app.threaded = True
        self.app.run(duration=0)
        self.assertFalse(self.app.engine._thread.is_alive())
        self.assertFalse(self.app.engine.snapshot().running)
        self.output.stop.assert_called_once()
        self.assertFalse(self.fire._closed)


class AudioAndLauncherTests(unittest.TestCase):
    def test_generated_audio_handles_polyphony_and_cleanup(self):
        with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
            sound = PreviewSound()
            self.addCleanup(sound.close)
            self.assertTrue(sound.available, sound.reason)
            for track in range(8):
                sound.note_on(track, 48 + track, 90)
            self.assertEqual(len(sound._voices), 8)
            sound.note_off(3, 51)
            self.assertNotIn((3, 51), sound._voices)
            sound.stop()
            self.assertFalse(sound._voices)

    def test_launcher_defaults_to_mock_and_hardware_is_explicit(self):
        from examples.apps.eight_track.__main__ import main

        for flags, backend in (([], "pygame"), (["--hardware"], False)):
            with (
                patch("examples.apps.eight_track.__main__.get_akai_fire") as factory,
                patch("examples.apps.eight_track.__main__.EightTrackApp") as app,
                patch("examples.apps.eight_track.__main__.PreviewSound"),
            ):
                main(flags + ["--duration", "0", "--silent"])
                factory.assert_called_once_with(use_mock=backend, max_workers=1)
                app.return_value.__enter__.return_value.run.assert_called_once_with(
                    duration=0
                )


if __name__ == "__main__":
    unittest.main()
