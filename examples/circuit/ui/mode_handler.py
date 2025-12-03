"""
Abstract base class for mode handlers.
Defines the common interface that all mode implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class ModeHandler(ABC):
    """
    Abstract base class defining the interface for all mode handlers.

    Each mode (Note, Mixer, Pattern, Step Edit, Settings) should implement
    this interface to ensure consistent behavior and enable polymorphic handling.
    """

    @abstractmethod
    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """
        Handle a pad press event.

        Args:
            pad_index: The pad that was pressed (0-63)
            velocity: The velocity of the press (0-127)

        Returns:
            True if the event was handled, False otherwise
        """
        pass

    @abstractmethod
    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """
        Handle an encoder rotation event.

        Args:
            encoder: The encoder name ("volume", "filter", "pan")
            direction: The rotation direction ("clockwise" or "counter_clockwise")
            velocity: The rotation speed/amount
        """
        pass

    @abstractmethod
    def handle_button_press(self, button: str):
        """
        Handle a button press event.

        Args:
            button: The button name (e.g., "grid_left", "grid_right", "select")
        """
        pass

    @abstractmethod
    def get_display_info(self) -> Dict[str, Any]:
        """
        Get information needed to update the display.

        Returns:
            Dictionary containing mode-specific display information
        """
        pass

    def on_enter(self, previous_mode) -> None:
        """
        Called when entering this mode.

        Override to perform initialization when the mode becomes active.

        Args:
            previous_mode: The mode that was active before this one
        """
        pass

    def on_exit(self) -> None:
        """
        Called when exiting this mode.

        Override to perform cleanup when leaving this mode.
        """
        pass

    def handle_step(self, step: int) -> None:
        """
        Called on each sequencer step (optional).

        Override to respond to step events while in this mode.

        Args:
            step: The current step number (0-15)
        """
        pass

    def handle_transport_change(self, state: str) -> None:
        """
        Called when transport state changes (optional).

        Override to respond to play/stop/record events.

        Args:
            state: The new transport state ("STOPPED", "PLAYING", "RECORDING")
        """
        pass
