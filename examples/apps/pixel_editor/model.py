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


@dataclass
class Picture:
    pixels: list[int] = field(default_factory=lambda: [0] * 64)
    brush: int = 4
    brightness: int = 75

    def paint(self, pad: int, *, erase: bool = False) -> None:
        if not 0 <= pad < 64:
            raise ValueError("Pad must be between 0 and 63")
        self.pixels[pad] = 0 if erase or self.pixels[pad] == self.brush else self.brush

    def pad_colors(self) -> list[tuple[int, int, int, int]]:
        return [
            (
                pad,
                *(
                    round(channel * self.brightness / 100)
                    for channel in PALETTE[color][1]
                ),
            )
            for pad, color in enumerate(self.pixels)
        ]

    def clear(self) -> None:
        self.pixels = [0] * 64

    def save(self, path: Path) -> None:
        payload = {
            "version": 1,
            "pixels": self.pixels,
            "brush": self.brush,
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
            or data["version"] != 1
        ):
            raise ValueError("Expected a version-1 picture")
        pixels = data.get("pixels")
        if (
            not isinstance(pixels, list)
            or len(pixels) != 64
            or any(
                type(color) is not int or not 0 <= color < len(PALETTE)
                for color in pixels
            )
        ):
            raise ValueError("Expected 64 palette indices between 0 and 8")
        brush, brightness = data.get("brush"), data.get("brightness")
        if type(brush) is not int or not 1 <= brush < len(PALETTE):
            raise ValueError("Brush must be between 1 and 8")
        if type(brightness) is not int or not 10 <= brightness <= 100:
            raise ValueError("Brightness must be between 10 and 100")
        return cls(pixels=pixels, brush=brush, brightness=brightness)
