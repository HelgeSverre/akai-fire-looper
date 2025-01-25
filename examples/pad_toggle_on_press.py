"""
AKAI Fire Example: Individual Pad Color Animation

This script demonstrates how to use the AKAI Fire MIDI controller to create
interactive pad animations. When a pad is pressed, it cycles through a color
animation sequence and then turns off.

Key Features:
- Global listener for all pad presses
- Individual color animation for each pad
- Thread-safe animation handling for multiple simultaneous pad animations
- Proper cleanup on exit
"""

import threading
import time
from typing import Set

from akai_fire import AkaiFire


class PadAnimator:
    def __init__(self):
        # Initialize the AKAI Fire controller
        self.fire = AkaiFire()
        self.fire.clear_all_pads()

        # Keep track of currently animating pads
        self.animating_pads: Set[int] = set()
        self.animation_lock = threading.Lock()

        # Define color sequence for animation
        self.color_sequence = [
            (3, 0, 0),  # Red
            (0, 3, 0),  # Green
            (0, 0, 3),  # Blue
            (3, 3, 0),  # Yellow
            (3, 0, 3),  # Magenta
            (0, 3, 3),  # Cyan
            (3, 3, 3),  # White
        ]

        # Setup pad listener
        self.setup_controls()
        print("Pad Animator initialized. Press any pad to trigger animation.")

    def setup_controls(self):
        """Set up pad listeners for all pads."""
        # Add listener for all pads (0-63)
        self.fire.add_global_listener(self.handle_pad_press)

    def handle_pad_press(self, pad_index: int):
        """Handle pad press events by starting animation in a new thread."""
        if pad_index not in self.animating_pads:
            print(f"Pad {pad_index} pressed - starting animation")
            # Start animation in a new thread
            animation_thread = threading.Thread(
                target=self.animate_pad, args=(pad_index,), daemon=True
            )
            animation_thread.start()

    def animate_pad(self, pad_index: int):
        """Animate a single pad through the color sequence."""
        with self.animation_lock:
            if pad_index in self.animating_pads:
                return
            self.animating_pads.add(pad_index)

        try:
            # Animate through color sequence
            for r, g, b in self.color_sequence:
                self.fire.set_pad_color(pad_index, r, g, b)
                time.sleep(0.1)  # Duration for each color

            # Fade out
            for intensity in range(3, -1, -1):
                self.fire.set_pad_color(pad_index, intensity, intensity, intensity)
                time.sleep(0.05)

            # Ensure pad is off at the end
            self.fire.set_pad_color(pad_index, 0, 0, 0)

        finally:
            with self.animation_lock:
                self.animating_pads.remove(pad_index)

    def run(self):
        """Main loop to keep the program running."""
        try:
            print("Running... Press Ctrl+C to exit")
            while True:
                time.sleep(0.1)  # Small sleep to prevent CPU hogging

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources and reset controller state."""
        print("Cleaning up...")
        self.fire.clear_all_pads()
        self.fire.close()


if __name__ == "__main__":
    animator = PadAnimator()
    animator.run()
