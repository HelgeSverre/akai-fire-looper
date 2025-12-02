"""
Pattern Mode implementation for pattern chains and scene management.
Handles pattern sequencing, scene triggers, and live performance.
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


class PatternMode:
    """
    Handles Pattern Mode functionality - pattern chains and scene management.
    Manages pattern sequences, scene triggers, and live performance features.
    """

    def __init__(self, sequencer, mode_manager):
        self.sequencer = sequencer
        self.mode_manager = mode_manager

        # Local state
        self.selected_scene = 0
        self.selected_track = 0

        # Register mode callbacks
        self.mode_manager.register_mode_callback(Mode.PATTERN, "on_enter", self._on_enter)
        self.mode_manager.register_mode_callback(Mode.PATTERN, "on_exit", self._on_exit)
        
        # Register this instance as the Pattern Mode handler
        self.mode_manager.register_mode_handler(Mode.PATTERN, self)

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Pattern Mode."""
        print("Entered Pattern Mode")
        self._update_mode_state()

    def _on_exit(self):
        """Called when exiting Pattern Mode."""
        print("Exited Pattern Mode")

    def _update_mode_state(self):
        """Update mode manager state with current Pattern Mode settings."""
        self.mode_manager.set_mode_state(
            Mode.PATTERN, "selected_scene", self.selected_scene
        )
        self.mode_manager.set_mode_state(
            Mode.PATTERN, "selected_track", self.selected_track
        )

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Handle pad press in Pattern Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row == grid.STEP_ROW:
            # Row 0: Scene triggers (0-15)
            self._trigger_scene(col)
            return True

        elif row == grid.TRACK_PATTERN_ROW:
            if col < 4:
                # Track selection (columns 0-3)
                self._select_track(col)
                return True
            elif col < 12:
                # Pattern selection for current track (columns 4-11)
                pattern_idx = col - 4
                self._select_pattern_for_track(self.selected_track, pattern_idx)
                return True

        elif row in [grid.INPUT_ROW_1, grid.INPUT_ROW_2]:
            # Rows 2-3: Pattern chain controls (simplified)
            chain_slot = col if row == grid.INPUT_ROW_1 else col + 16
            self._add_pattern_to_chain(chain_slot)
            return True

        return False

    def _trigger_scene(self, scene_index: int):
        """Trigger a scene (snapshot of all track patterns)."""
        if 0 <= scene_index < 16:
            self.selected_scene = scene_index
            print(f"Triggered scene {scene_index + 1}")
            
            # TODO: Implement actual scene triggering logic
            # For now, just select scene
            self._update_mode_state()

    def _select_track(self, track_index: int):
        """Select a different track for pattern editing."""
        if 0 <= track_index < len(self.sequencer.tracks):
            self.selected_track = track_index
            self.sequencer.set_current_track(track_index)
            self._update_mode_state()
            
            track = self.sequencer.get_current_track()
            print(f"Selected track {track_index + 1}: {track.name if track else 'Unknown'}")

    def _select_pattern_for_track(self, track_index: int, pattern_index: int):
        """Select a pattern for a specific track."""
        if 0 <= track_index < len(self.sequencer.tracks) and 0 <= pattern_index < 8:
            track = self.sequencer.tracks[track_index]
            if track:
                track.set_current_pattern(pattern_index)
                print(f"Track {track_index + 1} now playing pattern {pattern_index + 1}")

    def _add_pattern_to_chain(self, chain_slot: int):
        """Add current pattern to pattern chain."""
        if 0 <= chain_slot < 32:  # 32 chain slots
            track = self.sequencer.get_current_track()
            if track:
                current_pattern = track.current_pattern
                print(f"Added pattern {current_pattern + 1} to chain slot {chain_slot + 1}")
                # TODO: Implement actual pattern chaining logic

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder turns in Pattern Mode."""
        try:
            if encoder == "volume":
                # Scene selection
                if direction == "clockwise":
                    self.selected_scene = min(15, self.selected_scene + 1)
                else:
                    self.selected_scene = max(0, self.selected_scene - 1)
                self._update_mode_state()
                print(f"Selected scene {self.selected_scene + 1}")

            elif encoder == "filter":
                # Pattern length adjustment
                track = self.sequencer.get_current_track()
                if track:
                    pattern = track.get_current_pattern()
                    if pattern:
                        if direction == "clockwise":
                            new_length = min(64, pattern.length + 1)
                        else:
                            new_length = max(1, pattern.length - 1)
                        pattern.length = new_length
                        print(f"Pattern length: {new_length}")

            elif encoder == "pan":
                # Pattern bank selection (for future use)
                pass

        except Exception as e:
            print(f"Error in Pattern mode encoder handling ({encoder}, {direction}): {e}")

    def handle_button_press(self, button: str):
        """Handle button presses in Pattern Mode."""
        if button == "grid_left":
            # Previous scene
            if self.selected_scene > 0:
                self.selected_scene -= 1
                self._update_mode_state()
                print(f"Selected scene {self.selected_scene + 1}")
                
        elif button == "grid_right":
            # Next scene
            if self.selected_scene < 15:
                self.selected_scene += 1
                self._update_mode_state()
                print(f"Selected scene {self.selected_scene + 1}")

    def get_display_info(self) -> Dict[str, Any]:
        """Get information for display updates."""
        track = self.sequencer.get_current_track()
        pattern = track.get_current_pattern() if track else None
        
        return {
            "selected_scene": self.selected_scene,
            "selected_track": self.selected_track,
            "track_name": track.name if track else "Unknown",
            "pattern_index": track.current_pattern if track else 0,
            "pattern_length": pattern.length if pattern else 16,
        }