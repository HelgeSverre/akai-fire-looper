import random
import time

from akai_fire import AkaiFire

fire = AkaiFire()
canvas = fire.get_canvas()


def tv_snow(duration=10, fps=30):
    """≤
    Generate static random pixel values (TV snow noise) on the AKAI Fire's display.

    Args:
        duration (int): Duration of the noise animation in seconds (default: 10 seconds).
        fps (int): Frames per second to control the speed of noise updates (default: 30).
    """
    total_frames = int(duration * fps)  # Calculate total frames for the given duration

    print(f"Starting TV snow animation for {duration} seconds...")
    for frame in range(total_frames):
        # Clear the display
        canvas.clear()

        # Generate random pixels for the entire screen (128x64 resolution)
        for x in range(128):
            for y in range(64):
                if random.choice([True, False]):  # Randomly turn pixels on or off
                    canvas.set_pixel(x, y, 0)

        # Send the updated canvas to the device
        fire.render_to_display()

        # Pause to control frame rate
        time.sleep(1 / fps)


if __name__ == "__main__":
    try:
        tv_snow(duration=3, fps=30)
    except KeyboardInterrupt:
        print("Animation interrupted by user.")
    finally:
        print("Clearing display...")
        fire.clear_display()

        print("Closing connection...")
        fire.close()
