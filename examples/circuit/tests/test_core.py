"""
Tests for Circuit Sequencer Core Components

Tests cover:
- Pattern: Step manipulation, note storage, serialization
- Track: MIDI routing, pattern management, state
- Sequencer: Playback, recording, transport control
- Timing: BPM, step timing, quantization
- Scales: Note mapping, scale generation

This module demonstrates how to use the akai_fire_testing utilities
for core component testing.
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
circuit_dir = os.path.dirname(current_dir)
examples_dir = os.path.dirname(circuit_dir)
project_root = os.path.dirname(examples_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, circuit_dir)

# Import testing utilities from the new module
from akai_fire_testing import (
    # Core mocks
    MockMidiManager,
    ControllableTimingEngine,
    # Factory functions
    create_test_midi,
    create_test_timing,
    create_step_recorder,
)


class TestPattern(unittest.TestCase):
    """Tests for the Pattern class."""

    def setUp(self):
        from core.pattern import Pattern

        self.pattern = Pattern(name="Test Pattern")

    def test_default_length_is_16(self):
        """Pattern should default to 16 steps."""
        self.assertEqual(self.pattern.length, 16)

    def test_get_step_returns_step_object(self):
        """get_step should return a Step object."""
        from core.pattern import Step

        step = self.pattern.get_step(0)
        self.assertIsInstance(step, Step)

    def test_step_starts_empty(self):
        """New steps should have no notes."""
        step = self.pattern.get_step(0)
        self.assertFalse(step.has_notes())

    def test_add_note_to_step(self):
        """Should be able to add notes to a step."""
        step = self.pattern.get_step(0)
        step.add_note(60, 100)  # C4, velocity 100

        self.assertTrue(step.has_notes())
        notes = step.get_notes_with_velocities()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0], (60, 100))

    def test_polyphonic_step(self):
        """Steps should support multiple notes."""
        step = self.pattern.get_step(0)
        step.add_note(60, 100)  # C4
        step.add_note(64, 80)  # E4
        step.add_note(67, 90)  # G4

        notes = step.get_notes_with_velocities()
        self.assertEqual(len(notes), 3)

    def test_clear_step(self):
        """Should be able to clear a step."""
        step = self.pattern.get_step(0)
        step.add_note(60, 100)
        step.clear_notes()

        self.assertFalse(step.has_notes())

    def test_clear_all_steps(self):
        """Should be able to clear entire pattern."""
        self.pattern.get_step(0).add_note(60, 100)
        self.pattern.get_step(4).add_note(64, 100)
        self.pattern.get_step(8).add_note(67, 100)

        self.pattern.clear_all_steps()

        for i in range(self.pattern.length):
            self.assertFalse(self.pattern.get_step(i).has_notes())

    def test_has_content(self):
        """has_content should reflect if any steps have notes."""
        self.assertFalse(self.pattern.has_content())

        self.pattern.get_step(5).add_note(60, 100)
        self.assertTrue(self.pattern.has_content())

    def test_get_active_steps(self):
        """get_active_steps should return indices of non-empty steps."""
        self.pattern.get_step(0).add_note(60, 100)
        self.pattern.get_step(4).add_note(64, 100)
        self.pattern.get_step(8).add_note(67, 100)

        active = self.pattern.get_active_steps()
        self.assertEqual(active, [0, 4, 8])

    def test_step_velocity(self):
        """Step should track velocity for each note."""
        step = self.pattern.get_step(0)
        step.add_note(60, 127)
        step.add_note(64, 50)

        notes = step.get_notes_with_velocities()
        self.assertIn((60, 127), notes)
        self.assertIn((64, 50), notes)

    def test_step_gate_length(self):
        """Step should have configurable gate length."""
        step = self.pattern.get_step(0)
        self.assertEqual(step.gate_length, 1.0)  # Default (1 step duration)

        step.gate_length = 0.5
        self.assertEqual(step.gate_length, 0.5)

    def test_step_probability(self):
        """Step should have configurable probability."""
        step = self.pattern.get_step(0)
        self.assertEqual(step.probability, 1.0)  # Default

        step.probability = 0.5
        self.assertEqual(step.probability, 0.5)

    def test_step_micro_timing(self):
        """Step should have configurable micro-timing offset."""
        step = self.pattern.get_step(0)
        self.assertEqual(step.micro_timing, 0)  # Default

        step.micro_timing = 3
        self.assertEqual(step.micro_timing, 3)

    def test_pattern_serialization(self):
        """Pattern should serialize to and from dict."""
        self.pattern.get_step(0).add_note(60, 100)
        self.pattern.get_step(4).add_note(64, 80)

        data = self.pattern.to_dict()

        from core.pattern import Pattern

        restored = Pattern.from_dict(data)

        self.assertEqual(restored.name, self.pattern.name)
        self.assertEqual(restored.length, self.pattern.length)
        self.assertTrue(restored.get_step(0).has_notes())
        self.assertTrue(restored.get_step(4).has_notes())

    def test_start_point_default(self):
        """Pattern should default start_point to 0."""
        self.assertEqual(self.pattern.start_point, 0)

    def test_end_point_default(self):
        """Pattern should default end_point to None (meaning length-1)."""
        self.assertIsNone(self.pattern.end_point)

    def test_effective_end_point_when_none(self):
        """get_effective_end_point should return length-1 when end_point is None."""
        self.assertEqual(self.pattern.get_effective_end_point(), 15)

    def test_effective_end_point_when_set(self):
        """get_effective_end_point should return end_point when set."""
        self.pattern.end_point = 7
        self.assertEqual(self.pattern.get_effective_end_point(), 7)

    def test_playback_length(self):
        """get_playback_length should return end - start + 1."""
        self.assertEqual(self.pattern.get_playback_length(), 16)

        self.pattern.start_point = 4
        self.pattern.end_point = 11
        self.assertEqual(self.pattern.get_playback_length(), 8)

    def test_play_order_default_forward(self):
        """Pattern should default to FORWARD play order."""
        from core.pattern import PlayOrder

        self.assertEqual(self.pattern.play_order, PlayOrder.FORWARD)

    def test_get_next_step_forward(self):
        """FORWARD play order should increment step."""
        from core.pattern import PlayOrder

        self.pattern.play_order = PlayOrder.FORWARD

        self.assertEqual(self.pattern.get_next_step(0), 1)
        self.assertEqual(self.pattern.get_next_step(14), 15)
        self.assertEqual(self.pattern.get_next_step(15), 0)  # Wrap

    def test_get_next_step_reverse(self):
        """REVERSE play order should decrement step."""
        from core.pattern import PlayOrder

        self.pattern.play_order = PlayOrder.REVERSE

        self.assertEqual(self.pattern.get_next_step(15), 14)
        self.assertEqual(self.pattern.get_next_step(1), 0)
        self.assertEqual(self.pattern.get_next_step(0), 15)  # Wrap

    def test_get_next_step_with_start_end(self):
        """Play order should respect start/end points."""
        from core.pattern import PlayOrder

        self.pattern.start_point = 4
        self.pattern.end_point = 8
        self.pattern.play_order = PlayOrder.FORWARD

        self.assertEqual(self.pattern.get_next_step(4), 5)
        self.assertEqual(self.pattern.get_next_step(8), 4)  # Wrap to start

    def test_get_first_step_forward(self):
        """FORWARD should start at start_point."""
        self.pattern.start_point = 3
        self.assertEqual(self.pattern.get_first_step(), 3)

    def test_get_first_step_reverse(self):
        """REVERSE should start at end_point."""
        from core.pattern import PlayOrder

        self.pattern.play_order = PlayOrder.REVERSE
        self.pattern.end_point = 10
        self.assertEqual(self.pattern.get_first_step(), 10)

    def test_sync_rate_default(self):
        """Pattern should default to SIXTEENTH sync rate."""
        from core.pattern import SyncRate

        self.assertEqual(self.pattern.sync_rate, SyncRate.SIXTEENTH)

    def test_sync_rate_multiplier(self):
        """SyncRate should return correct multiplier."""
        from core.pattern import SyncRate

        self.assertEqual(SyncRate.SIXTEENTH.get_multiplier(), 1.0)
        self.assertEqual(SyncRate.EIGHTH.get_multiplier(), 2.0)
        self.assertEqual(SyncRate.QUARTER.get_multiplier(), 4.0)
        self.assertEqual(SyncRate.THIRTY_SECOND.get_multiplier(), 0.5)

    def test_mutate_shuffles_steps(self):
        """mutate should shuffle step positions."""
        # Add notes to specific steps
        for i in [0, 4, 8, 12]:
            self.pattern.get_step(i).add_note(60 + i, 100)

        original_active = self.pattern.get_active_steps()

        # Mutate (may or may not change order due to randomness)
        self.pattern.mutate()

        # Should still have same number of active steps
        new_active = self.pattern.get_active_steps()
        self.assertEqual(len(new_active), len(original_active))

    def test_mutate_preserves_note_data(self):
        """mutate should preserve notes, just at different positions."""
        self.pattern.get_step(0).add_note(60, 100)
        self.pattern.get_step(4).add_note(64, 80)
        self.pattern.get_step(8).add_note(67, 90)

        # Get all notes before mutate
        notes_before = set()
        for i in range(16):
            step = self.pattern.get_step(i)
            for note, vel in step.get_notes_with_velocities():
                notes_before.add((note, vel))

        self.pattern.mutate()

        # Get all notes after mutate
        notes_after = set()
        for i in range(16):
            step = self.pattern.get_step(i)
            for note, vel in step.get_notes_with_velocities():
                notes_after.add((note, vel))

        # Same notes should exist
        self.assertEqual(notes_before, notes_after)

    def test_tie_forward_default(self):
        """Step should default tie_forward to False."""
        step = self.pattern.get_step(0)
        self.assertFalse(step.tie_forward)

    def test_serialization_includes_new_fields(self):
        """Serialization should include end_point and sync_rate."""
        from core.pattern import Pattern, SyncRate, PlayOrder

        self.pattern.start_point = 2
        self.pattern.end_point = 10
        self.pattern.sync_rate = SyncRate.EIGHTH
        self.pattern.play_order = PlayOrder.REVERSE
        self.pattern.get_step(2).tie_forward = True

        data = self.pattern.to_dict()

        self.assertEqual(data["start_point"], 2)
        self.assertEqual(data["end_point"], 10)
        self.assertEqual(data["sync_rate"], "1/8")
        self.assertEqual(data["play_order"], "reverse")
        self.assertTrue(data["steps"][2]["tie_forward"])

        # Test deserialization
        restored = Pattern.from_dict(data)
        self.assertEqual(restored.start_point, 2)
        self.assertEqual(restored.end_point, 10)
        self.assertEqual(restored.sync_rate, SyncRate.EIGHTH)
        self.assertEqual(restored.play_order, PlayOrder.REVERSE)
        self.assertTrue(restored.get_step(2).tie_forward)


class TestTrack(unittest.TestCase):
    """Tests for the Track class."""

    def setUp(self):
        from core.track import Track

        self.track = Track(name="Test Track", color=(127, 0, 0), midi_channel=1)

    def test_track_has_8_patterns(self):
        """Track should have 8 pattern slots."""
        self.assertEqual(len(self.track.patterns), 8)

    def test_default_pattern_is_zero(self):
        """Current pattern should default to 0."""
        self.assertEqual(self.track.current_pattern, 0)

    def test_set_current_pattern(self):
        """Should be able to change current pattern."""
        self.track.set_current_pattern(3)
        self.assertEqual(self.track.current_pattern, 3)

    def test_set_current_pattern_validates_range(self):
        """Should reject invalid pattern indices."""
        self.track.set_current_pattern(10)
        self.assertEqual(self.track.current_pattern, 0)  # Unchanged

    def test_get_current_pattern(self):
        """Should return current pattern object."""
        from core.pattern import Pattern

        pattern = self.track.get_current_pattern()
        self.assertIsInstance(pattern, Pattern)

    def test_midi_channel_assignment(self):
        """Track should store MIDI channel."""
        self.assertEqual(self.track.midi_channel, 1)
        self.track.midi_channel = 10
        self.assertEqual(self.track.midi_channel, 10)

    def test_track_enabled_state(self):
        """Track should track enabled/disabled state."""
        self.assertTrue(self.track.enabled)
        self.track.enabled = False
        self.assertFalse(self.track.enabled)

    def test_track_solo_state(self):
        """Track should track solo state."""
        self.assertFalse(self.track.soloed)
        self.track.soloed = True
        self.assertTrue(self.track.soloed)

    def test_has_content(self):
        """has_content should check all patterns."""
        self.assertFalse(self.track.has_content())

        self.track.patterns[3].get_step(0).add_note(60, 100)
        self.assertTrue(self.track.has_content())

    def test_pattern_chain(self):
        """Should support pattern chaining."""
        self.track.set_pattern_chain([0, 1, 2, 3])
        self.assertTrue(self.track.is_pattern_chained())
        self.assertEqual(len(self.track.pattern_chain), 4)

    def test_pattern_chain_must_be_consecutive(self):
        """Pattern chain should enforce consecutive patterns."""
        self.track.set_pattern_chain([0, 2, 4])  # Not consecutive
        # Should only keep first pattern
        self.assertEqual(len(self.track.pattern_chain), 1)

    def test_clear_pattern(self):
        """Should be able to clear a specific pattern."""
        self.track.patterns[2].get_step(0).add_note(60, 100)
        self.track.clear_pattern(2)
        self.assertFalse(self.track.patterns[2].has_content())

    def test_copy_pattern(self):
        """Should be able to copy patterns."""
        self.track.patterns[0].get_step(0).add_note(60, 100)
        self.track.copy_pattern(0, 1)

        self.assertTrue(self.track.patterns[1].get_step(0).has_notes())

    def test_scale_setting(self):
        """Track should store scale setting."""
        self.assertEqual(self.track.scale, "MAJOR")
        self.track.scale = "DORIAN"
        self.assertEqual(self.track.scale, "DORIAN")

    def test_root_note_setting(self):
        """Track should store root note."""
        self.assertEqual(self.track.root_note, 60)  # C4
        self.track.root_note = 64  # E4
        self.assertEqual(self.track.root_note, 64)

    def test_octave_offset(self):
        """Track should support octave offset."""
        self.assertEqual(self.track.octave, 0)
        self.track.octave = 2
        self.assertEqual(self.track.get_root_note_in_octave(), 84)  # C6

    def test_note_range_constraint(self):
        """Track should constrain notes to range."""
        self.track.note_range = (36, 84)  # C2 to C6

        self.assertEqual(self.track.constrain_note_to_range(30), 36)
        self.assertEqual(self.track.constrain_note_to_range(60), 60)
        self.assertEqual(self.track.constrain_note_to_range(90), 84)

    def test_cc_assignments(self):
        """Track should store CC assignments."""
        self.assertEqual(self.track.get_cc_value("volume"), 7)
        self.track.set_cc_assignment("custom", 74)
        self.assertEqual(self.track.get_cc_value("custom"), 74)

    def test_track_serialization(self):
        """Track should serialize to and from dict."""
        self.track.patterns[0].get_step(0).add_note(60, 100)
        self.track.midi_channel = 5
        self.track.scale = "MINOR"

        data = self.track.to_dict()

        from core.track import Track

        restored = Track.from_dict(data)

        self.assertEqual(restored.name, self.track.name)
        self.assertEqual(restored.midi_channel, 5)
        self.assertEqual(restored.scale, "MINOR")
        self.assertTrue(restored.patterns[0].get_step(0).has_notes())


class TestSequencer(unittest.TestCase):
    """Tests for the Sequencer class."""

    def setUp(self):
        # Use factory function for cleaner setup
        self.mock_midi = create_test_midi()

        # Patch the MidiManager to avoid actual MIDI operations
        self.midi_patcher = patch("core.sequencer.MidiManager")
        self.mock_midi_class = self.midi_patcher.start()
        self.mock_midi_class.return_value = self.mock_midi

        from core.sequencer import Sequencer

        self.sequencer = Sequencer()

    def tearDown(self):
        self.midi_patcher.stop()

    def test_sequencer_has_4_tracks(self):
        """Sequencer should have 4 tracks."""
        self.assertEqual(len(self.sequencer.tracks), 4)

    def test_default_track_colors(self):
        """Tracks should have Circuit-style colors."""
        colors = [t.color for t in self.sequencer.tracks]
        self.assertEqual(colors[0], (255, 0, 0))  # Red
        self.assertEqual(colors[1], (0, 255, 0))  # Green
        self.assertEqual(colors[2], (0, 0, 255))  # Blue
        self.assertEqual(colors[3], (255, 255, 0))  # Yellow

    def test_default_midi_channels(self):
        """Tracks should have default MIDI channels."""
        channels = [t.midi_channel for t in self.sequencer.tracks]
        self.assertEqual(channels, [10, 1, 2, 3])  # Drums on 10, others 1-3

    def test_transport_starts_stopped(self):
        """Transport should start in stopped state."""
        from core.sequencer import TransportState

        self.assertEqual(self.sequencer.transport_state, TransportState.STOPPED)

    def test_play_starts_playback(self):
        """play() should start playback."""
        from core.sequencer import TransportState

        self.sequencer.play()
        self.assertEqual(self.sequencer.transport_state, TransportState.PLAYING)

    def test_stop_stops_playback(self):
        """stop() should stop playback."""
        from core.sequencer import TransportState

        self.sequencer.play()
        self.sequencer.stop()
        self.assertEqual(self.sequencer.transport_state, TransportState.STOPPED)

    def test_record_starts_recording(self):
        """record() should start recording."""
        from core.sequencer import TransportState

        self.sequencer.record()
        self.assertEqual(self.sequencer.transport_state, TransportState.RECORDING)

    def test_stop_sends_all_notes_off(self):
        """stop() should send all notes off."""
        self.sequencer.play()
        self.sequencer.stop()

        # Use MockMidiManager's query method
        all_notes_off_msgs = self.mock_midi.get_messages_by_type("all_notes_off")
        self.assertGreater(len(all_notes_off_msgs), 0)

    def test_set_bpm(self):
        """Should be able to set BPM."""
        self.sequencer.set_bpm(140.0)
        self.assertEqual(self.sequencer.get_bpm(), 140.0)

    def test_bpm_clamped(self):
        """BPM should be clamped to valid range."""
        self.sequencer.set_bpm(10.0)  # Too low
        self.assertGreaterEqual(self.sequencer.get_bpm(), 30.0)

        self.sequencer.set_bpm(500.0)  # Too high
        self.assertLessEqual(self.sequencer.get_bpm(), 300.0)

    def test_set_swing(self):
        """Should be able to set swing."""
        self.sequencer.set_swing(0.25)
        self.assertEqual(self.sequencer.get_swing(), 0.25)

    def test_current_track_selection(self):
        """Should track currently selected track."""
        self.assertEqual(self.sequencer.current_track, 0)
        self.sequencer.set_current_track(2)
        self.assertEqual(self.sequencer.current_track, 2)

    def test_get_status_returns_dict(self):
        """get_status should return comprehensive state."""
        status = self.sequencer.get_status()

        self.assertIn("transport_state", status)
        self.assertIn("current_track", status)
        self.assertIn("tracks", status)
        self.assertIn("timing", status)

    def test_step_callback_registration(self):
        """Should be able to register step callbacks using create_step_recorder."""
        # Use the step recorder utility
        callback, steps_received = create_step_recorder()

        self.sequencer.add_step_callback(callback)
        self.assertIn(callback, self.sequencer.step_callbacks)

    def test_transport_callback_registration(self):
        """Should be able to register transport callbacks."""
        callback_called = []

        def on_transport(state):
            callback_called.append(state)

        self.sequencer.add_transport_callback(on_transport)
        self.sequencer.play()

        from core.sequencer import TransportState

        self.assertIn(TransportState.PLAYING, callback_called)

    def test_16_scenes(self):
        """Sequencer should have 16 scenes."""
        self.assertEqual(len(self.sequencer.scenes), 16)

    def test_cleanup(self):
        """cleanup() should stop playback and cleanup MIDI."""
        self.sequencer.play()
        self.sequencer.cleanup()

        from core.sequencer import TransportState

        self.assertEqual(self.sequencer.transport_state, TransportState.STOPPED)


class TestScales(unittest.TestCase):
    """Tests for the scales module."""

    def test_major_scale_intervals(self):
        """Major scale should have correct intervals."""
        from core.scales import SCALES

        self.assertEqual(SCALES["MAJOR"], [0, 2, 4, 5, 7, 9, 11])

    def test_minor_scale_intervals(self):
        """Natural minor should have correct intervals."""
        from core.scales import SCALES

        self.assertEqual(SCALES["NATURAL_MINOR"], [0, 2, 3, 5, 7, 8, 10])

    def test_get_scale_notes(self):
        """get_scale_notes should return correct MIDI notes."""
        from core.scales import get_scale_notes

        # C Major starting at C4 (60)
        notes = get_scale_notes("MAJOR", 60, octaves=1)
        expected = [60, 62, 64, 65, 67, 69, 71]
        self.assertEqual(notes, expected)

    def test_get_scale_notes_multiple_octaves(self):
        """get_scale_notes should span multiple octaves."""
        from core.scales import get_scale_notes

        notes = get_scale_notes("MAJOR", 60, octaves=2)
        # Should have 14 notes (7 per octave)
        self.assertEqual(len(notes), 14)
        self.assertEqual(notes[7], 72)  # C5

    def test_is_root_note(self):
        """is_root_note should identify root notes."""
        from core.scales import is_root_note

        self.assertTrue(is_root_note(60, 60))  # C4 is root of C
        self.assertTrue(is_root_note(72, 60))  # C5 is also root of C
        self.assertFalse(is_root_note(62, 60))  # D is not root of C

    def test_get_note_name(self):
        """get_note_name should return correct names."""
        from core.scales import get_note_name

        self.assertEqual(get_note_name(60), "C4")
        self.assertEqual(get_note_name(61), "C#4")
        self.assertEqual(get_note_name(69), "A4")

    def test_map_pad_to_note(self):
        """map_pad_to_note should map keyboard index to MIDI note."""
        from core.scales import map_pad_to_note

        # Pad 0 should be root note
        note = map_pad_to_note(0, "MAJOR", 60)
        self.assertEqual(note, 60)

    def test_chromatic_scale(self):
        """Chromatic scale should include all 12 notes."""
        from core.scales import SCALES

        self.assertEqual(len(SCALES["CHROMATIC"]), 12)


class TestTiming(unittest.TestCase):
    """Tests for the timing engine."""

    def setUp(self):
        from core.timing import TimingEngine

        self.timing = TimingEngine(bpm=120.0)

    def test_default_bpm(self):
        """Should start with specified BPM."""
        self.assertEqual(self.timing.get_bpm(), 120.0)

    def test_set_bpm(self):
        """Should be able to change BPM."""
        self.timing.set_bpm(140.0)
        self.assertEqual(self.timing.get_bpm(), 140.0)

    def test_step_duration_at_120bpm(self):
        """At 120 BPM, 16th note should be 125ms."""
        # 120 BPM = 2 beats/second
        # 16th note = 1/4 beat = 125ms
        duration = self.timing.get_step_duration(0)
        self.assertAlmostEqual(duration, 0.125, places=3)

    def test_step_duration_scales_with_bpm(self):
        """Step duration should scale inversely with BPM."""
        self.timing.set_bpm(60.0)
        duration = self.timing.get_step_duration(0)
        self.assertAlmostEqual(duration, 0.25, places=3)

    def test_swing_affects_timing(self):
        """Swing should delay even-numbered steps."""
        self.timing.set_swing(0.5)

        duration_odd = self.timing.get_step_duration(0)
        duration_even = self.timing.get_step_duration(1)

        # With swing, even steps should have different duration
        self.assertNotAlmostEqual(duration_odd, duration_even, places=3)

    def test_quantization_modes(self):
        """Should support different quantization modes."""
        from core.timing import QuantizationMode

        self.timing.set_quantization(QuantizationMode.SIXTEENTH)
        self.assertEqual(self.timing.get_quantization(), QuantizationMode.SIXTEENTH)

    def test_timing_info(self):
        """get_timing_info should return current state."""
        info = self.timing.get_timing_info()

        self.assertIn("bpm", info)
        self.assertIn("step", info)
        self.assertIn("is_playing", info)


class TestControllableTimingIntegration(unittest.TestCase):
    """Tests demonstrating ControllableTimingEngine usage."""

    def test_manual_step_advancement(self):
        """Should be able to manually advance steps."""
        # Use factory function
        timing = create_test_timing(bpm=120, auto_start=True)

        # Record steps using step recorder
        callback, steps = create_step_recorder()
        timing.add_step_callback(callback)

        # Manually advance steps
        timing.advance_steps(4)

        # Verify all steps were recorded
        self.assertEqual(steps, [0, 1, 2, 3])

    def test_step_wrapping(self):
        """Steps should wrap at total_steps."""
        timing = create_test_timing(bpm=120, steps=16, auto_start=True)
        callback, steps = create_step_recorder()
        timing.add_step_callback(callback)

        # Advance past the end
        timing.advance_steps(18)

        # Should have wrapped
        self.assertEqual(steps[-2:], [0, 1])

    def test_no_callbacks_when_stopped(self):
        """Callbacks shouldn't fire when not playing."""
        timing = create_test_timing(bpm=120, auto_start=False)
        callback, steps = create_step_recorder()
        timing.add_step_callback(callback)

        timing.advance_steps(4)

        # No steps should be recorded
        self.assertEqual(steps, [])


class TestScene(unittest.TestCase):
    """Tests for the Scene class."""

    def setUp(self):
        from core.scene import Scene

        self.scene = Scene(name="Test Scene")

    def test_default_scene_is_empty(self):
        """New scene should have no assignments."""
        self.assertFalse(self.scene.has_content())

    def test_set_pattern_for_track(self):
        """Should be able to set pattern assignments."""
        self.scene.set_pattern_for_track(0, 3)
        self.assertEqual(self.scene.get_pattern_for_track(0), 3)

    def test_pattern_assignment_validates_range(self):
        """Should reject invalid track/pattern indices."""
        self.scene.set_pattern_for_track(5, 0)  # Invalid track
        self.scene.set_pattern_for_track(0, 10)  # Invalid pattern

        # Neither should be stored
        self.assertFalse(self.scene.has_content())

    def test_set_track_enabled(self):
        """Should track enabled state per track."""
        self.scene.set_track_enabled(0, False)
        self.assertFalse(self.scene.is_track_enabled(0))

    def test_default_track_enabled(self):
        """Tracks should default to enabled."""
        self.assertTrue(self.scene.is_track_enabled(0))

    def test_copy_current_state(self):
        """Should copy track state into scene."""
        from core.track import Track

        tracks = [
            Track(name="Track 1"),
            Track(name="Track 2"),
        ]
        tracks[0].set_current_pattern(2)
        tracks[0].enabled = False
        tracks[1].set_current_pattern(5)

        self.scene.copy_current_state(tracks)

        self.assertEqual(self.scene.get_pattern_for_track(0), 2)
        self.assertEqual(self.scene.get_pattern_for_track(1), 5)
        self.assertFalse(self.scene.is_track_enabled(0))

    def test_apply_to_tracks(self):
        """Should apply scene settings to tracks."""
        from core.track import Track

        tracks = [
            Track(name="Track 1"),
            Track(name="Track 2"),
        ]

        self.scene.set_pattern_for_track(0, 3)
        self.scene.set_pattern_for_track(1, 6)
        self.scene.set_track_enabled(0, False)

        self.scene.apply_to_tracks(tracks)

        self.assertEqual(tracks[0].current_pattern, 3)
        self.assertEqual(tracks[1].current_pattern, 6)
        self.assertFalse(tracks[0].enabled)

    def test_clear(self):
        """Should clear all assignments."""
        self.scene.set_pattern_for_track(0, 2)
        self.scene.set_track_enabled(1, False)
        self.scene.clear()

        self.assertFalse(self.scene.has_content())

    def test_get_summary(self):
        """Should return readable summary."""
        self.scene.set_pattern_for_track(0, 1)
        summary = self.scene.get_summary()

        self.assertIn("T1:P2", summary)  # Track 1 (0-indexed) with Pattern 2

    def test_serialization(self):
        """Scene should serialize and deserialize correctly."""
        self.scene.set_pattern_for_track(0, 3)
        self.scene.set_track_enabled(1, False)

        data = self.scene.to_dict()

        from core.scene import Scene

        restored = Scene.from_dict(data)

        self.assertEqual(restored.name, "Test Scene")
        self.assertEqual(restored.get_pattern_for_track(0), 3)
        self.assertFalse(restored.is_track_enabled(1))


class TestMidiMessage(unittest.TestCase):
    """Tests for the MidiMessage dataclass."""

    def test_midi_message_creation(self):
        """MidiMessage should hold message data."""
        from core.midi_manager import MidiMessage

        msg = MidiMessage(
            channel=1, data=[0x90, 60, 100], timestamp=0.0, note=60, velocity=100
        )

        self.assertEqual(msg.channel, 1)
        self.assertEqual(msg.note, 60)
        self.assertEqual(msg.velocity, 100)

    def test_midi_message_defaults(self):
        """MidiMessage optional fields should default to None."""
        from core.midi_manager import MidiMessage

        msg = MidiMessage(channel=1, data=[0xB0, 7, 100], timestamp=0.0)

        self.assertIsNone(msg.note)
        self.assertIsNone(msg.velocity)


class TestTapTempo(unittest.TestCase):
    """Tests for the Tap Tempo functionality in TimingEngine."""

    def setUp(self):
        from core.timing import TimingEngine

        self.timing = TimingEngine(bpm=120.0)

    def test_first_tap_returns_none(self):
        """First tap should return None (need at least 2 taps)."""
        result = self.timing.tap_tempo()
        self.assertIsNone(result)

    def test_two_taps_calculates_bpm(self):
        """Two taps should calculate BPM."""
        import time

        # Simulate two taps 0.5 seconds apart (120 BPM)
        self.timing._tap_times = [time.time() - 0.5]
        result = self.timing.tap_tempo()

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 120.0, delta=5.0)

    def test_bpm_clamped_to_valid_range(self):
        """BPM should be clamped to 30-300 range."""
        import time

        # Simulate very fast taps (would be > 300 BPM)
        self.timing._tap_times = [time.time() - 0.1]  # 600 BPM if unclamped
        result = self.timing.tap_tempo()

        self.assertLessEqual(result, 300.0)

    def test_reset_tap_tempo_clears_history(self):
        """reset_tap_tempo should clear tap history."""
        import time

        self.timing._tap_times = [time.time() - 1.0, time.time() - 0.5]
        self.timing.reset_tap_tempo()

        self.assertEqual(len(self.timing._tap_times), 0)

    def test_old_taps_cleared_on_timeout(self):
        """Taps older than timeout should be cleared."""
        import time

        # Add a very old tap (3 seconds ago, timeout is 2 seconds)
        self.timing._tap_times = [time.time() - 3.0]
        result = self.timing.tap_tempo()

        # Should return None because old taps were cleared
        self.assertIsNone(result)

    def test_max_taps_limited(self):
        """Should only keep last N taps."""
        import time

        # Simulate multiple rapid taps via tap_tempo()
        for i in range(10):
            self.timing.tap_tempo()
            time.sleep(0.01)  # Small delay to avoid timeout reset

        self.assertLessEqual(len(self.timing._tap_times), self.timing._max_taps)


class TestModeHandler(unittest.TestCase):
    """Tests for the ModeHandler abstract base class."""

    def test_mode_handler_is_abstract(self):
        """ModeHandler should not be directly instantiable."""
        from ui.mode_handler import ModeHandler

        with self.assertRaises(TypeError):
            ModeHandler()

    def test_mode_handler_defines_required_methods(self):
        """ModeHandler should define required abstract methods."""
        from ui.mode_handler import ModeHandler

        # Check abstract methods exist
        self.assertTrue(hasattr(ModeHandler, "handle_pad_press"))
        self.assertTrue(hasattr(ModeHandler, "handle_encoder_turn"))
        self.assertTrue(hasattr(ModeHandler, "handle_button_press"))
        self.assertTrue(hasattr(ModeHandler, "get_display_info"))


class TestSettingsMode(unittest.TestCase):
    """Tests for the SettingsMode class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock sequencer
        self.mock_sequencer = Mock()
        self.mock_sequencer.get_bpm.return_value = 120.0
        self.mock_sequencer.get_swing.return_value = 0.0
        self.mock_sequencer.timing = Mock()
        self.mock_sequencer.timing.quantization = Mock()
        self.mock_sequencer.timing.quantization.value = "1/16"

        # Create mock tracks
        self.mock_sequencer.tracks = [
            Mock(name="Track 1", midi_channel=10, scale="MAJOR"),
            Mock(name="Track 2", midi_channel=1, scale="MAJOR"),
            Mock(name="Track 3", midi_channel=2, scale="MAJOR"),
            Mock(name="Track 4", midi_channel=3, scale="MAJOR"),
        ]

        # Create mock mode manager
        self.mock_mode_manager = Mock()
        self.mock_mode_manager.grid = Mock()
        self.mock_mode_manager.grid.pad_position = lambda p: (p // 16, p % 16)
        self.mock_mode_manager.grid.STEP_ROW = 0
        self.mock_mode_manager.grid.TRACK_PATTERN_ROW = 1
        self.mock_mode_manager.grid.INPUT_ROW_1 = 2
        self.mock_mode_manager.grid.INPUT_ROW_2 = 3

    def test_settings_mode_initialization(self):
        """SettingsMode should initialize correctly."""
        from ui.modes.settings_mode import SettingsMode

        mode = SettingsMode(self.mock_sequencer, self.mock_mode_manager)

        self.assertEqual(mode.selected_item, 0)
        self.assertFalse(mode.editing_value)
        self.assertIsNotNone(mode.menu_items)

    def test_settings_mode_has_menu_items(self):
        """SettingsMode should have menu items."""
        from ui.modes.settings_mode import SettingsMode

        mode = SettingsMode(self.mock_sequencer, self.mock_mode_manager)

        self.assertGreater(len(mode.menu_items), 0)

    def test_settings_mode_get_display_info(self):
        """get_display_info should return valid data."""
        from ui.modes.settings_mode import SettingsMode

        mode = SettingsMode(self.mock_sequencer, self.mock_mode_manager)
        info = mode.get_display_info()

        self.assertIn("selected_item", info)
        self.assertIn("item_name", info)
        self.assertIn("category", info)

    def test_encoder_navigates_menu(self):
        """Encoder should navigate menu items."""
        from ui.modes.settings_mode import SettingsMode

        mode = SettingsMode(self.mock_sequencer, self.mock_mode_manager)
        initial_item = mode.selected_item

        mode.handle_encoder_turn("volume", "clockwise", 1)

        self.assertNotEqual(mode.selected_item, initial_item)


if __name__ == "__main__":
    unittest.main()
