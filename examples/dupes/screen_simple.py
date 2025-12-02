import os
import time

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire

if __name__ == "__main__":
    # Initialize controller (auto-detects hardware or falls back to mock GUI)

    fire = get_akai_fire()
    canvas = fire.new_canvas()

    # Draw some shapes and text
    canvas.draw_text("Hello, World!", 0, 0)

    os.makedirs("_screens", exist_ok=True)
    fire.render_to_bmp(os.path.join("_screens", "debug_screen.bmp"))
    fire.render_to_display()

    time.sleep(1)
    fire.clear_display()
    fire.close()
