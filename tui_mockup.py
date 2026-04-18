"""Pure visual mockup of the TUI AKAI Fire (iteration 2).

No akai_fire integration, no input handling — just a one-shot render so we
can iterate on the chassis look. Seeded with placeholder state.

Run:
    uv run python tui_mockup.py

Resize the terminal to at least 140 cols × 44 rows for best results.
"""

from __future__ import annotations

import colorsys
import sys

from PIL import Image, ImageDraw, ImageFont
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# ---------------------------------------------------------------------------
# Placeholder state
# ---------------------------------------------------------------------------

def sample_pad_colors() -> list[tuple[int, int, int]]:
    colors = []
    for row in range(4):
        for col in range(16):
            hue = (row * 16 + col) / 64
            r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.9)
            colors.append((int(r * 255), int(g * 255), int(b * 255)))
    for idx in (3, 7, 20, 42, 55):
        colors[idx] = (0, 0, 0)
    return colors


def sample_oled_bitmap() -> Image.Image:
    """A representative OLED frame: inverted title + log lines."""
    img = Image.new("1", (128, 64), 1)  # 1 = off / white background
    d = ImageDraw.Draw(img)
    try:
        body = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 11)
        head = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 9)
    except OSError:
        body = ImageFont.load_default()
        head = body
    # Inverted title bar
    d.rectangle([0, 0, 127, 11], fill=0)
    d.text((3, 1), "EVENT MONITOR", fill=1, font=head)
    # Log lines
    d.text((2, 16), "PAD 37 v100 +S", fill=0, font=body)
    d.text((2, 32), "BTN PLAY press", fill=0, font=body)
    d.text((2, 48), "ROT VOL +3", fill=0, font=body)
    return img


SAMPLE_PADS = sample_pad_colors()
SAMPLE_OLED = sample_oled_bitmap()
SAMPLE_BUTTONS_LIT = {"PLAY": True, "STEP": True}
SHIFT = True
ALT = False
FOCUS = ("pad", 37)
ROTARY_VALUES = {"VOL": 0.62, "PAN": 0.50, "FIL": 0.25, "RES": 0.80, "SEL": 0.10}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

OLED_FG = "rgb(255,160,50)"
OLED_BG = "black"
PANEL_BORDER = "grey42"


def render_oled_block(img: Image.Image) -> Text:
    """Render a 128×64 1-bit OLED as 64×16 cells using Unicode Braille
    chars — each cell encodes a 2-wide × 4-tall pixel block (8 dots).
    Proportional to the pad grid on screen."""
    pixels = img.load()
    w, h = img.size
    assert (w, h) == (128, 64)

    # Braille dot bit layout (ISO 11548-1):
    #   (x,y)  (x+1,y)     bits:  0  3
    #   (x,y+1)(x+1,y+1)          1  4
    #   (x,y+2)(x+1,y+2)          2  5
    #   (x,y+3)(x+1,y+3)          6  7
    DOT_BITS = [
        (0, 0, 0), (0, 1, 1), (0, 2, 2), (0, 3, 6),
        (1, 0, 3), (1, 1, 4), (1, 2, 5), (1, 3, 7),
    ]
    lit_style = f"{OLED_FG} on {OLED_BG}"
    empty_style = f"on {OLED_BG}"

    out = Text(no_wrap=True, overflow="ignore")
    for y in range(0, h, 4):
        for x in range(0, w, 2):
            mask = 0
            for dx, dy, bit in DOT_BITS:
                if pixels[x + dx, y + dy] == 0:
                    mask |= 1 << bit
            if mask == 0:
                out.append(" ", style=empty_style)
            else:
                out.append(chr(0x2800 + mask), style=lit_style)
        if y + 4 < h:
            out.append("\n")
    return out


def pad_cell(color: tuple[int, int, int], focused: bool) -> Text:
    r, g, b = color
    if max(color) < 16:
        if focused:
            return Text("[·]", style="bold reverse grey50")
        return Text(" · ", style="grey30")
    bg = f"rgb({r},{g},{b})"
    if focused:
        return Text(" ◉ ", style=f"bold black on {bg}")
    return Text("   ", style=f"on {bg}")


def render_pad_grid(colors: list[tuple[int, int, int]], focus_index: int | None) -> Text:
    out = Text(no_wrap=True)
    for row in range(4):
        for col in range(16):
            idx = row * 16 + col
            out.append_text(pad_cell(colors[idx], focus_index == idx))
            if col < 15:
                out.append(" ")
        if row < 3:
            out.append("\n")
    return out


def render_knob(name: str, value: float, focused: bool) -> Text:
    """Three-line knob tile: top arc / value bar / label."""
    bars = "▁▂▃▄▅▆▇█"
    bar_idx = min(len(bars) - 1, max(0, int(value * len(bars))))
    val_bar = bars[bar_idx] * 5
    face = "◉" if focused else "●"

    out = Text(no_wrap=True)
    style_face = "bold cyan" if focused else "white"
    style_label = "bold cyan" if focused else "grey70"
    out.append(f"  {face}  \n", style=style_face)
    out.append(f" {val_bar} \n", style="rgb(255,160,50)")
    out.append(f" {name:^5}", style=style_label)
    return out


def render_knobs_row(focus: tuple[str, int] | None) -> Text:
    names = ["VOL", "PAN", "FIL", "RES", "SEL"]
    focused_idx = focus[1] if focus and focus[0] == "rotary" else -1
    out = Text(no_wrap=True)
    for i, name in enumerate(names):
        # Stack each knob's 3 lines horizontally by rendering a small 3x7 block
        knob = render_knob(name, ROTARY_VALUES[name], focused_idx == i)
        # We need to interleave; simplest: render into a list of lines and
        # concatenate side-by-side.
        knob_lines = str(knob).split("\n")
        if i == 0:
            result_lines = knob_lines
        else:
            sep = "  "
            result_lines = [a + sep + b for a, b in zip(result_lines, knob_lines)]
    # Rebuild as Text with styles re-applied. Because we lose styles in the
    # hack above, just rebuild cleanly by rendering side-by-side via Columns.
    return out


def render_knobs_row_columns(focus: tuple[str, int] | None) -> Table:
    names = ["VOL", "PAN", "FIL", "RES", "SEL"]
    focused_idx = focus[1] if focus and focus[0] == "rotary" else -1
    t = Table.grid(padding=(0, 2), expand=False)
    for _ in names:
        t.add_column(justify="center")
    t.add_row(*(render_knob(n, ROTARY_VALUES[n], focused_idx == i) for i, n in enumerate(names)))
    return t


def render_button(label: str, lit: bool, focused: bool, width: int = 6) -> Text:
    text = f" {label:^{width-2}} "
    if lit and focused:
        return Text(text, style="bold black on yellow")
    if lit:
        return Text(text, style="black on bright_yellow")
    if focused:
        return Text(text, style="bold reverse")
    return Text(text, style="bright_white on grey23")


def render_button_row(labels: list[str], focus_idx: int, width: int = 6) -> Text:
    out = Text(no_wrap=True)
    for i, lbl in enumerate(labels):
        out.append_text(
            render_button(lbl, SAMPLE_BUTTONS_LIT.get(lbl, False), focus_idx == i, width)
        )
        if i < len(labels) - 1:
            out.append(" ")
    return out


def render_mute_solo_column(focus: tuple[str, int] | None) -> Text:
    focused_idx = focus[1] if focus and focus[0] == "mutesolo" else -1
    out = Text(no_wrap=True)
    for i in range(4):
        out.append_text(render_button(f"M{i+1}", False, focused_idx == i*2, width=4))
        out.append("  ")
        out.append_text(render_button(f"S{i+1}", False, focused_idx == i*2+1, width=4))
        if i < 3:
            out.append("\n")
    return out


def render_pattern_controls(focus: tuple[str, int] | None) -> Text:
    idx = focus[1] if focus and focus[0] == "pattern" else -1
    out = Text(no_wrap=True)
    out.append_text(render_button("<",  False, idx == 0, width=4))
    out.append(" ")
    out.append_text(render_button(">",  False, idx == 1, width=4))
    out.append("\n")
    out.append_text(render_button("▲",  False, idx == 2, width=4))
    out.append(" ")
    out.append_text(render_button("▼",  False, idx == 3, width=4))
    return out


def render_modifier_strip() -> Text:
    out = Text()
    def pill(name: str, on: bool) -> None:
        if on:
            out.append(f" {name} ", style="bold black on yellow")
        else:
            out.append(f" {name} ", style="dim")
    pill("SHIFT", SHIFT)
    out.append(" ")
    pill("ALT", ALT)
    return out


def render_footer(focus: tuple[str, int]) -> Text:
    t = Text()
    t.append(f" focus: {focus[0].upper()} #{focus[1]} ", style="black on cyan")
    t.append("   last: ", style="dim")
    t.append("PAD 37 v100 +S", style="bold")
    t.append("     ")
    t.append("Tab", style="bold")
    t.append("=region  ", style="dim")
    t.append("←→↑↓", style="bold")
    t.append("=nav  ", style="dim")
    t.append("Enter", style="bold")
    t.append("=press  ", style="dim")
    t.append("s/a", style="bold")
    t.append("=mods  ", style="dim")
    t.append("Ctrl+Q", style="bold")
    t.append("=quit", style="dim")
    return t


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------

def build_view() -> Group:
    oled_panel = Panel(
        render_oled_block(SAMPLE_OLED),
        title="[bold]OLED 128×64[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
        width=68,   # 64 cells of content + 2 border + 2 padding
    )

    knobs_panel = Panel(
        render_knobs_row_columns(FOCUS),
        title="[bold]knobs[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )

    top_row = Table.grid(expand=False, padding=(0, 2))
    top_row.add_column()
    top_row.add_column()
    top_row.add_row(oled_panel, knobs_panel)

    # --- Button bar ---
    focus_key = lambda region: FOCUS[1] if FOCUS[0] == region else -1
    button_bar = Table.grid(expand=False, padding=(0, 3))
    button_bar.add_column()
    button_bar.add_column()
    button_bar.add_column()
    button_bar.add_row(
        render_button_row(["BANK", "SEL"], focus_key("btn_bank")),
        render_button_row(["STEP", "NOTE", "DRUM", "PERF"], focus_key("btn_mode")),
        render_button_row(["PAT", "PLAY", "STOP", "REC"], focus_key("btn_transport")),
    )

    # --- Pad grid row ---
    pad_panel = Panel(
        render_pad_grid(SAMPLE_PADS, FOCUS[1] if FOCUS[0] == "pad" else None),
        title="[bold]pads 16×4[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )

    mute_solo_panel = Panel(
        render_mute_solo_column(FOCUS),
        title="[bold]mute/solo[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )

    pattern_panel = Panel(
        render_pattern_controls(FOCUS),
        title="[bold]pattern[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )

    grid_row = Table.grid(expand=False, padding=(0, 1))
    grid_row.add_column()
    grid_row.add_column()
    grid_row.add_column()
    grid_row.add_row(mute_solo_panel, pad_panel, pattern_panel)

    # --- Modifier + bottom buttons ---
    mod_strip = Table.grid(expand=False, padding=(0, 4))
    mod_strip.add_column()
    mod_strip.add_column()
    mod_strip.add_row(
        render_modifier_strip(),
        render_button_row(["BROWSER"], focus_key("btn_bottom"), width=11),
    )

    return Group(
        Align.left(top_row),
        Text(""),
        button_bar,
        Text(""),
        grid_row,
        Text(""),
        mod_strip,
        Text(""),
        render_footer(FOCUS),
    )


def main() -> int:
    # Support --svg=<path> to dump a rendered SVG (captures colors)
    svg_out = None
    for a in sys.argv[1:]:
        if a.startswith("--svg="):
            svg_out = a.split("=", 1)[1]

    if svg_out:
        console = Console(record=True, width=160, force_terminal=True)
        console.print(build_view())
        console.save_svg(svg_out, title="AKAI Fire TUI Mockup")
        print(f"wrote {svg_out}")
        return 0

    console = Console()
    if console.width < 140 or console.height < 40:
        console.print(
            f"[yellow]terminal is {console.width}x{console.height}; "
            "try 140×44 or larger for a non-wrapped view.[/]"
        )
    console.print(build_view())
    return 0


if __name__ == "__main__":
    sys.exit(main())
