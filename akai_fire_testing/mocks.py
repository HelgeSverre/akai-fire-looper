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
        self.pixels: List[List[int]] = [[0] * width for _ in range(height)]

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

    def set_pixel(self, x: int, y: int, color: int = 1):
        """
        Set a pixel value (0=off, 1=on for monochrome).

        Args:
            x: X coordinate
            y: Y coordinate
            color: Pixel value (0 or 1)
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def get_pixel(self, x: int, y: int) -> int:
        """
        Get a pixel value.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Pixel value (0 or 1), 0 if out of bounds
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y][x]
        return 0

    # =========================================================================
    # Text Drawing
    # =========================================================================

    def draw_text(self, text: str, x: int, y: int, font=None, color: int = 1):
        """
        Draw text and record the operation.

        Args:
            text: Text to draw
            x: X coordinate
            y: Y coordinate
            font: Font (ignored in mock, for API compatibility)
            color: Text color (0 or 1)
        """
        self.text_drawn.append((text, x, y))
        self._render_simple_text(text, x, y, color)

    def _render_simple_text(self, text: str, x: int, y: int, color: int = 1):
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

    def draw_rect(self, x: int, y: int, w: int, h: int, color: int = 1):
        """
        Draw rectangle outline and record.

        Args:
            x, y: Top-left corner
            w, h: Width and height
            color: Line color (0 or 1)
        """
        self.rects_drawn.append((x, y, w, h, False))
        for dx in range(w):
            self.set_pixel(x + dx, y, color)
            self.set_pixel(x + dx, y + h - 1, color)
        for dy in range(h):
            self.set_pixel(x, y + dy, color)
            self.set_pixel(x + w - 1, y + dy, color)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int = 1):
        """
        Draw filled rectangle and record.

        Args:
            x, y: Top-left corner
            w, h: Width and height
            color: Fill color (0 or 1)
        """
        self.rects_drawn.append((x, y, w, h, True))
        for dy in range(h):
            for dx in range(w):
                self.set_pixel(x + dx, y + dy, color)

    def draw_rectangle(self, x: int, y: int, w: int, h: int, color: int = 1):
        """Alias for draw_rect."""
        self.draw_rect(x, y, w, h, color)

    def fill_rectangle(self, x: int, y: int, w: int, h: int, color: int = 1):
        """Alias for fill_rect."""
        self.fill_rect(x, y, w, h, color)

    def draw_border(self, thickness: int = 1, color: int = 1):
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

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 1):
        """Draw horizontal line."""
        self.lines_drawn.append((x, y, x + length, y))
        for dx in range(length):
            self.set_pixel(x + dx, y, color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 1):
        """Draw vertical line."""
        self.lines_drawn.append((x, y, x, y + length))
        for dy in range(length):
            self.set_pixel(x, y + dy, color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 1):
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

    def draw_circle(self, cx: int, cy: int, radius: int, color: int = 1):
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

    def fill_circle(self, cx: int, cy: int, radius: int, color: int = 1):
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
        """Draw a page layout with title and content lines."""
        if header_inverted:
            self.fill_rect(0, 0, self.width, 10, 1)
        self.draw_text(title, 2, 1)
        for i, line in enumerate(lines):
            self.draw_text(line, 2, 14 + i * 10)

    def draw_value_page(
        self,
        title: str,
        value: Any,
        unit: str = "",
        min_value: float = 0,
        max_value: float = 100,
    ):
        """Draw a value display page."""
        self.draw_text(title, 2, 2)
        self.draw_text(f"{value}{unit}", 40, 30)

    def draw_menu(self, title: str, items: list, selected_index: int):
        """Draw a menu with selectable items."""
        self.draw_text(title, 2, 2)
        for i, item in enumerate(items):
            prefix = ">" if i == selected_index else " "
            self.draw_text(f"{prefix}{item}", 4, 14 + i * 10)

    def draw_grid_info(
        self,
        title: str,
        rows: int,
        cols: int,
        cell_values: list = None,
        selected_cell: tuple = None,
    ):
        """Draw a grid information display."""
        self.draw_text(title, 2, 2)

    def draw_split_screen(
        self, left_title: str, left_content: list, right_title: str, right_content: list
    ):
        """Draw a split-screen layout."""
        self.draw_vertical_line(64, 0, self.height)
        self.draw_text(left_title, 2, 2)
        self.draw_text(right_title, 66, 2)

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

        # Create scaled monochrome image (white on black)
        img = Image.new("RGB", (self.width * scale, self.height * scale), (0, 0, 0))
        pixels_out = img.load()

        for y in range(self.height):
            for x in range(self.width):
                if self.pixels[y][x]:
                    # White pixel (monochrome like AKAI Fire OLED)
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

            # Pixel data (bottom-up) - monochrome white on black
            for y in range(scaled_height - 1, -1, -1):
                for x in range(scaled_width):
                    src_x = x // scale
                    src_y = y // scale
                    if self.pixels[src_y][src_x]:
                        # White pixel (BGR format)
                        f.write(bytes([255, 255, 255]))
                    else:
                        # Black pixel
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


class MockAkaiFire:
    """
    Lightweight mock of AkaiFire for testing.

    Unlike the pygame MockAkaiFire, this doesn't create any windows
    and is suitable for headless testing.

    Features:
        - Records all pad color changes
        - Records all button LED changes
        - Simulates pad presses and button presses for testing event handlers
        - Provides assertions for verifying visual state
        - Connection simulation for testing connect/disconnect scenarios

    Example:
        >>> fire = MockAkaiFire()
        >>> @fire.on_pad()
        ... def on_pad(pad_index, velocity):
        ...     fire.set_pad_color(pad_index, 127, 0, 0)
        >>> fire.simulate_pad_press(5, velocity=100)
        >>> fire.assert_pad_color(5, (127, 0, 0))
    """

    # MIDI Constants (matching real AkaiFire)
    NOTE_ON = 0x90
    NOTE_OFF = 0x80
    CC = 0xB0

    # Button constants (matching real AkaiFire hex values)
    BUTTON_SELECT = 0x19
    BUTTON_BANK = 0x1A
    BUTTON_PAT_UP = 0x1F
    BUTTON_PAT_DOWN = 0x20
    BUTTON_BROWSER = 0x21
    BUTTON_GRID_LEFT = 0x22
    BUTTON_GRID_RIGHT = 0x23
    BUTTON_SOLO_1 = 0x24
    BUTTON_SOLO_2 = 0x25
    BUTTON_SOLO_3 = 0x26
    BUTTON_SOLO_4 = 0x27
    BUTTON_STEP = 0x2C
    BUTTON_NOTE = 0x2D
    BUTTON_DRUM = 0x2E
    BUTTON_PERFORM = 0x2F
    BUTTON_SHIFT = 0x30
    BUTTON_ALT = 0x31
    BUTTON_PATTERN = 0x32
    BUTTON_PLAY = 0x33
    BUTTON_STOP = 0x34
    BUTTON_REC = 0x35

    # Solo button index mapping (matches real AkaiFire)
    SOLO_BUTTONS = {
        1: 0x24,  # BUTTON_SOLO_1
        2: 0x25,  # BUTTON_SOLO_2
        3: 0x26,  # BUTTON_SOLO_3
        4: 0x27,  # BUTTON_SOLO_4
    }

    # Rotary constants (matching real AkaiFire hex values)
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # LED values
    LED_OFF = 0x00
    LED_DULL_RED = 0x01
    LED_HIGH_RED = 0x02
    LED_DULL_GREEN = 0x01
    LED_HIGH_GREEN = 0x02
    LED_DULL_YELLOW = 0x01
    LED_HIGH_YELLOW = 0x02

    # Rectangle LED Values
    RECTANGLE_LED_OFF = 0x00
    RECTANGLE_LED_DULL_RED = 0x01
    RECTANGLE_LED_DULL_GREEN = 0x02
    RECTANGLE_LED_HIGH_RED = 0x03
    RECTANGLE_LED_HIGH_GREEN = 0x04

    # Control Bank Field Constants
    FIELD_BASE = 0x10
    FIELD_CHANNEL = 0x01
    FIELD_MIXER = 0x02
    FIELD_USER1 = 0x04
    FIELD_USER2 = 0x08

    # Control Bank LED State Constants (matching real AkaiFire)
    CONTROL_BANK_ALL_OFF = 0x10
    CONTROL_BANK_ALL_ON = 0x1F
    CONTROL_BANK_CHANNEL = 0x11
    CONTROL_BANK_MIXER = 0x12
    CONTROL_BANK_USER1 = 0x14
    CONTROL_BANK_USER2 = 0x03  # Note: Real uses 0x03 (different from pattern)
    CONTROL_BANK_CHANNEL_AND_MIXER = 0x13
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1 = 0x17
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2 = 0x1B
    CONTROL_BANK_CHANNEL_AND_USER1 = 0x15
    CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2 = 0x1D
    CONTROL_BANK_CHANNEL_AND_USER2 = 0x19
    CONTROL_BANK_MIXER_AND_USER1_AND_USER2 = 0x1E
    CONTROL_BANK_MIXER_AND_USER2 = 0x1A
    CONTROL_BANK_USER1_AND_USER2 = 0x1C

    def __init__(self):
        """Initialize mock controller."""
        self._canvas = MockCanvas()

        # State tracking
        self.pad_colors: List[Tuple[int, int, int]] = [(0, 0, 0)] * 64
        self.button_leds: Dict[int, int] = {}
        self.track_leds: Dict[int, int] = {}
        self.control_bank_state = 0

        # Event history for assertions
        self.pad_events: List[PadEvent] = []
        self.button_events: List[ButtonEvent] = []
        self.render_count = 0

        # Event handlers (supporting both decorator and add_* patterns)
        self._pad_handlers: List[Tuple[Optional[int], Callable]] = []
        self._global_pad_handlers: List[Callable] = []
        self._button_handlers: Dict[int, List[Callable]] = {}
        self._global_button_handlers: List[Callable] = []
        self._rotary_handlers: Dict[int, List[Callable]] = {}
        self._global_rotary_handlers: List[Callable] = []
        self._rotary_touch_handlers: Dict[int, List[Callable]] = {}
        self._global_rotary_touch_handlers: List[Callable] = []

        # Modifier state
        self._shift_pressed = False
        self._alt_pressed = False

        # Connection state simulation
        self._connected = True
        self._connection_error = None

        # Closed state
        self._closed = False

    # =========================================================================
    # Canvas Access
    # =========================================================================

    def get_canvas(self) -> MockCanvas:
        """Get the mock canvas."""
        return self._canvas

    def new_canvas(self) -> MockCanvas:
        """Create a new mock canvas."""
        self._canvas = MockCanvas()
        return self._canvas

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
        """
        if not self._connected:
            return False
        if 0 <= pad_index < 64:
            # Clamp values
            r = max(0, min(127, r))
            g = max(0, min(127, g))
            b = max(0, min(127, b))
            color = (r, g, b)
            self.pad_colors[pad_index] = color
            self.pad_events.append(PadEvent(pad_index, color))
            return True
        return False

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
        """Set button LED and record the event."""
        if not self._connected:
            return False
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
        """Set track LED (1-4)."""
        if not self._connected:
            return False
        if 1 <= track <= 4:
            self.track_leds[track] = value
            return True
        return False

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

    def render_to_display(self, canvas=None):
        """Record a render call."""
        self.render_count += 1

    def render_to_bmp(self, output_path: str, image_format: str = "BMP") -> str:
        """
        Save canvas to BMP file (for testing without hardware).

        Args:
            output_path: File path to save to
            image_format: Image format (default BMP)

        Returns:
            Path where file was saved
        """
        return self._canvas.save_screenshot(output_path)

    def clear_display(self):
        """Clear the display."""
        self._canvas.clear()

    # =========================================================================
    # Modifier State
    # =========================================================================

    def is_shift_pressed(self) -> bool:
        """Returns whether the shift key is currently held down."""
        return self._shift_pressed

    def is_alt_pressed(self) -> bool:
        """Returns whether the alt key is currently held down."""
        return self._alt_pressed

    @property
    def shift_pressed(self) -> bool:
        """Check if shift is currently pressed."""
        return self._shift_pressed

    @property
    def alt_pressed(self) -> bool:
        """Check if alt is currently pressed."""
        return self._alt_pressed

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
    # Utility Methods
    # =========================================================================

    @staticmethod
    def pad_position(pad_index: int) -> Tuple[int, int]:
        """
        Get the column and row for a given pad index.

        Args:
            pad_index: Pad index (0-63)

        Returns:
            Tuple of (column, row) where column is 0-15 and row is 0-3

        Raises:
            ValueError: If pad index is out of range
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        column = pad_index % 16
        row = pad_index // 16
        return column, row

    @staticmethod
    def get_pad_column(pad_index: int) -> int:
        """
        Get the column number for a given pad index.

        Args:
            pad_index: Pad index (0-63)

        Returns:
            Column number (1-16)
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index % 16) + 1

    @staticmethod
    def get_pad_row(pad_index: int) -> int:
        """
        Get the row number for a given pad index.

        Args:
            pad_index: Pad index (0-63)

        Returns:
            Row number (1-4)
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index // 16) + 1

    def get_solo_index(self, button_id: int) -> Optional[int]:
        """
        Convert a BUTTON_SOLO_* constant to its index (1-4).

        Args:
            button_id: Button ID constant

        Returns:
            Solo index (1-4) or None if not a solo button
        """
        for index, bid in self.SOLO_BUTTONS.items():
            if bid == button_id:
                return index
        return None

    @staticmethod
    def list_midi_ports() -> Dict[str, List[str]]:
        """
        List available MIDI ports (mock version returns empty lists).

        Returns:
            Dictionary with 'input' and 'output' lists
        """
        return {"input": [], "output": []}

    # =========================================================================
    # Event Decorators
    # =========================================================================

    def on_pad(self, pad_index=None):
        """
        Decorator for pad events.

        Args:
            pad_index: Specific pad(s) to listen to, or None for all pads.
                       Can be int, list of ints, or None.

        Returns:
            Decorator function

        Usage:
            @fire.on_pad(0)  # Single pad
            def handle_pad(velocity): ...

            @fire.on_pad([0, 1, 2])  # Multiple pads
            def handle_pads(pad_index, velocity): ...

            @fire.on_pad()  # All pads
            def handle_any_pad(pad_index, velocity): ...
        """

        def decorator(func):
            if pad_index is None:
                self._global_pad_handlers.append(func)
            elif isinstance(pad_index, (list, tuple)):
                for idx in pad_index:
                    self._pad_handlers.append((idx, func))
            else:
                self._pad_handlers.append((pad_index, func))
            return func

        return decorator

    def on_button(self, button_id=None):
        """
        Decorator for button events.

        Args:
            button_id: Button to listen to, or None for all buttons

        Returns:
            Decorator function

        Usage:
            @fire.on_button(fire.BUTTON_PLAY)
            def handle_play(event): ...

            @fire.on_button()  # Global handler
            def handle_any_button(button_id, event): ...
        """

        def decorator(func):
            if button_id is None:
                self._global_button_handlers.append(func)
            else:
                if button_id not in self._button_handlers:
                    self._button_handlers[button_id] = []
                self._button_handlers[button_id].append(func)
            return func

        return decorator

    # Valid rotary IDs (for validation)
    VALID_ROTARY_IDS = [
        0x10,
        0x11,
        0x12,
        0x13,
        0x76,
    ]  # VOLUME, PAN, FILTER, RESONANCE, SELECT

    def on_rotary_turn(self, rotary_id=None):
        """
        Decorator for rotary turn events.

        Args:
            rotary_id: Rotary encoder to listen to, or None for all

        Returns:
            Decorator function

        Usage:
            @fire.on_rotary_turn(fire.ROTARY_VOLUME)
            def handle_volume(direction, velocity): ...

            @fire.on_rotary_turn()  # Global handler
            def handle_any_rotary(rotary_id, direction, velocity): ...

        Raises:
            ValueError: If rotary_id is not a valid rotary constant
        """

        def decorator(func):
            if rotary_id is None:
                self._global_rotary_handlers.append(func)
            else:
                if rotary_id not in self.VALID_ROTARY_IDS:
                    raise ValueError(f"Invalid rotary ID: {rotary_id}")
                if rotary_id not in self._rotary_handlers:
                    self._rotary_handlers[rotary_id] = []
                self._rotary_handlers[rotary_id].append(func)
            return func

        return decorator

    def on_rotary_touch(self, rotary_id=None):
        """
        Decorator for rotary touch events.

        Args:
            rotary_id: Rotary encoder to listen to, or None for all

        Returns:
            Decorator function

        Usage:
            @fire.on_rotary_touch(fire.ROTARY_VOLUME)
            def handle_volume_touch(event): ...  # "touch" or "release"

            @fire.on_rotary_touch()  # Global handler
            def handle_any_touch(rotary_id, event): ...

        Raises:
            ValueError: If rotary_id is not a valid rotary constant
        """

        def decorator(func):
            if rotary_id is None:
                self._global_rotary_touch_handlers.append(func)
            else:
                if rotary_id not in self.VALID_ROTARY_IDS:
                    raise ValueError(f"Invalid rotary ID: {rotary_id}")
                if rotary_id not in self._rotary_touch_handlers:
                    self._rotary_touch_handlers[rotary_id] = []
                self._rotary_touch_handlers[rotary_id].append(func)
            return func

        return decorator

    def on_solo(self, index: Optional[int] = None):
        """
        Decorator for solo button events.

        Args:
            index: Solo button index (1-4), or None for all solo buttons

        Returns:
            Decorator function

        Usage:
            @fire.on_solo(1)
            def handle_solo_1(event): ...  # "press" or "release"

            @fire.on_solo()  # Global handler
            def handle_any_solo(index, event): ...
        """

        def decorator(func):
            if index is None:
                # Global solo handler - wrap to translate button_id to index
                def global_wrapper(button_id, event):
                    solo_index = self.get_solo_index(button_id)
                    if solo_index is not None:
                        func(solo_index, event)

                self._global_button_handlers.append(global_wrapper)
            else:
                # Specific solo button
                if 1 <= index <= 4:
                    button_id = self.SOLO_BUTTONS[index]
                    if button_id not in self._button_handlers:
                        self._button_handlers[button_id] = []
                    self._button_handlers[button_id].append(func)
                else:
                    raise ValueError("Solo index must be 1-4")
            return func

        return decorator

    # =========================================================================
    # Listener Methods (add_* pattern for compatibility)
    # =========================================================================

    def add_listener(self, pad_indices, callback: Callable):
        """
        Add listener for specific pad presses.

        Args:
            pad_indices: Pad index or list of pad indices (0-63)
            callback: Function to call when pad is pressed
        """
        if isinstance(pad_indices, (list, tuple)):
            for idx in pad_indices:
                if 0 <= idx <= 63:
                    self._pad_handlers.append((idx, callback))
        else:
            if 0 <= pad_indices <= 63:
                self._pad_handlers.append((pad_indices, callback))

    def add_global_listener(self, callback: Callable):
        """
        Add global listener for all pad presses.

        Args:
            callback: Function(pad_index, velocity) to call
        """
        self._global_pad_handlers.append(callback)

    def add_button_listener(self, button_id: int, callback: Callable):
        """
        Add listener for button events.

        Args:
            button_id: Button ID constant
            callback: Function(event) to call where event is "press" or "release"
        """
        if button_id not in self._button_handlers:
            self._button_handlers[button_id] = []
        self._button_handlers[button_id].append(callback)

    def add_rotary_listener(self, rotary_id: int, callback: Callable):
        """
        Add listener for rotary turn events.

        Args:
            rotary_id: Rotary ID constant
            callback: Function(direction, velocity) to call

        Raises:
            ValueError: If rotary_id is not valid
        """
        if rotary_id not in self.VALID_ROTARY_IDS:
            raise ValueError(f"Invalid rotary ID: {rotary_id}")
        if rotary_id not in self._rotary_handlers:
            self._rotary_handlers[rotary_id] = []
        self._rotary_handlers[rotary_id].append(callback)

    def add_rotary_touch_listener(self, rotary_id: int, callback: Callable):
        """
        Add listener for rotary touch events.

        Args:
            rotary_id: Rotary ID constant
            callback: Function(event) to call where event is "touch" or "release"

        Raises:
            ValueError: If rotary_id is not valid
        """
        if rotary_id not in self.VALID_ROTARY_IDS:
            raise ValueError(f"Invalid rotary ID: {rotary_id}")
        if rotary_id not in self._rotary_touch_handlers:
            self._rotary_touch_handlers[rotary_id] = []
        self._rotary_touch_handlers[rotary_id].append(callback)

    # =========================================================================
    # Event Simulation (for testing)
    # =========================================================================

    def simulate_pad_press(self, pad_index: int, velocity: int = 100):
        """
        Simulate a pad press for testing.

        Args:
            pad_index: Pad index (0-63)
            velocity: Press velocity (0-127)

        Note:
            Matches real AkaiFire behavior:
            - Specific pad handlers receive (velocity) only
            - Global pad handlers receive (pad_index, velocity)
        """
        # Handle specific pad handlers - they receive ONLY velocity (matches real behavior)
        for handler_pad, handler in self._pad_handlers:
            if handler_pad == pad_index:
                handler(velocity)

        # Handle global pad handlers - they receive (pad_index, velocity)
        for handler in self._global_pad_handlers:
            handler(pad_index, velocity)

    def simulate_pad_release(self, pad_index: int):
        """
        Simulate a pad release for testing.

        Args:
            pad_index: Pad index (0-63)

        Note:
            Pad release sends velocity 0.
        """
        # Specific pad handlers receive ONLY velocity (matches real behavior)
        for handler_pad, handler in self._pad_handlers:
            if handler_pad == pad_index:
                handler(0)

        # Global pad handlers receive (pad_index, velocity)
        for handler in self._global_pad_handlers:
            handler(pad_index, 0)

    def simulate_button_press(self, button_id: int):
        """
        Simulate a button press for testing.

        Args:
            button_id: Button ID
        """
        # Update modifier state
        if button_id == self.BUTTON_SHIFT:
            self._shift_pressed = True
        elif button_id == self.BUTTON_ALT:
            self._alt_pressed = True

        # Handle specific button handlers
        if button_id in self._button_handlers:
            for handler in self._button_handlers[button_id]:
                handler("press")

        # Handle global button handlers
        for handler in self._global_button_handlers:
            handler(button_id, "press")

    def simulate_button_release(self, button_id: int):
        """
        Simulate a button release for testing.

        Args:
            button_id: Button ID
        """
        # Update modifier state
        if button_id == self.BUTTON_SHIFT:
            self._shift_pressed = False
        elif button_id == self.BUTTON_ALT:
            self._alt_pressed = False

        # Handle specific button handlers
        if button_id in self._button_handlers:
            for handler in self._button_handlers[button_id]:
                handler("release")

        # Handle global button handlers
        for handler in self._global_button_handlers:
            handler(button_id, "release")

    def simulate_rotary_turn(self, rotary_id: int, direction: str, velocity: int = 1):
        """
        Simulate a rotary encoder turn.

        Args:
            rotary_id: Rotary encoder ID
            direction: "clockwise" or "counterclockwise" (or "left"/"right" as aliases)
            velocity: Turn velocity
        """
        # Normalize direction names
        if direction == "left":
            direction = "counterclockwise"
        elif direction == "right":
            direction = "clockwise"

        # Handle specific rotary handlers
        if rotary_id in self._rotary_handlers:
            for handler in self._rotary_handlers[rotary_id]:
                handler(direction, velocity)

        # Handle global rotary handlers
        for handler in self._global_rotary_handlers:
            handler(rotary_id, direction, velocity)

    def simulate_rotary_touch(self, rotary_id: int):
        """
        Simulate a rotary encoder touch.

        Args:
            rotary_id: Rotary encoder ID
        """
        # Handle specific touch handlers
        if rotary_id in self._rotary_touch_handlers:
            for handler in self._rotary_touch_handlers[rotary_id]:
                handler("touch")

        # Handle global touch handlers
        for handler in self._global_rotary_touch_handlers:
            handler(rotary_id, "touch")

    def simulate_rotary_release(self, rotary_id: int):
        """
        Simulate a rotary encoder release.

        Args:
            rotary_id: Rotary encoder ID
        """
        # Handle specific touch handlers
        if rotary_id in self._rotary_touch_handlers:
            for handler in self._rotary_touch_handlers[rotary_id]:
                handler("release")

        # Handle global touch handlers
        for handler in self._global_rotary_touch_handlers:
            handler(rotary_id, "release")

    def simulate_solo_press(self, index: int):
        """
        Simulate a solo button press.

        Args:
            index: Solo index (1-4)
        """
        if 1 <= index <= 4:
            button_id = self.SOLO_BUTTONS[index]
            self.simulate_button_press(button_id)

    def simulate_solo_release(self, index: int):
        """
        Simulate a solo button release.

        Args:
            index: Solo index (1-4)
        """
        if 1 <= index <= 4:
            button_id = self.SOLO_BUTTONS[index]
            self.simulate_button_release(button_id)

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
