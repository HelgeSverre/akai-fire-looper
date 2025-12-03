#!/usr/bin/env python3
"""
Quick smoke test to verify pygame works on this system.
Opens a mock AKAI Fire window for 3 seconds.

Run: uv run python examples/circuit/test_pygame_smoke.py
"""
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mock_gui_pygame import MockAkaiFire


def main():
    print("Starting pygame smoke test...")
    print("A window should appear showing the AKAI Fire mock GUI.")
    print("It will close automatically after 3 seconds.\n")

    try:
        fire = MockAkaiFire()
        print("✓ MockAkaiFire initialized")

        # Set some pad colors in a pattern
        for i in range(16):
            fire.set_pad_color(i, 127, 0, 0)  # Red row 1
        for i in range(16, 32):
            fire.set_pad_color(i, 0, 127, 0)  # Green row 2
        for i in range(32, 48):
            fire.set_pad_color(i, 0, 0, 127)  # Blue row 3
        for i in range(48, 64):
            fire.set_pad_color(i, 127, 127, 0)  # Yellow row 4
        print("✓ Pad colors set")

        # Draw on OLED screen
        canvas = fire.get_canvas()
        canvas.clear()
        canvas.draw_text("Pygame Smoke Test", 10, 10)
        canvas.draw_text("All systems OK!", 20, 30)
        canvas.draw_rect(5, 5, 118, 54, 1)  # Border
        print("✓ Canvas drawn")

        # Run event loop for 3 seconds
        start = time.time()
        frame_count = 0
        while fire.running and time.time() - start < 3:
            if not fire.process_events():
                break
            frame_count += 1
            time.sleep(0.016)  # ~60 FPS

        fire.close()
        print(f"✓ Event loop ran for {frame_count} frames")
        print("\n✓ Pygame smoke test PASSED!")
        return 0

    except Exception as e:
        print(f"\n✗ Pygame smoke test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
