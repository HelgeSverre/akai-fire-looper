"""
AKAI Fire Example: Color Cycling Pads

This script demonstrates how to use the AKAI Fire MIDI controller to control the pad LEDs.
The example cycles through all pads, setting their RGB color values in sequence.
Each color (red, green, blue) goes through its full intensity range before moving to the next color.

Key Features:
- Cycles through each color channel (R, G, B) independently
- For each color, cycles through all intensity levels (0-3)
- Updates all 64 pads in sequence for each intensity level
- Clears the pads and resets the device state on exit
"""

import time

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


def main():
    """
    Main function to run the color cycling animation on the AKAI Fire.
    The function initializes the device, cycles through colors and intensities,
    and ensures proper cleanup on exit.
    """
    # Initialize controller (auto-detects hardware or falls back to mock GUI)
    with get_akai_fire() as fire:
        # Clear any existing pad colors
        fire.clear_all_pads()

        try:
            print("Starting color cycling animation...")
            # Run entire color cycle three times
            for _ in range(3):
                # Cycle through each color (R, G, B)
                for color_index in range(3):  # 0=Red, 1=Green, 2=Blue
                    print(
                        f"Cycling {'Red' if color_index == 0 else 'Green' if color_index == 1 else 'Blue'}"
                    )

                    # Cycle through intensity levels (0-3)
                    for intensity in range(4):
                        # Update all pads with current color and intensity
                        for pad_index in range(64):
                            # Create RGB values based on current color_index
                            red = intensity if color_index == 0 else 0
                            green = intensity if color_index == 1 else 0
                            blue = intensity if color_index == 2 else 0

                            # Set the color of each pad
                            fire.set_pad_color(pad_index, red, green, blue)
                            time.sleep(0.01)  # Small delay for smoother animation

                        # Pause at each intensity level
                        time.sleep(0.01)

        except KeyboardInterrupt:
            print("Animation interrupted by user.")


if __name__ == "__main__":
    main()
