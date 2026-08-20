"""
Mock objects for testing AKAI Fire applications.

This module provides lightweight mock implementations that don't require
pygame or hardware, suitable for headless testing.

Classes:
    MockCanvas: Canvas with operation recording and BMP screenshot export
    MockAkaiFire: Mock controller with state tracking and event simulation
"""

from typing import List, Dict, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
import time
import struct
import os

from akai_fire.errors import InvalidParameterError

# =============================================================================
# Data Classes for Event Recording
# =============================================================================


@dataclass
class PadEvent:
    """Recorded pad color change event."""

    pad_index: int
    color: Tuple[int, int, int]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ButtonEvent:
    """Recorded button LED event."""

    button_id: int
    value: int
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# MockCanvas
# =============================================================================


class MockCanvas:
    """
    Mock Canvas for testing without PIL dependency.

    Mirrors the real :class:`akai_fire.canvas.Canvas` API *and* its
    pixel-value convention: the buffer starts all-``1`` (unlit) and
    drawing with the default ``color=0`` lights pixels — on hardware a
    black (0) PIL pixel is an ON OLED pixel. Screenshots render
    pixel==0 as lit so visual-regression baselines match device output.

    Provides all the same methods as the real Canvas class but records
    operations for later verification. Also supports saving screenshots
    as BMP files for visual regression testing (similar to Playwright).

    Features:
        - Records all drawing operations for assertion
        - Maintains pixel buffer for screenshot capture
        - Can save to BMP without PIL dependency
        - Optional PIL integration for enhanced screenshots

    Example:
        >>> canvas = MockCanvas()
        >>> canvas.draw_text("Hello", 10, 10)
        >>> canvas.draw_rect(0, 0, 128, 64)
        >>> assert len(canvas.text_drawn) == 1
        >>> canvas.save_screenshot("test_output/hello.bmp")
    """

    # Standard dimensions (matching real AKAI Fire OLED)
    WIDTH = 128
    HEIGHT = 64

    # Typography constants for consistent spacing (matching real Canvas)
    HEADER_HEIGHT = 16  # Standard header height
    TEXT_MARGIN_Y = 3  # Top margin for header text
    CONTENT_GAP = 2  # Gap between header and content
    CONTENT_START = HEADER_HEIGHT + CONTENT_GAP  # Y=18

    def __init__(self, width: int = 128, height: int = 64):
        """
        Initialize mock canvas.

        Args:
            width: Canvas width in pixels (default 128 for AKAI Fire OLED)
            height: Canvas height in pixels (default 64 for AKAI Fire OLED)
        """
        self.width = width
        self.height = height
        # Start unlit (1), matching real Canvas's Image.new("1", ..., 1).
        self.pixels: List[List[int]] = [[1] * width for _ in range(height)]

        # Operation recording for assertions
        self.text_drawn: List[Tuple[str, int, int]] = []
        self.rects_drawn: List[Tuple[int, int, int, int, bool]] = (
            []
        )  # (x, y, w, h, filled)
        self.lines_drawn: List[Tuple[int, int, int, int]] = []  # (x0, y0, x1, y1)
        self.circles_drawn: List[Tuple[int, int, int, bool]] = []  # (cx, cy, r, filled)
        self.clear_count = 0
        self._screenshot_count = 0

    # =========================================================================
    # Basic Drawing Operations
    # =========================================================================

    def clear(self, color: int = 1):
        """
        Clear the canvas and reset operation history.

        Args:
            color: Fill color (0=black, 1=white, default=white like real Canvas)
        """
        self.pixels = [[color] * self.width for _ in range(self.height)]
        self.text_drawn.clear()
        self.rects_drawn.clear()
        self.lines_drawn.clear()
        self.circles_drawn.clear()
        self.clear_count += 1

    def clone(self) -> "MockCanvas":
        """
        Create a copy of the current canvas.

        Returns:
            New MockCanvas with identical content
        """
        cloned = MockCanvas(self.width, self.height)
        # Copy pixel data
        for y in range(self.height):
            for x in range(self.width):
                cloned.pixels[y][x] = self.pixels[y][x]
        # Copy operation history
        cloned.text_drawn = list(self.text_drawn)
        cloned.rects_drawn = list(self.rects_drawn)
        cloned.circles_drawn = list(self.circles_drawn)
        cloned.lines_drawn = list(self.lines_drawn)
        return cloned

    def set_pixel(self, x: int, y: int, color: int = 0):
        """
        Set a pixel value (0=lit/ON, 1=unlit — matching real Canvas,
        where a black PIL pixel is an ON OLED pixel).

        Args:
            x: X coordinate
            y: Y coordinate
            color: Pixel value (0 or 1)
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def get_pixel(self, x: int, y: int) -> Optional[int]:
        """
        Get a pixel value.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Pixel value (0 or 1), or None if out of bounds
            (matching real Canvas).
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y][x]
        return None

    # =========================================================================
    # Text Drawing
    # =========================================================================

    def draw_text(self, text: str, x: int, y: int, font=None, color: int = 0):
        """
        Draw text and record the operation.

        Args:
            text: Text to draw
            x: X coordinate
            y: Y coordinate
            font: Font (ignored in mock, for API compatibility)
            color: Text color (0=lit, 1=unlit; default 0 like real Canvas)
        """
        self.text_drawn.append((text, x, y))
        self._render_simple_text(text, x, y, color)

    def _render_simple_text(self, text: str, x: int, y: int, color: int = 0):
        """Render text using a simple bitmap representation for screenshots."""
        char_width = 5
        char_height = 7
        for i, char in enumerate(text):
            if char != " ":
                cx = x + i * char_width
                for dy in range(min(char_height, 6)):
                    for dx in range(min(char_width - 1, 4)):
                        self.set_pixel(cx + dx, y + dy, color)

    # =========================================================================
    # Rectangle Drawing
    # =========================================================================

    def draw_rect(self, x: int, y: int, width: int, height: int, color: int = 0):
        """
        Draw rectangle outline and record.

        Args:
            x, y: Top-left corner
            width, height: Size
            color: Line color (0=lit, default 0 like real Canvas)
        """
        self.rects_drawn.append((x, y, width, height, False))
        for dx in range(width):
            self.set_pixel(x + dx, y, color)
            self.set_pixel(x + dx, y + height - 1, color)
        for dy in range(height):
            self.set_pixel(x, y + dy, color)
            self.set_pixel(x + width - 1, y + dy, color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: int = 0):
        """
        Draw filled rectangle and record.

        Args:
            x, y: Top-left corner
            width, height: Size
            color: Fill color (0=lit, default 0 like real Canvas)
        """
        self.rects_drawn.append((x, y, width, height, True))
        for dy in range(height):
            for dx in range(width):
                self.set_pixel(x + dx, y + dy, color)

    def draw_rectangle(self, x: int, y: int, w: int, h: int, color: int = 1):
        """Alias for draw_rect."""
        self.draw_rect(x, y, w, h, color)

    def fill_rectangle(self, x: int, y: int, w: int, h: int, color: int = 1):
        """Alias for fill_rect."""
        self.fill_rect(x, y, w, h, color)

    def draw_border(self, thickness: int = 1, color: int = 0):
        """
        Draw border around canvas.

        Args:
            thickness: Border thickness in pixels
            color: Border color (0 or 1)
        """
        for t in range(thickness):
            self.draw_rect(t, t, self.width - 2 * t, self.height - 2 * t, color)

    # =========================================================================
    # Line Drawing
    # =========================================================================

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw horizontal line."""
        self.lines_drawn.append((x, y, x + length, y))
        for dx in range(length):
            self.set_pixel(x + dx, y, color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw vertical line."""
        self.lines_drawn.append((x, y, x, y + length))
        for dy in range(length):
            self.set_pixel(x, y + dy, color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 0):
        """
        Draw line between two points using Bresenham's algorithm.

        Args:
            x0, y0: Start point
            x1, y1: End point
            color: Line color (0 or 1)
        """
        self.lines_drawn.append((x0, y0, x1, y1))
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    # =========================================================================
    # Circle Drawing
    # =========================================================================

    def draw_circle(self, cx: int, cy: int, radius: int, color: int = 0):
        """
        Draw circle outline using midpoint algorithm.

        Args:
            cx, cy: Center point
            radius: Circle radius
            color: Line color (0 or 1)
        """
        self.circles_drawn.append((cx, cy, radius, False))
        x, y = radius, 0
        err = 0

        while x >= y:
            self.set_pixel(cx + x, cy + y, color)
            self.set_pixel(cx + y, cy + x, color)
            self.set_pixel(cx - y, cy + x, color)
            self.set_pixel(cx - x, cy + y, color)
            self.set_pixel(cx - x, cy - y, color)
            self.set_pixel(cx - y, cy - x, color)
            self.set_pixel(cx + y, cy - x, color)
            self.set_pixel(cx + x, cy - y, color)

            y += 1
            err += 1 + 2 * y
            if 2 * (err - x) + 1 > 0:
                x -= 1
                err += 1 - 2 * x

    def fill_circle(self, cx: int, cy: int, radius: int, color: int = 0):
        """
        Draw filled circle.

        Args:
            cx, cy: Center point
            radius: Circle radius
            color: Fill color (0 or 1)
        """
        self.circles_drawn.append((cx, cy, radius, True))
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if x * x + y * y <= radius * radius:
                    self.set_pixel(cx + x, cy + y, color)

    # =========================================================================
    # High-Level Drawing Methods (ScreenManager compatibility)
    # =========================================================================

    def draw_page(self, title: str, lines: list, header_inverted: bool = True):
        """Draw a page layout (mirrors real Canvas geometry and colors)."""
        if header_inverted:
            self.fill_rect(0, 0, self.width, self.HEADER_HEIGHT, color=0)
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)
        else:
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=0)
            self.draw_horizontal_line(0, self.HEADER_HEIGHT, self.width, color=0)
        y_offset = self.CONTENT_START
        line_height = 12
        for i, line in enumerate(lines):
            if y_offset + line_height > self.height:
                break
            self.draw_text(line, 2, y_offset + (i * line_height))

    def draw_value_page(
        self,
        title: str,
        value: Any,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        show_bar: bool = True,
    ):
        """Draw a value display page (mirrors real Canvas signature)."""
        self.fill_rect(0, 0, self.width, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)
        self.draw_text(str(value), 2, 20, color=0)
        if show_bar and min_val is not None and max_val is not None:
            bar_y = 40
            bar_height = 8
            if max_val == min_val:
                normalized = 1.0 if float(value) >= float(max_val) else 0.0
            else:
                normalized = (float(value) - min_val) / (max_val - min_val)
            normalized = max(0.0, min(1.0, normalized))
            bar_width = int(normalized * (self.width - 4))
            self.draw_rect(2, bar_y, self.width - 4, bar_height)
            self.fill_rect(2, bar_y, bar_width, bar_height)

    def draw_menu(self, title: str, items: list, selected_index: int):
        """Draw a menu with a highlighted selection (mirrors real Canvas)."""
        self.fill_rect(0, 0, self.width, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)
        y_offset = self.CONTENT_START
        line_height = 12
        visible_items = min(4, len(items))
        start_idx = max(0, min(selected_index - 1, len(items) - visible_items))
        for i in range(visible_items):
            idx = start_idx + i
            if idx >= len(items):
                break
            if idx == selected_index:
                self.fill_rect(
                    0, y_offset + (i * line_height), self.width, line_height, color=0
                )
                self.draw_text(items[idx], 4, y_offset + (i * line_height), color=1)
            else:
                self.draw_text(items[idx], 4, y_offset + (i * line_height))

    def draw_grid_info(
        self,
        title: str,
        rows: int,
        cols: int,
        cell_info: Optional[list] = None,
    ):
        """Draw a grid outline plus ``(row, col, text)`` cells
        (mirrors real Canvas signature)."""
        cell_info = cell_info or []
        self.fill_rect(0, 0, self.width, 12, color=0)
        self.draw_text(title, 2, 2, color=1)
        cell_width = (self.width - 4) // cols
        cell_height = (self.height - 20) // rows
        for row in range(rows + 1):
            self.draw_horizontal_line(2, 16 + (row * cell_height), self.width - 4)
        for col in range(cols + 1):
            self.draw_vertical_line(2 + (col * cell_width), 16, rows * cell_height)
        for row, col, text in cell_info:
            self.draw_text(
                text, 2 + (col * cell_width) + 2, 16 + (row * cell_height) + 2
            )

    def draw_split_screen(self, title: str, left_content: list, right_content: list):
        """Draw a split-screen layout (mirrors real Canvas signature)."""
        self.fill_rect(0, 0, self.width, 12, color=0)
        self.draw_text(title, 2, 2, color=1)
        mid_x = self.width // 2
        self.draw_vertical_line(mid_x, 15, self.height - 15)
        y_offset = 15
        line_height = 12
        for i, line in enumerate(left_content):
            if y_offset + (i * line_height) + line_height > self.height:
                break
            self.draw_text(line, 2, y_offset + (i * line_height))
        for i, line in enumerate(right_content):
            if y_offset + (i * line_height) + line_height > self.height:
                break
            self.draw_text(line, mid_x + 2, y_offset + (i * line_height))

    # =========================================================================
    # Screenshot / BMP Export
    # =========================================================================

    def save_screenshot(self, path: str, scale: int = 4) -> str:
        """
        Save the current canvas state as a BMP image.

        Similar to Playwright's screenshot functionality - useful for
        visual regression testing or debugging test failures.

        Args:
            path: Output file path (should end in .bmp)
            scale: Scale factor for the image (default 4x for visibility)

        Returns:
            The path where the screenshot was saved
        """
        self._screenshot_count += 1

        # Ensure directory exists
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Try PIL first for better quality
        try:
            return self._save_with_pil(path, scale)
        except ImportError:
            return self._save_raw_bmp(path, scale)

    def _save_with_pil(self, path: str, scale: int) -> str:
        """Save using PIL for better quality screenshots."""
        from PIL import Image

        # Create scaled monochrome image (lit pixels bright on black).
        # pixel==0 is ON on the OLED (black PIL pixel = lit LED), so it
        # renders white here — matching real device output.
        img = Image.new("RGB", (self.width * scale, self.height * scale), (0, 0, 0))
        pixels_out = img.load()

        for y in range(self.height):
            for x in range(self.width):
                if not self.pixels[y][x]:
                    # Lit pixel (monochrome like AKAI Fire OLED)
                    for sy in range(scale):
                        for sx in range(scale):
                            pixels_out[x * scale + sx, y * scale + sy] = (255, 255, 255)

        img.save(path)
        return path

    def _save_raw_bmp(self, path: str, scale: int) -> str:
        """Save as raw BMP without PIL dependency."""
        scaled_width = self.width * scale
        scaled_height = self.height * scale

        # BMP row size must be multiple of 4
        row_size = ((scaled_width * 3 + 3) // 4) * 4
        padding = row_size - scaled_width * 3

        # File size
        pixel_data_size = row_size * scaled_height
        file_size = 54 + pixel_data_size  # Header + pixels

        with open(path, "wb") as f:
            # BMP Header (14 bytes)
            f.write(b"BM")  # Magic
            f.write(struct.pack("<I", file_size))  # File size
            f.write(struct.pack("<HH", 0, 0))  # Reserved
            f.write(struct.pack("<I", 54))  # Pixel data offset

            # DIB Header (40 bytes)
            f.write(struct.pack("<I", 40))  # Header size
            f.write(struct.pack("<i", scaled_width))  # Width
            f.write(struct.pack("<i", scaled_height))  # Height (positive = bottom-up)
            f.write(struct.pack("<HH", 1, 24))  # Planes, bits per pixel
            f.write(struct.pack("<I", 0))  # Compression (none)
            f.write(struct.pack("<I", pixel_data_size))  # Image size
            f.write(struct.pack("<ii", 2835, 2835))  # Pixels per meter
            f.write(struct.pack("<II", 0, 0))  # Colors

            # Pixel data (bottom-up) - lit pixels bright on black
            # (pixel==0 is ON on the OLED, matching real device output)
            for y in range(scaled_height - 1, -1, -1):
                for x in range(scaled_width):
                    src_x = x // scale
                    src_y = y // scale
                    if not self.pixels[src_y][src_x]:
                        # Lit pixel (BGR format)
                        f.write(bytes([255, 255, 255]))
                    else:
                        # Unlit pixel
                        f.write(bytes([0, 0, 0]))
                # Row padding
                f.write(bytes(padding))

        return path

    def auto_screenshot(self, directory: str, prefix: str = "screen") -> str:
        """
        Automatically save a numbered screenshot.

        Args:
            directory: Directory to save screenshots
            prefix: Filename prefix

        Returns:
            Path to saved screenshot
        """
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{prefix}_{self._screenshot_count:04d}.bmp")
        return self.save_screenshot(path)

    # =========================================================================
    # Assertion Helpers
    # =========================================================================

    def assert_pixel(self, x: int, y: int, expected: int):
        """Assert a pixel has a specific value."""
        actual = self.get_pixel(x, y)
        assert actual == expected, f"Pixel ({x},{y}): expected {expected}, got {actual}"

    def assert_text_drawn(self, text: str, x: int = None, y: int = None):
        """Assert text was drawn, optionally at specific position."""
        for drawn_text, dx, dy in self.text_drawn:
            if drawn_text == text:
                if x is not None and dx != x:
                    continue
                if y is not None and dy != y:
                    continue
                return
        raise AssertionError(f"Text '{text}' not found at ({x}, {y})")

    def assert_rect_drawn(self, x: int, y: int, w: int, h: int, filled: bool = False):
        """Assert a rectangle was drawn."""
        expected = (x, y, w, h, filled)
        assert expected in self.rects_drawn, f"Rectangle {expected} not found"

    def get_text_at_row(self, row: int) -> Optional[str]:
        """Get text drawn at approximately the specified row."""
        # Approximate row height is 10 pixels, starting at y=14
        target_y = 14 + row * 10
        for text, x, y in self.text_drawn:
            if abs(y - target_y) < 5:
                return text
        return None


# =============================================================================
# MockAkaiFire
# =============================================================================


from akai_fire.device import AkaiFireDevice


class MockAkaiFire(AkaiFireDevice):
    """Lightweight headless mock of AkaiFire for testing.

    Unlike the pygame MockAkaiFire, this doesn't create any windows
    and is suitable for headless CI.

    Features:
        - Records all pad color changes (``pad_events``)
        - Records all button LED changes (``button_events``)
        - ``simulate_*`` helpers for programmatic event injection
        - ``assert_*`` helpers for verifying visual state
        - Connection simulation for testing connect/disconnect scenarios

    Inherits MIDI constants, modifier state, pad-geometry utilities, and
    solo-button lookup from :class:`AkaiFireDevice`.

    Example:
        >>> fire = MockAkaiFire()
        >>> @fire.on_pad()
        ... def on_pad(pad_index, velocity):
        ...     fire.set_pad_color(pad_index, 127, 0, 0)
        >>> fire.simulate_pad_press(5, velocity=100)
        >>> fire.assert_pad_color(5, (127, 0, 0))
    """

    def __init__(self):
        """Initialize mock controller."""
        super().__init__()  # installs self._lock + modifier flags

        # Canvas is exposed as ``self.canvas`` so it matches the base
        # class's get_canvas() / render_to_display() contract.
        self.canvas = MockCanvas()

        # State tracking
        self.pad_colors: List[Tuple[int, int, int]] = [(0, 0, 0)] * 64
        self.button_leds: Dict[int, int] = {}
        self.track_leds: Dict[int, int] = {}
        self.control_bank_state = 0

        # Event history for assertions
        self.pad_events: List[PadEvent] = []
        self.button_events: List[ButtonEvent] = []
        self.render_count = 0

        # Listener registries (pad_listeners / button_listeners /
        # rotary_listeners / rotary_touch_listeners) are provided by
        # AkaiFireDevice.__init__.

        # Connection state simulation
        self._connected = True
        self._connection_error = None

        # Closed state
        self._closed = False

    # =========================================================================
    # Canvas Access
    # =========================================================================

    # get_canvas is inherited from AkaiFireDevice.

    def new_canvas(self) -> MockCanvas:
        """Create a new mock canvas."""
        self.canvas = MockCanvas()
        return self.canvas

    # =========================================================================
    # Pad Control
    # =========================================================================

    def set_pad_color(self, pad_index: int, r: int, g: int, b: int) -> bool:
        """
        Set pad color and record the event.

        Args:
            pad_index: Pad index (0-63)
            r, g, b: Color components (0-127)

        Returns:
            True if successful

        Raises:
            InvalidParameterError: If pad index is out of range
                (matching real hardware).
        """
        if not isinstance(pad_index, int) or not (0 <= pad_index <= 63):
            raise InvalidParameterError(
                f"Pad index must be integer 0-63, got: {pad_index}"
            )
        if not self._connected:
            return False
        # Clamp values
        r = max(0, min(127, r))
        g = max(0, min(127, g))
        b = max(0, min(127, b))
        color = (r, g, b)
        self.pad_colors[pad_index] = color
        self.pad_events.append(PadEvent(pad_index, color))
        return True

    def set_pad_color_fast(self, pad_index: int, r: int, g: int, b: int) -> bool:
        """
        Fast path for setting pad color - assumes valid inputs.

        Args:
            pad_index: Pad index (0-63)
            r, g, b: Color components (0-127)

        Returns:
            True if successful
        """
        return self.set_pad_color(pad_index, r, g, b)

    def set_multiple_pad_colors(
        self, pad_colors: List[Tuple[int, int, int, int]]
    ) -> bool:
        """
        Set multiple pad colors efficiently.

        Args:
            pad_colors: List of (pad_index, r, g, b) tuples

        Returns:
            True if successful
        """
        if not self._connected:
            return False
        for pad_data in pad_colors:
            if len(pad_data) == 4:
                index, r, g, b = pad_data
                self.set_pad_color(index, r, g, b)
        return True

    def set_all_pads(self, color: Tuple[int, int, int]) -> bool:
        """
        Set all pads to the same color.

        Args:
            color: Tuple of (r, g, b) values (0-127)

        Returns:
            True if successful
        """
        if not self._connected:
            return False
        r, g, b = color
        for i in range(64):
            self.set_pad_color(i, r, g, b)
        return True

    def reset_pads(self, r: int = 0, g: int = 0, b: int = 0) -> bool:
        """
        Reset all pads to a specific color (default black).

        Args:
            r, g, b: Color components (0-127)

        Returns:
            True if successful
        """
        return self.set_all_pads((r, g, b))

    def clear_pad(self, pad_index: int) -> bool:
        """Clear a single pad to black."""
        return self.set_pad_color(pad_index, 0, 0, 0)

    def clear_all_pads(self) -> bool:
        """Clear all pad colors to black."""
        return self.set_all_pads((0, 0, 0))

    # =========================================================================
    # Button/LED Control
    # =========================================================================

    def set_button_led(self, button_id: int, value: int) -> bool:
        """Set button LED and record the event.

        Raises:
            InvalidParameterError: If button_id is not an addressable
                LED button (matching real hardware).
        """
        if not self._connected:
            return False
        if button_id not in self.BUTTON_LED_IDS:
            raise InvalidParameterError(
                f"Invalid button ID: {button_id}. "
                f"Valid buttons: {sorted(self.BUTTON_LED_IDS)}"
            )
        value = max(0, min(2, value))
        self.button_leds[button_id] = value
        self.button_events.append(ButtonEvent(button_id, value))
        return True

    def clear_all_button_leds(self) -> bool:
        """Clear all button LEDs."""
        if not self._connected:
            return False
        self.button_leds.clear()
        return True

    def set_track_led(self, track: int, value: int) -> bool:
        """Set track LED (1-4). ``value`` is a RECTANGLE_LED_* constant (0-4)."""
        if not self._connected:
            return False
        if not (1 <= track <= 4):
            return False
        value = max(0, min(4, value))
        self.track_leds[track] = value
        return True

    def clear_track_led(self, track: int) -> bool:
        """Clear a single track LED."""
        return self.set_track_led(track, 0)

    def clear_all_track_leds(self) -> bool:
        """Clear all track LEDs."""
        if not self._connected:
            return False
        self.track_leds.clear()
        return True

    def set_control_bank_leds(self, state: int) -> bool:
        """Set control bank LED state."""
        if not self._connected:
            return False
        self.control_bank_state = state
        return True

    def clear_control_bank_leds(self) -> bool:
        """Clear control bank LEDs."""
        return self.set_control_bank_leds(0)

    def clear_all(self) -> bool:
        """Clear all LEDs and pads."""
        success = True
        success &= self.clear_all_pads()
        success &= self.clear_all_button_leds()
        success &= self.clear_all_track_leds()
        success &= self.clear_control_bank_leds()
        return success

    # =========================================================================
    # Display Control
    # =========================================================================

    # render_to_display / clear_display are inherited from AkaiFireDevice.
    # render_count is bumped in _deliver_display.

    def _deliver_display(self, canvas) -> None:
        """Record a render call (for assertion in tests)."""
        self.render_count += 1

    def render_to_bmp(self, output_path: str, image_format: str = "BMP") -> str:
        """Save canvas to BMP file via MockCanvas's screenshot helper."""
        return self.canvas.save_screenshot(output_path)

    # =========================================================================
    # Modifier State (is_shift_pressed / is_alt_pressed / properties
    # are inherited from AkaiFireDevice)
    # =========================================================================

    def _set_shift_pressed(self, pressed: bool):
        """Internal method to set shift state (for testing)."""
        self._shift_pressed = pressed

    def _set_alt_pressed(self, pressed: bool):
        """Internal method to set alt state (for testing)."""
        self._alt_pressed = pressed

    # =========================================================================
    # Connection Simulation
    # =========================================================================

    def is_connected(self) -> bool:
        """Check if controller is connected."""
        return self._connected and not self._closed

    def disconnect(self):
        """
        Simulate disconnection for testing error handling.

        After calling this, all LED/pad operations will return False.
        """
        self._connected = False
        self._connection_error = "Simulated disconnection"

    def connect(self):
        """
        Simulate reconnection.

        Restores normal operation after disconnect().
        """
        self._connected = True
        self._connection_error = None

    def reconnect(self) -> bool:
        """
        Attempt to reconnect (simulation).

        Returns:
            True if reconnection successful
        """
        self._connected = True
        self._connection_error = None
        return True

    def get_connection_error(self) -> Optional[str]:
        """Get the last connection error message."""
        return self._connection_error

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start_listening(self):
        """Start listening for events (no-op in mock)."""
        pass

    def close(self):
        """Close the mock controller."""
        self._closed = True
        self._connected = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    # =========================================================================
    # Utility Methods (pad_position, get_pad_column, get_pad_row,
    # get_solo_index, list_midi_ports are inherited from AkaiFireDevice)
    # =========================================================================

    # =========================================================================
    # Event Decorators
    # =========================================================================

    # Decorators (on_pad / on_button / on_rotary_turn / on_rotary_touch
    # / on_solo) and listener adders (add_listener / add_global_listener
    # / add_button_listener / add_rotary_listener /
    # add_rotary_touch_listener) are inherited from AkaiFireDevice.

    # =========================================================================
    # Event Simulation (for testing) — thin wrappers over the base's
    # _dispatch_* helpers. Modifier-first latching lives in
    # _dispatch_button on the base.
    # =========================================================================

    def simulate_pad_press(self, pad_index: int, velocity: int = 100):
        """Simulate a pad press. Global handlers get (pad_index, velocity)."""
        self._dispatch_pad(pad_index, velocity)

    def simulate_pad_release(self, pad_index: int):
        """Simulate a pad release (velocity=0)."""
        self._dispatch_pad(pad_index, 0)

    def simulate_button_press(self, button_id: int):
        """Simulate a button press. Modifiers are latched automatically."""
        self._dispatch_button(button_id, "press")

    def simulate_button_release(self, button_id: int):
        """Simulate a button release."""
        self._dispatch_button(button_id, "release")

    def simulate_rotary_turn(self, rotary_id: int, direction: str, velocity: int = 1):
        """Simulate a rotary turn. ``left``/``right`` alias to CCW/CW."""
        if direction == "left":
            direction = "counterclockwise"
        elif direction == "right":
            direction = "clockwise"
        self._dispatch_rotary_turn(rotary_id, direction, velocity)

    def simulate_rotary_touch(self, rotary_id: int):
        """Simulate a rotary touch."""
        self._dispatch_rotary_touch(rotary_id, "touch")

    def simulate_rotary_release(self, rotary_id: int):
        """Simulate a rotary release."""
        self._dispatch_rotary_touch(rotary_id, "release")

    def simulate_solo_press(self, index: int):
        """Simulate a solo button press. ``index`` is 1..4."""
        if 1 <= index <= 4:
            self._dispatch_button(self.SOLO_BUTTONS[index], "press")

    def simulate_solo_release(self, index: int):
        """Simulate a solo button release. ``index`` is 1..4."""
        if 1 <= index <= 4:
            self._dispatch_button(self.SOLO_BUTTONS[index], "release")

    # =========================================================================
    # Assertion Helpers
    # =========================================================================

    def assert_pad_color(self, pad_index: int, expected_color: Tuple[int, int, int]):
        """
        Assert a pad has a specific color.

        Args:
            pad_index: Pad index (0-63)
            expected_color: Expected RGB tuple

        Raises:
            AssertionError: If color doesn't match
        """
        actual = self.pad_colors[pad_index]
        assert (
            actual == expected_color
        ), f"Pad {pad_index}: expected {expected_color}, got {actual}"

    def assert_pad_not_black(self, pad_index: int):
        """
        Assert a pad is not black (has some color).

        Args:
            pad_index: Pad index (0-63)

        Raises:
            AssertionError: If pad is black
        """
        color = self.pad_colors[pad_index]
        assert color != (0, 0, 0), f"Pad {pad_index} is black but shouldn't be"

    def assert_button_led(self, button_id: int, expected_value: int):
        """
        Assert a button LED has a specific value.

        Args:
            button_id: Button ID
            expected_value: Expected LED value

        Raises:
            AssertionError: If value doesn't match
        """
        actual = self.button_leds.get(button_id, 0)
        assert (
            actual == expected_value
        ), f"Button {button_id}: expected {expected_value}, got {actual}"

    def get_lit_pads(self) -> List[int]:
        """
        Get list of pads that are not black.

        Returns:
            List of pad indices with non-black colors
        """
        return [i for i, color in enumerate(self.pad_colors) if color != (0, 0, 0)]

    def get_pad_colors_by_row(self) -> List[List[Tuple[int, int, int]]]:
        """
        Get pad colors organized by row (4 rows of 16).

        Returns:
            List of 4 rows, each containing 16 color tuples
        """
        return [self.pad_colors[row * 16 : (row + 1) * 16] for row in range(4)]

    def get_pads_with_color(self, color: Tuple[int, int, int]) -> List[int]:
        """
        Get all pad indices with a specific color.

        Args:
            color: RGB tuple to search for

        Returns:
            List of pad indices with that color
        """
        return [i for i, c in enumerate(self.pad_colors) if c == color]

    def reset_event_history(self):
        """Reset all event history for fresh test assertions."""
        self.pad_events.clear()
        self.button_events.clear()
        self.render_count = 0
