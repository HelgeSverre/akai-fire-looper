"""Picture state and JSON storage, independent of MIDI and screen drawing."""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PALETTE = (
    ("Off", (0, 0, 0)),
    ("Red", (127, 0, 0)),
    ("Orange", (127, 48, 0)),
    ("Yellow", (127, 127, 0)),
    ("Green", (0, 127, 0)),
    ("Cyan", (0, 127, 127)),
    ("Blue", (0, 0, 127)),
    ("Purple", (80, 0, 127)),
    ("White", (127, 127, 127)),
)


BLACK = (0, 0, 0)


@dataclass
class Picture:
    pixels: list[tuple[int, int, int]] = field(default_factory=lambda: [BLACK] * 64)
    brush: int = 4
    brightness: int = 75
    custom_color: tuple[int, int, int] | None = None

    @property
    def brush_color(self) -> tuple[int, int, int]:
        return (
            self.custom_color
            if self.custom_color is not None
            else PALETTE[self.brush][1]
        )

    @property
    def brush_name(self) -> str:
        return "Custom" if self.custom_color is not None else PALETTE[self.brush][0]

    def select_color(self, delta: int) -> None:
        self.brush = 1 + (self.brush - 1 + delta) % (len(PALETTE) - 1)
        self.custom_color = None

    def adjust_channel(self, channel: int, delta: int) -> None:
        color = list(self.brush_color)
        color[channel] = max(0, min(127, color[channel] + delta))
        if tuple(color) != self.brush_color:
            self.custom_color = tuple(color)

    def paint(self, pad: int, *, erase: bool = False) -> None:
        if not 0 <= pad < 64:
            raise ValueError("Pad must be between 0 and 63")
        self.pixels[pad] = (
            BLACK if erase or self.pixels[pad] == self.brush_color else self.brush_color
        )

    def pad_colors(self) -> list[tuple[int, int, int, int]]:
        return [
            (
                pad,
                *(round(channel * self.brightness / 100) for channel in color),
            )
            for pad, color in enumerate(self.pixels)
        ]

    def clear(self) -> None:
        self.pixels = [BLACK] * 64

    def save(self, path: Path) -> None:
        payload = {
            "version": 2,
            "pixels": self.pixels,
            "brush": self.brush,
            "custom_color": self.custom_color,
            "brightness": self.brightness,
        }
        # A failed write must not truncate the previous picture. The temporary
        # file shares the destination directory so replacement stays atomic.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path) -> "Picture":
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or type(data.get("version")) is not int
            or data["version"] not in (1, 2)
        ):
            raise ValueError("Expected a version-1 or version-2 picture")
        pixels = data.get("pixels")
        if not isinstance(pixels, list) or len(pixels) != 64:
            raise ValueError("Expected 64 pixels")
        custom_color = None
        if data["version"] == 1:
            if any(
                type(color) is not int or not 0 <= color < len(PALETTE)
                for color in pixels
            ):
                raise ValueError("Expected palette indices between 0 and 8")
            pixels = [PALETTE[color][1] for color in pixels]
        else:
            pixels = [cls._read_color(color) for color in pixels]
            if data.get("custom_color") is not None:
                custom_color = cls._read_color(data["custom_color"])
        brush, brightness = data.get("brush"), data.get("brightness")
        if type(brush) is not int or not 1 <= brush < len(PALETTE):
            raise ValueError("Brush must be between 1 and 8")
        if type(brightness) is not int or not 10 <= brightness <= 100:
            raise ValueError("Brightness must be between 10 and 100")
        return cls(
            pixels=pixels, brush=brush, brightness=brightness, custom_color=custom_color
        )

    @staticmethod
    def _read_color(value) -> tuple[int, int, int]:
        if (
            not isinstance(value, list)
            or len(value) != 3
            or any(
                type(channel) is not int or not 0 <= channel <= 127 for channel in value
            )
        ):
            raise ValueError("Expected three RGB levels between 0 and 127")
        return tuple(value)
