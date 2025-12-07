"""
Note Mode implementation for scale-based MIDI input and composition.
Primary mode for creating and editing patterns.
"""

from typing import Dict, Any, List, Optional
import sys
import os

# Add parent directories to path
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)

from ui.screen_manager import Mode
from core.scales import get_scale_notes, map_pad_to_note, get_note_name, is_root_note
from core.sequencer import TransportState


class NoteMode:
    """
    Handles Note Mode functionality - the primary composition mode.
    Manages scale-based keyboard input, track selection, and pattern editing.
    """

    def __init__(self, sequencer, mode_manager):
        self.sequencer = sequencer
        self.mode_manager = mode_manager

        # Local state (non-duplicated)
        self.current_notes_playing = []

        # Recently played notes for display
        self.recent_notes = {}

        # Register mode callbacks
        self.mode_manager.register_mode_callback(Mode.NOTE, "on_enter", self._on_enter)
        self.mode_manager.register_mode_callback(Mode.NOTE, "on_exit", self._on_exit)

        # Register this instance as the Note Mode handler
        self.mode_manager.register_mode_handler(Mode.NOTE, self)

    @property
    def selected_track(self):
        """Get current track index from sequencer (single source of truth)."""
        return self.sequencer.current_track

    @property
    def selected_pattern(self):
        """Get current pattern index from current track."""
        track = self.sequencer.get_current_track()
        return track.current_pattern if track else 0

    @property
    def current_scale(self):
        """Get current scale from current track."""
        track = self.sequencer.get_current_track()
        return track.scale if track else "MAJOR"

    @property
    def root_note(self):
        """Get root note from current track."""
        track = self.sequencer.get_current_track()
        return track.root_note if track else 60

    @property
    def octave_offset(self):
        """Get octave offset from current track."""
        track = self.sequencer.get_current_track()
        return track.octave if track else 0

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Note Mode."""
        print("Entered Note Mode")

        # Update mode state (properties will get current values from sequencer)
        self._update_mode_state()

    def _on_exit(self):
        """Called when exiting Note Mode."""
        print("Exited Note Mode")
        # Stop any playing notes
        self._stop_all_notes()

    def _update_mode_state(self):
        """Update mode manager state with current Note Mode settings."""
        self.mode_manager.set_mode_state(
            Mode.NOTE, "selected_track", self.selected_track
        )
        self.mode_manager.set_mode_state(
            Mode.NOTE, "selected_pattern", self.selected_pattern
        )
        self.mode_manager.set_mode_state(Mode.NOTE, "current_scale", self.current_scale)
        self.mode_manager.set_mode_state(Mode.NOTE, "root_note", self.root_note)
        self.mode_manager.set_mode_state(Mode.NOTE, "octave_offset", self.octave_offset)
        self.mode_manager.set_mode_state(
            Mode.NOTE, "current_notes", self.current_notes_playing
        )

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Handle pad press in Note Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row == grid.STEP_ROW:
            # Row 1: Step sequencer (visual only in Note Mode)
            return False

        elif row == grid.TRACK_PATTERN_ROW:
            # Track selection now via SOLO buttons, cols 0-3 can show patterns 1-4 duplicate
            if 4 <= col < 12:
                # Pattern selection
                pattern_num = col - 4
                self._select_pattern(pattern_num)
                return True

        elif row in [grid.INPUT_ROW_1, grid.INPUT_ROW_2]:
            # Scale keyboard
            keyboard_index = col if row == grid.INPUT_ROW_1 else col + 16
            self._play_note_from_keyboard(keyboard_index, velocity)
            return True

        return False

    def handle_pad_release(self, pad_index: int):
        """Handle pad release in Note Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row in [grid.INPUT_ROW_1, grid.INPUT_ROW_2]:
            # Stop note from keyboard
            keyboard_index = col if row == grid.INPUT_ROW_1 else col + 16
            self._stop_note_from_keyboard(keyboard_index)

    def _select_track(self, track_index: int):
        """Select a different track."""
        if 0 <= track_index < len(self.sequencer.tracks):
            # Set track in sequencer (single source of truth)
            self.sequencer.set_current_track(track_index)

            # Update mode state (properties will get updated values)
            self._update_mode_state()

            track = self.sequencer.get_current_track()
            print(
                f"Selected track {track_index + 1}: {track.name if track else 'Unknown'}"
            )

    def _select_pattern(self, pattern_index: int):
        """Select a different pattern for the current track."""
        if 0 <= pattern_index < 8:
            # Set pattern in track (single source of truth)
            track = self.sequencer.get_current_track()
            if track:
                track.set_current_pattern(pattern_index)

                self._update_mode_state()
                print(
                    f"Selected pattern {pattern_index + 1} for track {self.selected_track + 1}"
                )

    def _play_note_from_keyboard(self, keyboard_index: int, velocity: int):
        """Play a note from the scale keyboard."""
        # Get MIDI note for this keyboard position
        adjusted_root = self.root_note + (self.octave_offset * 12)
        scale_notes = get_scale_notes(self.current_scale, adjusted_root, octaves=3)

        if keyboard_index < len(scale_notes):
            midi_note = scale_notes[keyboard_index]
            track = self.sequencer.get_current_track()

            # Constrain to track's note range
            final_note = track.constrain_note_to_range(midi_note)

            # Send MIDI note
            self.sequencer.midi.send_note_on(track.midi_channel, final_note, velocity)

            # Track for visual feedback
            self.current_notes_playing.append(final_note)
            self._update_recent_notes(final_note, velocity)

            # Record note if in recording mode
            if self.sequencer.transport_state == TransportState.RECORDING:
                self.sequencer.record_note(self.selected_track, final_note, velocity)

            print(
                f"Playing note: {get_note_name(final_note)} ({final_note}) vel:{velocity}"
            )

            # Update visual state
            self._update_mode_state()

    def _stop_note_from_keyboard(self, keyboard_index: int):
        """Stop a note from the scale keyboard."""
        # Get MIDI note for this keyboard position
        adjusted_root = self.root_note + (self.octave_offset * 12)
        scale_notes = get_scale_notes(self.current_scale, adjusted_root, octaves=3)

        if keyboard_index < len(scale_notes):
            midi_note = scale_notes[keyboard_index]
            track = self.sequencer.get_current_track()
            final_note = track.constrain_note_to_range(midi_note)

            # Send MIDI note off
            self.sequencer.midi.send_note_off(track.midi_channel, final_note)

            # Remove from currently playing notes
            if final_note in self.current_notes_playing:
                self.current_notes_playing.remove(final_note)

            # Update visual state
            self._update_mode_state()

    def _stop_all_notes(self):
        """Stop all currently playing notes."""
        track = self.sequencer.get_current_track()
        for note in self.current_notes_playing:
            self.sequencer.midi.send_note_off(track.midi_channel, note)

        self.current_notes_playing.clear()
        self._update_mode_state()

    def _update_recent_notes(self, note: int, velocity: int):
        """Update the recent notes display."""
        if self.selected_track not in self.recent_notes:
            self.recent_notes[self.selected_track] = []

        # Add note with timestamp
        import time

        self.recent_notes[self.selected_track].append(
            {"note": note, "velocity": velocity, "time": time.time()}
        )

        # Keep only last 5 notes
        self.recent_notes[self.selected_track] = self.recent_notes[self.selected_track][
            -5:
        ]

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder turns in Note Mode."""
        try:
            if encoder == "volume":
                # BPM control
                current_bpm = self.sequencer.get_bpm()
                if direction == "clockwise":
                    bpm_change = velocity * 0.5
                else:  # counterclockwise
                    bpm_change = -velocity * 0.5
                new_bpm = max(30.0, min(300.0, current_bpm + bpm_change))
                self.sequencer.set_bpm(new_bpm)

            elif encoder == "filter":
                # Swing control
                current_swing = self.sequencer.get_swing()
                if direction == "clockwise":
                    swing_change = velocity * 0.01  # 1% increments
                else:  # counterclockwise
                    swing_change = -velocity * 0.01
                new_swing = max(0.0, min(0.75, current_swing + swing_change))
                self.sequencer.set_swing(new_swing)

            elif encoder == "pan":
                # Quantization control (cycle through options)
                if direction == "clockwise":
                    self._next_quantization()
                else:  # counterclockwise
                    self._prev_quantization()

        except Exception as e:
            print(f"Error in encoder handling ({encoder}, {direction}): {e}")

    def _next_quantization(self):
        """Cycle to next quantization setting."""
        from ...core.timing import QuantizationMode

        modes = [
            QuantizationMode.OFF,
            QuantizationMode.QUARTER,
            QuantizationMode.EIGHTH,
            QuantizationMode.SIXTEENTH,
            QuantizationMode.THIRTY_SECOND,
        ]

        current = self.sequencer.timing.get_quantization()
        try:
            current_index = modes.index(current)
            next_index = (current_index + 1) % len(modes)
            self.sequencer.set_quantization(modes[next_index])
        except ValueError:
            self.sequencer.set_quantization(QuantizationMode.SIXTEENTH)

    def _prev_quantization(self):
        """Cycle to previous quantization setting."""
        from ...core.timing import QuantizationMode

        modes = [
            QuantizationMode.OFF,
            QuantizationMode.QUARTER,
            QuantizationMode.EIGHTH,
            QuantizationMode.SIXTEENTH,
            QuantizationMode.THIRTY_SECOND,
        ]

        current = self.sequencer.timing.get_quantization()
        try:
            current_index = modes.index(current)
            prev_index = (current_index - 1) % len(modes)
            self.sequencer.set_quantization(modes[prev_index])
        except ValueError:
            self.sequencer.set_quantization(QuantizationMode.SIXTEENTH)

    def handle_button_press(self, button: str):
        """Handle button presses in Note Mode."""
        if button == "grid_left":
            # Octave down
            track = self.sequencer.get_current_track()
            if track:
                track.octave = max(-5, track.octave - 1)
                self._update_mode_state()
                print(f"Octave: {track.octave}")

        elif button == "grid_right":
            # Octave up
            track = self.sequencer.get_current_track()
            if track:
                track.octave = min(5, track.octave + 1)
                self._update_mode_state()
                print(f"Octave: {track.octave}")

    def get_display_info(self) -> Dict[str, Any]:
        """Get information for display updates."""
        return {
            "current_scale": self.current_scale,
            "root_note": self.root_note,
            "octave_offset": self.octave_offset,
            "current_notes": self.current_notes_playing,
            "recent_notes": self.recent_notes.get(self.selected_track, []),
        }

    def clear_pattern(self):
        """Clear the current pattern."""
        track = self.sequencer.get_current_track()
        track.clear_pattern(self.selected_pattern)
        print(
            f"Cleared pattern {self.selected_pattern + 1} on track {self.selected_track + 1}"
        )

    def duplicate_pattern(self, to_pattern: int):
        """Duplicate current pattern to another pattern slot."""
        if 0 <= to_pattern < 8:
            track = self.sequencer.get_current_track()
            track.copy_pattern(self.selected_pattern, to_pattern)
            print(
                f"Duplicated pattern {self.selected_pattern + 1} to pattern {to_pattern + 1}"
            )

    def set_scale(self, scale_name: str, root_note: Optional[int] = None):
        """Change the current scale and optionally root note."""
        from ...core.scales import SCALES

        if scale_name in SCALES:
            track = self.sequencer.get_current_track()
            if track:
                track.scale = scale_name

                if root_note is not None:
                    track.root_note = root_note

                self._update_mode_state()
                print(
                    f"Scale changed to: {get_note_name(track.root_note)} {scale_name}"
                )
        else:
            print(f"Unknown scale: {scale_name}")

    def get_current_pattern_info(self) -> Dict[str, Any]:
        """Get information about the current pattern."""
        track = self.sequencer.get_current_track()
        pattern = track.get_current_pattern()

        return {
            "track_name": track.name,
            "track_index": self.selected_track,
            "pattern_index": self.selected_pattern,
            "pattern_name": pattern.name,
            "pattern_length": pattern.length,
            "has_content": pattern.has_content(),
            "active_steps": pattern.get_active_steps(),
        }

    def on_track_changed(self):
        """Called when track selection changes via SOLO buttons."""
        # Update mode state to reflect new track
        self._update_mode_state()
        track = self.sequencer.get_current_track()
        print(
            f"Note Mode: Track changed to {self.selected_track + 1}: {track.name if track else 'Unknown'}"
        )
