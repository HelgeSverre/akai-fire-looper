import logging
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
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


class _HandlerDispatcher:
    """Dispatches user handlers on a worker thread pool so slow or
    throwing handlers cannot stall the MIDI polling thread.

    Backpressure strategy is **caller-runs**: when the bounded submit
    queue is saturated, the MIDI polling thread runs the handler inline
    (logging a warning). No event is ever dropped; under sustained
    overload the MIDI thread briefly stalls instead.

    Every submission is wrapped with a per-handler try/except that
    routes exceptions through ``logger.exception`` so one misbehaving
    listener cannot kill the worker or silence siblings.
    """

    def __init__(self, max_workers: int = 4, queue_size: int = 64):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="akai-fire-handler",
        )
        self._sem = threading.BoundedSemaphore(queue_size)

    def submit(self, fn, *args) -> None:
        if not self._sem.acquire(blocking=False):
            logger.warning(
                "Handler queue full; running %r inline on MIDI thread", fn
            )
            try:
                fn(*args)
            except Exception:
                logger.exception("Handler %r raised (inline)", fn)
            return

        def _run():
            try:
                fn(*args)
            except Exception:
                logger.exception("Handler %r raised", fn)
            finally:
                self._sem.release()

        try:
            self._executor.submit(_run)
        except RuntimeError:
            # Executor already shut down — run inline so we don't lose the event.
            self._sem.release()
            try:
                fn(*args)
            except Exception:
                logger.exception("Handler %r raised (post-shutdown)", fn)

    def shutdown(self) -> None:
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            logger.exception("Error shutting down handler dispatcher")


from akai_fire.device import AkaiFireDevice


# noinspection GrazieInspection
class AkaiFire(AkaiFireDevice):
    """Real AKAI Fire MIDI controller.

    MIDI constants, modifier state, pad-geometry utilities, and the
    solo-button index lookup are inherited from :class:`AkaiFireDevice`.
    This class adds the hardware-specific rtmidi I/O, SysEx encoding,
    async dispatcher, and MIDI-polling thread.
    """

    # render_to_display / render_to_bmp / clear_display / get_canvas
    # are inherited from AkaiFireDevice — authored once so the
    # canvas=None signature cannot drift again. Subclasses (this one
    # included) implement _deliver_display and new_canvas.

    def _deliver_display(self, canvas) -> None:
        """Encode the canvas as an OLED SysEx message and send it."""
        if not self.midi_out:
            raise StateError("MIDI output not initialized")

        if not isinstance(canvas, Canvas):
            raise InvalidParameterError(
                f"Expected Canvas object, got: {type(canvas).__name__}"
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
        pixels = canvas.image.load()
        for y in range(canvas.HEIGHT):
            y_div_8 = y // 8
            y_mod_8 = y % 8
            for x in range(canvas.WIDTH):
                if pixels[x, y] == 0:  # Black pixel in PIL = ON in OLED
                    x_mapped = x + canvas.WIDTH * y_div_8
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

    def __init__(
        self,
        port_name=None,
        *,
        async_handlers: bool = True,
        max_workers: int = 4,
        handler_queue_size: int = 64,
        send_retry_delay: float = 0.01,
        send_max_retries: int = 2,
    ):
        """Initialize AKAI Fire controller.

        Args:
            port_name: MIDI port name to look for. Defaults to "FL STUDIO FIRE".
            async_handlers: If True (default), user callbacks registered via
                ``@on_pad`` / ``@on_button`` / ``@on_rotary_*`` / ``add_*_listener``
                run on a background thread pool so a slow callback cannot stall
                the MIDI polling thread. Set False for strict serial dispatch on
                the polling thread.
            max_workers: Number of worker threads in the handler dispatch pool.
                ``1`` preserves strict FIFO ordering across all events; the
                default ``4`` allows parallel handling of independent events.
            handler_queue_size: Bounded-queue size for handler submission. When
                the queue is full, the MIDI thread runs the handler inline
                (caller-runs backpressure); no event is dropped.
            send_retry_delay: Seconds to wait between MIDI send retries.
            send_max_retries: Max MIDI send retry attempts.
        """
        # Base class installs self._lock + modifier flags.
        super().__init__()

        # _stop_event replaces the old ``self.listening`` bool; Event
        # acquires no lock on is_set(), so the polling loop doesn't spin
        # an RLock every iteration.
        self._stop_event = threading.Event()
        self._stop_event.set()  # "stopped" until start_listening clears it
        self.listening_thread = None

        # Handler dispatch: thread pool with per-handler exception isolation.
        self._dispatcher: Optional[_HandlerDispatcher] = (
            _HandlerDispatcher(max_workers=max_workers, queue_size=handler_queue_size)
            if async_handlers
            else None
        )

        # MIDI send retry tuning.
        self._send_retry_delay = send_retry_delay
        self._send_max_retries = send_max_retries

        self.canvas = Canvas()
        self.look_for_port = port_name or "FL STUDIO FIRE"

        # Listener registries are provided by AkaiFireDevice.__init__.

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

    # Decorators (on_pad / on_button / on_rotary_turn / on_rotary_touch /
    # on_solo) and listener adders are inherited from AkaiFireDevice.

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
    def listening(self) -> bool:
        """True while the MIDI listening thread is running."""
        return not self._stop_event.is_set()

    def start_listening(self):
        """Start the event listening thread (idempotent)."""
        with self._lock:
            if self._stop_event.is_set():
                self._stop_event.clear()
                self.listening_thread = threading.Thread(
                    target=self._listen, daemon=True
                )
                self.listening_thread.start()
                logger.debug("Started listening thread")

    def _send_midi_safe(
        self,
        message: List[int],
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ) -> bool:
        """Send MIDI message with error handling and retry logic.

        Args:
            message: MIDI message to send.
            max_retries: Max retry attempts. Defaults to the instance's
                ``send_max_retries`` (2).
            retry_delay: Seconds between retries. Defaults to the instance's
                ``send_retry_delay`` (0.01s).

        Returns:
            True if message sent successfully, False otherwise.
        """
        if not self.midi_out:
            logger.error("MIDI output port not initialized")
            return False

        if max_retries is None:
            max_retries = self._send_max_retries
        if retry_delay is None:
            retry_delay = self._send_retry_delay

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
        self._stop_event.set()
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=2.0)  # Don't wait forever

        if self._dispatcher is not None:
            self._dispatcher.shutdown()
            self._dispatcher = None

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

    # Listener adders (add_listener / add_rotary_listener / etc.) and
    # _invoke are inherited from AkaiFireDevice.

    # Controller IDs for the two categories that overlap 0x90/0x80 with
    # buttons (rotary touches precede button decoding for that reason).
    _TOUCHABLE_ROTARIES = (
        0x10,  # ROTARY_VOLUME
        0x11,  # ROTARY_PAN
        0x12,  # ROTARY_FILTER
        0x13,  # ROTARY_RESONANCE
    )
    _BUTTON_IDS = (
        0x19, 0x1A, 0x1F, 0x20, 0x21, 0x22, 0x23,
        0x24, 0x25, 0x26, 0x27, 0x2C, 0x2D, 0x2E, 0x2F,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35,
    )
    _ROTARY_IDS = (0x10, 0x11, 0x12, 0x13, 0x76)

    def _process_message(self, message):
        """Decode a raw MIDI message and route it to a ``_dispatch_*`` helper.

        Parsing errors are logged and swallowed so a malformed packet
        doesn't kill the listening thread. Dispatch itself (modifier
        latching, listener-list snapshot, per-handler exception
        isolation) lives on :class:`AkaiFireDevice`.
        """
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

        # Rotary touch events share 0x90/0x80 with buttons — must come first.
        if status in (0x90, 0x80) and controller in self._TOUCHABLE_ROTARIES:
            event = "touch" if status == 0x90 else "release"
            self._dispatch_rotary_touch(controller, event)
            return

        if status in (0x90, 0x80) and controller in self._BUTTON_IDS:
            event = "press" if status == 0x90 else "release"
            self._dispatch_button(controller, event)
            return

        if status == 0x90 and value > 0:
            pad_index = controller - 54
            if 0 <= pad_index <= 63:
                self._dispatch_pad(pad_index, value)
            return

        if status == 0xB0 and controller in self._ROTARY_IDS:
            direction = "clockwise" if value < 0x40 else "counterclockwise"
            velocity = value if value < 0x40 else (0x80 - value)
            self._dispatch_rotary_turn(controller, direction, velocity)
            return

    def _listen(self):
        """Poll the MIDI input port for messages and dispatch them.

        Uses ``self._stop_event`` for termination; ``is_set()`` is lockless,
        so the loop doesn't acquire an RLock every iteration. The 1 ms
        idle sleep keeps CPU usage low while MIDI is quiet.
        """
        while not self._stop_event.is_set():
            message = self.midi_in.get_message()
            if message:
                self._process_message(message)
            else:
                time.sleep(0.001)


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


def get_akai_fire(
    use_mock: Optional[Union[bool, str]] = None, **kwargs
) -> Union[AkaiFire, Any]:
    """Get an AKAI Fire instance (hardware or mock).

    Args:
        use_mock:
            - ``True`` — force the interactive pygame mock.
            - ``False`` — force hardware (raises if unavailable).
            - ``"tui"`` — force the terminal-UI mock (``mock_gui_tui``).
            - ``"pygame"`` — explicit alias for the pygame mock.
            - ``None`` — auto-detect: try hardware, fall back to the pygame mock.
        **kwargs: Additional arguments passed to the selected constructor.

    Returns:
        AkaiFire instance or mock instance.
    """
    if use_mock == "tui":
        try:
            from mock_gui_tui import MockAkaiFire

            return MockAkaiFire(**kwargs)
        except ImportError:
            logger.error("TUI mock not available (install 'rich')")
            raise
    if use_mock is True or use_mock == "pygame":
        try:
            from mock_gui_pygame import MockAkaiFire

            return MockAkaiFire(**kwargs)
        except ImportError:
            logger.error("Mock GUI not available")
            raise
    if use_mock is False:
        return AkaiFire(**kwargs)

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
