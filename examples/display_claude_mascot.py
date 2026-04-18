"""Render the Claude mascot on the AKAI Fire's 128x64 OLED.

The mascot shape comes from the canonical SVG animation's final frame.
Rectangles are given in SVG units (50-unit grid) and scaled down to fit the OLED.

Runs against hardware if available, otherwise falls back to the pygame mock.
Pass --preview-only to skip hardware and just write a BMP.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import Canvas, get_akai_fire


# Each tuple: (x, y, w, h) in source SVG units. Extracted from the final frame
# (fill-opacity=1) of the Lottie animation SVG.
BODY_RECTS = [
    # legs
    (1436, 1651, 100, 200),
    (1136, 1651, 100, 200),
    # ears (4x4 grid squares each)
    (1736, 1251, 200, 200),
    (736, 1251, 200, 200),
    # vertical spine strips that connect ears to body top
    (1536, 1251, 100, 400),
    (1036, 1251, 100, 400),
    # tall side strips running full body + legs
    (1636, 1151, 100, 700),
    (936, 1151, 100, 700),
    # main body block
    (1136, 1151, 400, 500),
    # top bar across the head
    (936, 1051, 800, 100),
]

# Eyes — these punch holes back out of the body.
EYE_RECTS = [
    (1536, 1151, 100, 100),
    (1036, 1151, 100, 100),
]


def bbox(rects):
    xs0 = min(r[0] for r in rects)
    ys0 = min(r[1] for r in rects)
    xs1 = max(r[0] + r[2] for r in rects)
    ys1 = max(r[1] + r[3] for r in rects)
    return xs0, ys0, xs1 - xs0, ys1 - ys0


def draw_mascot(canvas: Canvas, target_h: int = 60) -> tuple[int, int, int, int]:
    """Draw mascot scaled to `target_h` OLED pixels tall, centered on the canvas."""
    src_x, src_y, src_w, src_h = bbox(BODY_RECTS)
    scale = target_h / src_h
    dst_w = round(src_w * scale)
    dst_h = round(src_h * scale)
    ox = (Canvas.WIDTH - dst_w) // 2
    oy = (Canvas.HEIGHT - dst_h) // 2

    def place(rect):
        x, y, w, h = rect
        x0 = ox + round((x - src_x) * scale)
        y0 = oy + round((y - src_y) * scale)
        x1 = ox + round((x + w - src_x) * scale)
        y1 = oy + round((y + h - src_y) * scale)
        return x0, y0, max(1, x1 - x0), max(1, y1 - y0)

    for rect in BODY_RECTS:
        x, y, w, h = place(rect)
        canvas.fill_rect(x, y, w, h, color=0)  # 0 = ON
    for rect in EYE_RECTS:
        x, y, w, h = place(rect)
        canvas.fill_rect(x, y, w, h, color=1)  # 1 = OFF (punches eye holes)

    return ox, oy, dst_w, dst_h


def build_canvas(target_h: int = 60) -> tuple[Canvas, int, int, int, int]:
    canvas = Canvas()
    canvas.clear(1)
    ox, oy, w, h = draw_mascot(canvas, target_h=target_h)
    return canvas, ox, oy, w, h


def preview_only(preview_path: str, target_h: int = 60) -> None:
    canvas, ox, oy, w, h = build_canvas(target_h=target_h)
    canvas.image.save(preview_path, format="BMP")
    print(f"Saved preview to {preview_path}  (mascot {w}x{h} at ({ox},{oy}))")


def render_live(preview_path: str | None = None, target_h: int = 60) -> None:
    canvas, ox, oy, w, h = build_canvas(target_h=target_h)
    if preview_path:
        canvas.image.save(preview_path, format="BMP")
        print(f"Saved preview to {preview_path}  (mascot {w}x{h} at ({ox},{oy}))")

    with get_akai_fire() as fire:
        fire.render_to_display(canvas)
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target_h = 60
    for a in sys.argv[1:]:
        if a.startswith("--height="):
            target_h = int(a.split("=", 1)[1])
    path = args[0] if args else "/tmp/claude_mascot.bmp"

    if "--preview-only" in sys.argv:
        preview_only(path, target_h=target_h)
    else:
        render_live(preview_path=path, target_h=target_h)
