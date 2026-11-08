"""
Mode manager for handling different UI modes and their transitions.
Coordinates between screen display and pad grid updates.
"""

from typing import Any, Callable, Dict

from examples.apps.circuit.ui.grid_manager import GridManager
from examples.apps.circuit.ui.screen_manager import Mode, ScreenManager


class ModeManager:
    """
    Manages UI mode switching and coordinates screen and grid updates.
    Handles the Circuit Tracks-inspired mode system.
    """

    def __init__(self, screen_manager: ScreenManager, grid_manager: GridManager):
        self.screen = screen_manager
        self.grid = grid_manager
        self.current_mode = Mode.NOTE

        # Mode-specific state
        self.mode_state = {
            Mode.NOTE: {},
            Mode.MIXER: {},
            Mode.PATTERN: {},
            Mode.STEP_EDIT: {},
            Mode.SETTINGS: {},
        }

        # Mode transition callbacks
        self.mode_callbacks = {}

        # Mode handler registry (will be populated by mode instances)
        self.mode_handlers = {}

    def set_mode(self, new_mode: Mode):
        """Switch to a different mode."""
        if new_mode != self.current_mode:
            # Call exit callback for current mode
            if self.current_mode in self.mode_callbacks:
                exit_callback = self.mode_callbacks[self.current_mode].get("on_exit")
                if exit_callback:
                    exit_callback()

            # Switch modes
            old_mode = self.current_mode
            self.current_mode = new_mode

            # Update screen and grid
            self.screen.set_mode(new_mode)
            self.grid.set_mode(new_mode)

            # Call enter callback for new mode
            if new_mode in self.mode_callbacks:
                enter_callback = self.mode_callbacks[new_mode].get("on_enter")
                if enter_callback:
                    enter_callback(old_mode)

            print(f"Mode switched: {old_mode.value} → {new_mode.value}")

    def get_current_mode(self) -> Mode:
        """Get the current mode."""
        return self.current_mode

    def update_display(self, sequencer_status: Dict[str, Any], **kwargs):
        """Update both screen and grid displays."""
        # Add mode-specific state to kwargs
        mode_kwargs = kwargs.copy()
        mode_kwargs.update(self.mode_state[self.current_mode])

        # Update screen and grid
        self.screen.update_display(sequencer_status, **mode_kwargs)
        self.grid.update_grid(sequencer_status, **mode_kwargs)

    def set_mode_state(self, mode: Mode, key: str, value: Any):
        """Set mode-specific state."""
        if mode not in self.mode_state:
            self.mode_state[mode] = {}
        self.mode_state[mode][key] = value

    def register_mode_callback(
        self, mode: Mode, callback_type: str, callback: Callable
    ):
        """Register a callback for mode transitions."""
        if mode not in self.mode_callbacks:
            self.mode_callbacks[mode] = {}
        self.mode_callbacks[mode][callback_type] = callback

    def register_mode_handler(self, mode: Mode, handler):
        """Register a mode handler instance."""
        self.mode_handlers[mode] = handler

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Route input to the registered mode; handlers own its behavior."""
        handler = self.mode_handlers.get(self.current_mode)
        return (
            handler.handle_pad_press(pad_index, velocity)
            if handler is not None
            else False
        )
