import logging
import threading
import time
from collections import defaultdict
from typing import Optional, Union, List, Tuple, Dict, Any

import rtmidi
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logger = logging.getLogger(__name__)


class AkaiFireError(Exception):
    """Base exception for AKAI Fire library."""

    pass


class MIDIConnectionError(AkaiFireError):
    """Raised when MIDI connection fails."""

    pass


class MIDISendError(AkaiFireError):
    """Raised when sending MIDI message fails."""

    pass


class InvalidParameterError(AkaiFireError):
    """Raised when invalid parameters are provided."""

    pass


class HardwareError(AkaiFireError):
    """Raised when hardware communication fails."""

    pass


class StateError(AkaiFireError):
    """Raised when operation is invalid for current state."""

    pass


class Canvas:
    WIDTH, HEIGHT = 128, 64

    # Typography constants for consistent spacing
    HEADER_HEIGHT = 16  # Standard header height
    TEXT_MARGIN_Y = 3  # Top margin for header text
    CONTENT_GAP = 2  # Gap between header and content
    CONTENT_START = HEADER_HEIGHT + CONTENT_GAP  # Y=18

    def __init__(self):
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 1)
        self.draw = ImageDraw.Draw(self.image)

    def clone(self):
        """Create a copy of the current canvas."""
        cloned_canvas = Canvas()
        cloned_canvas.image = self.image.copy()
        cloned_canvas.draw = ImageDraw.Draw(cloned_canvas.image)
        return cloned_canvas

    def clear(self, color: int = 1):
        """Clear the canvas."""
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), color)
        self.draw = ImageDraw.Draw(self.image)

    def get_pixel(self, x, y) -> Optional[int]:
        """Get a pixel from the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            return self.image.getpixel((x, y))
        return None

    def set_pixel(self, x, y, color: int = 0):
        """Set a pixel on the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.image.putpixel((x, y), color)

    def draw_rect(self, x, y, width, height, color: int = 0):
        """Draw rectangle outline."""
        if width <= 0 or height <= 0:
            return
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], outline=color)

    def fill_rect(self, x, y, width, height, color: int = 0):
        """Draw filled rectangle."""
        if width <= 0 or height <= 0:
            return
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], fill=color)

    def draw_text(self, text, x, y, font=None, color: int = 0):
        """Draw text."""
        if font is None:
            font = ImageFont.load_default()

        self.draw.text((x, y), text, fill=color, font=font)

    def draw_border(self, thickness: int = 1, color: int = 0):
        """Draw a border around the entire canvas."""
        for i in range(thickness):
            self.draw_rect(i, i, self.WIDTH - 2 * i, self.HEIGHT - 2 * i, color)

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a horizontal line using PIL's line method for efficiency."""
        if length > 0 and 0 <= y < self.HEIGHT:
            x_end = min(x + length - 1, self.WIDTH - 1)
            self.draw.line([(x, y), (x_end, y)], fill=color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a vertical line using PIL's line method for efficiency."""
        if length > 0 and 0 <= x < self.WIDTH:
            y_end = min(y + length - 1, self.HEIGHT - 1)
            self.draw.line([(x, y), (x, y_end)], fill=color)

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Draw a rectangle."""
        self.draw_horizontal_line(x, y, width, color)
        self.draw_horizontal_line(x, y + height - 1, width, color)
        self.draw_vertical_line(x, y, height, color)
        self.draw_vertical_line(x + width - 1, y, height, color)

    def fill_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Fill a rectangle."""
        for i in range(height):
            self.draw_horizontal_line(x, y + i, width, color)

    def draw_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Draw a circle using PIL's ellipse method."""
        bbox = [x0 - radius, y0 - radius, x0 + radius, y0 + radius]
        self.draw.ellipse(bbox, outline=color)

    def fill_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Fill a circle using PIL's ellipse method."""
        bbox = [x0 - radius, y0 - radius, x0 + radius, y0 + radius]
        self.draw.ellipse(bbox, fill=color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 0):
        """Draw a line using Bresenham's line algorithm."""
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

    def draw_page(self, title: str, lines: list[str], header_inverted: bool = True):
        """
        Draw a basic page layout with header and content lines.

        Args:
            title: Title text for the header
            lines: List of text lines to display below header
            header_inverted: If True, header is black with white text
        """
        # Header with optional inversion
        if header_inverted:
            self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)
        else:
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=0)
            self.draw_horizontal_line(0, self.HEADER_HEIGHT, self.WIDTH, color=0)

        # Content lines with proper spacing
        y_offset = self.CONTENT_START  # Start below header
        line_height = 12  # Standard line height

        for i, line in enumerate(lines):
            if y_offset + line_height > self.HEIGHT:
                break  # Don't draw beyond screen bounds
            self.draw_text(line, 2, y_offset + (i * line_height))

    def draw_value_page(
        self,
        title: str,
        value: Union[int, float, str],
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        show_bar: bool = True,
    ):
        """
        Draw a page showing a value with optional bar visualization.

        Args:
            title: Title text for the header
            value: Current value to display
            min_val: Minimum value for bar scaling (if showing bar)
            max_val: Maximum value for bar scaling (if showing bar)
            show_bar: Whether to show a progress bar
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)

        # Large value display
        value_text = str(value)
        self.draw_text(value_text, 2, 20, color=0)

        # Optional bar visualization
        if show_bar and min_val is not None and max_val is not None:
            bar_y = 40
            bar_height = 8
            normalized = (float(value) - min_val) / (max_val - min_val)
            bar_width = int(normalized * (self.WIDTH - 4))

            # Bar outline
            self.draw_rect(2, bar_y, self.WIDTH - 4, bar_height)
            # Bar fill
            self.fill_rect(2, bar_y, bar_width, bar_height)

    def draw_menu(self, title: str, items: list[str], selected_index: int):
        """
        Draw a menu with selectable items.

        Args:
            title: Title text for the header
            items: List of menu items
            selected_index: Index of currently selected item
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)

        # Menu items
        y_offset = self.CONTENT_START
        line_height = 12

        visible_items = min(4, len(items))  # Show max 4 items at once
        start_idx = max(0, min(selected_index - 1, len(items) - visible_items))

        for i in range(visible_items):
            idx = start_idx + i
            if idx >= len(items):
                break

            # Highlight selected item
            if idx == selected_index:
                self.fill_rect(
                    0, y_offset + (i * line_height), self.WIDTH, line_height, color=0
                )
                self.draw_text(items[idx], 4, y_offset + (i * line_height), color=1)
            else:
                self.draw_text(items[idx], 4, y_offset + (i * line_height))

    def draw_grid_info(
        self, title: str, rows: int, cols: int, cell_info: list[tuple[int, int, str]]
    ):
        """
        Draw information about a grid layout (useful for pad layouts).

        Args:
            title: Title text for the header
            rows: Number of rows in grid
            cols: Number of columns in grid
            cell_info: List of (row, col, text) tuples showing cell contents
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Draw grid outline
        cell_width = (self.WIDTH - 4) // cols
        cell_height = (self.HEIGHT - 20) // rows

        for row in range(rows + 1):
            y = 16 + (row * cell_height)
            self.draw_horizontal_line(2, y, self.WIDTH - 4)

        for col in range(cols + 1):
            x = 2 + (col * cell_width)
            self.draw_vertical_line(x, 16, (rows * cell_height))

        # Draw cell contents
        for row, col, text in cell_info:
            x = 2 + (col * cell_width) + 2
            y = 16 + (row * cell_height) + 2
            self.draw_text(text, x, y)

    def draw_split_screen(
        self, title: str, left_content: list[str], right_content: list[str]
    ):
        """
        Draw a screen split into two columns.

        Args:
            title: Title text for the header
            left_content: List of text lines for left column
            right_content: List of text lines for right column
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Split line
        mid_x = self.WIDTH // 2
        self.draw_vertical_line(mid_x, 15, self.HEIGHT - 15)

        # Left content
        y_offset = 15
        line_height = 12
        for i, line in enumerate(left_content):
            if y_offset + (i * line_height) + line_height > self.HEIGHT:
                break
            self.draw_text(line, 2, y_offset + (i * line_height))

        # Right content
        for i, line in enumerate(right_content):
            if y_offset + (i * line_height) + line_height > self.HEIGHT:
                break
            self.draw_text(line, mid_x + 2, y_offset + (i * line_height))


# noinspection GrazieInspection
class AkaiFire:
    # MIDI Constants
    NOTE_ON = 0x90
    NOTE_OFF = 0x80
    CC = 0xB0

    # Rotary Controls
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # Buttons
    BUTTON_SELECT = 0x19
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
    BUTTON_BANK = 0x1A
    BUTTON_BROWSER = 0x21
    BUTTON_SOLO_1 = 0x24
    BUTTON_SOLO_2 = 0x25
    BUTTON_SOLO_3 = 0x26
    BUTTON_SOLO_4 = 0x27
    BUTTON_PAT_UP = 0x1F
    BUTTON_PAT_DOWN = 0x20
    BUTTON_GRID_LEFT = 0x22
    BUTTON_GRID_RIGHT = 0x23

    # Solo Button mapped to index
    SOLO_BUTTONS = {
        1: BUTTON_SOLO_1,
        2: BUTTON_SOLO_2,
        3: BUTTON_SOLO_3,
        4: BUTTON_SOLO_4,
    }

    # LED Values
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

    # todo    temporary
    FIELD_BASE = 0x10  # Base flag, must be set for valid combinations
    FIELD_CHANNEL = 0x01
    FIELD_MIXER = 0x02
    FIELD_USER1 = 0x04
    FIELD_USER2 = 0x08

    # Constants for Control Bank LED States
    CONTROL_BANK_ALL_OFF = 0x10
    CONTROL_BANK_ALL_ON = 0x1F
    CONTROL_BANK_CHANNEL = 0x11
    CONTROL_BANK_CHANNEL_AND_MIXER = 0x13
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1 = 0x17
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2 = 0x1B
    CONTROL_BANK_CHANNEL_AND_USER1 = 0x15
    CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2 = 0x1D
    CONTROL_BANK_CHANNEL_AND_USER2 = 0x19
    CONTROL_BANK_MIXER = 0x12
    CONTROL_BANK_MIXER_AND_USER1_AND_USER2 = 0x1E
    CONTROL_BANK_MIXER_AND_USER2 = 0x1A
    CONTROL_BANK_USER1 = 0x14
    CONTROL_BANK_USER1_AND_USER2 = 0x1C
    CONTROL_BANK_USER2 = 0x03

    def render_to_display(self, canvas=None):
        """Render the canvas to the OLED display with optimizations.

        Args:
            canvas: Canvas object to render, or None to use internal canvas

        Raises:
            InvalidParameterError: If canvas is not a Canvas object
            StateError: If MIDI output is not available
        """
        if not self.midi_out:
            raise StateError("MIDI output not initialized")

        buffer = canvas if canvas is not None else self.canvas

        # Validate canvas type
        if not isinstance(buffer, Canvas):
            raise InvalidParameterError(
                f"Expected Canvas object, got: {type(buffer).__name__}"
            )

        # For OLED 128x64, calculated as ceil(128*64/7)
        bitmap_size = 1171
        bitmap = [0] * bitmap_size

        # Static mapping table - could be class constant for better performance
        bitmap_pixel_mapping = [
            [13, 0, 1, 2, 3, 4, 5, 6],
            [19, 20, 7, 8, 9, 10, 11, 12],
            [25, 26, 27, 14, 15, 16, 17, 18],
            [31, 32, 33, 34, 21, 22, 23, 24],
            [37, 38, 39, 40, 41, 28, 29, 30],
            [43, 44, 45, 46, 47, 48, 35, 36],
            [49, 50, 51, 52, 53, 54, 55, 42],
        ]

        # Convert canvas to bitmap - optimized with direct pixel access
        pixels = buffer.image.load()  # Direct pixel access is faster
        for y in range(buffer.HEIGHT):
            y_div_8 = y // 8
            y_mod_8 = y % 8
            for x in range(buffer.WIDTH):
                if pixels[x, y] == 0:  # Black pixel in PIL = ON in OLED
                    x_mapped = x + buffer.WIDTH * y_div_8
                    rb = bitmap_pixel_mapping[x_mapped % 7][y_mod_8]
                    index = (x_mapped // 7) * 8 + (rb // 7)
                    bitmap[index] |= 1 << (rb % 7)

        # Send to display
        sysex_data = [
            0xF0,
            0x47,
            0x7F,
            0x43,
            0x0E,
            (len(bitmap) + 4) >> 7,
            (len(bitmap) + 4) & 0x7F,
            0,
            0x07,
            0,
            0x7F,
        ]
        sysex_data.extend(bitmap)
        sysex_data.append(0xF7)

        self.midi_out.send_message(sysex_data)

    def render_to_bmp(self, output_path: str, image_format="BMP"):
        """Factory method to save canvas as BMP file."""
        self.canvas.image.save(output_path, format=image_format)

    def clear_display(self):
        """Clear the OLED display."""
        self.canvas.clear()
        self.render_to_display()

    def get_canvas(self) -> Canvas:
        """Get the current canvas for drawing."""
        return self.canvas

    def new_canvas(self) -> Canvas:
        """Create a new blank canvas."""
        self.canvas = Canvas()
        return self.canvas

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clears display and closes connection"""
        self.clear_display()
        self.close()

    def __init__(self, port_name=None):
        """Initialize AKAI Fire controller with improved error handling."""
        # Thread safety
        self._lock = threading.RLock()
        self.listening = False
        self.listening_thread = None

        self.canvas = Canvas()
        self.look_for_port = port_name or "FL STUDIO FIRE"

        # Modifier state
        self._shift_pressed = False
        self._alt_pressed = False

        # Initialize listener collections (thread-safe)
        self.button_listeners = defaultdict(list)
        self.pad_listeners = defaultdict(list)
        self.rotary_listeners = defaultdict(list)
        self.rotary_touch_listeners = defaultdict(list)

        # Performance optimizations
        self._last_pad_states = {}  # Track pad states to avoid redundant updates
        self._batch_threshold = (
            5  # Use batch updates if updating more than this many pads
        )
        self._cached_messages = {}  # Will be populated after MIDI init

        # Initialize MIDI ports
        try:
            self.midi_in = rtmidi.MidiIn()
            self.midi_out = rtmidi.MidiOut()
            self.input_port_index, self.output_port_index = self._find_ports()

            if self.output_port_index is None or self.input_port_index is None:
                ports = self.list_midi_ports()
                raise MIDIConnectionError(
                    f"AKAI Fire MIDI ports not found. Looking for: '{self.look_for_port}'. "
                    f"Available ports: {ports}"
                )

            self.midi_out.open_port(self.output_port_index)
            self.midi_in.open_port(self.input_port_index)

        except Exception as e:
            raise MIDIConnectionError(f"Failed to initialize MIDI: {e}")

        # Modifier-key state (_shift_pressed / _alt_pressed) is latched
        # inline in _process_message before any user handler runs, so code
        # reading is_shift_pressed() / is_alt_pressed() from a pad handler
        # always sees a coherent value — even under async dispatch.

        # Initialize performance caches
        self._init_performance_caches()

    def on_button(self, button_id=None):
        """
        Decorator for button events.

        Usage:
            @fire.on_button(BUTTON_PLAY)  # Specific button
            def handle_play(event):
                print(f"Play button {event}")

            @fire.on_button()  # Global button handler
            def handle_any_button(button_id, event):
                print(f"Button {button_id} {event}")
        """

        def decorator(func):
            with self._lock:
                key = "global" if button_id is None else button_id
                if key not in self.button_listeners:
                    self.button_listeners[key] = []
                self.button_listeners[key].append(func)
            self.start_listening()
            return func

        return decorator

    def on_rotary_turn(self, rotary_id=None):
        """
        Decorator for rotary knob turns. Supports multiple listeners per rotary.

        Usage:
            @fire.on_rotary_turn(ROTARY_VOLUME)  # Specific rotary
            def handle_volume(direction, velocity):
                print(f"Volume turned {direction} at {velocity}")

            @fire.on_rotary_turn()  # Global rotary handler
            def handle_any_rotary(rotary_id, direction, velocity):
                print(f"Rotary {rotary_id} turned {direction} at {velocity}")
        """

        def decorator(func):
            with self._lock:
                if rotary_id is None:
                    self.rotary_listeners["global"].append(func)
                else:
                    if rotary_id not in [
                        self.ROTARY_VOLUME,
                        self.ROTARY_PAN,
                        self.ROTARY_FILTER,
                        self.ROTARY_RESONANCE,
                        self.ROTARY_SELECT,
                    ]:
                        raise ValueError("Invalid rotary ID")

                    if rotary_id not in self.rotary_listeners:
                        self.rotary_listeners[rotary_id] = []
                    self.rotary_listeners[rotary_id].append(func)

            self.start_listening()

            return func

        return decorator

    def on_rotary_touch(self, rotary_id=None):
        """
        Decorator for rotary touch events. Supports multiple listeners per rotary.

        Usage:
            @fire.on_rotary_touch(ROTARY_VOLUME)  # Specific rotary
            def handle_volume_touch(event):
                print(f"Volume knob {event}")

            @fire.on_rotary_touch()  # Global touch handler
            def handle_any_touch(rotary_id, event):
                print(f"Rotary {rotary_id} {event}")
        """

        def decorator(func):
            with self._lock:
                if rotary_id is None:
                    self.rotary_touch_listeners["global"].append(func)
                else:
                    if rotary_id not in [
                        self.ROTARY_VOLUME,
                        self.ROTARY_PAN,
                        self.ROTARY_FILTER,
                        self.ROTARY_RESONANCE,
                        self.ROTARY_SELECT,
                    ]:
                        raise ValueError("Invalid rotary ID")
                    self.rotary_touch_listeners[rotary_id].append(func)
            self.start_listening()
            return func

        return decorator

    def on_pad(self, pad_index=None):
        """
        Decorator for pad presses. Supports multiple listeners per pad.

        Usage:
            @fire.on_pad(0)  # Single pad
            def handle_pad(velocity):
                print(f"Pad pressed with velocity {velocity}")

            @fire.on_pad([0,1,2,3])  # Multiple pads
            def handle_pads(pad_index, velocity):
                print(f"Pad {pad_index} pressed with velocity {velocity}")

            @fire.on_pad()  # All pads
            def handle_any_pad(pad_index, velocity):
                print(f"Pad {pad_index} pressed with velocity {velocity}")
        """

        def decorator(func):
            with self._lock:
                if pad_index is None:
                    self.pad_listeners["global"].append(func)
                elif isinstance(pad_index, (list, tuple)):
                    for idx in pad_index:
                        if not (0 <= idx <= 63):
                            raise ValueError("Pad index must be between 0 and 63")
                        self.pad_listeners[idx].append(func)
                else:
                    if not (0 <= pad_index <= 63):
                        raise ValueError("Pad index must be between 0 and 63")
                    self.pad_listeners[pad_index].append(func)
            self.start_listening()
            return func

        return decorator

    def on_solo(self, index: Optional[Union[int]] = None):
        """
        Decorator for solo button events. Supports index (1-4) for specific solo buttons.

        Args:
            index: Solo button number (1-4) or None for global handler

        Usage:
            @fire.on_solo(1)  # Specific solo button
            def handle_solo_1(event):  # event will be "press" or "release"
                print(f"Solo 1 {event}")

            @fire.on_solo()  # Global handler
            def handle_any_solo(index, event):  # index will be 1-4
                print(f"Solo {index} {event}")

        Raises:
            ValueError: If the index is invalid (must be 1-4)
        """

        def decorator(func):
            with self._lock:
                if index is None:
                    # For global handler, register for all solo buttons
                    # We use a wrapper to translate button_id to index for consistent API
                    def global_wrapper(button_id, event):
                        if button_id in self.SOLO_BUTTONS.values():
                            solo_index = self.get_solo_index(button_id)
                            func(solo_index, event)

                    self.button_listeners["global"].append(global_wrapper)
                else:
                    # Validate index
                    if not isinstance(index, int) or index not in self.SOLO_BUTTONS:
                        raise ValueError("Solo button index must be 1-4")

                    # Get the actual button ID from index
                    button_id = self.SOLO_BUTTONS[index]
                    self.button_listeners[button_id].append(func)

            self.start_listening()
            return func

        return decorator

    def get_solo_index(self, button_id: int) -> Optional[int]:
        """Convert a BUTTON_SOLO_* constant to its index (1-4)"""
        for index, bid in self.SOLO_BUTTONS.items():
            if bid == button_id:
                return index
        return None

    def is_shift_pressed(self) -> bool:
        """Returns whether the shift key is currently held down"""
        return self._shift_pressed

    def is_alt_pressed(self) -> bool:
        """Returns whether the alt key is currently held down"""
        return self._alt_pressed

    def _init_performance_caches(self):
        """Initialize performance optimization caches."""
        # Pre-compute common sysex messages
        self._cached_messages["clear_pads"] = self._create_sysex_message(
            [(i, 0, 0, 0) for i in range(64)]
        )
        self._cached_messages["all_white"] = self._create_sysex_message(
            [(i, 127, 127, 127) for i in range(64)]
        )
        self._cached_messages["all_red"] = self._create_sysex_message(
            [(i, 127, 0, 0) for i in range(64)]
        )
        self._cached_messages["all_green"] = self._create_sysex_message(
            [(i, 0, 127, 0) for i in range(64)]
        )
        self._cached_messages["all_blue"] = self._create_sysex_message(
            [(i, 0, 0, 127) for i in range(64)]
        )

    @property
    def shift_pressed(self) -> bool:
        """Check if shift is currently pressed."""
        return self._shift_pressed

    @property
    def alt_pressed(self) -> bool:
        """Check if alt is currently pressed."""
        return self._alt_pressed

    def start_listening(self):
        """Start the event listening thread with proper thread safety."""
        with self._lock:
            if not self.listening:
                self.listening = True
                self.listening_thread = threading.Thread(
                    target=self._listen, daemon=True
                )
                self.listening_thread.start()
                logger.debug("Started listening thread")

    def _send_midi_safe(
        self, message: List[int], max_retries: int = 3, retry_delay: float = 0.1
    ) -> bool:
        """Send MIDI message with error handling and retry logic.

        Args:
            message: MIDI message to send
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.midi_out:
            logger.error("MIDI output port not initialized")
            return False

        for attempt in range(max_retries):
            try:
                self.midi_out.send_message(message)
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to send MIDI message {message} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to send MIDI message after {max_retries} attempts: {message}"
                    )

        return False

    @staticmethod
    def list_midi_ports() -> Dict[str, List[str]]:
        """List all available MIDI ports."""
        try:
            import rtmidi

            midi_in = rtmidi.MidiIn()
            midi_out = rtmidi.MidiOut()
            return {"input": midi_in.get_ports(), "output": midi_out.get_ports()}
        except Exception as e:
            logger.error(f"Failed to list MIDI ports: {e}")
            return {"input": [], "output": []}

    def _find_ports(self):
        """Find the Akai Fire MIDI input and output ports."""
        input_port = None
        output_port = None

        try:
            input_ports = self.midi_in.get_ports()
            output_ports = self.midi_out.get_ports()
        except Exception as e:
            raise HardwareError(f"Failed to enumerate MIDI ports: {e}")

        # Search for input port
        for i, port_name in enumerate(input_ports):
            if self.look_for_port in port_name:
                input_port = i
                logger.info(f"Found Akai Fire MIDI INPUT port: {port_name}")
                break

        # Search for output port
        for i, port_name in enumerate(output_ports):
            if self.look_for_port in port_name:
                output_port = i
                logger.info(f"Found Akai Fire MIDI OUTPUT port: {port_name}")
                break

        # Log available ports if not found
        if input_port is None or output_port is None:
            logger.warning(
                f"AKAI Fire ports not found. Looking for: '{self.look_for_port}'"
            )
            logger.warning(f"Available input ports: {input_ports}")
            logger.warning(f"Available output ports: {output_ports}")

        return input_port, output_port

    def close(self):
        """Closes the MIDI input and output ports safely."""
        with self._lock:
            self.listening = False
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=2.0)  # Don't wait forever

        try:
            if hasattr(self, "midi_in") and self.midi_in:
                self.midi_in.close_port()
        except Exception as e:
            logger.error(f"Error closing MIDI input: {e}")

        try:
            if hasattr(self, "midi_out") and self.midi_out:
                self.midi_out.close_port()
        except Exception as e:
            logger.error(f"Error closing MIDI output: {e}")

    def reconnect(self) -> bool:
        """Attempt to reconnect to MIDI ports.

        Returns:
            True if reconnection successful, False otherwise
        """
        logger.info("Attempting to reconnect to AKAI Fire...")

        # Close existing connections
        self.close()

        try:
            # Re-initialize MIDI
            self.midi_in = rtmidi.MidiIn()
            self.midi_out = rtmidi.MidiOut()
            self.input_port_index, self.output_port_index = self._find_ports()

            if self.output_port_index is None or self.input_port_index is None:
                logger.error("AKAI Fire ports not found during reconnection")
                return False

            self.midi_out.open_port(self.output_port_index)
            self.midi_in.open_port(self.input_port_index)

            # Clear cached states
            self._last_pad_states.clear()

            # Restart listener if it was running
            if self.listening:
                self.start_listening()

            logger.info("Successfully reconnected to AKAI Fire")
            return True

        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if MIDI ports are connected and responsive.

        Returns:
            True if connected, False otherwise
        """
        if not hasattr(self, "midi_out") or not self.midi_out:
            return False

        try:
            # Try to send a harmless message (clear a non-existent pad)
            test_msg = [
                0xF0,
                0x47,
                0x7F,
                0x43,
                0x65,
                0x00,
                0x04,
                0xFF,
                0x00,
                0x00,
                0x00,
                0xF7,
            ]
            self.midi_out.send_message(test_msg)
            return True
        except Exception:
            return False

    def clear_all(self) -> bool:
        """Clear all LEDs and display."""
        success = True
        success &= self.clear_all_pads()
        success &= self.clear_all_button_leds()
        success &= self.clear_all_track_leds()
        success &= self.clear_all_track_leds()
        success &= self.clear_control_bank_leds()
        self.clear_display()
        return success

    @staticmethod
    def _create_sysex_message(pad_colors):
        """
        Constructs a SysEx message to update pads on the Akai Fire.
        :param pad_colors: List of (index, red, green, blue) tuples for the pads to update.
        :return: A SysEx message as a list of bytes.
        """
        sysex_header = [0xF0, 0x47, 0x7F, 0x43, 0x65]

        # Length of payload
        length = len(pad_colors) * 4
        length_high = (length >> 7) & 0x7F
        length_low = length & 0x7F

        # Construct payload for pads
        payload = []
        for index, red, green, blue in pad_colors:
            payload.extend(
                [
                    index & 0x3F,
                    red & 0x7F,
                    green & 0x7F,
                    blue & 0x7F,
                ]
            )

        return sysex_header + [length_high, length_low] + payload + [0xF7]

    def set_pad_color(self, index: int, red: int, green: int, blue: int) -> bool:
        """
        Set pad color with validation.

        Args:
            index: Pad index (0-63)
            red: Red component (0-127)
            green: Green component (0-127)
            blue: Blue component (0-127)

        Returns:
            bool: True if successful

        Raises:
            InvalidParameterError: If pad index is out of range
        """
        if not isinstance(index, int) or not (0 <= index <= 63):
            raise InvalidParameterError(f"Pad index must be integer 0-63, got: {index}")

        # Clamp color values with validation
        if not isinstance(red, int):
            raise InvalidParameterError(
                f"Red value must be integer, got: {type(red).__name__}"
            )
        if not isinstance(green, int):
            raise InvalidParameterError(
                f"Green value must be integer, got: {type(green).__name__}"
            )
        if not isinstance(blue, int):
            raise InvalidParameterError(
                f"Blue value must be integer, got: {type(blue).__name__}"
            )

        red = max(0, min(127, red))
        green = max(0, min(127, green))
        blue = max(0, min(127, blue))

        # Check if color actually changed (performance optimization)
        state_key = f"{index}:{red}:{green}:{blue}"
        if state_key in self._last_pad_states:
            return True  # No need to update
        self._last_pad_states[state_key] = True

        sysex_message = self._create_sysex_message([(index, red, green, blue)])
        return self._send_midi_safe(sysex_message)

    def set_pad_color_fast(self, index: int, red: int, green: int, blue: int) -> bool:
        """
        Fast path for setting pad color - assumes valid inputs.

        Use this when you know inputs are valid (0-63 for index, 0-127 for colors).
        Skips validation for better performance in tight loops.

        Args:
            index: Pad index (0-63) - MUST be valid
            red: Red component (0-127) - MUST be valid
            green: Green component (0-127) - MUST be valid
            blue: Blue component (0-127) - MUST be valid

        Returns:
            bool: True if successful
        """
        sysex_message = self._create_sysex_message([(index, red, green, blue)])
        return self._send_midi_safe(sysex_message)

    def set_multiple_pad_colors(
        self, pad_colors: List[Tuple[int, int, int, int]]
    ) -> bool:
        """
        Set multiple pad colors efficiently.

        Args:
            pad_colors: List of (index, red, green, blue) tuples

        Returns:
            bool: True if successful
        """
        # Validate and clamp values
        validated_colors = []
        for pad_data in pad_colors:
            if len(pad_data) == 4:
                index, red, green, blue = pad_data
                if 0 <= index <= 63:
                    red = max(0, min(127, red))
                    green = max(0, min(127, green))
                    blue = max(0, min(127, blue))
                    validated_colors.append((index, red, green, blue))
                else:
                    logger.warning(f"Invalid pad index: {index}")

        if validated_colors:
            sysex_message = self._create_sysex_message(validated_colors)
            return self._send_midi_safe(sysex_message)
        return False

    def clear_pad(self, index: int) -> bool:
        """Clear a single pad."""
        return self.set_pad_color(index, 0, 0, 0)

    def clear_all_pads(self) -> bool:
        """Clear all pads efficiently using cached message."""
        # Use cached clear message for better performance
        if hasattr(self, "_cached_messages") and "clear_pads" in self._cached_messages:
            return self._send_midi_safe(self._cached_messages["clear_pads"])
        else:
            # Fallback to creating message
            pad_colors = [(i, 0, 0, 0) for i in range(64)]
            sysex_message = self._create_sysex_message(pad_colors)
            return self._send_midi_safe(sysex_message)

    def reset_pads(self, red: int = 0, green: int = 0, blue: int = 0) -> bool:
        """Reset all pads to a specific color."""
        pad_colors = [(i, red, green, blue) for i in range(64)]
        return self.set_multiple_pad_colors(pad_colors)

    def set_all_pads(self, color: Tuple[int, int, int]) -> bool:
        """
        Set all pads to the same color - optimized version.

        Args:
            color: Tuple of (red, green, blue) values (0-127)

        Returns:
            bool: True if successful
        """
        r, g, b = color
        # Check for cached common colors
        if r == 0 and g == 0 and b == 0 and "clear_pads" in self._cached_messages:
            return self._send_midi_safe(self._cached_messages["clear_pads"])
        elif (
            r == 127 and g == 127 and b == 127 and "all_white" in self._cached_messages
        ):
            return self._send_midi_safe(self._cached_messages["all_white"])
        elif r == 127 and g == 0 and b == 0 and "all_red" in self._cached_messages:
            return self._send_midi_safe(self._cached_messages["all_red"])
        elif r == 0 and g == 127 and b == 0 and "all_green" in self._cached_messages:
            return self._send_midi_safe(self._cached_messages["all_green"])
        elif r == 0 and g == 0 and b == 127 and "all_blue" in self._cached_messages:
            return self._send_midi_safe(self._cached_messages["all_blue"])
        else:
            # Fallback to creating message
            return self.reset_pads(r, g, b)

    def set_button_led(self, button_id: int, value: int) -> bool:
        """Set button LED state with validation."""
        # Validate button ID
        valid_buttons = [
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_PATTERN,
            self.BUTTON_BROWSER,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
            self.BUTTON_BANK,
            self.BUTTON_SELECT,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
        ]

        if button_id not in valid_buttons:
            raise InvalidParameterError(
                f"Invalid button ID: {button_id}. Valid buttons: {valid_buttons}"
            )

        value = max(0, min(2, value))
        message = [self.CC, button_id, value]
        return self._send_midi_safe(message)

    def clear_all_button_leds(self) -> bool:
        """Clear all button LEDs."""
        success = True
        for button_id in [
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_PATTERN,
            self.BUTTON_BROWSER,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
            self.BUTTON_BANK,
            self.BUTTON_SELECT,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
        ]:
            if not self.set_button_led(button_id, 0):
                success = False
        return success

    def clear_all_track_leds(self) -> bool:
        """Clear all track LEDs."""
        success = True
        for i in range(1, 5):
            if not self.set_track_led(i, 0):
                success = False
        return success

    def clear_track_led(self, track_number: int) -> bool:
        """Clear a single track LED."""
        return self.set_track_led(track_number, 0)

    def set_track_led(self, track_number: int, value: int) -> bool:
        """Set track LED (1-4) with validation."""
        if not (1 <= track_number <= 4):
            logger.warning(f"Invalid track number: {track_number}")
            return False

        cc_map = {1: 0x65, 2: 0x66, 3: 0x67, 4: 0x68}
        value = max(0, min(2, value))
        message = [self.CC, cc_map[track_number], value]
        return self._send_midi_safe(message)

    def clear_control_bank_leds(self) -> bool:
        """Clear control bank LEDs."""
        return self.set_control_bank_leds(0)

    def set_control_bank_leds(self, state: int) -> bool:
        """Set control bank LED state."""
        message = [self.CC, 0x1B, state & 0x7F]
        return self._send_midi_safe(message)

    def add_rotary_listener(self, rotary_id, callback):
        """
        Adds a listener for rotary control turn events.
        :param rotary_id: One of the ROTARY_* constants.
        :param callback: Function to call when the rotary control is turned.
                     The callback receives (direction, velocity).
        """
        if rotary_id not in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        ]:
            raise ValueError(f"Invalid rotary ID: {rotary_id}")

        with self._lock:
            self.rotary_listeners[rotary_id].append(callback)
        self.start_listening()

    def add_rotary_touch_listener(self, rotary_id, callback):
        """
        Adds a listener for rotary control touch events.
        :param rotary_id: One of the ROTARY_* constants.
        :param callback: Function to call when the rotary control is touched or released.
                         The callback receives (event), where event is "touch" or "release".
        """
        if rotary_id not in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        ]:
            raise ValueError(f"Invalid rotary ID: {rotary_id}")

        with self._lock:
            self.rotary_touch_listeners[rotary_id].append(callback)
        self.start_listening()

    def add_button_listener(self, button_id, callback):
        """
        Adds a listener for button press and release events.
        :param button_id: One of the BUTTON_* constants.
        :param callback: Function to call when the button is pressed or released.
                     The callback receives (event), where event is "press" or "release".
        """
        if button_id not in [
            self.BUTTON_SELECT,
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_PATTERN,
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_BANK,
            self.BUTTON_BROWSER,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ]:
            raise ValueError(f"Invalid button ID: {button_id}")

        with self._lock:
            self.button_listeners[button_id].append(callback)
        self.start_listening()

    def add_listener(self, pad_indices, callback):
        """
        Adds a listener for specific pad presses.
        :param pad_indices: List of pad indices to listen for.
        :param callback: Function to call when a pad in the list is pressed.
        """
        with self._lock:
            for index in pad_indices:
                if not (0 <= index <= 63):
                    raise ValueError("Pad index must be between 0 and 63")
                if index not in self.pad_listeners:
                    self.pad_listeners[index] = []

                self.pad_listeners[index].append(callback)

        self.start_listening()

    @staticmethod
    def pad_position(pad_index) -> tuple:
        """
        Determines the column and row of a pad based on its index.
        :param pad_index: Pad index (0-63).
        :return:  (column, row)
        """
        col = pad_index % 16
        row = pad_index // 16

        return col, row

    @staticmethod
    def get_pad_column(pad_index):
        """
        Determines which column a pad belongs to (1-16).
        :param pad_index: Pad index (0-63).
        :return: Column number (1-16).
        """
        return (pad_index % 16) + 1

    @staticmethod
    def get_pad_row(pad_index):
        """
        Determines which row a pad belongs to (1-4).
        :param pad_index: Pad index (0-63).
        :return: Row number (1-4).
        """
        return (pad_index // 16) + 1

    def _invoke(self, handler, *args):
        """Call a user handler with per-handler exception isolation.

        A raised exception is logged but does not prevent subsequent handlers
        (registered for the same or different events) from running.
        """
        try:
            handler(*args)
        except Exception:
            logger.exception("Handler %r raised", handler)

    def _process_message(self, message):
        """Process a single MIDI message and dispatch to listeners.

        Message parsing errors are logged and swallowed so a malformed packet
        does not kill the listening thread. Handler exceptions are isolated
        per-handler via :meth:`_invoke`.
        """
        # --- message parsing (narrow exception scope) ---------------------
        try:
            if not message or not isinstance(message, (list, tuple)):
                return
            if not isinstance(message[0], (list, tuple)):
                return

            data, _ = message
            if len(data) < 3:
                return

            status = data[0]
            controller = data[1]
            value = data[2]
        except (ValueError, IndexError, TypeError):
            logger.warning("Malformed MIDI message: %r", message, exc_info=True)
            return

        # --- dispatch (per-handler exception isolation via _invoke) -------

        # Handle rotary touch events first. (Note On/Off for rotary controls)
        # This needs to come before button handling since they share the same status codes.
        if status in [0x90, 0x80] and controller in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
        ]:
            event = "touch" if status == 0x90 else "release"

            with self._lock:
                handlers = list(self.rotary_touch_listeners[controller])
                global_handlers = list(self.rotary_touch_listeners["global"])

            for handler in handlers:
                self._invoke(handler, event)
            for handler in global_handlers:
                self._invoke(handler, controller, event)
            return

        # Latch modifier-key state inline, before any user handler runs.
        # This preserves the invariant that a pad/button handler reading
        # fire.is_shift_pressed() / is_alt_pressed() observes coherent
        # state, even when handlers are later dispatched asynchronously.
        if status in (0x90, 0x80) and controller in (self.BUTTON_SHIFT, self.BUTTON_ALT):
            pressed = status == 0x90
            if controller == self.BUTTON_SHIFT:
                self._shift_pressed = pressed
            else:
                self._alt_pressed = pressed
            # fall through into the normal button-dispatch block below

        # Handle button events
        if status in [0x90, 0x80] and controller in [
            self.BUTTON_SELECT,
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_PATTERN,
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_BANK,
            self.BUTTON_BROWSER,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ]:
            event = "press" if status == 0x90 else "release"

            with self._lock:
                handlers = list(self.button_listeners[controller])
                global_handlers = list(self.button_listeners["global"])

            for handler in handlers:
                self._invoke(handler, event)
            for handler in global_handlers:
                self._invoke(handler, controller, event)
            return

        # Handle pad events (0x90 = Note On, value > 0 = velocity)
        if status == 0x90 and value > 0:
            pad_index = controller - 54
            if 0 <= pad_index <= 63:
                with self._lock:
                    handlers = list(self.pad_listeners[pad_index])
                    global_handlers = list(self.pad_listeners["global"])

                for handler in handlers:
                    self._invoke(handler, value)
                for handler in global_handlers:
                    self._invoke(handler, pad_index, value)
            return

        # Handle rotary turn events (Control Change)
        if status == 0xB0 and controller in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        ]:
            direction = "clockwise" if value < 0x40 else "counterclockwise"
            velocity = value if value < 0x40 else (0x80 - value)

            with self._lock:
                handlers = list(self.rotary_listeners[controller])
                global_handlers = list(self.rotary_listeners["global"])

            for handler in handlers:
                self._invoke(handler, direction, velocity)
            for handler in global_handlers:
                self._invoke(handler, controller, direction, velocity)
            return

    def _listen(self):
        """Internal method to listen for MIDI messages."""
        while True:
            with self._lock:
                if not self.listening:
                    break
            message = self.midi_in.get_message()
            if message:
                self._process_message(message)
            time.sleep(0.001)  # 1ms loop interval


# Convenience functions for device discovery and auto-selection
def discover_akai_fire() -> Optional[str]:
    """
    Discover connected AKAI Fire device.

    Returns:
        str: Port name if found, None otherwise
    """
    ports = AkaiFire.list_midi_ports()

    for port in ports["input"]:
        if "FIRE" in port.upper():
            return port

    return None


def get_akai_fire(use_mock: Optional[bool] = None, **kwargs) -> Union[AkaiFire, Any]:
    """
    Get AKAI Fire instance (hardware or mock).

    Args:
        use_mock: True to force mock, False to force hardware, None to auto-detect
        **kwargs: Additional arguments passed to constructor

    Returns:
        AkaiFire instance or mock instance
    """
    if use_mock is True:
        try:
            from mock_gui_pygame import MockAkaiFire

            return MockAkaiFire(**kwargs)
        except ImportError:
            logger.error("Mock GUI not available")
            raise
    elif use_mock is False:
        return AkaiFire(**kwargs)
    else:
        # Auto-detect
        try:
            return AkaiFire(**kwargs)
        except (MIDIConnectionError, Exception) as e:
            logger.info(f"Hardware not available ({e}), trying mock...")
            try:
                from mock_gui_pygame import MockAkaiFire

                return MockAkaiFire(**kwargs)
            except ImportError:
                logger.error("Neither hardware nor mock available")
                raise
