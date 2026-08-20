"""Scroll "You're absolutely right!" across the OLED while Clawd walks alongside.

Each character does a little sine-wave dance as it scrolls.
"""

import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from akai_fire import Canvas, get_akai_fire
from examples.animate_clawd import DEFAULT_GIF, load_frames  # reuse pipeline

TEXT = "You're absolutely right!  "  # trailing spaces = gap before it loops
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_SIZE = 14
FPS = 30
SCROLL_PX_PER_FRAME = 2
WAVE_AMP = 3  # vertical dance amplitude in px
WAVE_FREQ = 0.35  # radians per char
WAVE_SPEED = 0.25  # radians per frame

OLED_W, OLED_H = Canvas.WIDTH, Canvas.HEIGHT
TEXT_BASELINE_Y = 8  # top of text band
CLAWD_SCALE_H = 28  # height for the walking clawd beneath the text


def load_font() -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except OSError:
        return ImageFont.load_default()


def char_widths(font, text: str) -> list[int]:
    """Per-char advance widths using font metrics."""
    widths = []
    probe = Image.new("1", (1, 1))
    d = ImageDraw.Draw(probe)
    for ch in text:
        bbox = d.textbbox((0, 0), ch, font=font)
        widths.append(bbox[2] - bbox[0] + 1)  # +1 for a bit of kerning
    return widths


def render_text_band(
    font,
    text: str,
    widths: list[int],
    scroll_px: int,
    frame: int,
    band_w: int,
    band_h: int,
) -> Image.Image:
    """Draw the scrolling, dancing text onto a band of (band_w x band_h)."""
    total_w = sum(widths)
    band = Image.new("1", (band_w, band_h), 1)  # 1 = off
    draw = ImageDraw.Draw(band)

    # Draw the string twice end-to-end so it loops seamlessly.
    x_cursor = -(scroll_px % total_w)
    for repeat in range(2):
        for i, ch in enumerate(text):
            if x_cursor > band_w:
                break
            if x_cursor + widths[i] >= 0:
                y_off = int(
                    round(WAVE_AMP * math.sin(frame * WAVE_SPEED + i * WAVE_FREQ))
                )
                draw.text((x_cursor, y_off + 2), ch, font=font, fill=0)  # 0 = on
            x_cursor += widths[i]
        # second pass starts right after the first
    return band


def prep_clawd_frames(target_h: int) -> list[Image.Image]:
    """Load clawd gif and preshrink to a walking-sized silhouette (1-bit)."""
    raw = load_frames(Path(DEFAULT_GIF))  # already 128x64 1-bit, orange=on
    # crop each to its content bbox, then resize to target_h
    shrunk = []
    for f in raw:
        # invert so content is white for bbox
        inv = f.point(lambda p: 255 if p == 0 else 0, mode="L")
        bbox = inv.getbbox()
        if bbox is None:
            shrunk.append(Image.new("1", (1, target_h), 1))
            continue
        crop = f.crop(bbox)
        ratio = target_h / crop.height
        new_w = max(1, int(round(crop.width * ratio)))
        shrunk.append(crop.resize((new_w, target_h), Image.NEAREST))
    return shrunk


def play(duration: float | None = None) -> None:
    font = load_font()
    widths = char_widths(font, TEXT)
    total_text_w = sum(widths)

    clawd_frames = prep_clawd_frames(CLAWD_SCALE_H)

    deadline = None if duration is None else time.time() + duration
    delay = 1 / FPS
    frame = 0

    with get_akai_fire() as fire:
        canvas = Canvas()
        try:
            while True:
                canvas.clear(1)
                # Text band at top
                band = render_text_band(
                    font,
                    TEXT,
                    widths,
                    scroll_px=frame * SCROLL_PX_PER_FRAME,
                    frame=frame,
                    band_w=OLED_W,
                    band_h=FONT_SIZE + WAVE_AMP * 2 + 4,
                )
                canvas.image.paste(band, (0, 2))

                # Clawd walking at the bottom, scrolling opposite direction
                cf = clawd_frames[frame % len(clawd_frames)]
                cw = cf.width
                # scroll clawd right-to-left
                cx = OLED_W - ((frame * 1) % (OLED_W + cw))
                cy = OLED_H - cf.height - 1
                canvas.image.paste(cf, (cx, cy))

                fire.render_to_display(canvas)
                frame += 1
                time.sleep(delay)
                if deadline is not None and time.time() >= deadline:
                    fire.clear_display()
                    return
        except KeyboardInterrupt:
            fire.clear_display()


def preview(duration_frames: int = 60) -> None:
    """Save a horizontal filmstrip preview instead of talking to hardware."""
    font = load_font()
    widths = char_widths(font, TEXT)
    clawd_frames = prep_clawd_frames(CLAWD_SCALE_H)

    strip = Image.new("1", (OLED_W, OLED_H * 6), 1)
    picks = [0, 6, 12, 18, 24, 30]
    for row, frame in enumerate(picks):
        canvas = Image.new("1", (OLED_W, OLED_H), 1)
        band = render_text_band(
            font,
            TEXT,
            widths,
            scroll_px=frame * SCROLL_PX_PER_FRAME,
            frame=frame,
            band_w=OLED_W,
            band_h=FONT_SIZE + WAVE_AMP * 2 + 4,
        )
        canvas.paste(band, (0, 2))
        cf = clawd_frames[frame % len(clawd_frames)]
        cx = OLED_W - ((frame * 1) % (OLED_W + cf.width))
        cy = OLED_H - cf.height - 1
        canvas.paste(cf, (cx, cy))
        strip.paste(canvas, (0, row * OLED_H))
    strip = strip.resize((OLED_W * 3, strip.height * 3), Image.NEAREST)
    strip.save("/tmp/dance_right_preview.png")
    print("wrote /tmp/dance_right_preview.png")


if __name__ == "__main__":
    duration = None
    for a in sys.argv[1:]:
        if a.startswith("--duration="):
            duration = float(a.split("=", 1)[1])
    if "--preview-only" in sys.argv:
        preview()
    else:
        play(duration=duration)
