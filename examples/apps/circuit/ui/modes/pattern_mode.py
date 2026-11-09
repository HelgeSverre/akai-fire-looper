"""
Pattern Mode implementation for pattern chains and scene management.
Handles pattern sequencing, scene triggers, and live performance.
"""

from typing import Any, Dict

from examples.apps.circuit.ui.screen_manager import Mode


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

        # Pattern chain building state
        self.chain_starts: dict[int, int] = {}

        # Register mode callbacks
        self.mode_manager.register_mode_callback(
            Mode.PATTERN, "on_enter", self._on_enter
        )
        self.mode_manager.register_mode_callback(Mode.PATTERN, "on_exit", self._on_exit)

        # Register this instance as the Pattern Mode handler
        self.mode_manager.register_mode_handler(Mode.PATTERN, self)

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Pattern Mode."""
        self.selected_track = self.sequencer.current_track
        self.selected_scene = self.sequencer.current_scene
        self.cancel_chain_selection()

    def _on_exit(self):
        """Called when exiting Pattern Mode."""
        self.cancel_chain_selection()

    def _update_mode_state(self):
        """Update mode manager state with current Pattern Mode settings."""
        self.mode_manager.set_mode_state(
            Mode.PATTERN, "selected_scene", self.selected_scene
        )
        self.mode_manager.set_mode_state(
            Mode.PATTERN, "selected_track", self.selected_track
        )

    def handle_pad_press(
        self, pad_index: int, velocity: int, *, shifted: bool = False
    ) -> bool:
        row, col = self.mode_manager.grid.pad_position(pad_index)
        if not (0 <= row < len(self.sequencer.tracks) and 0 <= col < 8):
            return False
        self._select_track(row)
        if shifted:
            if row not in self.chain_starts:
                self.chain_starts[row] = col
            else:
                start, end = sorted((self.chain_starts.pop(row), col))
                with self.sequencer.lock:
                    track = self.sequencer.tracks[row]
                    track.set_pattern_chain(list(range(start, end + 1)))
                    track.set_current_pattern(start)
                    self._reset_playback_position(row)
        else:
            self.chain_starts.pop(row, None)
            self._select_pattern_for_track(row, col)
        self._update_mode_state()
        return True

    def cancel_chain_selection(self):
        """SHIFT release or leaving Patterns cancels unfinished endpoints."""
        self.chain_starts.clear()
        self._update_mode_state()

    def _trigger_scene(self, scene_index: int):
        """Trigger a scene (snapshot of all track patterns)."""
        if 0 <= scene_index < 16:
            self.selected_scene = scene_index
            self.sequencer.launch_scene(scene_index)
            self._update_mode_state()

    def _select_track(self, track_index: int):
        """Select a different track for pattern editing."""
        if 0 <= track_index < len(self.sequencer.tracks):
            self.selected_track = track_index
            self.sequencer.set_current_track(track_index)
            self._update_mode_state()

            track = self.sequencer.get_current_track()
            print(
                f"Selected track {track_index + 1}: {track.name if track else 'Unknown'}"
            )

    def _select_pattern_for_track(self, track_index: int, pattern_index: int):
        """Select a pattern for a specific track."""
        if 0 <= track_index < len(self.sequencer.tracks) and 0 <= pattern_index < 8:
            track = self.sequencer.tracks[track_index]
            if track:
                with self.sequencer.lock:
                    track.set_pattern_chain([])
                    track.set_current_pattern(pattern_index)
                    self._reset_playback_position(track_index)
                print(
                    f"Track {track_index + 1} now playing pattern {pattern_index + 1}"
                )

    def _reset_playback_position(self, track_index):
        """Restart a replacement pattern under the caller's sequencer lock."""
        pattern = self.sequencer.tracks[track_index].get_current_pattern()
        pattern.reset_ping_pong()
        self.sequencer.pattern_chain_positions[track_index] = 0
        self.sequencer.pattern_chain_step_counts[track_index] = 0
        self.sequencer.track_step_positions[track_index] = pattern.get_first_step()

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
                            new_length = min(32, pattern.length + 1)
                        else:
                            new_length = max(1, pattern.length - 1)
                        pattern.set_length(new_length)
                        print(f"Pattern length: {new_length}")

            elif encoder == "pan":
                # Pattern bank selection (for future use)
                pass

        except Exception as e:
            print(
                f"Error in Pattern mode encoder handling ({encoder}, {direction}): {e}"
            )

    def handle_button_press(self, button: str):
        """Choose a scene with arrows/SELECT turn; press SELECT to launch."""
        if button == "select":
            self._trigger_scene(self.selected_scene)
        elif button == "grid_left":
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
            "chain_starts": self.chain_starts.copy(),
            "selected_scene": self.selected_scene,
            "selected_track": self.selected_track,
            "track_name": track.name if track else "Unknown",
            "pattern_index": track.current_pattern if track else 0,
            "pattern_length": pattern.length if pattern else 16,
        }
