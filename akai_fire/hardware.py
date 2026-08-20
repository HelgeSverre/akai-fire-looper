"""Hardware-backed AKAI Fire implementation (rtmidi + SysEx + polling).

Kept in its own module so ``import akai_fire`` (or downstream imports of
``akai_fire.device`` from the testing package) can avoid pulling in
``rtmidi`` unless something actually dereferences :class:`AkaiFire`,
:func:`get_akai_fire`, or :func:`discover_akai_fire`.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple, Union

import rtmidi

from akai_fire.canvas import Canvas
from akai_fire.device import AkaiFireDevice
from akai_fire.errors import (
    HardwareError,
    InvalidParameterError,
    MIDIConnectionError,
    MIDISendError,
    StateError,
)

logger = logging.getLogger(__name__)


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
            logger.warning("Handler queue full; running %r inline on MIDI thread", fn)
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

        try:
            self.midi_out.send_message(sysex_data)
        except Exception as e:
            raise MIDISendError(f"Failed to send display SysEx message: {e}") from e

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
        # Remember the ctor args so reconnect() can rebuild the dispatcher
        # after close() tore it down.
        self._async_handlers = async_handlers
        self._max_workers = max_workers
        self._handler_queue_size = handler_queue_size
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

        # Snapshot listener state BEFORE close() clears _stop_event; otherwise
        # self.listening is always False here and the restart branch below is
        # unreachable.
        was_listening = self.listening

        # Close existing connections (also tears down the dispatcher).
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

            # Always rebuild the async dispatcher that close() tore down,
            # regardless of whether we are about to start listening: a
            # later start_listening() must not silently fall back to
            # inline dispatch on the polling thread.
            if self._dispatcher is None and self._async_handlers:
                self._dispatcher = _HandlerDispatcher(
                    max_workers=self._max_workers,
                    queue_size=self._handler_queue_size,
                )

            # Restart listener if it was running pre-close.
            if was_listening:
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

        color = (red, green, blue)
        # Short-circuit only when the pad is ALREADY showing this color.
        # _last_pad_states keys are pad indices, not historical states.
        if self._last_pad_states.get(index) == color:
            return True

        sysex_message = self._create_sysex_message([(index, red, green, blue)])
        sent = self._send_midi_safe(sysex_message)
        if sent:
            self._last_pad_states[index] = color
        return sent

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
        sent = self._send_midi_safe(sysex_message)
        if sent:
            # Keep the cache coherent so a later set_pad_color() with the
            # same color correctly short-circuits and a different color
            # correctly sends.
            self._last_pad_states[index] = (red, green, blue)
        return sent

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
            sent = self._send_midi_safe(sysex_message)
            if sent:
                for idx, r, g, b in validated_colors:
                    self._last_pad_states[idx] = (r, g, b)
            return sent
        return False

    def clear_pad(self, index: int) -> bool:
        """Clear a single pad."""
        return self.set_pad_color(index, 0, 0, 0)

    def clear_all_pads(self) -> bool:
        """Clear all pads efficiently using cached message."""
        # Use cached clear message for better performance
        if hasattr(self, "_cached_messages") and "clear_pads" in self._cached_messages:
            sent = self._send_midi_safe(self._cached_messages["clear_pads"])
        else:
            # Fallback to creating message
            pad_colors = [(i, 0, 0, 0) for i in range(64)]
            sysex_message = self._create_sysex_message(pad_colors)
            sent = self._send_midi_safe(sysex_message)
        if sent:
            self._last_pad_states = {i: (0, 0, 0) for i in range(64)}
        return sent

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
        cached_key = None
        if r == 0 and g == 0 and b == 0 and "clear_pads" in self._cached_messages:
            cached_key = "clear_pads"
        elif (
            r == 127 and g == 127 and b == 127 and "all_white" in self._cached_messages
        ):
            cached_key = "all_white"
        elif r == 127 and g == 0 and b == 0 and "all_red" in self._cached_messages:
            cached_key = "all_red"
        elif r == 0 and g == 127 and b == 0 and "all_green" in self._cached_messages:
            cached_key = "all_green"
        elif r == 0 and g == 0 and b == 127 and "all_blue" in self._cached_messages:
            cached_key = "all_blue"

        if cached_key is not None:
            sent = self._send_midi_safe(self._cached_messages[cached_key])
            if sent:
                self._last_pad_states = {i: (r, g, b) for i in range(64)}
            return sent
        # Fallback to creating message (reset_pads → set_multiple_pad_colors
        # already updates _last_pad_states).
        return self.reset_pads(r, g, b)

    def set_button_led(self, button_id: int, value: int) -> bool:
        """Set button LED state with validation."""
        if button_id not in self.BUTTON_LED_IDS:
            raise InvalidParameterError(
                f"Invalid button ID: {button_id}. "
                f"Valid buttons: {sorted(self.BUTTON_LED_IDS)}"
            )

        value = max(0, min(2, value))
        message = [self.CC, button_id, value]
        return self._send_midi_safe(message)

    def clear_all_button_leds(self) -> bool:
        """Clear all button LEDs."""
        success = True
        for button_id in sorted(self.BUTTON_LED_IDS):
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
        0x19,
        0x1A,
        0x1F,
        0x20,
        0x21,
        0x22,
        0x23,
        0x24,
        0x25,
        0x26,
        0x27,
        0x2C,
        0x2D,
        0x2E,
        0x2F,
        0x30,
        0x31,
        0x32,
        0x33,
        0x34,
        0x35,
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
