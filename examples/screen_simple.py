import os
import time

from akai_fire import AkaiFire

if __name__ == "__main__":
    fire = AkaiFire()
    canvas = fire.new_canvas()

    # Draw some shapes and text
    canvas.draw_text("Hello, World!", 0, 0)

    os.makedirs("_screens", exist_ok=True)
    fire.render_to_bmp(os.path.join("_screens", "debug_screen.bmp"))
    fire.render_to_display()

    time.sleep(1)
    fire.clear_display()
    fire.close()
