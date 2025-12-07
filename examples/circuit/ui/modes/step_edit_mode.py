"""
Step Edit Mode implementation for detailed step editing.
Handles per-step parameter editing, velocity, timing, and note editing.
"""

from typing import Dict, Any, Optional
import copy
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


class StepEditMode:
    """
    Handles Step Edit Mode functionality - detailed step parameter editing.
    Manages per-step velocity, timing, note selection, and parameter tweaking.
    """

    def __init__(self, sequencer, mode_manager):
        self.sequencer = sequencer
        self.mode_manager = mode_manager

        # Local state
        self.selected_step = 0
        self.selected_track = 0
        self.edit_parameter = "velocity"  # velocity, timing, pitch, etc.

        # Clipboard for step copy/paste
        self.clipboard_step = None  # Holds a deep copy of a Step

        # Register mode callbacks
        self.mode_manager.register_mode_callback(
            Mode.STEP_EDIT, "on_enter", self._on_enter
        )
        self.mode_manager.register_mode_callback(
            Mode.STEP_EDIT, "on_exit", self._on_exit
        )

        # Register this instance as the Step Edit Mode handler
        self.mode_manager.register_mode_handler(Mode.STEP_EDIT, self)

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Step Edit Mode."""
        print("Entered Step Edit Mode")
        self.selected_track = self.sequencer.current_track
        self._update_mode_state()

    def _on_exit(self):
        """Called when exiting Step Edit Mode."""
        print("Exited Step Edit Mode")

    def _update_mode_state(self):
        """Update mode manager state with current Step Edit Mode settings."""
        self.mode_manager.set_mode_state(
            Mode.STEP_EDIT, "selected_step", self.selected_step
        )
        self.mode_manager.set_mode_state(
            Mode.STEP_EDIT, "selected_track", self.selected_track
        )
        self.mode_manager.set_mode_state(
            Mode.STEP_EDIT, "edit_parameter", self.edit_parameter
        )

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Handle pad press in Step Edit Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row == grid.STEP_ROW:
            # Row 0: Step selection (0-15)
            self._select_step(col)
            return True

        elif row == grid.TRACK_PATTERN_ROW:
            # Track selection now via SOLO buttons
            if col < 4:
                # Columns 0-3: Parameter quick select (same as 4-7)
                self._select_parameter(col)
                return True
            elif col < 8:
                # Parameter selection (columns 4-7)
                self._select_parameter(col - 4)
                return True
            elif col < 12:
                # Step operations (columns 8-11): copy, paste, clear, duplicate
                self._handle_step_operation(col - 8)
                return True

        elif row in [grid.INPUT_ROW_1, grid.INPUT_ROW_2]:
            # Rows 2-3: Parameter value adjustment
            value_index = col if row == grid.INPUT_ROW_1 else col + 16
            self._adjust_step_parameter(value_index, velocity)
            return True

        return False

    def _select_step(self, step_index: int):
        """Select a step for editing."""
        if 0 <= step_index < 16:
            self.selected_step = step_index
            self._update_mode_state()

            track = self.sequencer.get_current_track()
            if track:
                pattern = track.get_current_pattern()
                if pattern:
                    step = pattern.get_step(step_index)
                    has_content = step is not None
                    print(
                        f"Selected step {step_index + 1} ({'has content' if has_content else 'empty'})"
                    )

    def _select_track(self, track_index: int):
        """Select a different track for step editing."""
        if 0 <= track_index < len(self.sequencer.tracks):
            self.selected_track = track_index
            self.sequencer.set_current_track(track_index)
            self._update_mode_state()

            track = self.sequencer.get_current_track()
            print(
                f"Selected track {track_index + 1}: {track.name if track else 'Unknown'}"
            )

    def _select_parameter(self, param_index: int):
        """Select which parameter to edit."""
        parameters = ["velocity", "timing", "pitch", "length"]
        if 0 <= param_index < len(parameters):
            self.edit_parameter = parameters[param_index]
            self._update_mode_state()
            print(f"Editing parameter: {self.edit_parameter}")

    def _handle_step_operation(self, operation_index: int):
        """Handle step operations: copy, paste, clear, duplicate."""
        operations = ["copy", "paste", "clear", "duplicate"]
        if not (0 <= operation_index < len(operations)):
            return

        operation = operations[operation_index]
        track = self.sequencer.get_current_track()
        if not track:
            return

        pattern = track.get_current_pattern()
        if not pattern:
            return

        if operation == "copy":
            # Copy current step to clipboard
            step = pattern.get_step(self.selected_step)
            self.clipboard_step = copy.deepcopy(step)
            print(f"Copied step {self.selected_step + 1}")

        elif operation == "paste":
            # Paste clipboard to current step
            if self.clipboard_step is None:
                print("Clipboard empty - nothing to paste")
                return
            pattern.steps[self.selected_step] = copy.deepcopy(self.clipboard_step)
            print(f"Pasted to step {self.selected_step + 1}")

        elif operation == "clear":
            # Clear current step
            pattern.clear_step(self.selected_step)
            print(f"Cleared step {self.selected_step + 1}")

        elif operation == "duplicate":
            # Copy current step to the next step
            if self.selected_step >= pattern.length - 1:
                print("Cannot duplicate: already at last step")
                return
            next_step = self.selected_step + 1
            current_step = pattern.get_step(self.selected_step)
            pattern.steps[next_step] = copy.deepcopy(current_step)
            print(f"Duplicated step {self.selected_step + 1} to step {next_step + 1}")

    def _adjust_step_parameter(self, value_index: int, velocity: int):
        """Adjust the selected parameter for the current step."""
        track = self.sequencer.get_current_track()
        if not track:
            return

        pattern = track.get_current_pattern()
        if not pattern:
            return

        step = pattern.get_step(self.selected_step)
        if not step:
            print(f"No step content at step {self.selected_step + 1}")
            return

        if self.edit_parameter == "velocity":
            # Map pad velocity to step velocity
            new_velocity = max(1, min(127, velocity * 2))
            step.velocity = new_velocity
            print(f"Step {self.selected_step + 1} velocity: {new_velocity}")

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder turns in Step Edit Mode."""
        try:
            if encoder == "volume":
                # Step navigation
                if direction == "clockwise":
                    next_step = min(15, self.selected_step + 1)
                else:
                    next_step = max(0, self.selected_step - 1)
                self._select_step(next_step)

        except Exception as e:
            print(
                f"Error in Step Edit mode encoder handling ({encoder}, {direction}): {e}"
            )

    def handle_button_press(self, button: str):
        """Handle button presses in Step Edit Mode."""
        if button == "grid_left":
            # Previous step
            if self.selected_step > 0:
                self._select_step(self.selected_step - 1)

        elif button == "grid_right":
            # Next step
            if self.selected_step < 15:
                self._select_step(self.selected_step + 1)

    def get_display_info(self) -> Dict[str, Any]:
        """Get information for display updates."""
        track = self.sequencer.get_current_track()
        pattern = track.get_current_pattern() if track else None
        step = pattern.get_step(self.selected_step) if pattern else None

        return {
            "selected_step": self.selected_step,
            "selected_track": self.selected_track,
            "edit_parameter": self.edit_parameter,
            "track_name": track.name if track else "Unknown",
            "step_has_content": step is not None,
            "step_velocity": step.velocity if step else 0,
        }

    def on_track_changed(self):
        """Called when track selection changes via SOLO buttons."""
        self.selected_track = self.sequencer.current_track
        self._update_mode_state()
        track = self.sequencer.get_current_track()
        print(
            f"Step Edit Mode: Track changed to {self.selected_track + 1}: {track.name if track else 'Unknown'}"
        )
