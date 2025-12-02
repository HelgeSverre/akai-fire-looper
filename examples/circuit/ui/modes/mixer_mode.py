"""
Mixer Mode implementation for track control and mixing.
Handles track volume, pan, effects, and mute/solo operations.
"""

from typing import Dict, Any
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


class MixerMode:
    """
    Handles Mixer Mode functionality - track control and mixing.
    Manages track levels, effects, mute/solo, and MIDI routing.
    """

    def __init__(self, sequencer, mode_manager):
        self.sequencer = sequencer
        self.mode_manager = mode_manager

        # Local state
        self.selected_track = 0

        # Register mode callbacks
        self.mode_manager.register_mode_callback(Mode.MIXER, "on_enter", self._on_enter)
        self.mode_manager.register_mode_callback(Mode.MIXER, "on_exit", self._on_exit)
        
        # Register this instance as the Mixer Mode handler
        self.mode_manager.register_mode_handler(Mode.MIXER, self)

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Mixer Mode."""
        print("Entered Mixer Mode")
        self._update_mode_state()

    def _on_exit(self):
        """Called when exiting Mixer Mode."""
        print("Exited Mixer Mode")

    def _update_mode_state(self):
        """Update mode manager state with current Mixer Mode settings."""
        self.mode_manager.set_mode_state(
            Mode.MIXER, "selected_track", self.selected_track
        )

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Handle pad press in Mixer Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row == grid.STEP_ROW:
            # Row 0: Step sequencer (visual feedback only in Mixer Mode)
            return False

        elif row == grid.TRACK_PATTERN_ROW:
            if col < 4:
                # Track selection (columns 0-3)
                self._select_track(col)
                return True
            elif col < 8:
                # Track mute toggles (columns 4-7)
                track_idx = col - 4
                self._toggle_track_mute(track_idx)
                return True
            elif col < 12:
                # Track solo toggles (columns 8-11)
                track_idx = col - 8
                self._toggle_track_solo(track_idx)
                return True

        elif row in [grid.INPUT_ROW_1, grid.INPUT_ROW_2]:
            # Rows 2-3: Track level controls (simplified)
            track_idx = col if col < 4 else col - 4
            if track_idx < 4:
                self._adjust_track_level(track_idx, velocity)
                return True

        return False

    def _select_track(self, track_index: int):
        """Select a different track for mixing."""
        if 0 <= track_index < len(self.sequencer.tracks):
            self.selected_track = track_index
            self.sequencer.set_current_track(track_index)
            self._update_mode_state()
            
            track = self.sequencer.get_current_track()
            print(f"Selected track {track_index + 1} for mixing: {track.name if track else 'Unknown'}")

    def _toggle_track_mute(self, track_index: int):
        """Toggle mute state for a track."""
        if 0 <= track_index < len(self.sequencer.tracks):
            track = self.sequencer.tracks[track_index]
            if track:
                track.muted = not getattr(track, 'muted', False)
                state = "muted" if track.muted else "unmuted"
                print(f"Track {track_index + 1} {state}")

    def _toggle_track_solo(self, track_index: int):
        """Toggle solo state for a track."""
        if 0 <= track_index < len(self.sequencer.tracks):
            track = self.sequencer.tracks[track_index]
            if track:
                track.solo = not getattr(track, 'solo', False)
                state = "solo" if track.solo else "normal"
                print(f"Track {track_index + 1} {state}")

    def _adjust_track_level(self, track_index: int, velocity: int):
        """Adjust track level based on pad velocity."""
        if 0 <= track_index < len(self.sequencer.tracks):
            track = self.sequencer.tracks[track_index]
            if track:
                # Convert velocity to level (0-127)
                track.level = min(127, velocity * 2)  # Simple mapping
                print(f"Track {track_index + 1} level: {track.level}")

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder turns in Mixer Mode."""
        try:
            if encoder == "volume":
                # Master level control
                if direction == "clockwise":
                    level_change = velocity * 2
                else:
                    level_change = -velocity * 2
                # Apply to current track for now
                track = self.sequencer.get_current_track()
                if track:
                    current_level = getattr(track, 'level', 64)
                    new_level = max(0, min(127, current_level + level_change))
                    track.level = new_level
                    print(f"Track {self.selected_track + 1} level: {new_level}")

            elif encoder == "filter":
                # Pan control
                if direction == "clockwise":
                    pan_change = velocity
                else:
                    pan_change = -velocity
                track = self.sequencer.get_current_track()
                if track:
                    current_pan = getattr(track, 'pan', 64)
                    new_pan = max(0, min(127, current_pan + pan_change))
                    track.pan = new_pan
                    print(f"Track {self.selected_track + 1} pan: {new_pan}")

            elif encoder == "pan":
                # Effect send control
                if direction == "clockwise":
                    send_change = velocity
                else:
                    send_change = -velocity
                track = self.sequencer.get_current_track()
                if track:
                    current_send = getattr(track, 'reverb_send', 0)
                    new_send = max(0, min(127, current_send + send_change))
                    track.reverb_send = new_send
                    print(f"Track {self.selected_track + 1} reverb send: {new_send}")

        except Exception as e:
            print(f"Error in Mixer mode encoder handling ({encoder}, {direction}): {e}")

    def handle_button_press(self, button: str):
        """Handle button presses in Mixer Mode."""
        if button == "grid_left":
            # Previous track
            if self.selected_track > 0:
                self._select_track(self.selected_track - 1)
        elif button == "grid_right":
            # Next track
            if self.selected_track < len(self.sequencer.tracks) - 1:
                self._select_track(self.selected_track + 1)

    def get_display_info(self) -> Dict[str, Any]:
        """Get information for display updates."""
        track = self.sequencer.get_current_track()
        return {
            "selected_track": self.selected_track,
            "track_name": track.name if track else "Unknown",
            "track_level": getattr(track, 'level', 64) if track else 0,
            "track_pan": getattr(track, 'pan', 64) if track else 64,
            "track_muted": getattr(track, 'muted', False) if track else False,
            "track_solo": getattr(track, 'solo', False) if track else False,
        }