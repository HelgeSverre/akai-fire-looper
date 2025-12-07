"""
Mode management for modal AKAI Fire applications.

Provides:
- ModeHandler: Abstract base class for mode implementations
- ModeManagerMixin: Adds mode switching and event dispatch to apps
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Type, Optional, Callable, List


class ModeHandler(ABC):
    """
    Abstract base class for mode handlers.

    Each mode in your application should subclass this and implement
    the required methods. Modes handle events and provide display info.

    Example:
        class NoteMode(ModeHandler):
            def __init__(self, app):
                self.app = app

            def handle_pad_press(self, pad, velocity):
                # Play a note
                self.app.play_note(pad, velocity)
                return True

            def handle_encoder_turn(self, encoder, direction, velocity):
                if encoder == "volume":
                    self.app.adjust_volume(direction, velocity)

            def handle_button_press(self, button):
                return False

            def get_display_info(self):
                return {"mode": "NOTE", "note_count": len(self.app.notes)}
    """

    @abstractmethod
    def handle_pad_press(self, pad: int, velocity: int) -> bool:
        """
        Handle pad press event.

        Args:
            pad: Pad index (0-63)
            velocity: Press velocity (0-127)

        Returns:
            True if the event was handled, False to pass to other handlers
        """
        pass

    @abstractmethod
    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """
        Handle encoder turn event.

        Args:
            encoder: Encoder name ("volume", "pan", "filter", "resonance", "select")
            direction: "clockwise" or "counterclockwise"
            velocity: Turn speed (1-127)
        """
        pass

    @abstractmethod
    def handle_button_press(self, button: str) -> bool:
        """
        Handle button press event.

        Args:
            button: Button name (e.g., "grid_left", "grid_right")

        Returns:
            True if the event was handled, False to pass to other handlers
        """
        pass

    @abstractmethod
    def get_display_info(self) -> Dict[str, Any]:
        """
        Get mode-specific data for display rendering.

        Returns:
            Dictionary with mode-specific display information.
            This is used by the app's on_update() to render the screen.
        """
        pass

    # Optional lifecycle hooks

    def on_enter(self, previous_mode: Optional["ModeHandler"] = None):
        """
        Called when this mode becomes active.

        Args:
            previous_mode: The mode that was active before, or None if first mode
        """
        pass

    def on_exit(self):
        """Called when leaving this mode for another."""
        pass

    def on_step(self, step: int):
        """
        Called on each sequencer step (for apps that use sequencing).

        Args:
            step: Current step index
        """
        pass

    def on_transport_change(self, state: str):
        """
        Called when transport state changes.

        Args:
            state: New transport state ("stopped", "playing", "recording")
        """
        pass


class ModeManagerMixin:
    """
    Mixin that adds mode management to an AkaiFireApp.

    Usage:
        class MyApp(AkaiFireApp, ModeManagerMixin):
            def on_init(self):
                # Initialize mode manager
                self.init_mode_manager(Mode, Mode.MAIN)

                # Register mode handlers
                self.register_mode(Mode.MAIN, MainMode(self))
                self.register_mode(Mode.SETTINGS, SettingsMode(self))

                # Set initial mode
                self.set_mode(Mode.MAIN)

            def on_pad_press(self, pad, velocity):
                # Dispatch to current mode
                self.dispatch_pad_press(pad, velocity)
    """

    # Encoder ID to name mapping (matching hardware constants)
    ENCODER_NAMES = {
        0x10: "volume",
        0x11: "pan",
        0x12: "filter",
        0x13: "resonance",
        0x76: "select",
    }

    def init_mode_manager(self, mode_enum: Type[Enum], default_mode: Enum):
        """
        Initialize the mode manager.

        Call this in your on_init() method.

        Args:
            mode_enum: The Enum class defining your modes
            default_mode: The mode to start in
        """
        self._modes: Dict[Enum, ModeHandler] = {}
        self._mode_enum = mode_enum
        self._current_mode: Optional[Enum] = None
        self._default_mode = default_mode
        self._mode_state: Dict[Enum, Dict[str, Any]] = {}
        self._mode_callbacks: Dict[Enum, Dict[str, List[Callable]]] = {}

    def register_mode(self, mode_id: Enum, handler: ModeHandler):
        """
        Register a mode handler.

        Args:
            mode_id: Mode enum value
            handler: ModeHandler instance
        """
        self._modes[mode_id] = handler
        self._mode_state[mode_id] = {}
        self._mode_callbacks[mode_id] = {"on_enter": [], "on_exit": []}

    def register_mode_callback(self, mode_id: Enum, event: str, callback: Callable):
        """
        Register a callback for mode lifecycle events.

        Args:
            mode_id: Mode enum value
            event: "on_enter" or "on_exit"
            callback: Function to call
        """
        if mode_id in self._mode_callbacks:
            if event in self._mode_callbacks[mode_id]:
                self._mode_callbacks[mode_id][event].append(callback)

    def set_mode(self, mode_id: Enum):
        """
        Switch to a different mode.

        Calls on_exit() on the old mode and on_enter() on the new mode.

        Args:
            mode_id: Mode enum value to switch to
        """
        if mode_id not in self._modes:
            raise ValueError(f"Mode {mode_id} not registered")

        old_mode = self._current_mode
        old_handler = self._modes.get(old_mode) if old_mode else None

        # Exit old mode
        if old_handler:
            old_handler.on_exit()
            for callback in self._mode_callbacks.get(old_mode, {}).get("on_exit", []):
                callback()

        # Switch mode
        self._current_mode = mode_id
        new_handler = self._modes[mode_id]

        # Enter new mode
        new_handler.on_enter(old_handler)
        for callback in self._mode_callbacks.get(mode_id, {}).get("on_enter", []):
            callback(old_mode)

        # Update mode button LEDs if fire is available
        if hasattr(self, "fire"):
            self._update_mode_button_leds()

        print(f"Mode switched: {old_mode} -> {mode_id}")

    def _update_mode_button_leds(self):
        """Update mode button LEDs to show current mode."""
        # Map modes to button constants (customize in subclass)
        mode_buttons = getattr(self, "MODE_BUTTONS", {})
        for mode, button in mode_buttons.items():
            if mode == self._current_mode:
                self.fire.set_button_led(button, 2)  # Bright
            else:
                self.fire.set_button_led(button, 0)  # Off

    @property
    def current_mode(self) -> Optional[Enum]:
        """Get the current mode."""
        return self._current_mode

    @property
    def current_handler(self) -> Optional[ModeHandler]:
        """Get the current mode's handler."""
        return self._modes.get(self._current_mode)

    def get_mode_state(self, mode_id: Enum, key: str, default: Any = None) -> Any:
        """Get a value from mode-specific state storage."""
        return self._mode_state.get(mode_id, {}).get(key, default)

    def set_mode_state(self, mode_id: Enum, key: str, value: Any):
        """Set a value in mode-specific state storage."""
        if mode_id not in self._mode_state:
            self._mode_state[mode_id] = {}
        self._mode_state[mode_id][key] = value

    # =========================================================================
    # Event Dispatch
    # =========================================================================

    def dispatch_pad_press(self, pad: int, velocity: int) -> bool:
        """
        Route pad press to current mode handler.

        Args:
            pad: Pad index (0-63)
            velocity: Press velocity (0-127)

        Returns:
            True if the event was handled
        """
        if self.current_handler:
            return self.current_handler.handle_pad_press(pad, velocity)
        return False

    def dispatch_encoder_turn(self, encoder_id: int, direction: str, velocity: int):
        """
        Route encoder turn to current mode handler.

        Converts encoder ID to name before dispatching.

        Args:
            encoder_id: Hardware encoder ID
            direction: "clockwise" or "counterclockwise"
            velocity: Turn speed (1-127)
        """
        if self.current_handler:
            encoder_name = self.ENCODER_NAMES.get(encoder_id, "unknown")
            self.current_handler.handle_encoder_turn(encoder_name, direction, velocity)

    def dispatch_button_press(self, button: str) -> bool:
        """
        Route button press to current mode handler.

        Args:
            button: Button name

        Returns:
            True if the event was handled
        """
        if self.current_handler:
            return self.current_handler.handle_button_press(button)
        return False

    def dispatch_step(self, step: int):
        """
        Notify current mode of a sequencer step.

        Args:
            step: Current step index
        """
        if self.current_handler:
            self.current_handler.on_step(step)

    def dispatch_transport_change(self, state: str):
        """
        Notify current mode of transport state change.

        Args:
            state: New transport state
        """
        if self.current_handler:
            self.current_handler.on_transport_change(state)
