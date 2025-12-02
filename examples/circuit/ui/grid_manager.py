"""
Grid manager for AKAI Fire 4×16 pad layout and visual feedback.
Handles all pad color updates and visual sequencer display.
"""

import sys
import os
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum

# Add parent directory to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from akai_fire import AkaiFire
except ImportError:
    # Fallback for development
    class AkaiFire:
        def set_pad_color(self, pad: int, r: int, g: int, b: int):
            pass

        def clear_all_pads(self):
            pass


from ui.screen_manager import Mode
from core.scales import get_scale_notes, is_root_note


class GridManager:
    """
    Manages the AKAI Fire's 4×16 pad grid for visual feedback and interaction.
    Provides Circuit Tracks-inspired layout and color coding.
    """

    def __init__(self, fire_controller: AkaiFire):
        self.fire = fire_controller

        # Grid dimensions (AKAI Fire: 4 rows × 16 columns = 64 pads)
        self.ROWS = 4
        self.COLS = 16
        self.TOTAL_PADS = self.ROWS * self.COLS

        # Row assignments (as per specification)
        self.STEP_ROW = 0  # Row 1: 16-step sequencer display
        self.TRACK_PATTERN_ROW = 1  # Row 2: Track control + Pattern selection
        self.INPUT_ROW_1 = 2  # Row 3: Context-sensitive input
        self.INPUT_ROW_2 = 3  # Row 4: Context-sensitive input

        # Track colors (Circuit Tracks inspired) - 0-127 range for AKAI Fire
        self.TRACK_COLORS = [
            (127, 0, 0),  # Track 1: Red (Drums)
            (0, 127, 0),  # Track 2: Green (Bass)
            (0, 0, 127),  # Track 3: Blue (Lead)
            (127, 127, 0),  # Track 4: Yellow (Pad)
        ]

        # Brightness levels for different states
        self.BRIGHTNESS = {
            "dim": 25,  # Empty/Available/Inactive
            "medium": 75,  # Has Content/Armed/Selected
            "bright": 127,  # Currently Playing/Recording/Active
        }

        # Special state colors - 0-127 range for AKAI Fire
        self.STATE_COLORS = {
            "current_step": (127, 127, 127),  # White - current playhead position
            "armed": (127, 64, 0),  # Orange - armed for recording
            "recording": (127, 0, 0),  # Red - currently recording
            "muted": (80, 0, 80),  # Purple - muted track/clip
            "soloed": (0, 100, 100),  # Cyan - soloed track
            "beat_marker": (32, 32, 32),  # Gray - beat markers
        }

        # Current mode for context-sensitive display
        self.current_mode = Mode.NOTE

        # Grid state tracking
        self.pad_colors = [(0, 0, 0)] * self.TOTAL_PADS

        # Step highlighting state
        self.last_current_step = -1
        self.original_step_colors = {}

    def pad_index(self, row: int, col: int) -> int:
        """Convert row, col to pad index."""
        return row * self.COLS + col

    def pad_position(self, pad_index: int) -> Tuple[int, int]:
        """Convert pad index to (row, col)."""
        return (pad_index // self.COLS, pad_index % self.COLS)

    def set_pad_color(self, pad_index: int, color: Tuple[int, int, int]):
        """Set a pad color and update the controller."""
        if 0 <= pad_index < self.TOTAL_PADS:
            self.pad_colors[pad_index] = color
            r, g, b = color
            self.fire.set_pad_color(pad_index, r, g, b)

    def set_mode(self, mode: Mode):
        """Set the current display mode."""
        self.current_mode = mode
        self.clear_all_pads()

    def clear_all_pads(self):
        """Clear all pad colors."""
        for i in range(self.TOTAL_PADS):
            self.set_pad_color(i, (0, 0, 0))

    def update_grid(self, sequencer_status: Dict[str, Any], **kwargs):
        """Update the entire grid based on current mode and sequencer status."""
        if self.current_mode == Mode.NOTE:
            self._update_note_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.MIXER:
            self._update_mixer_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.PATTERN:
            self._update_pattern_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.STEP_EDIT:
            self._update_step_edit_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.SETTINGS:
            self._update_settings_mode(sequencer_status, **kwargs)

    def _update_note_mode(self, status: Dict[str, Any], **kwargs):
        """Update grid for Note Mode - sequencer display + track/pattern control + keyboard."""
        # Clear grid first
        self.clear_all_pads()

        # Row 1: Step sequencer display
        self._draw_step_sequencer(status, **kwargs)

        # Row 2: Track and pattern selection
        self._draw_track_pattern_control(status)

        # Rows 3-4: Scale-based keyboard
        self._draw_scale_keyboard(status, **kwargs)

    def _draw_step_sequencer(self, status: Dict[str, Any], **kwargs):
        """Draw the 16-step sequencer visualization on Row 1."""
        timing = status.get("timing", {})
        tracks = status.get("tracks", [])
        current_track_idx = status.get("current_track", 1) - 1

        # Use current_step from kwargs if provided (from main loop), otherwise from timing
        current_step = kwargs.get("current_step", timing.get("step", 0))
        is_playing = timing.get("is_playing", False)

        # Get current track info
        if 0 <= current_track_idx < len(tracks):
            track_color = self.TRACK_COLORS[current_track_idx]
            track_info = tracks[current_track_idx]
            current_pattern = track_info.get("current_pattern", 1) - 1
        else:
            track_color = (127, 127, 127)
            current_pattern = 0

        # Draw 16 steps
        for step in range(16):
            pad_index = self.pad_index(self.STEP_ROW, step)

            # Determine step state
            if is_playing and step == current_step:
                # Current playhead position
                color = self.STATE_COLORS["current_step"]
            elif self._step_has_content(
                current_track_idx, current_pattern, step, tracks
            ):
                # Step has content
                brightness = self.BRIGHTNESS["medium"]
                color = tuple(c * brightness // 127 for c in track_color)
            elif step % 4 == 0:
                # Beat marker (every 4th step)
                color = self.STATE_COLORS["beat_marker"]
            else:
                # Empty step
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

    def _step_has_content(
        self, track_idx: int, pattern_idx: int, step: int, tracks: List[Dict]
    ) -> bool:
        """Check if a step has content (this is a simplified check)."""
        # In a full implementation, this would check the actual pattern data
        # For now, we'll simulate some content
        if 0 <= track_idx < len(tracks):
            track_info = tracks[track_idx]
            return track_info.get("has_content", False)
        return False

    def _draw_track_pattern_control(self, status: Dict[str, Any]):
        """Draw track and pattern control on Row 2."""
        tracks = status.get("tracks", [])
        current_track_idx = status.get("current_track", 1) - 1

        # Tracks 1-4 (columns 0-3)
        for i in range(4):
            pad_index = self.pad_index(self.TRACK_PATTERN_ROW, i)

            if i < len(tracks):
                track_info = tracks[i]
                track_color = self.TRACK_COLORS[i]

                if i == current_track_idx:
                    # Currently selected track
                    brightness = self.BRIGHTNESS["bright"]
                elif track_info.get("enabled", True):
                    # Enabled track
                    brightness = self.BRIGHTNESS["medium"]
                else:
                    # Disabled track
                    brightness = self.BRIGHTNESS["dim"]

                if track_info.get("soloed", False):
                    color = self.STATE_COLORS["soloed"]
                elif not track_info.get("enabled", True):
                    color = self.STATE_COLORS["muted"]
                else:
                    color = tuple(c * brightness // 127 for c in track_color)
            else:
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

        # Patterns 1-8 (columns 4-11)
        if 0 <= current_track_idx < len(tracks):
            track_info = tracks[current_track_idx]
            current_pattern = track_info.get("current_pattern", 1) - 1
            track_color = self.TRACK_COLORS[current_track_idx]

            for i in range(8):
                pad_index = self.pad_index(self.TRACK_PATTERN_ROW, i + 4)

                if i == current_pattern:
                    # Currently selected pattern
                    brightness = self.BRIGHTNESS["bright"]
                    color = tuple(c * brightness // 127 for c in track_color)
                else:
                    # Other patterns (dim)
                    brightness = self.BRIGHTNESS["dim"]
                    color = tuple(c * brightness // 127 for c in track_color)

                self.set_pad_color(pad_index, color)

    def _draw_scale_keyboard(self, status: Dict[str, Any], **kwargs):
        """Draw scale-based keyboard on Rows 3-4."""
        current_track_idx = status.get("current_track", 1) - 1

        # Get scale info from kwargs or defaults
        scale_name = kwargs.get("current_scale", "MAJOR")
        root_note = kwargs.get("root_note", 60)
        octave_offset = kwargs.get("octave_offset", 0)

        # Get track color
        if 0 <= current_track_idx < len(self.TRACK_COLORS):
            track_color = self.TRACK_COLORS[current_track_idx]
        else:
            track_color = (127, 127, 127)

        # Get scale notes for 32 pads (2 rows)
        adjusted_root = root_note + (octave_offset * 12)
        scale_notes = get_scale_notes(scale_name, adjusted_root, octaves=3)

        # Draw keyboard across rows 3-4
        for i in range(32):  # 2 rows × 16 columns
            row = self.INPUT_ROW_1 if i < 16 else self.INPUT_ROW_2
            col = i % 16
            pad_index = self.pad_index(row, col)

            if i < len(scale_notes):
                note = scale_notes[i]

                # Check if this is a root note
                if is_root_note(note, root_note):
                    # Root notes are brighter
                    brightness = self.BRIGHTNESS["bright"]
                else:
                    # Other scale notes are medium brightness
                    brightness = self.BRIGHTNESS["medium"]

                color = tuple(c * brightness // 127 for c in track_color)
            else:
                # No note mapped
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

    def _update_mixer_mode(self, status: Dict[str, Any], **kwargs):
        """Update grid for Mixer Mode - MIDI activity + track control + CC controls."""
        self.clear_all_pads()

        # Row 1: MIDI activity indicators
        self._draw_midi_activity(status, **kwargs)

        # Row 2: Track mute/solo + Scene triggers
        self._draw_mixer_control(status)

        # Rows 3-4: MIDI CC controls (32 controllers)
        self._draw_cc_controls(**kwargs)

    def _draw_midi_activity(self, status: Dict[str, Any], **kwargs):
        """Draw MIDI activity visualization on Row 1."""
        midi_activity = kwargs.get("midi_activity", {})

        for i in range(16):
            pad_index = self.pad_index(self.STEP_ROW, i)

            # Get activity for track (every 4 pads = one track)
            track_idx = i // 4
            if track_idx < 4 and track_idx in midi_activity:
                activity = midi_activity[track_idx]
                if activity.get("active", False):
                    velocity = activity.get("velocity", 0)
                    track_color = self.TRACK_COLORS[track_idx]
                    brightness = max(self.BRIGHTNESS["dim"], velocity)
                    color = tuple(c * brightness // 127 for c in track_color)
                else:
                    color = (0, 0, 0)
            else:
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

    def _draw_mixer_control(self, status: Dict[str, Any]):
        """Draw track mute/solo and scene controls on Row 2."""
        tracks = status.get("tracks", [])
        current_scene = status.get("current_scene", 1) - 1

        # Track controls (columns 0-3)
        for i in range(4):
            pad_index = self.pad_index(self.TRACK_PATTERN_ROW, i)

            if i < len(tracks):
                track_info = tracks[i]
                track_color = self.TRACK_COLORS[i]

                if track_info.get("soloed", False):
                    color = self.STATE_COLORS["soloed"]
                elif not track_info.get("enabled", True):
                    color = self.STATE_COLORS["muted"]
                else:
                    brightness = self.BRIGHTNESS["medium"]
                    color = tuple(c * brightness // 127 for c in track_color)
            else:
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

        # Scene triggers (columns 4-11)
        for i in range(8):
            pad_index = self.pad_index(self.TRACK_PATTERN_ROW, i + 4)

            if i == current_scene:
                # Active scene
                color = (127, 127, 127)  # White
            else:
                # Other scenes
                color = (64, 64, 64)  # Gray

            self.set_pad_color(pad_index, color)

    def _draw_cc_controls(self, **kwargs):
        """Draw CC control grid on Rows 3-4."""
        cc_values = kwargs.get("cc_values", {})

        # Draw 32 CC controllers
        for i in range(32):
            row = self.INPUT_ROW_1 if i < 16 else self.INPUT_ROW_2
            col = i % 16
            pad_index = self.pad_index(row, col)

            cc_num = i + 1  # CC1-CC32
            if cc_num in cc_values:
                value = cc_values[cc_num]
                # Map CC value (0-127) to brightness
                brightness = max(self.BRIGHTNESS["dim"], value)
                color = (brightness, brightness, brightness)
            else:
                color = (
                    self.BRIGHTNESS["dim"],
                    self.BRIGHTNESS["dim"],
                    self.BRIGHTNESS["dim"],
                )

            self.set_pad_color(pad_index, color)

    def _update_pattern_mode(self, status: Dict[str, Any], **kwargs):
        """Update grid for Pattern Mode - pattern chaining visualization."""
        self.clear_all_pads()

        tracks = status.get("tracks", [])
        selected_track = kwargs.get("selected_track", 0)

        # Show all patterns across the grid
        for track_idx in range(4):
            if track_idx >= len(tracks):
                continue

            track_info = tracks[track_idx]
            track_color = self.TRACK_COLORS[track_idx]
            current_pattern = track_info.get("current_pattern", 1) - 1
            pattern_chain = track_info.get("pattern_chain", [])

            # Draw 8 patterns per track
            for pattern_idx in range(8):
                # Map to grid position
                pad_index = self.pad_index(track_idx, pattern_idx)

                if pattern_chain and pattern_idx in [p - 1 for p in pattern_chain]:
                    # Part of pattern chain
                    brightness = self.BRIGHTNESS["bright"]
                elif pattern_idx == current_pattern:
                    # Current pattern
                    brightness = self.BRIGHTNESS["medium"]
                else:
                    # Other patterns
                    brightness = self.BRIGHTNESS["dim"]

                color = tuple(c * brightness // 127 for c in track_color)
                self.set_pad_color(pad_index, color)

    def _update_step_edit_mode(self, status: Dict[str, Any], **kwargs):
        """Update grid for Step Edit Mode - parameter editing."""
        self.clear_all_pads()

        step_info = kwargs.get("step_info", {})
        edit_parameter = kwargs.get("edit_parameter", "velocity")

        # Row 1: Show current pattern with selected step highlighted
        self._draw_step_sequencer(status, **kwargs)

        # Highlight selected step in yellow
        selected_step = step_info.get("step", 0) - 1
        if 0 <= selected_step < 16:
            pad_index = self.pad_index(self.STEP_ROW, selected_step)
            self.set_pad_color(pad_index, (127, 127, 0))  # Yellow

        # Row 2: Parameter selection
        parameters = ["velocity", "gate", "probability", "micro"]
        for i, param in enumerate(parameters):
            pad_index = self.pad_index(self.TRACK_PATTERN_ROW, i)
            if param == edit_parameter:
                color = (127, 127, 127)  # White for selected
            else:
                color = (64, 64, 64)  # Gray for others
            self.set_pad_color(pad_index, color)

        # Rows 3-4: Value adjustment (32 levels)
        if edit_parameter == "velocity":
            current_value = step_info.get("velocity", 85)
            max_value = 127
        elif edit_parameter == "gate":
            current_value = int(step_info.get("gate", 0.75) * 127)
            max_value = 127
        elif edit_parameter == "probability":
            current_value = int(step_info.get("probability", 1.0) * 127)
            max_value = 127
        else:  # micro_timing
            current_value = (step_info.get("micro_timing", 0) + 6) * 127 // 12
            max_value = 127

        # Draw value bars
        for i in range(32):
            row = self.INPUT_ROW_1 if i < 16 else self.INPUT_ROW_2
            col = i % 16
            pad_index = self.pad_index(row, col)

            # Calculate if this pad should be lit based on current value
            pad_threshold = (i * max_value) // 32
            if current_value >= pad_threshold:
                brightness = max(
                    self.BRIGHTNESS["dim"], 127 - (i * 4)
                )  # Fade from bright to dim
                color = (brightness, brightness, brightness)
            else:
                color = (0, 0, 0)

            self.set_pad_color(pad_index, color)

    def _update_settings_mode(self, status: Dict[str, Any], **kwargs):
        """Update grid for Settings Mode - minimal display."""
        self.clear_all_pads()

        # Just show a simple pattern to indicate settings mode
        for i in range(4):
            pad_index = self.pad_index(1, i * 4)  # Every 4th pad on row 2
            self.set_pad_color(pad_index, (64, 64, 64))

    def flash_pad(
        self, pad_index: int, color: Tuple[int, int, int], duration: float = 0.1
    ):
        """Flash a pad briefly (for user feedback)."""
        # This would need to be implemented with a timer for actual flashing
        # For now, just set the color
        self.set_pad_color(pad_index, color)

    def get_pad_for_note_input(self, row: int, col: int) -> Optional[int]:
        """Get MIDI note for a pad in the keyboard area."""
        if row not in [self.INPUT_ROW_1, self.INPUT_ROW_2]:
            return None

        # Convert to keyboard index (0-31)
        if row == self.INPUT_ROW_1:
            keyboard_index = col
        else:
            keyboard_index = col + 16

        return keyboard_index  # This would be mapped to actual MIDI note in the mode handler

    def highlight_current_step(self, step: int):
        """Highlight the current playing step."""
        # Clear previous step highlight
        if self.last_current_step >= 0:
            previous_pad_index = self.pad_index(self.STEP_ROW, self.last_current_step)
            # Restore original color if we saved it
            if previous_pad_index in self.original_step_colors:
                original_color = self.original_step_colors[previous_pad_index]
                self.set_pad_color(previous_pad_index, original_color)

        # Highlight new step
        if 0 <= step < 16:
            pad_index = self.pad_index(self.STEP_ROW, step)
            # Save original color before changing it
            if pad_index not in self.original_step_colors:
                self.original_step_colors[pad_index] = self.pad_colors[pad_index]
            self.set_pad_color(pad_index, self.STATE_COLORS["current_step"])
            self.last_current_step = step
