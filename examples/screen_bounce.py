"""
AKAI Fire Example: Bouncing Ball Animation

This script demonstrates how to use the AKAI Fire MIDI controller's bitmap display
to render a simple animation. A ball moves around the display, bouncing off the edges
of the screen. The animation runs for a specified number of seconds or until the user interrupts it.

Key Features:
- Clears the screen before rendering each frame.
- Draws a filled circle (the ball) at updated positions.
- Adjusts the ball's position based on velocity and detects collisions with screen edges.
- Adjustable frame rate (FPS) for controlling animation speed.
"""

import time

from akai_fire import AkaiFire, AkaiFireBitmap

# Initialize AKAI Fire and bitmap objects
fire = AkaiFire()
bitmap = AkaiFireBitmap()


def main(duration=10):
    """
    Main function to run the bouncing ball animation on the AKAI Fire's display.

    Args:
        duration (int): Duration of the animation in seconds (default: 10 seconds).
    """
    # Animation parameters
    x, y = 32, 32  # Initial position of the ball
    radius = 10  # Radius of the ball
    dx, dy = 4, 2  # Velocity of the ball
    fps = 30  # Frames per second
    total_frames = int(duration * fps)  # Calculate total frames for the given duration

    try:
        print(f"Starting animation for {duration} seconds...")
        for frame in range(total_frames):
            # Clear the display
            bitmap.clear()

            # Draw the ball at the current position
            bitmap.fill_circle(x, y, radius, 1)

            # Send the updated bitmap to the device
            fire.send_bitmap(bitmap)

            # Update ball position
            x += dx
            y += dy

            # Check for collisions with screen edges and bounce
            if x - radius <= 0 or x + radius >= 128:  # Horizontal bounds
                dx = -dx
            if y - radius <= 0 or y + radius >= 64:  # Vertical bounds
                dy = -dy

            # Pause to control frame rate
            time.sleep(1 / fps)
    except KeyboardInterrupt:
        print("Animation interrupted by user.")
    finally:
        print("Clearing display...")
        fire.clear_bitmap()

        print("Closing connection...")
        fire.close()


if __name__ == "__main__":
    # You can change the duration by passing a value to `main(duration=...)`
    main(duration=10)
