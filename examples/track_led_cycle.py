"""
AKAI Fire Example: Track LED Animation

This script demonstrates how to control the rectangular track LEDs on the AKAI Fire controller.
The track LEDs are the four narrow vertical LEDs located between the solo buttons and the pads,
one for each track lane (1-4). The script creates an alternating animation pattern that
switches between green and red color sequences.

Key Features:
- Alternates the animation direction (1->4 then 4->1)
- Creates different color patterns for even/odd rounds
- Demonstrates both red and green LED states
- Shows how to create "trail" effects with LED states

Usage:
    python track_led_animation.py

The script will run 4 rounds of animations, alternating between:
- Left-to-right green animations with trailing effects
- Right-to-left red animations with clean transitions
"""

import time

from akai_fire import AkaiFire


def main():
    # Initialize the AKAI Fire controller
    fire = AkaiFire()

    # Run 4 rounds of animations
    for round in range(4):
        # Alternate the order of the track LEDs (1-2-3-4 then 4-3-2-1 etc.)
        # Even rounds: left to right, Odd rounds: right to left
        track_list = [1, 2, 3, 4] if round % 2 == 0 else [4, 3, 2, 1]

        # Define color sequence based on round number
        # Even rounds: Green with trailing effect
        # Odd rounds: Red with clean transitions
        colors = (
            [
                AkaiFire.RECTANGLE_LED_OFF,  # Start off
                AkaiFire.RECTANGLE_LED_DULL_GREEN,  # Fade in
                AkaiFire.RECTANGLE_LED_HIGH_GREEN,  # Peak brightness
                AkaiFire.RECTANGLE_LED_DULL_GREEN,  # Leave a trail
            ]
            if round % 2 == 0
            else [
                AkaiFire.RECTANGLE_LED_OFF,  # Start off
                AkaiFire.RECTANGLE_LED_DULL_RED,  # Fade in
                AkaiFire.RECTANGLE_LED_HIGH_RED,  # Peak brightness
                AkaiFire.RECTANGLE_LED_DULL_RED,  # Fade out
                AkaiFire.RECTANGLE_LED_OFF,  # End off (no trail)
            ]
        )

        # Animate each track LED in sequence
        for track_index in track_list:
            print(f"Cycling track LED {track_index}...")

            # Apply each color in the sequence
            for color in colors:
                print(f"[Track {track_index}] Changing color to {color}")
                fire.set_track_led(track_index, color)
                time.sleep(0.05)  # Short delay between color changes

            time.sleep(0.05)  # Pause between tracks
    print("Done.")
    fire.close()


if __name__ == "__main__":
    print("Clearing all pads and buttons...")
    main()
