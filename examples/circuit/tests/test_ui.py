"""
Tests for Circuit Sequencer UI Components

Tests cover:
- GridManager: Pad colors, layout, mode-specific displays
- ScreenManager: OLED display rendering
- ModeManager: Mode switching, state management
- Mode handlers: Note mode, mixer mode, pattern mode, step edit mode

This module demonstrates how to use the akai_fire_testing utilities
for comprehensive UI testing.
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
    MockAkaiFire,
    MockMidiManager,
    MockCanvas,
    # Factory functions
    create_test_fire,
    create_test_canvas,
    # Assertion helpers
    assert_pad_grid,
    assert_row_pattern,
    assert_screen_contains,
    assert_screen_title,
    snapshot_pad_state,
    assert_pad_state_changed,
)


class TestGridManager(unittest.TestCase):
    """Tests for the GridManager class."""

    def setUp(self):
        # Use factory function for cleaner setup
        self.mock_fire, self.mock_midi = create_test_fire()
        from ui.grid_manager import GridManager
        self.grid = GridManager(self.mock_fire)

    def test_grid_dimensions(self):
        """Grid should be 4 rows x 16 columns."""
        self.assertEqual(self.grid.ROWS, 4)
        self.assertEqual(self.grid.COLS, 16)
        self.assertEqual(self.grid.TOTAL_PADS, 64)

    def test_pad_index_conversion(self):
        """Should convert row/col to pad index correctly."""
        self.assertEqual(self.grid.pad_index(0, 0), 0)
        self.assertEqual(self.grid.pad_index(0, 15), 15)
        self.assertEqual(self.grid.pad_index(1, 0), 16)
        self.assertEqual(self.grid.pad_index(3, 15), 63)

    def test_pad_position_conversion(self):
        """Should convert pad index to row/col correctly."""
        self.assertEqual(self.grid.pad_position(0), (0, 0))
        self.assertEqual(self.grid.pad_position(15), (0, 15))
        self.assertEqual(self.grid.pad_position(16), (1, 0))
        self.assertEqual(self.grid.pad_position(63), (3, 15))

    def test_set_pad_color(self):
        """Should set pad color via fire controller."""
        self.grid.set_pad_color(0, (127, 0, 0))
        # Use MockAkaiFire's built-in assertion
        self.mock_fire.assert_pad_color(0, (127, 0, 0))

    def test_clear_all_pads(self):
        """Should clear all pads to black."""
        # Set some colors first
        self.grid.set_pad_color(0, (127, 0, 0))
        self.grid.set_pad_color(32, (0, 127, 0))

        self.grid.clear_all_pads()

        # Use assertion helper - all pads should be off (empty list)
        assert_pad_grid(self.mock_fire, expected_lit=[])

    def test_track_colors_in_valid_range(self):
        """Track colors should be in 0-127 range."""
        for color in self.grid.TRACK_COLORS:
            for component in color:
                self.assertGreaterEqual(component, 0)
                self.assertLessEqual(component, 127)

    def test_state_colors_in_valid_range(self):
        """State colors should be in 0-127 range."""
        for color in self.grid.STATE_COLORS.values():
            for component in color:
                self.assertGreaterEqual(component, 0)
                self.assertLessEqual(component, 127)

    def test_brightness_levels(self):
        """Brightness levels should be valid."""
        self.assertEqual(self.grid.BRIGHTNESS["dim"], 25)
        self.assertEqual(self.grid.BRIGHTNESS["medium"], 75)
        self.assertEqual(self.grid.BRIGHTNESS["bright"], 127)

    def test_row_constants(self):
        """Row constants should be correctly defined."""
        self.assertEqual(self.grid.STEP_ROW, 0)
        self.assertEqual(self.grid.TRACK_PATTERN_ROW, 1)
        self.assertEqual(self.grid.INPUT_ROW_1, 2)
        self.assertEqual(self.grid.INPUT_ROW_2, 3)

    def test_set_mode_clears_pads(self):
        """Setting mode should clear all pads."""
        self.grid.set_pad_color(0, (127, 0, 0))

        # Take snapshot before mode change
        snapshot = snapshot_pad_state(self.mock_fire)

        from ui.screen_manager import Mode
        self.grid.set_mode(Mode.MIXER)

        # Assert pad changed
        assert_pad_state_changed(self.mock_fire, snapshot, changed_pads=[0])
        self.mock_fire.assert_pad_color(0, (0, 0, 0))

    def test_update_grid_note_mode(self):
        """Should update grid for note mode."""
        from ui.screen_manager import Mode
        self.grid.set_mode(Mode.NOTE)

        status = {
            "current_track": 1,
            "tracks": [
                {"name": "Drums", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": True},
                {"name": "Bass", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
                {"name": "Lead", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
                {"name": "Pad", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
            ],
            "timing": {"step": 0, "is_playing": False},
        }

        self.grid.update_grid(status, current_scale="MAJOR", root_note=60)

        # Use assertion helper to verify pads are lit
        lit_pads = self.mock_fire.get_lit_pads()
        self.assertGreater(len(lit_pads), 0)

    def test_track_selection_pads_lit(self):
        """Track selection pads (row 1, cols 0-3) should be lit."""
        from ui.screen_manager import Mode
        self.grid.set_mode(Mode.NOTE)

        status = {
            "current_track": 1,
            "tracks": [
                {"name": "T1", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
                {"name": "T2", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
                {"name": "T3", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
                {"name": "T4", "enabled": True, "soloed": False,
                 "current_pattern": 1, "has_content": False},
            ],
            "timing": {"step": 0, "is_playing": False},
        }

        self.grid.update_grid(status, current_scale="MAJOR", root_note=60)

        # Track pads should be lit (pads 16, 17, 18, 19 in row 1)
        for pad_idx in [16, 17, 18, 19]:
            self.mock_fire.assert_pad_not_black(pad_idx)


class TestModeManager(unittest.TestCase):
    """Tests for the ModeManager class."""

    def setUp(self):
        self.mock_fire, _ = create_test_fire()

        from ui.grid_manager import GridManager
        from ui.screen_manager import ScreenManager, Mode

        self.grid = GridManager(self.mock_fire)
        self.screen = ScreenManager(self.mock_fire.get_canvas())

        from ui.mode_manager import ModeManager
        self.mode_manager = ModeManager(self.screen, self.grid)

    def test_default_mode_is_note(self):
        """Default mode should be NOTE."""
        from ui.screen_manager import Mode
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.NOTE)

    def test_set_mode(self):
        """Should be able to change mode."""
        from ui.screen_manager import Mode
        self.mode_manager.set_mode(Mode.MIXER)
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.MIXER)

    def test_mode_callbacks_called_on_transition(self):
        """Mode callbacks should be called on transitions."""
        from ui.screen_manager import Mode

        enter_called = []
        exit_called = []

        self.mode_manager.register_mode_callback(
            Mode.MIXER, "on_enter", lambda old: enter_called.append(old)
        )
        self.mode_manager.register_mode_callback(
            Mode.NOTE, "on_exit", lambda: exit_called.append(True)
        )

        self.mode_manager.set_mode(Mode.MIXER)

        self.assertEqual(len(enter_called), 1)
        self.assertEqual(enter_called[0], Mode.NOTE)
        self.assertEqual(len(exit_called), 1)

    def test_cycle_mode(self):
        """cycle_mode should go through modes in order."""
        from ui.screen_manager import Mode

        self.assertEqual(self.mode_manager.get_current_mode(), Mode.NOTE)

        self.mode_manager.cycle_mode()
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.MIXER)

        self.mode_manager.cycle_mode()
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.PATTERN)

        self.mode_manager.cycle_mode()
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.SETTINGS)

        self.mode_manager.cycle_mode()
        self.assertEqual(self.mode_manager.get_current_mode(), Mode.NOTE)

    def test_mode_state_storage(self):
        """Should store mode-specific state."""
        from ui.screen_manager import Mode

        self.mode_manager.set_mode_state(Mode.NOTE, "selected_track", 2)
        value = self.mode_manager.get_mode_state(Mode.NOTE, "selected_track")

        self.assertEqual(value, 2)

    def test_mode_state_default(self):
        """Should return default for missing state."""
        from ui.screen_manager import Mode

        value = self.mode_manager.get_mode_state(
            Mode.NOTE, "nonexistent", default="default"
        )
        self.assertEqual(value, "default")

    def test_handle_pad_press_note_mode(self):
        """Should handle pad presses in note mode."""
        from ui.screen_manager import Mode

        # Press a track selection pad (row 1, col 0)
        handled = self.mode_manager.handle_pad_press(16, 100)

        self.assertTrue(handled)
        # Should update selected track in state
        track = self.mode_manager.get_mode_state(Mode.NOTE, "selected_track")
        self.assertEqual(track, 0)

    def test_handle_pad_press_track_2(self):
        """Should handle track 2 selection."""
        from ui.screen_manager import Mode

        # Press track 2 pad (row 1, col 1)
        self.mode_manager.handle_pad_press(17, 100)

        track = self.mode_manager.get_mode_state(Mode.NOTE, "selected_track")
        self.assertEqual(track, 1)

    def test_handle_pad_press_pattern_selection(self):
        """Should handle pattern selection."""
        from ui.screen_manager import Mode

        # Press pattern 3 pad (row 1, col 6 = 4+2)
        self.mode_manager.handle_pad_press(22, 100)

        pattern = self.mode_manager.get_mode_state(Mode.NOTE, "selected_pattern")
        self.assertEqual(pattern, 2)


class TestNoteMode(unittest.TestCase):
    """Tests for NoteMode handler."""

    def setUp(self):
        self.mock_fire, _ = create_test_fire()

        # Patch MIDI with our MockMidiManager
        self.midi_patcher = patch('core.sequencer.MidiManager')
        self.mock_midi_class = self.midi_patcher.start()
        self.mock_midi = MockMidiManager()
        self.mock_midi_class.return_value = self.mock_midi

        from ui.grid_manager import GridManager
        from ui.screen_manager import ScreenManager

        self.grid = GridManager(self.mock_fire)
        self.screen = ScreenManager(self.mock_fire.get_canvas())

        from ui.mode_manager import ModeManager
        self.mode_manager = ModeManager(self.screen, self.grid)

        from core.sequencer import Sequencer
        self.sequencer = Sequencer()

        from ui.modes.note_mode import NoteMode
        self.note_mode = NoteMode(self.sequencer, self.mode_manager)

    def tearDown(self):
        self.midi_patcher.stop()

    def test_selected_track_from_sequencer(self):
        """selected_track should come from sequencer."""
        self.sequencer.set_current_track(2)
        self.assertEqual(self.note_mode.selected_track, 2)

    def test_handle_keyboard_pad_press(self):
        """Should handle keyboard pad presses and send MIDI."""
        # Pad in input row (row 2, col 0)
        result = self.note_mode.handle_pad_press(32, 100)

        self.assertTrue(result)
        # Use MockMidiManager's assertion helpers
        notes = self.mock_midi.get_notes_on()
        self.assertGreater(len(notes), 0)

    def test_track_selection_changes_sequencer(self):
        """Selecting a track should update sequencer."""
        self.note_mode._select_track(1)
        self.assertEqual(self.sequencer.current_track, 1)

    def test_get_display_info(self):
        """get_display_info should return current state."""
        info = self.note_mode.get_display_info()

        self.assertIn("current_scale", info)
        self.assertIn("root_note", info)
        self.assertIn("octave_offset", info)
        self.assertIn("current_notes", info)

    def test_octave_change_via_button(self):
        """Grid buttons should change octave."""
        initial_octave = self.sequencer.get_current_track().octave

        self.note_mode.handle_button_press("grid_right")

        new_octave = self.sequencer.get_current_track().octave
        self.assertEqual(new_octave, initial_octave + 1)

    def test_bpm_change_via_encoder(self):
        """Volume encoder should change BPM."""
        initial_bpm = self.sequencer.get_bpm()

        self.note_mode.handle_encoder_turn("volume", "clockwise", 2)

        new_bpm = self.sequencer.get_bpm()
        self.assertGreater(new_bpm, initial_bpm)


class TestScreenManager(unittest.TestCase):
    """Tests for the ScreenManager class."""

    def setUp(self):
        # Use factory function for canvas
        self.canvas = create_test_canvas()

        from ui.screen_manager import ScreenManager
        self.screen = ScreenManager(self.canvas)

    def test_draw_header(self):
        """Should draw header on screen."""
        self.screen._draw_header("TEST", "PLAYING")

        # Use assertion helper
        assert_screen_contains(self.canvas, "TEST")

    def test_draw_startup_screen(self):
        """Should draw startup screen."""
        self.screen.draw_startup_screen("1.0")

        # Use assertion helper to check version is shown
        assert_screen_contains(self.canvas, "1.0")

    def test_update_display_note_mode(self):
        """Should update display for note mode."""
        from ui.screen_manager import Mode
        self.screen.set_mode(Mode.NOTE)

        status = {
            "transport_state": "PLAYING",
            "current_track": 1,
            "tracks": [
                {"name": "Drums", "midi_channel": 10, "current_pattern": 1},
            ],
            "timing": {"bpm": 120, "step": 4},
        }

        self.screen.update_display(status, current_scale="MAJOR", root_note=60)

        # Canvas should have been cleared and drawn to
        self.assertGreater(self.canvas.clear_count, 0)


class TestMixerMode(unittest.TestCase):
    """Tests for MixerMode handler."""

    def setUp(self):
        self.mock_fire, _ = create_test_fire()

        # Patch MIDI
        self.midi_patcher = patch('core.sequencer.MidiManager')
        self.mock_midi_class = self.midi_patcher.start()
        self.mock_midi = MockMidiManager()
        self.mock_midi_class.return_value = self.mock_midi

        from ui.grid_manager import GridManager
        from ui.screen_manager import ScreenManager, Mode

        self.grid = GridManager(self.mock_fire)
        self.screen = ScreenManager(self.mock_fire.get_canvas())

        from ui.mode_manager import ModeManager
        self.mode_manager = ModeManager(self.screen, self.grid)

        from core.sequencer import Sequencer
        self.sequencer = Sequencer()

        from ui.modes.mixer_mode import MixerMode
        self.mixer_mode = MixerMode(self.sequencer, self.mode_manager)

    def tearDown(self):
        self.midi_patcher.stop()

    def test_toggle_track_mute(self):
        """Should toggle track mute state."""
        track = self.sequencer.tracks[0]
        initial_state = getattr(track, 'muted', False)

        self.mixer_mode._toggle_track_mute(0)

        self.assertEqual(track.muted, not initial_state)

    def test_toggle_track_solo(self):
        """Should toggle track solo state."""
        track = self.sequencer.tracks[0]
        initial_state = getattr(track, 'solo', False)

        self.mixer_mode._toggle_track_solo(0)

        self.assertEqual(track.solo, not initial_state)


class TestPatternMode(unittest.TestCase):
    """Tests for PatternMode handler."""

    def setUp(self):
        self.mock_fire, _ = create_test_fire()

        # Patch MIDI
        self.midi_patcher = patch('core.sequencer.MidiManager')
        self.mock_midi_class = self.midi_patcher.start()
        self.mock_midi = MockMidiManager()
        self.mock_midi_class.return_value = self.mock_midi

        from ui.grid_manager import GridManager
        from ui.screen_manager import ScreenManager

        self.grid = GridManager(self.mock_fire)
        self.screen = ScreenManager(self.mock_fire.get_canvas())

        from ui.mode_manager import ModeManager
        self.mode_manager = ModeManager(self.screen, self.grid)

        from core.sequencer import Sequencer
        self.sequencer = Sequencer()

        from ui.modes.pattern_mode import PatternMode
        self.pattern_mode = PatternMode(self.sequencer, self.mode_manager)

    def tearDown(self):
        self.midi_patcher.stop()

    def test_select_pattern_via_internal(self):
        """Should select pattern on track via internal method."""
        self.pattern_mode._select_pattern_for_track(0, 3)

        track = self.sequencer.tracks[0]
        self.assertEqual(track.current_pattern, 3)

    def test_select_track(self):
        """Should select a different track."""
        self.pattern_mode._select_track(2)

        self.assertEqual(self.pattern_mode.selected_track, 2)
        self.assertEqual(self.sequencer.current_track, 2)

    def test_trigger_scene(self):
        """Should trigger scene selection."""
        self.pattern_mode._trigger_scene(5)

        self.assertEqual(self.pattern_mode.selected_scene, 5)

    def test_get_display_info(self):
        """Should return display information."""
        info = self.pattern_mode.get_display_info()

        self.assertIn("selected_scene", info)
        self.assertIn("selected_track", info)
        self.assertIn("track_name", info)


class TestStepEditMode(unittest.TestCase):
    """Tests for StepEditMode handler."""

    def setUp(self):
        self.mock_fire, _ = create_test_fire()

        # Patch MIDI
        self.midi_patcher = patch('core.sequencer.MidiManager')
        self.mock_midi_class = self.midi_patcher.start()
        self.mock_midi = MockMidiManager()
        self.mock_midi_class.return_value = self.mock_midi

        from ui.grid_manager import GridManager
        from ui.screen_manager import ScreenManager

        self.grid = GridManager(self.mock_fire)
        self.screen = ScreenManager(self.mock_fire.get_canvas())

        from ui.mode_manager import ModeManager
        self.mode_manager = ModeManager(self.screen, self.grid)

        from core.sequencer import Sequencer
        self.sequencer = Sequencer()

        from ui.modes.step_edit_mode import StepEditMode
        self.step_edit_mode = StepEditMode(self.sequencer, self.mode_manager)

    def tearDown(self):
        self.midi_patcher.stop()

    def test_select_step_via_pad(self):
        """Should select a step via pad press (row 0)."""
        # Pad 5 is row 0, col 5 - should select step 5
        self.step_edit_mode.handle_pad_press(5, 100)
        self.assertEqual(self.step_edit_mode.selected_step, 5)

    def test_select_parameter_via_pad(self):
        """Should select parameter via pad press (row 1, cols 4-7)."""
        # Pad 20 is row 1, col 4 - velocity parameter
        self.step_edit_mode.handle_pad_press(20, 100)
        self.assertEqual(self.step_edit_mode.edit_parameter, "velocity")

    def test_selected_step_property(self):
        """selected_step should be accessible."""
        self.step_edit_mode._select_step(3)
        self.assertEqual(self.step_edit_mode.selected_step, 3)

    def test_edit_parameter_property(self):
        """edit_parameter should be accessible."""
        self.assertEqual(self.step_edit_mode.edit_parameter, "velocity")

    def test_step_gate_length_accessible(self):
        """Should be able to access step gate length."""
        track = self.sequencer.get_current_track()
        pattern = track.get_current_pattern()
        step = pattern.get_step(0)

        self.assertEqual(step.gate_length, 0.75)

    def test_step_probability_accessible(self):
        """Should be able to access step probability."""
        track = self.sequencer.get_current_track()
        pattern = track.get_current_pattern()
        step = pattern.get_step(0)

        self.assertEqual(step.probability, 1.0)


if __name__ == "__main__":
    unittest.main()
