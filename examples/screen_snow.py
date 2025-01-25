import random
import time

from akai_fire import AkaiFire, AkaiFireBitmap

# Initialize AKAI Fire and bitmap objects
fire = AkaiFire()
bitmap = AkaiFireBitmap()


def tv_snow(duration=10, fps=30):
    """
    Generate static random pixel values (TV snow noise) on the AKAI Fire's display.

    Args:
        duration (int): Duration of the noise animation in seconds (default: 10 seconds).
        fps (int): Frames per second to control the speed of noise updates (default: 30).
    """
    total_frames = int(duration * fps)  # Calculate total frames for the given duration

    print(f"Starting TV snow animation for {duration} seconds...")
    for frame in range(total_frames):
        # Clear the display
        bitmap.clear()

        # Generate random pixels for the entire screen (128x64 resolution)
        for x in range(128):
            for y in range(64):
                if random.choice([True, False]):  # Randomly turn pixels on or off
                    bitmap.set_pixel(x, y, 1)

        # Send the updated bitmap to the device
        fire.send_bitmap(bitmap)

        # Pause to control frame rate
        time.sleep(1 / fps)


if __name__ == "__main__":
    try:
        # You can adjust the duration and fps by passing values to `tv_snow(duration=..., fps=...)`
        for fps in [10, 20, 30, 60]:
            print(f"Starting TV snow animation at {fps} FPS...")
            tv_snow(duration=3, fps=fps)
    except KeyboardInterrupt:
        print("Animation interrupted by user.")
    finally:
        print("Clearing display...")
        fire.clear_bitmap()

        print("Closing connection...")
        fire.close()
