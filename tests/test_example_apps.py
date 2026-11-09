"""Executable contracts for the maintained examples; no physical MIDI ports."""

import csv
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from akai_fire_framework import AkaiFireApp, TransportState
from akai_fire_testing import MockAkaiFire, MockMidiManager
from examples.apps.circuit.core.midi_manager import MidiMessage
from examples.apps.circuit.core.sequencer import Sequencer
from examples.apps.circuit.core.sequencer import TransportState as CircuitState
from examples.apps.circuit.core.timing import TimingEngine
from examples.apps.circuit.main import CircuitSequencer
from examples.apps.circuit.ui.screen_manager import Mode
from examples.apps.looper.clip import Clip, ClipState
from examples.apps.looper.looper_app import LooperApp
from examples.apps.midi_scope import MidiScopeApp
from examples.apps.synth_editor.app import SynthEditorApp
from examples.apps.synth_editor.midi import SynthOutput


class AppContracts(unittest.TestCase):
    def test_color_cycle_reaches_full_brightness_in_each_channel(self):
        from examples import pads_color_cycle

        fire = MockAkaiFire()
        with (
            patch.object(pads_color_cycle, "get_akai_fire", return_value=fire),
            patch.object(pads_color_cycle, "wait"),
            patch.object(fire, "set_pad_color", wraps=fire.set_pad_color) as send,
        ):
            pads_color_cycle.main()
        colors = {call.args[1:] for call in send.call_args_list}
        for primary in ((127, 0, 0), (0, 127, 0), (0, 0, 127)):
            self.assertIn(primary, colors)
        self.assertTrue(fire._closed)
        self.assertEqual(fire.pad_colors, [(0, 0, 0)] * 64)

    def test_all_examples_import_without_opening_midi(self):
        with (
            patch("rtmidi.MidiIn", side_effect=AssertionError("input on import")),
            patch("rtmidi.MidiOut", side_effect=AssertionError("output on import")),
        ):
            for path in sorted(Path("examples").rglob("*.py")):
                if path.name == "__main__.py" or "tests" in path.parts:
                    continue
                module = ".".join(path.with_suffix("").parts)
                with self.subTest(module=module):
                    importlib.import_module(module)

    def test_press_hook_ignores_mock_release(self):
        fire = MockAkaiFire()
        app = AkaiFireApp(fire)
        app.on_pad_press = Mock()
        fire.simulate_pad_press(1, 100)
        fire.simulate_pad_release(1)
        app.on_pad_press.assert_called_once_with(1, 100)
        app.shutdown()

    def test_removal_failure_still_fences_callbacks_and_cleans_app(self):
        fire = MockAkaiFire()
        app = AkaiFireApp(fire)
        app.on_stop = Mock()
        app.on_pad_press = Mock()
        app.on_button_press = Mock()
        fire.clear_all = Mock()
        fire.remove_rotary_listener = Mock(side_effect=RuntimeError("remove failed"))
        # Removers were captured during registration, so fail the original
        # registered removal callable via its shared registry implementation.
        with (
            patch.object(
                fire,
                "_remove_registered_listener",
                side_effect=RuntimeError("remove failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            app.shutdown()
        app.on_stop.assert_called_once()
        fire.clear_all.assert_called_once()
        fire.simulate_pad_press(0)
        fire.simulate_button_press(fire.BUTTON_PLAY)
        app.on_pad_press.assert_not_called()
        app.on_button_press.assert_not_called()

    def test_led_demos_close_cleanly_when_window_closes(self):
        from examples import leds_control_bank, leds_track_cycle

        for module in (leds_control_bank, leds_track_cycle):
            with self.subTest(module=module.__name__):
                fire = MockAkaiFire()
                with (
                    patch.object(module, "get_akai_fire", return_value=fire),
                    patch.object(module, "wait", side_effect=KeyboardInterrupt),
                    patch.object(fire, "close", wraps=fire.close) as close,
                ):
                    module.main()
                close.assert_called_once()

    def test_empty_midi_port_menu_still_navigates(self):
        from examples.sequencer_basic import MenuOption

        option = MenuOption("MIDI input", [])
        option.next_option()
        option.prev_option()
        self.assertEqual(option.get_current_option(), "(none)")

    def test_zero_duration_starts_and_stops_once(self):
        fire = MockAkaiFire()
        app = AkaiFireApp(fire)
        app.on_start = Mock()
        app.on_stop = Mock()
        with app:
            app.run(duration=0)
        app.on_start.assert_called_once()
        app.on_stop.assert_called_once()
        self.assertFalse(app.running)
        self.assertEqual(fire.pad_listeners["global"], [])

    def test_invalid_duration_is_rejected(self):
        with AkaiFireApp(MockAkaiFire()) as app:
            for duration in (-1, float("inf"), float("nan")):
                with self.subTest(duration=duration), self.assertRaises(ValueError):
                    app.run(duration=duration)

    def test_procedural_example_pumps_input_and_closes(self):
        from examples import events_basic

        fire = MockAkaiFire()
        fire.close = Mock()

        def pump():
            fire.simulate_pad_press(17, 100)
            return False

        fire.process_events = pump
        with patch.object(events_basic, "get_akai_fire", return_value=fire):
            events_basic.main()
        fire.close.assert_called_once()
        self.assertTrue(
            any(
                event.pad_index == 17 and event.color == (0, 100, 0)
                for event in fire.pad_events
            )
        )

    def test_pad_counter_and_modal_transport_wait_for_foreground_tick(self):
        from examples.apps.modal_demo import ModalDemoApp
        from examples.apps.pad_counter import PadCounterApp

        with MockAkaiFire() as fire, PadCounterApp(fire) as app:
            fire.simulate_pad_press(63)
            self.assertEqual(app.count, 0)
            app.tick(0)
            self.assertEqual((app.count, app.last_pad), (1, 63))
            fire.assert_pad_color(63, (0, 127, 0))
            app.running = True
            fire.simulate_button_press(fire.BUTTON_STOP)
            self.assertTrue(app.running)
            app.tick(0)
            self.assertFalse(app.running)
        with MockAkaiFire() as fire, ModalDemoApp(fire) as app:
            fire.simulate_button_press(fire.BUTTON_PLAY)
            self.assertEqual(app.transport_state, TransportState.STOPPED)
            app.tick(0)
            self.assertEqual(app.transport_state, TransportState.PLAYING)
            fire.simulate_button_release(fire.BUTTON_PLAY)
            app.tick(0)
            self.assertEqual(app.transport_state, TransportState.PLAYING)
            fire.simulate_button_press(fire.BUTTON_PLAY)
            app.tick(0)
            self.assertEqual(app.transport_state, TransportState.STOPPED)

    def test_looper_rec_has_one_owner_and_cancels_armed(self):
        fire = MockAkaiFire()
        with LooperApp(fire) as app:
            fire.simulate_button_press(fire.BUTTON_REC)
            app.tick(0)
            self.assertEqual(app.transport_state, TransportState.ARMED)
            self.assertEqual(app.grid.selected_clip.state, ClipState.ARMED)
            fire.simulate_button_press(fire.BUTTON_REC)
            app.tick(0)
            self.assertEqual(app.transport_state, TransportState.STOPPED)
            self.assertEqual(app.grid.selected_clip.state, ClipState.EMPTY)

    def test_looper_recording_uses_requested_bpm(self):
        clip = Clip(length_bars=1)
        with patch("examples.apps.looper.clip.time.monotonic", return_value=10):
            clip.start_recording(60)
        with patch("examples.apps.looper.clip.time.monotonic", return_value=11):
            clip.record_note_on(60, 90)
        with patch("examples.apps.looper.clip.time.monotonic", return_value=12):
            clip.record_note_off(60)
        self.assertEqual(clip.events[0].time, 0.25)
        self.assertEqual(clip.events[0].duration, 0.25)


class SynthContracts(unittest.TestCase):
    def setUp(self):
        self.port = Mock()
        self.port.get_ports.return_value = ["FL STUDIO FIRE", "JT-4000 MICRO"]
        self.factory = patch("rtmidi.MidiOut", return_value=self.port).start()
        self.addCleanup(patch.stopall)
        self.output = SynthOutput(channel=3)
        self.addCleanup(self.output.close)

    def test_auto_connects_only_unique_jt4000_and_sends_nothing_on_start(self):
        self.port.open_port.assert_called_once_with(1)
        self.port.send_message.assert_not_called()
        with SynthEditorApp(MockAkaiFire(), output=self.output) as app:
            self.port.send_message.assert_not_called()
            self.assertTrue(all(value is None for value in app.values.values()))

    def test_fire_output_is_rejected(self):
        with self.assertRaises(ValueError):
            SynthOutput("FL STUDIO FIRE")

    def test_ambiguous_auto_detection_stays_in_preview(self):
        self.port.get_ports.return_value = ["JT-4000 A", "JT-4000 B"]
        with patch("rtmidi.MidiOut", return_value=self.port):
            output = SynthOutput()
            self.assertIsNone(output.port_name)
            output.cc(74, 100)
            self.port.send_message.assert_not_called()
            output.close()

    def test_encoders_and_pad_faders_send_profile_ccs(self):
        fire = MockAkaiFire()
        with SynthEditorApp(fire, output=self.output) as app:
            fire.simulate_rotary_turn(fire.ROTARY_VOLUME, "clockwise", 3)
            app.tick(0)
            self.port.send_message.assert_called_with([0xB2, 74, 67])
            fire.simulate_pad_press(31)
            app.tick(0)
            self.port.send_message.assert_called_with([0xB2, 71, 127])
            fire.simulate_button_press(fire.BUTTON_GRID_RIGHT)
            app.tick(0)
            fire.simulate_pad_press(0)
            app.tick(0)
            self.port.send_message.assert_called_with([0xB2, 81, 0])
            fire.simulate_button_press(fire.BUTTON_BROWSER)
            app.tick(0)
            app.tick(0.04)
            self.assertGreater(len(fire.get_canvas().text_drawn), 0)

    def test_shift_snapshot_controls_fine_steps_and_channel_after_release(self):
        fire = MockAkaiFire()
        with SynthEditorApp(fire, output=self.output) as app:
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            fire.simulate_rotary_turn(fire.ROTARY_VOLUME, "clockwise", 20)
            fire.simulate_button_press(fire.BUTTON_GRID_RIGHT)
            fire.simulate_button_release(fire.BUTTON_SHIFT)
            self.assertIsNone(app.values[74])
            self.assertEqual(self.output.channel, 3)
            app.tick(0)
            self.assertEqual(app.values[74], 65)
            self.assertEqual((app.page, self.output.channel), (0, 4))

    def test_audition_expires_without_pad_release(self):
        with patch("examples.apps.synth_editor.midi.time.monotonic", return_value=10):
            self.output.audition(60, 90)
        self.port.send_message.assert_called_with([0x92, 60, 90])
        with patch(
            "examples.apps.synth_editor.midi.time.monotonic", return_value=10.31
        ):
            self.output.update()
        self.port.send_message.assert_called_with([0x82, 60, 0])
        self.assertEqual(self.output.notes, {})

    def test_channel_change_silences_old_channel(self):
        self.output.audition(60)
        self.output.set_channel(5)
        self.port.send_message.assert_called_with([0x82, 60, 0])
        self.output.cc(74, 20)
        self.port.send_message.assert_called_with([0xB4, 74, 20])

    def test_close_releases_port_even_if_note_off_fails(self):
        self.output.audition(60)
        self.port.send_message.side_effect = RuntimeError("unplugged")
        with self.assertRaises(RuntimeError):
            self.output.close()
        self.port.close_port.assert_called()
        self.assertTrue(self.output.closed)

    def test_injected_synth_output_is_silenced_but_not_closed(self):
        with SynthEditorApp(MockAkaiFire(), output=self.output):
            self.output.audition(60)
        self.port.send_message.assert_called_with([0x82, 60, 0])
        self.assertEqual(self.output.notes, {})
        self.port.close_port.assert_not_called()
        self.assertFalse(self.output.closed)

    def test_failed_multi_note_panic_clears_bookkeeping_and_borrowed_fire(self):
        fire = MockAkaiFire()
        app = SynthEditorApp(fire, output=self.output)
        self.output.audition(60)
        self.output.audition(64)
        fire.clear_all = Mock()
        self.port.send_message.reset_mock()
        self.port.send_message.side_effect = RuntimeError("unplugged")
        with self.assertRaises(RuntimeError):
            app.shutdown()
        self.assertEqual(self.port.send_message.call_count, 2)
        self.assertEqual(self.output.notes, {})
        fire.clear_all.assert_called_once()

    def test_snapshot_roundtrip_and_atomic_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            with SynthEditorApp(
                MockAkaiFire(), output=self.output, snapshot_path=path
            ) as app:
                app._set_value(0, 100)
                app.save_snapshot()
                app._set_value(0, 10)
                app.load_snapshot()
                self.assertEqual(app.values[74], 100)
                self.port.send_message.assert_called_with([0xB2, 74, 100])
                path.write_text(
                    json.dumps(
                        {"profile": "jt4000-cc-v1", "values": {"74": 1, "71": 128}}
                    )
                )
                self.port.send_message.reset_mock()
                with self.assertRaises(ValueError):
                    app.load_snapshot()
                self.port.send_message.assert_not_called()


class ScopeContracts(unittest.TestCase):
    def test_freeze_graph_and_export(self):
        fire = MockAkaiFire()
        with MidiScopeApp(fire) as app, tempfile.TemporaryDirectory() as directory:
            fire.simulate_pad_press(9, 110)
            fire.simulate_rotary_turn(fire.ROTARY_VOLUME, "clockwise", 5)
            self.assertEqual(app.trace[-1], 69)
            fire.simulate_button_press(fire.BUTTON_PLAY)
            count = len(app.events)
            fire.simulate_pad_press(9, 100)
            self.assertEqual(len(app.events), count)
            self.assertEqual(app.counts[9], 1)
            app.on_update(1)
            self.assertEqual(app.activity[9], 1)
            path = Path(directory) / "events.csv"
            app.export_csv(path)
            with path.open() as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1][1:], ["pad", "9", "110"])
            fire.simulate_button_press(fire.BUTTON_STOP)
            self.assertEqual(len(app.events), 0)


class CircuitContracts(unittest.TestCase):
    def setUp(self):
        self.midi = MockMidiManager()
        self.patcher = patch(
            "examples.apps.circuit.core.sequencer.MidiManager", return_value=self.midi
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_app_modes_step_editor_and_settings_use_real_state(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_STEP)
            app.tick(0)
            fire.simulate_pad_press(18)  # Pitch parameter
            app.tick(0)
            fire.simulate_pad_press(36)  # Pitch C#? index 4 -> MIDI 40
            app.tick(0)
            step = app.sequencer.get_current_track().get_current_pattern().get_step(0)
            self.assertEqual(step.notes, [40])
            fire.simulate_pad_press(16)  # Velocity parameter
            app.tick(0)
            fire.simulate_pad_press(63)
            app.tick(0)
            self.assertEqual(step.velocities, [127])
            fire.simulate_pad_press(19)  # Gate length
            app.tick(0)
            fire.simulate_pad_press(63)
            app.tick(0)
            self.assertEqual(step.gate_length, 4)
            app.tick(0.04)
            self.assertEqual(
                app.step_edit_mode.get_display_info()["step_info"]["notes"], [40]
            )
            fire.simulate_button_press(fire.BUTTON_BROWSER)
            app.tick(0)
            fire.simulate_rotary_turn(fire.ROTARY_FILTER, "clockwise", 5)
            app.tick(0)
            self.assertEqual(app.sequencer.get_bpm(), 125)
            app.tick(0.04)
            fire.simulate_button_press(fire.BUTTON_DRUM)
            app.tick(0)
            app.mixer_mode._toggle_track_solo(0)
            self.assertTrue(app.sequencer.tracks[0].soloed)
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            app.tick(0)
            app.sequencer.tracks[0].get_current_pattern().set_length(31)
            fire.simulate_rotary_turn(fire.ROTARY_FILTER, "clockwise", 1)
            app.tick(0)
            pattern = app.sequencer.tracks[0].get_current_pattern()
            self.assertEqual((pattern.length, len(pattern.steps)), (32, 32))
            app.run(duration=0)
        self.assertEqual(fire.button_listeners["global"], [])

    def test_queued_pattern_gesture_uses_original_shift_and_release_cancels(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            fire.simulate_pad_press(17)
            fire.simulate_pad_press(20)
            fire.simulate_button_release(fire.BUTTON_SHIFT)
            self.assertEqual(app.mode_manager.current_mode, Mode.NOTE)
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [1, 2, 3, 4])
            self.assertEqual(app.pattern_mode.chain_starts, {})
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            fire.simulate_pad_press(16)
            fire.simulate_button_release(fire.BUTTON_SHIFT)
            app.tick(0)
            self.assertEqual(app.pattern_mode.chain_starts, {})
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [1, 2, 3, 4])

    def make_sequencer(self):
        sequencer = Sequencer()
        # Drain explicit timestamps instead of racing a real worker in unit tests.
        sequencer._scheduler = Mock()
        self.addCleanup(sequencer.cleanup)
        return sequencer

    def test_settings_select_press_edits_and_confirms_value(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_BROWSER)
            app.tick(0)
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 3)
            app.tick(0)
            self.assertEqual(app.sequencer.get_bpm(), 123)
            self.assertEqual(app.settings_mode.selected_item, 0)
            app.tick(0.04)
            labels = [text for text, _, _ in app.canvas.text_drawn]
            self.assertIn("Edit: BPM", labels)
            self.assertIn("Press SELECT: done", labels)
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 2)
            app.tick(0)
            self.assertEqual(app.settings_mode.selected_item, 2)
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "counterclockwise", 1)
            app.tick(0)
            self.assertEqual(app.settings_mode.selected_item, 1)
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 1)
            app.tick(0)
            self.assertAlmostEqual(app.sequencer.get_swing(), 0.05)
            fire.simulate_button_press(fire.BUTTON_BROWSER)
            app.tick(0)
            self.assertFalse(app.settings_mode.editing_value)

    def test_pattern_rows_select_and_chain_their_own_tracks(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            app.tick(0)
            app.on_start()
            for row in range(4):
                fire.simulate_pad_press(row * 16 + 3, 100)
                app.tick(0)
                self.assertEqual(app.sequencer.current_track, row)
                self.assertEqual(fire.track_leds[row + 1], 2)
                self.assertEqual(app.sequencer.tracks[row].current_pattern, 3)
                self.assertEqual(app.sequencer.tracks[row].pattern_chain, [])
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            app.tick(0)
            fire.simulate_pad_press(17, 100)  # Track 2, pattern 2.
            app.tick(0)
            app.tick(0.04)
            self.assertIn("T2 P2>tap end", [t for t, _, _ in app.canvas.text_drawn])
            fire.simulate_pad_press(20, 100)  # Track 2, pattern 5.
            app.tick(0)
            fire.simulate_button_release(fire.BUTTON_SHIFT)
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [1, 2, 3, 4])
            self.assertEqual(app.sequencer.tracks[1].current_pattern, 1)
            self.assertEqual(app.sequencer.tracks[2].pattern_chain, [])
            fire.simulate_pad_press(34, 100)  # Track 3 must not alter track 2.
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [1, 2, 3, 4])
            fire.simulate_pad_press(22, 100)  # A normal tap replaces that row's chain.
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [])
            self.assertEqual(app.sequencer.tracks[1].current_pattern, 6)

    def test_unfinished_pattern_chain_cancels_on_shift_release_or_mode_exit(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            for cancel in (fire.BUTTON_SHIFT, fire.BUTTON_NOTE):
                fire.simulate_button_press(fire.BUTTON_PERFORM)
                app.tick(0)
                fire.simulate_button_press(fire.BUTTON_SHIFT)
                app.tick(0)
                fire.simulate_pad_press(48, 100)
                app.tick(0)
                if cancel == fire.BUTTON_SHIFT:
                    fire.simulate_button_release(cancel)
                    app.tick(0)
                else:
                    fire.simulate_button_press(cancel)
                    app.tick(0)
                    fire.simulate_button_release(fire.BUTTON_SHIFT)
                    app.tick(0)
                fire.simulate_button_press(fire.BUTTON_PERFORM)
                app.tick(0)
                fire.simulate_button_press(fire.BUTTON_SHIFT)
                app.tick(0)
                fire.simulate_pad_press(55, 100)
                app.tick(0)
                self.assertTrue(
                    all(not track.pattern_chain for track in app.sequencer.tracks)
                )
                fire.simulate_button_release(fire.BUTTON_SHIFT)
                app.tick(0)

    def test_pattern_endpoints_are_independent_and_allow_reverse_order(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            app.tick(0)
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            app.tick(0)
            fire.simulate_pad_press(5, 100)
            app.tick(0)
            fire.simulate_pad_press(17, 100)
            app.tick(0)
            self.assertEqual(app.pattern_mode.chain_starts, {0: 5, 1: 1})
            fire.simulate_pad_press(2, 100)
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[0].pattern_chain, [2, 3, 4, 5])
            self.assertEqual(app.pattern_mode.chain_starts, {1: 1})
            fire.simulate_pad_press(19, 100)
            app.tick(0)
            self.assertEqual(app.sequencer.tracks[1].pattern_chain, [1, 2, 3])
            fire.simulate_pad_press(15, 100)  # Unused right half cannot start a chain.
            app.tick(0)
            self.assertEqual(app.pattern_mode.chain_starts, {})

    def test_replacing_chain_restarts_its_playback_position(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            seq = app.sequencer
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            app.tick(0)
            seq.pattern_chain_positions[0] = 5
            seq.pattern_chain_step_counts[0] = 11
            seq.track_step_positions[0] = 12
            fire.simulate_button_press(fire.BUTTON_SHIFT)
            app.tick(0)
            fire.simulate_pad_press(0, 100)
            app.tick(0)
            fire.simulate_pad_press(1, 100)
            app.tick(0)
            fire.simulate_button_release(fire.BUTTON_SHIFT)
            app.tick(0)
            self.assertIs(
                seq._get_current_pattern_for_track(0, 0), seq.tracks[0].patterns[0]
            )
            self.assertEqual(seq.pattern_chain_positions[0], 0)
            self.assertEqual(seq.pattern_chain_step_counts[0], 0)
            self.assertEqual(seq.track_step_positions[0], 0)
            seq.pattern_chain_step_counts[0] = 8
            fire.simulate_pad_press(3, 100)
            app.tick(0)
            self.assertEqual(seq.pattern_chain_step_counts[0], 0)

    def test_settings_select_runs_save_action_without_entering_edit_mode(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app, tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            app.settings_mode.settings_path = str(path)
            fire.simulate_button_press(fire.BUTTON_BROWSER)
            app.tick(0)
            index = next(
                i
                for i, item in enumerate(app.settings_mode.menu_items)
                if item["name"] == "Save Settings"
            )
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", index)
            app.tick(0)
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["bpm"], 120)
            self.assertFalse(app.settings_mode.editing_value)

    def test_select_launches_scene_and_keeps_pending_marker_until_applied(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_PERFORM)
            app.tick(0)
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 1)
            app.tick(0)
            app.tick(0.04)
            self.assertIn("Scene 2?", [t for t, _, _ in app.canvas.text_drawn])
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            self.assertEqual(app.sequencer.current_scene, 1)
            app.tick(0.04)
            self.assertIn("Scene 2", [t for t, _, _ in app.canvas.text_drawn])
            # Drive a playing transition without starting the real clock thread.
            app.sequencer.transport_state = CircuitState.PLAYING
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 1)
            app.tick(0)
            fire.simulate_button_press(fire.BUTTON_SELECT)
            app.tick(0)
            self.assertEqual(app.sequencer.queued_scene, 2)
            app.tick(0.04)
            self.assertIn("S3 Q3", [t for t, _, _ in app.canvas.text_drawn])
            fire.simulate_rotary_turn(fire.ROTARY_SELECT, "clockwise", 1)
            app.tick(0)
            app.tick(0.04)
            self.assertIn("S4 Q3", [t for t, _, _ in app.canvas.text_drawn])
            app.sequencer._process_queued_changes()
            app.tick(0.04)
            self.assertEqual(app.sequencer.current_scene, 2)
            self.assertIn("Scene 4?", [t for t, _, _ in app.canvas.text_drawn])

    def test_mixer_mute_pad_updates_status_oled_and_pad_color(self):
        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            fire.simulate_button_press(fire.BUTTON_DRUM)
            app.tick(0)
            app.tick(0.04)
            normal = fire.pad_colors[16]
            other_tracks = list(fire.pad_colors[17:20])
            for muted, marker in ((True, "-"), (False, "+")):
                fire.simulate_pad_press(16, 100)
                app.tick(0)
                app.tick(0.04)
                self.assertEqual(app.sequencer.tracks[0].muted, muted)
                self.assertEqual(
                    app.sequencer.get_status()["tracks"][0]["muted"], muted
                )
                labels = [text for text, _, _ in app.canvas.text_drawn]
                self.assertIn(f"{marker}1 Drums", labels)
                self.assertEqual(
                    fire.pad_colors[16],
                    app.grid_manager.STATE_COLORS["muted"] if muted else normal,
                )
                self.assertEqual(fire.pad_colors[17:20], other_tracks)

    def test_scheduled_gate_and_stop_cancel_delayed_note(self):
        seq = self.make_sequencer()
        with patch(
            "examples.apps.circuit.core.sequencer.time.monotonic", return_value=0
        ):
            seq._schedule_note((1, 60), 100, 10, 0.02)
        seq._process_due_events(10)
        self.assertEqual(len(self.midi.get_notes_on()), 1)
        seq._process_due_events(10.03)
        self.assertEqual(len(self.midi.get_notes_off()), 1)
        with patch(
            "examples.apps.circuit.core.sequencer.time.monotonic", return_value=0
        ):
            seq._schedule_note((1, 62), 100, 20, 1)
        seq.stop()
        count = len(self.midi.get_notes_on())
        seq._process_due_events(30)
        self.assertEqual(len(self.midi.get_notes_on()), count)

    def test_retrigger_ignores_old_note_off(self):
        seq = self.make_sequencer()
        with patch(
            "examples.apps.circuit.core.sequencer.time.monotonic", return_value=0
        ):
            seq._schedule_note((1, 60), 100, 10, 1)
            seq._process_due_events(10)
            seq._schedule_note((1, 60), 100, 10.5, 2)
            seq._process_due_events(10.5)
        offs = len(self.midi.get_notes_off())
        seq._process_due_events(11.1)
        self.assertEqual(len(self.midi.get_notes_off()), offs)
        seq._process_due_events(13)
        self.assertEqual(len(self.midi.get_notes_off()), offs + 1)

    def test_solo_only_schedules_soloed_track(self):
        seq = self.make_sequencer()
        for track in seq.tracks:
            track.get_current_pattern().get_step(0).add_note(60)
        seq.tracks[1].soloed = True
        seq.transport_state = CircuitState.PLAYING
        seq._on_step(0)
        self.assertEqual(
            [msg.channel for msg in self.midi.messages if msg.type == "note_on"], [1]
        )

    def test_solo_silences_an_existing_tied_note(self):
        seq = self.make_sequencer()
        step = seq.tracks[0].get_current_pattern().get_step(0)
        step.add_note(60)
        step.tie_forward = True
        seq.transport_state = CircuitState.PLAYING
        seq._on_step(0)
        self.assertIn((10, 60), seq.active_notes)
        seq.set_track_soloed(1, True)
        self.assertNotIn((10, 60), seq.active_notes)
        self.assertEqual(self.midi.get_notes_off(10), [60])
        seq._process_due_events(float("inf"))
        self.assertEqual(len(self.midi.get_notes_on()), 1)

    def test_tie_ends_at_empty_following_step(self):
        seq = self.make_sequencer()
        step = seq.tracks[0].get_current_pattern().get_step(0)
        step.add_note(60)
        step.tie_forward = True
        seq.transport_state = CircuitState.PLAYING
        seq._on_step(0)
        seq._on_step(1)
        self.assertEqual(self.midi.get_notes_off(10), [60])
        self.assertEqual(seq.tied_notes, {})

    def test_probability_rejection_ends_carried_tie(self):
        seq = self.make_sequencer()
        pattern = seq.tracks[0].get_current_pattern()
        for index in (0, 1):
            pattern.get_step(index).add_note(60)
        pattern.get_step(0).tie_forward = True
        pattern.get_step(1).probability = 0
        seq.transport_state = CircuitState.PLAYING
        seq._on_step(0)
        with patch("random.random", return_value=0):
            seq._on_step(1)
        self.assertEqual(self.midi.get_notes_off(10), [60])
        self.assertEqual(seq.tied_notes, {})

    def test_muted_track_advances_silently(self):
        seq = self.make_sequencer()
        pattern = seq.tracks[0].get_current_pattern()
        pattern.get_step(0).add_note(60)
        pattern.get_step(1).add_note(61)
        seq.set_track_muted(0, True)
        seq.transport_state = CircuitState.PLAYING
        seq._on_step(0)
        self.assertEqual(self.midi.get_notes_on(), [])
        self.assertEqual(seq.track_step_positions[0], 1)
        seq.set_track_muted(0, False)
        seq._on_step(1)
        self.assertEqual(self.midi.get_notes_on(10), [(61, 85)])

    def test_pattern_shrink_clamps_playback_range(self):
        seq = self.make_sequencer()
        pattern = seq.tracks[0].get_current_pattern()
        pattern.start_point = pattern.end_point = 15
        pattern.set_length(8)
        self.assertEqual((pattern.start_point, pattern.end_point), (7, 7))
        self.assertEqual(pattern.get_playback_length(), 1)

    def test_full_gate_uses_swung_step_duration(self):
        seq = self.make_sequencer()
        seq.set_swing(0.5)
        track = seq.tracks[0]
        pattern = track.get_current_pattern()
        step = pattern.get_step(1)
        step.add_note(60)
        with patch(
            "examples.apps.circuit.core.sequencer.time.monotonic", return_value=10
        ):
            seq._play_step(track, 0, step, pattern, 1)
        self.assertAlmostEqual(
            seq.scheduled_notes[0][0], 10 + seq.timing.get_step_duration(1)
        )

    def test_input_records_selected_recording_track(self):
        seq = self.make_sequencer()
        seq.transport_state = CircuitState.RECORDING
        seq.recording_track = 2
        self.midi.input_callback(MidiMessage(3, [0x92, 64, 100], 0, 64, 100))
        self.assertEqual(seq.tracks[2].get_current_pattern().get_step(0).notes, [64])

    def test_clock_keeps_advancing_after_four_bars(self):
        timing = TimingEngine(120)
        timing.is_playing = True
        timing.start_time = 0
        with patch(
            "examples.apps.circuit.core.timing.time.monotonic", return_value=8.3
        ):
            step, _ = timing.get_current_step_info()
        self.assertEqual(step, 2)

    def test_note_entry_demo_records_content_and_stops(self):
        from examples.apps.circuit.demo_e2e import DemoRunner

        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            demo = DemoRunner()
            demo.fire, demo.app = fire, app
            demo.wait = Mock(side_effect=lambda seconds: app.tick(0))
            demo.demo_note_entry()
            self.assertTrue(app.sequencer.tracks[0].has_content())
            self.assertEqual(app.sequencer.transport_state, CircuitState.STOPPED)

    def test_demo_dispatch_reaches_framework_global_handlers(self):
        from examples.apps.circuit.demo_e2e import DemoRunner

        fire = MockAkaiFire()
        with CircuitSequencer(fire) as app:
            demo = DemoRunner()
            demo.fire, demo.app = fire, app
            demo.wait = Mock(side_effect=lambda seconds: app.tick(0))
            demo.simulate_button_press(fire.BUTTON_DRUM)
            self.assertEqual(app.mode_manager.current_mode, Mode.MIXER)
            demo.simulate_button_press(fire.BUTTON_NOTE)
            demo.simulate_encoder_turn(fire.ROTARY_VOLUME, "clockwise", 2)
            self.assertEqual(app.sequencer.get_bpm(), 121)


if __name__ == "__main__":
    unittest.main()
