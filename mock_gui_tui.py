"""Terminal-UI mock of the AKAI Fire controller (scaffold — commit 1 of 4).

A third mock class alongside :mod:`mock_gui_pygame` (interactive GUI) and
:mod:`akai_fire_testing.mocks` (headless test fixture). This one renders the
device in a terminal using :mod:`rich`, with keyboard navigation instead of
mouse clicks.

Exposed through ``get_akai_fire(use_mock="tui")``.

This commit scaffolds the API surface — state, constants, setters, and
decorators — so :class:`MockAkaiFire` is a drop-in replacement for the
pygame mock in non-rendering paths. Rendering (the rich Layout) and
keyboard input are added in subsequent commits.

Use ``headless=True`` to skip the render thread and stdin reader; tests
(and tests-of-tests) rely on this.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import rich  # noqa: F401  # late-imported in rendering code, probe here
except ImportError as e:  # pragma: no cover - dep guard
    raise ImportError(
        "mock_gui_tui requires the 'rich' package. "
        "Install with: pip install rich   (or uv pip install rich)"
    ) from e

# Reuse the real Canvas from akai_fire so the OLED API is identical.
from akai_fire import Canvas


logger = logging.getLogger(__name__)


class MockAkaiFire:
    """Terminal-UI mock of the AKAI Fire controller.

    API parity with :class:`mock_gui_pygame.MockAkaiFire`; see that class
    for semantic contracts. The TUI-specific rendering and input threads
    are filled in by later commits — this scaffold already supports
    every setter, decorator, and state query.
    """

    # ------------------------------------------------------------------
    # MIDI constants — copied verbatim from mock_gui_pygame.MockAkaiFire
    # ------------------------------------------------------------------
    NOTE_ON = 0x90
    NOTE_OFF = 0x80
    CC = 0xB0

    # Button Constants
    BUTTON_PLAY = 0x33
    BUTTON_STOP = 0x34
    BUTTON_REC = 0x35
    BUTTON_SHIFT = 0x30
    BUTTON_ALT = 0x31
    BUTTON_STEP = 0x2C
    BUTTON_NOTE = 0x2D
    BUTTON_DRUM = 0x2E
    BUTTON_PERFORM = 0x2F
    BUTTON_PATTERN = 0x32
    BUTTON_BROWSER = 0x21
    BUTTON_GRID_LEFT = 0x22
    BUTTON_GRID_RIGHT = 0x23
    BUTTON_BANK = 0x1A
    BUTTON_SELECT = 0x19
    BUTTON_SOLO_1 = 0x24
    BUTTON_SOLO_2 = 0x25
    BUTTON_SOLO_3 = 0x26
    BUTTON_SOLO_4 = 0x27
    BUTTON_PAT_UP = 0x1F
    BUTTON_PAT_DOWN = 0x20

    # Rotary Controls
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # LED Values
    LED_OFF = 0x00
    LED_DULL_RED = 0x01
    LED_HIGH_RED = 0x02
    LED_DULL_GREEN = 0x01
    LED_HIGH_GREEN = 0x02
    LED_DULL_YELLOW = 0x03
    LED_HIGH_YELLOW = 0x04

    # Rectangle (track) LED values
    RECTANGLE_LED_OFF = 0x00
    RECTANGLE_LED_DULL_RED = 0x01
    RECTANGLE_LED_DULL_GREEN = 0x02
    RECTANGLE_LED_HIGH_RED = 0x03
    RECTANGLE_LED_HIGH_GREEN = 0x04

    # Control bank field constants
    FIELD_BASE = 0x10
    FIELD_CHANNEL = 0x01
    FIELD_MIXER = 0x02
    FIELD_USER1 = 0x04
    FIELD_USER2 = 0x08

    # Control bank LED states
    CONTROL_BANK_ALL_OFF = 0x00
    CONTROL_BANK_CHANNEL = FIELD_BASE | FIELD_CHANNEL
    CONTROL_BANK_MIXER = FIELD_BASE | FIELD_MIXER
    CONTROL_BANK_USER1 = FIELD_BASE | FIELD_USER1
    CONTROL_BANK_USER2 = FIELD_BASE | FIELD_USER2
    CONTROL_BANK_ALL_ON = (
        FIELD_BASE | FIELD_CHANNEL | FIELD_MIXER | FIELD_USER1 | FIELD_USER2
    )

    SOLO_BUTTONS: Dict[int, int] = {
        1: BUTTON_SOLO_1,
        2: BUTTON_SOLO_2,
        3: BUTTON_SOLO_3,
        4: BUTTON_SOLO_4,
    }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(
        self,
        port_name: str = "Mock AKAI Fire (TUI)",
        *,
        headless: bool = False,
    ) -> None:
        """Initialize the TUI mock.

        Args:
            port_name: Cosmetic label shown in the chassis title.
            headless: If True, skip the render thread and stdin reader.
                Used by tests to exercise state and dispatch without a
                real TTY.
        """
        self.port_name = port_name
        self._headless = headless
        self._closed = False

        # --- state (mirrors mock_gui_pygame field-for-field) ----------
        self._state_lock = threading.RLock()

        self.pad_colors: List[List[int]] = [[0, 0, 0] for _ in range(64)]
        self.button_leds: Dict[int, int] = {}
        self.track_leds: List[int] = [0, 0, 0, 0]
        self.control_bank_state: int = 0

        self.canvas = Canvas()

        # Modifier state — latched on SHIFT/ALT key (toggle behaviour).
        self._shift_pressed: bool = False
        self._alt_pressed: bool = False

        # Listener registries
        self.pad_listeners: Dict[int, List[Callable]] = defaultdict(list)
        self.global_pad_listeners: List[Callable] = []
        self.button_listeners: Dict[int, List[Callable]] = defaultdict(list)
        self.global_button_listeners: List[Callable] = []
        self.rotary_listeners: Dict[int, List[Callable]] = defaultdict(list)
        self.global_rotary_listeners: List[Callable] = []
        self.rotary_touch_listeners: Dict[int, List[Callable]] = defaultdict(list)
        self.global_rotary_touch_listeners: List[Callable] = []

        # --- rendering / input threads (filled in later commits) -----
        self._dirty = threading.Event()
        self._dirty.set()
        self._render_thread: Optional[threading.Thread] = None
        self._input_thread: Optional[threading.Thread] = None

        # Focus cursor — (region, index); region is one of "pad", "rotary",
        # "btn_mode", "btn_transport", "btn_bank", "btn_bottom", "mutesolo",
        # "pattern". Default puts the user on pad 0.
        self._focus: Tuple[str, int] = ("pad", 0)

        if not self._headless:
            self._start_threads()

    def __enter__(self) -> "MockAkaiFire":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.clear_display()
        self.close()

    def close(self) -> None:
        """Shut down render/input threads and release resources."""
        if self._closed:
            return
        self._closed = True
        self._stop_threads()

    def process_events(self) -> bool:
        """No-op for the TUI mock; both threads run autonomously.

        Retained for API parity with ``mock_gui_pygame.MockAkaiFire`` so
        caller loops like ``while fire.process_events(): ...`` still work.
        """
        return not self._closed

    def start_listening(self) -> None:
        """No-op (listener dispatch happens on the input thread)."""

    # ------------------------------------------------------------------
    # Thread management — stubs for commits 2 & 3
    # ------------------------------------------------------------------

    def _start_threads(self) -> None:
        """Start render + input threads. Filled in by later commits."""
        # Placeholder — commits 2 (render) and 3 (input) will populate.

    def _stop_threads(self) -> None:
        """Stop render + input threads. Idempotent."""
        for t in (self._render_thread, self._input_thread):
            if t and t.is_alive():
                t.join(timeout=0.5)
        self._render_thread = None
        self._input_thread = None

    def _mark_dirty(self) -> None:
        self._dirty.set()

    # ------------------------------------------------------------------
    # Pad / LED setters
    # ------------------------------------------------------------------

    def set_pad_color(self, index: int, red: int, green: int, blue: int) -> bool:
        if not (0 <= index < 64):
            return False
        with self._state_lock:
            self.pad_colors[index] = [
                max(0, min(127, red)),
                max(0, min(127, green)),
                max(0, min(127, blue)),
            ]
        self._mark_dirty()
        return True

    def set_pad_color_fast(self, index: int, red: int, green: int, blue: int) -> bool:
        """Alias of :meth:`set_pad_color` on the mock (no perf path to skip)."""
        return self.set_pad_color(index, red, green, blue)

    def set_multiple_pad_colors(self, pad_colors: List[Tuple[int, int, int, int]]) -> bool:
        with self._state_lock:
            for entry in pad_colors:
                if len(entry) != 4:
                    continue
                idx, r, g, b = entry
                if 0 <= idx < 64:
                    self.pad_colors[idx] = [
                        max(0, min(127, r)),
                        max(0, min(127, g)),
                        max(0, min(127, b)),
                    ]
        self._mark_dirty()
        return True

    def set_all_pads(self, color: Tuple[int, int, int]) -> bool:
        r, g, b = color
        with self._state_lock:
            for i in range(64):
                self.pad_colors[i] = [
                    max(0, min(127, r)),
                    max(0, min(127, g)),
                    max(0, min(127, b)),
                ]
        self._mark_dirty()
        return True

    def reset_pads(self, red: int = 0, green: int = 0, blue: int = 0) -> None:
        self.set_all_pads((red, green, blue))

    def clear_pad(self, index: int) -> bool:
        return self.set_pad_color(index, 0, 0, 0)

    def clear_all_pads(self) -> None:
        self.set_all_pads((0, 0, 0))

    def set_button_led(self, button_id: int, value: int) -> None:
        with self._state_lock:
            self.button_leds[button_id] = value
        self._mark_dirty()

    def clear_all_button_leds(self) -> None:
        with self._state_lock:
            self.button_leds.clear()
        self._mark_dirty()

    def set_track_led(self, track_number: int, value: int) -> bool:
        if not (1 <= track_number <= 4):
            return False
        with self._state_lock:
            self.track_leds[track_number - 1] = value
        self._mark_dirty()
        return True

    def clear_track_led(self, track_number: int) -> bool:
        return self.set_track_led(track_number, 0)

    def clear_all_track_leds(self) -> None:
        with self._state_lock:
            self.track_leds = [0, 0, 0, 0]
        self._mark_dirty()

    def set_control_bank_leds(self, state: int) -> None:
        with self._state_lock:
            self.control_bank_state = state
        self._mark_dirty()

    def clear_control_bank_leds(self) -> None:
        self.set_control_bank_leds(0)

    def clear_all(self) -> None:
        self.clear_all_pads()
        self.clear_all_button_leds()
        self.clear_all_track_leds()
        self.clear_control_bank_leds()
        self.clear_display()

    # ------------------------------------------------------------------
    # OLED canvas
    # ------------------------------------------------------------------

    def get_canvas(self) -> Canvas:
        return self.canvas

    def new_canvas(self) -> Canvas:
        self.canvas = Canvas()
        self._mark_dirty()
        return self.canvas

    def render_to_display(self, canvas: Optional[Canvas] = None) -> None:
        """Swap in ``canvas`` (if provided) as the current display buffer.

        Matches ``AkaiFire.render_to_display(canvas=None)`` — the passed
        canvas becomes the one the render thread draws from next frame.
        """
        if canvas is not None:
            self.canvas = canvas
        self._mark_dirty()

    def render_to_bmp(self, filename: str, image_format: str = "BMP") -> None:
        self.canvas.image.save(filename, image_format)

    def clear_display(self) -> None:
        self.canvas.clear()
        self._mark_dirty()

    # ------------------------------------------------------------------
    # Event decorators
    # ------------------------------------------------------------------

    def on_pad(self, pad_index: Any = None) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            with self._state_lock:
                if pad_index is None:
                    self.global_pad_listeners.append(func)
                elif isinstance(pad_index, (list, tuple)):
                    for idx in pad_index:
                        if 0 <= idx <= 63:
                            self.pad_listeners[idx].append(func)
                else:
                    if 0 <= pad_index <= 63:
                        self.pad_listeners[pad_index].append(func)
            return func

        return decorator

    def on_button(self, button_id: Optional[int] = None) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            with self._state_lock:
                if button_id is None:
                    self.global_button_listeners.append(func)
                else:
                    self.button_listeners[button_id].append(func)
            return func

        return decorator

    def on_rotary_turn(self, rotary_id: Optional[int] = None) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            with self._state_lock:
                if rotary_id is None:
                    self.global_rotary_listeners.append(func)
                else:
                    self.rotary_listeners[rotary_id].append(func)
            return func

        return decorator

    def on_rotary_touch(self, rotary_id: Optional[int] = None) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            with self._state_lock:
                if rotary_id is None:
                    self.global_rotary_touch_listeners.append(func)
                else:
                    self.rotary_touch_listeners[rotary_id].append(func)
            return func

        return decorator

    def on_solo(self, index: Optional[int] = None) -> Callable[[Callable], Callable]:
        """Solo button decorator. ``index`` is 1-4, or None for all solos."""

        def decorator(func: Callable) -> Callable:
            with self._state_lock:
                if index is None:

                    def wrapper(button_id: int, event: str) -> None:
                        solo_index = self.get_solo_index(button_id)
                        if solo_index is not None:
                            func(solo_index, event)

                    self.global_button_listeners.append(wrapper)
                else:
                    if 1 <= index <= 4:
                        button_id = self.SOLO_BUTTONS[index]
                        self.button_listeners[button_id].append(func)
            return func

        return decorator

    # ------------------------------------------------------------------
    # Listener adders (non-decorator forms)
    # ------------------------------------------------------------------

    def add_listener(self, pad_indices: Any, callback: Callable) -> None:
        with self._state_lock:
            if isinstance(pad_indices, (list, tuple)):
                for idx in pad_indices:
                    if 0 <= idx <= 63:
                        self.pad_listeners[idx].append(callback)
            else:
                if 0 <= pad_indices <= 63:
                    self.pad_listeners[pad_indices].append(callback)

    def add_global_listener(self, callback: Callable) -> None:
        with self._state_lock:
            self.global_pad_listeners.append(callback)

    def add_button_listener(self, button_id: int, callback: Callable) -> None:
        with self._state_lock:
            self.button_listeners[button_id].append(callback)

    def add_rotary_listener(self, rotary_id: int, callback: Callable) -> None:
        with self._state_lock:
            self.rotary_listeners[rotary_id].append(callback)

    def add_rotary_touch_listener(self, rotary_id: int, callback: Callable) -> None:
        with self._state_lock:
            self.rotary_touch_listeners[rotary_id].append(callback)

    # ------------------------------------------------------------------
    # Modifier state
    # ------------------------------------------------------------------

    def is_shift_pressed(self) -> bool:
        return self._shift_pressed

    def is_alt_pressed(self) -> bool:
        return self._alt_pressed

    @property
    def shift_pressed(self) -> bool:
        return self._shift_pressed

    @property
    def alt_pressed(self) -> bool:
        return self._alt_pressed

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def pad_position(pad_index: int) -> Tuple[int, int]:
        """Return ``(column, row)`` 0-indexed for a pad index 0-63."""
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return pad_index % 16, pad_index // 16

    @staticmethod
    def get_pad_column(pad_index: int) -> int:
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return pad_index % 16

    @staticmethod
    def get_pad_row(pad_index: int) -> int:
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return pad_index // 16

    @classmethod
    def get_solo_index(cls, button_id: int) -> Optional[int]:
        for index, bid in cls.SOLO_BUTTONS.items():
            if bid == button_id:
                return index
        return None

    @staticmethod
    def list_midi_ports() -> Dict[str, List[str]]:
        return {"input": [], "output": []}


if __name__ == "__main__":
    # Smoke test — construct headless, do some setter calls, close.
    with MockAkaiFire(headless=True) as fire:
        fire.set_pad_color(0, 127, 0, 0)
        fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
        fire.set_track_led(1, fire.RECTANGLE_LED_HIGH_GREEN)
        print(f"pad 0: {fire.pad_colors[0]}")
        print(f"PLAY LED: {fire.button_leds.get(fire.BUTTON_PLAY)}")
        print(f"track 1 LED: {fire.track_leds[0]}")
    print("smoke test ok")
