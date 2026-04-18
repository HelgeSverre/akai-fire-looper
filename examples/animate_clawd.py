"""Play the official Clawd mascot animation on the AKAI Fire's 128x64 OLED.

Source is the `clawd-magnifier.gif` (or any GIF you point it at) shipped with
the Claude desktop app. Each frame is cropped to the mascot's bounding box,
scaled to fit the OLED, and thresholded to 1-bit:

    orange body pixel -> ON  (lit)
    anything else    -> OFF (dark)

Run:

    uv run python examples/animate_clawd.py                     # use default gif path
    uv run python examples/animate_clawd.py /path/to/file.gif   # custom gif
    uv run python examples/animate_clawd.py --preview-only      # no hardware, just dump frames
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from akai_fire import Canvas, get_akai_fire


DEFAULT_GIF = "/Applications/Claude.app/Contents/Resources/ion-dist/images/install-hub/clawd-magnifier.gif"

OLED_W, OLED_H = Canvas.WIDTH, Canvas.HEIGHT
TARGET_FPS = 24
FRAME_DELAY = 1 / TARGET_FPS


def orange_mask(rgb: Image.Image) -> Image.Image:
    """Return a 1-bit PIL image where body (orange) pixels are 0 (ON)."""
    w, h = rgb.size
    out = Image.new("1", (w, h), 1)  # 1 = OFF
    px_in = rgb.load()
    px_out = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px_in[x, y]
            # orange body: strong red, modest green, low-ish blue; red dominates
            if r > 120 and r > g + 20 and r > b + 30 and g < 200:
                px_out[x, y] = 0  # ON
    return out


def frame_to_oled(frame_rgba: Image.Image) -> Image.Image:
    """Crop to mascot, fit into 128x64, threshold to 1-bit."""
    # crop to non-transparent region (mascot bbox)
    alpha = frame_rgba.split()[-1]
    bbox = alpha.getbbox()
    if bbox is None:
        return Image.new("1", (OLED_W, OLED_H), 1)
    cropped = frame_rgba.crop(bbox).convert("RGB")

    # fit into OLED preserving aspect; leave a 2px margin
    max_w, max_h = OLED_W - 4, OLED_H - 4
    scale = min(max_w / cropped.width, max_h / cropped.height)
    new_w = max(1, int(round(cropped.width * scale)))
    new_h = max(1, int(round(cropped.height * scale)))
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    mask = orange_mask(resized)

    # center on 128x64
    out = Image.new("1", (OLED_W, OLED_H), 1)
    ox = (OLED_W - new_w) // 2
    oy = (OLED_H - new_h) // 2
    out.paste(mask, (ox, oy))
    return out


def load_frames(gif_path: Path) -> list[Image.Image]:
    img = Image.open(gif_path)
    n = getattr(img, "n_frames", 1)
    frames = []
    for i in range(n):
        img.seek(i)
        frames.append(frame_to_oled(img.convert("RGBA")))
    return frames


def dump_previews(frames: list[Image.Image], outdir: Path, stride: int = 1) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(frames[::stride]):
        preview = f.resize((OLED_W * 4, OLED_H * 4), Image.NEAREST)
        preview.save(outdir / f"frame_{i:03d}.png")
    print(f"wrote {len(frames[::stride])} previews to {outdir}  (stride={stride})")


def make_contact_sheet(frames: list[Image.Image], out: Path, cols: int = 8, stride: int = 4) -> None:
    picks = frames[::stride]
    rows = (len(picks) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * OLED_W, rows * OLED_H), (40, 40, 40, 255))
    for i, f in enumerate(picks):
        sheet.paste(f.convert("RGBA"), ((i % cols) * OLED_W, (i // cols) * OLED_H))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(out)
    print(f"contact sheet -> {out} ({len(picks)} frames, stride={stride})")


def play_on_hardware(frames: list[Image.Image], fps: int = TARGET_FPS, duration: float | None = None) -> None:
    delay = 1 / fps
    deadline = None if duration is None else time.time() + duration
    with get_akai_fire() as fire:
        canvas = Canvas()
        try:
            while True:
                for f in frames:
                    canvas.image = f.copy()
                    fire.render_to_display(canvas)
                    time.sleep(delay)
                    if deadline is not None and time.time() >= deadline:
                        fire.clear_display()
                        return
        except KeyboardInterrupt:
            fire.clear_display()


def main() -> None:
    args = sys.argv[1:]
    preview_only = "--preview-only" in args
    duration = None
    for a in args:
        if a.startswith("--duration="):
            duration = float(a.split("=", 1)[1])
    args = [a for a in args if not a.startswith("--")]
    gif_path = Path(args[0]) if args else Path(DEFAULT_GIF)

    print(f"loading {gif_path}")
    frames = load_frames(gif_path)
    print(f"{len(frames)} frames, {OLED_W}x{OLED_H}")

    if preview_only:
        outdir = Path("/tmp/clawd-oled-frames")
        make_contact_sheet(frames, Path("/tmp/clawd-oled-sheet.png"), cols=10, stride=max(1, len(frames) // 40))
        dump_previews(frames[:8], outdir, stride=1)
    else:
        play_on_hardware(frames, duration=duration)


if __name__ == "__main__":
    main()
