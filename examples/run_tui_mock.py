"""Smoke-test launcher for the TUI mock (commit 2 of 4).

Opens the terminal UI, paints a rainbow onto the pad grid, lights a couple
of buttons, and pushes some OLED content so you can eyeball the rendering.

Run:
    uv run python examples/run_tui_mock.py

The mock closes itself after --duration seconds (default 15). Press Ctrl+C
to quit early.

Input handling isn't wired yet (that's commit 3); this is render-only.
"""

from __future__ import annotations

import colorsys
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


def main() -> None:
    duration = 15.0
    for a in sys.argv[1:]:
        if a.startswith("--duration="):
            duration = float(a.split("=", 1)[1])

    fire = get_akai_fire(use_mock="tui")
    try:
        # Rainbow + some dark cells
        for i in range(64):
            r, g, b = colorsys.hsv_to_rgb(i / 64, 0.85, 0.9)
            fire.set_pad_color(i, int(r * 127), int(g * 127), int(b * 127))
        for idx in (3, 7, 20, 42, 55):
            fire.set_pad_color(idx, 0, 0, 0)

        # Lit buttons
        fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
        fire.set_button_led(fire.BUTTON_STEP, fire.LED_HIGH_RED)
        fire.set_track_led(2, fire.RECTANGLE_LED_HIGH_GREEN)

        # OLED content
        canvas = fire.get_canvas()
        canvas.clear()
        canvas.fill_rect(0, 0, canvas.WIDTH, 11, color=0)
        canvas.draw_text("HELLO FROM TUI", 4, 2, color=1)
        canvas.draw_text("pads rainbow", 2, 18)
        canvas.draw_text("PLAY lit", 2, 30)
        canvas.draw_text("track 2 on", 2, 42)
        fire.render_to_display()

        time.sleep(duration)
    except KeyboardInterrupt:
        pass
    finally:
        fire.close()


if __name__ == "__main__":
    main()
