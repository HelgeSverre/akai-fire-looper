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
    from rich.align import Align
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError as e:  # pragma: no cover - dep guard
    raise ImportError(
        "mock_gui_tui requires the 'rich' package. "
        "Install with: pip install rich   (or uv pip install rich)"
    ) from e

from PIL import Image

# Reuse the real Canvas from akai_fire so the OLED API is identical.
from akai_fire import Canvas


logger = logging.getLogger(__name__)

RENDER_FPS = 20
OLED_FG = "rgb(255,160,50)"
OLED_BG = "black"
PANEL_BORDER = "grey42"

# Regions cycled by Tab (commit 3 uses this order).
REGIONS = (
    "rotary",
    "btn_bank",
    "btn_mode",
    "btn_transport",
    "pad",
    "mutesolo",
    "pattern",
    "btn_bottom",
)

# Button-row layouts: (region_name, [(label, button_id), ...]).
# Duplicated from MockAkaiFire's button constants so the renderer doesn't
# need to reach back into the class (avoids a self-import cycle).
_BANK_ROW = [("BANK", 0x1A), ("SEL", 0x19)]
_MODE_ROW = [("STEP", 0x2C), ("NOTE", 0x2D), ("DRUM", 0x2E), ("PERF", 0x2F)]
_TRANSPORT_ROW = [("PAT", 0x32), ("PLAY", 0x33), ("STOP", 0x34), ("REC", 0x35)]
_BROWSER_BUTTON = ("BROWSER", 0x21)


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

        # --- rendering / input threads -------------------------------
        self._dirty = threading.Event()
        self._dirty.set()
        self._stop_flag = threading.Event()
        self._render_thread: Optional[threading.Thread] = None
        self._input_thread: Optional[threading.Thread] = None

        # Focus cursor — (region, index); region is one of "pad", "rotary",
        # "btn_mode", "btn_transport", "btn_bank", "btn_bottom", "mutesolo",
        # "pattern". Default puts the user on pad 0.
        self._focus: Tuple[str, int] = ("pad", 0)

        # Last event string shown in the footer; updated by dispatch helpers.
        self._last_event_text: str = ""

        # Background release timers (kept to stop them on close()).
        self._release_timers: List[threading.Timer] = []

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
        """Start render + input threads.

        The render thread owns a ``rich.live.Live`` that redraws on
        ``self._dirty`` edges (fallback cadence = 1 / RENDER_FPS).
        The input thread reads keys from stdin in cbreak mode.
        """
        self._render_thread = threading.Thread(
            target=self._render_loop, name="akai-fire-tui-render", daemon=True
        )
        self._render_thread.start()

        import sys
        if sys.stdin.isatty():
            self._input_thread = threading.Thread(
                target=self._input_loop, name="akai-fire-tui-input", daemon=True
            )
            self._input_thread.start()

    def _stop_threads(self) -> None:
        """Stop render + input threads. Idempotent."""
        self._stop_flag.set()
        self._dirty.set()  # wake a waiting render thread
        for timer in self._release_timers:
            timer.cancel()
        self._release_timers.clear()
        for t in (self._render_thread, self._input_thread):
            if t and t.is_alive():
                t.join(timeout=0.5)
        self._render_thread = None
        self._input_thread = None

    def _mark_dirty(self) -> None:
        self._dirty.set()

    def _render_loop(self) -> None:
        console = Console()
        interval = 1.0 / RENDER_FPS
        try:
            with Live(
                self._build_view(),
                console=console,
                refresh_per_second=RENDER_FPS,
                screen=False,
                transient=False,
            ) as live:
                while not self._stop_flag.is_set():
                    # Wait for a dirty flag or the fallback interval.
                    self._dirty.wait(timeout=interval)
                    self._dirty.clear()
                    if self._stop_flag.is_set():
                        break
                    live.update(self._build_view(), refresh=True)
        except Exception:  # pragma: no cover - render-thread guard
            logger.exception("TUI render thread crashed")

    # ------------------------------------------------------------------
    # Input — keyboard reader + key dispatch
    # ------------------------------------------------------------------

    def _input_loop(self) -> None:  # pragma: no cover - needs a real TTY
        """Read keys from stdin in cbreak mode and dispatch them."""
        import select
        import sys
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop_flag.is_set():
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not ready:
                    continue
                ch = sys.stdin.read(1)
                if not ch:
                    continue
                key = self._translate_key(ch)
                if key:
                    self._dispatch_key(key)
        except Exception:
            logger.exception("TUI input thread crashed")
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            except Exception:
                pass

    def _translate_key(self, ch: str) -> Optional[str]:
        """Translate raw char(s) from stdin into a logical key name.

        Returns None for unhandled input. Consumes escape sequences for
        arrow keys by reading additional bytes.
        """
        import sys

        if ch == "\x1b":
            # CSI escape sequence — arrow keys etc.
            seq = sys.stdin.read(2)
            return {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}.get(seq)
        if ch == "\t":
            return "tab"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch == "\x11":  # Ctrl+Q
            return "ctrl_q"
        if ch == "\x03":  # Ctrl+C
            return "ctrl_q"
        return ch  # literal char: "s", "a", "+", "-", "." etc.

    def _dispatch_key(self, key: str) -> None:
        """Route a logical key press to the right action."""
        # Global shortcuts first — available in any region.
        if key == "ctrl_q":
            self._stop_flag.set()
            return
        if key == "s":
            self._toggle_shift()
            return
        if key == "a":
            self._toggle_alt()
            return
        if key == "space":
            self._press_button_with_release(self.BUTTON_PLAY)
            return
        if key == ".":
            self._press_button_with_release(self.BUTTON_STOP)
            return
        if key == "tab":
            self._cycle_region(+1)
            return
        if key == "?":
            self._last_event_text = (
                "Tab region ←→↑↓ nav Enter press s/a mods Ctrl+Q quit"
            )
            self._mark_dirty()
            return
        if key in ("up", "down", "left", "right"):
            self._move_focus_within_region(key)
            return
        if key == "enter":
            self._activate_focus()
            return
        if key in ("+", "="):
            self._turn_focused_rotary(direction="clockwise", velocity=1)
            return
        if key == "-":
            self._turn_focused_rotary(direction="counterclockwise", velocity=1)
            return

    # -- public-ish back-doors for tests & scripted input --------------

    def inject_key(self, key: str) -> None:
        """Inject a logical key without needing a real TTY.

        Mainly for tests; key names match :meth:`_translate_key` output
        (``"up"``, ``"down"``, ``"left"``, ``"right"``, ``"enter"``,
        ``"space"``, ``"tab"``, ``"ctrl_q"``, ``"s"``, ``"a"``, ``"?"``,
        ``"+"``, ``"-"``, ``"."``, and any single printable char).
        """
        self._dispatch_key(key)

    def set_focus(self, region: str, index: int = 0) -> None:
        """Programmatically move the focus cursor."""
        if region not in REGIONS:
            raise ValueError(f"unknown region: {region!r}")
        with self._state_lock:
            self._focus = (region, index)
        self._mark_dirty()

    # -- focus navigation ---------------------------------------------

    def _cycle_region(self, delta: int) -> None:
        try:
            idx = REGIONS.index(self._focus[0])
        except ValueError:
            idx = 0
        new_region = REGIONS[(idx + delta) % len(REGIONS)]
        with self._state_lock:
            self._focus = (new_region, 0)
        self._mark_dirty()

    def _move_focus_within_region(self, key: str) -> None:
        region, index = self._focus
        new_index = index
        if region == "pad":
            col = index % 16
            row = index // 16
            if key == "up":
                row = max(0, row - 1)
            elif key == "down":
                row = min(3, row + 1)
            elif key == "left":
                col = max(0, col - 1)
            elif key == "right":
                col = min(15, col + 1)
            new_index = row * 16 + col
        elif region in ("btn_bank", "btn_mode", "btn_transport", "btn_bottom"):
            max_idx = {
                "btn_bank": 1,
                "btn_mode": 3,
                "btn_transport": 3,
                "btn_bottom": 0,
            }[region]
            if key == "left":
                new_index = max(0, index - 1)
            elif key == "right":
                new_index = min(max_idx, index + 1)
        elif region == "rotary":
            if key == "left":
                new_index = max(0, index - 1)
            elif key == "right":
                new_index = min(4, index + 1)
        elif region == "mutesolo":
            # 8 cells: 0=M1 1=S1 2=M2 3=S2 ... 6=M4 7=S4
            if key == "up":
                new_index = max(0, index - 2)
            elif key == "down":
                new_index = min(7, index + 2)
            elif key == "left" and index % 2 == 1:
                new_index = index - 1
            elif key == "right" and index % 2 == 0:
                new_index = min(7, index + 1)
        elif region == "pattern":
            # 0=< 1=> 2=▲ 3=▼
            if key == "left" and index in (1, 3):
                new_index = index - 1
            elif key == "right" and index in (0, 2):
                new_index = index + 1
            elif key == "up" and index in (2, 3):
                new_index = index - 2
            elif key == "down" and index in (0, 1):
                new_index = index + 2

        if new_index != index:
            with self._state_lock:
                self._focus = (region, new_index)
            self._mark_dirty()

    # -- activation ---------------------------------------------------

    def _activate_focus(self) -> None:
        region, index = self._focus
        if region == "pad":
            self._fire_pad(index, velocity=100)
        elif region == "btn_bank":
            self._press_button_with_release(_BANK_ROW[index][1])
        elif region == "btn_mode":
            self._press_button_with_release(_MODE_ROW[index][1])
        elif region == "btn_transport":
            self._press_button_with_release(_TRANSPORT_ROW[index][1])
        elif region == "btn_bottom":
            self._press_button_with_release(_BROWSER_BUTTON[1])
        elif region == "rotary":
            rotary_ids = (
                self.ROTARY_VOLUME,
                self.ROTARY_PAN,
                self.ROTARY_FILTER,
                self.ROTARY_RESONANCE,
                self.ROTARY_SELECT,
            )
            self._fire_rotary_touch(rotary_ids[index], "touch")
            # Auto-release after 1s (matches plan; pygame mock has no touch
            # release either)
            self._schedule(
                1.0,
                lambda rid=rotary_ids[index]: self._fire_rotary_touch(rid, "release"),
            )
        elif region == "mutesolo":
            solo_index = index // 2 + 1  # 1-4
            is_solo = index % 2 == 1
            if is_solo:
                self._press_button_with_release(self.SOLO_BUTTONS[solo_index])
            # Mute buttons don't have MIDI IDs on the real Fire, so no dispatch.
        elif region == "pattern":
            bid = (
                self.BUTTON_GRID_LEFT,
                self.BUTTON_GRID_RIGHT,
                self.BUTTON_PAT_UP,
                self.BUTTON_PAT_DOWN,
            )[index]
            self._press_button_with_release(bid)

    def _turn_focused_rotary(self, direction: str, velocity: int) -> None:
        if self._focus[0] != "rotary":
            return
        rotary_ids = (
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        )
        # Double the velocity when SHIFT is latched (matches the plan).
        if self._shift_pressed:
            velocity *= 4
        self._fire_rotary_turn(rotary_ids[self._focus[1]], direction, velocity)

    # -- listener dispatch ("fire" = emit to registered listeners) -----

    def _fire_pad(self, pad_index: int, velocity: int = 100) -> None:
        with self._state_lock:
            specific = list(self.pad_listeners.get(pad_index, []))
            globals_ = list(self.global_pad_listeners)
        mods = self._mod_suffix()
        self._record_event(f"PAD {pad_index:02d} v{velocity}{mods}")
        for h in specific:
            self._call_listener(h, velocity)
        for h in globals_:
            self._call_listener(h, pad_index, velocity)

    def _fire_button(self, button_id: int, event: str) -> None:
        # Modifier-first latching — must happen before any listener runs.
        if button_id == self.BUTTON_SHIFT:
            with self._state_lock:
                self._shift_pressed = event == "press"
        elif button_id == self.BUTTON_ALT:
            with self._state_lock:
                self._alt_pressed = event == "press"

        with self._state_lock:
            specific = list(self.button_listeners.get(button_id, []))
            globals_ = list(self.global_button_listeners)
        self._record_event(f"BTN 0x{button_id:02X} {event}{self._mod_suffix()}")
        for h in specific:
            self._call_listener(h, event)
        for h in globals_:
            self._call_listener(h, button_id, event)

    def _fire_rotary_turn(self, rotary_id: int, direction: str, velocity: int) -> None:
        with self._state_lock:
            specific = list(self.rotary_listeners.get(rotary_id, []))
            globals_ = list(self.global_rotary_listeners)
        arrow = "+" if direction == "clockwise" else "-"
        self._record_event(f"ROT 0x{rotary_id:02X} {arrow}{velocity}{self._mod_suffix()}")
        for h in specific:
            self._call_listener(h, direction, velocity)
        for h in globals_:
            self._call_listener(h, rotary_id, direction, velocity)

    def _fire_rotary_touch(self, rotary_id: int, event: str) -> None:
        with self._state_lock:
            specific = list(self.rotary_touch_listeners.get(rotary_id, []))
            globals_ = list(self.global_rotary_touch_listeners)
        self._record_event(f"TOUCH 0x{rotary_id:02X} {event}{self._mod_suffix()}")
        for h in specific:
            self._call_listener(h, event)
        for h in globals_:
            self._call_listener(h, rotary_id, event)

    def _press_button_with_release(self, button_id: int, delay: float = 0.12) -> None:
        """Fire press now, schedule release after ``delay`` seconds."""
        self._fire_button(button_id, "press")
        self._schedule(delay, lambda: self._fire_button(button_id, "release"))

    def _toggle_shift(self) -> None:
        event = "release" if self._shift_pressed else "press"
        self._fire_button(self.BUTTON_SHIFT, event)

    def _toggle_alt(self) -> None:
        event = "release" if self._alt_pressed else "press"
        self._fire_button(self.BUTTON_ALT, event)

    # -- helpers ------------------------------------------------------

    def _mod_suffix(self) -> str:
        suffix = ""
        if self._shift_pressed:
            suffix += "S"
        if self._alt_pressed:
            suffix += "A"
        return ("+" + suffix) if suffix else ""

    def _record_event(self, text: str) -> None:
        with self._state_lock:
            self._last_event_text = text
        self._mark_dirty()

    def _call_listener(self, handler: Callable, *args: Any) -> None:
        try:
            handler(*args)
        except Exception:
            logger.exception("TUI handler %r raised", handler)

    def _schedule(self, delay: float, fn: Callable[[], None]) -> None:
        """Run fn after delay on a daemon timer thread (tracked for cleanup)."""
        timer = threading.Timer(delay, fn)
        timer.daemon = True
        timer.start()
        self._release_timers.append(timer)

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

    # ------------------------------------------------------------------
    # Rendering — ported from tui_mockup.py prototype
    # ------------------------------------------------------------------

    def _build_view(self) -> Group:
        """Snapshot state and compose the chassis Group under a single lock."""
        with self._state_lock:
            pads = [tuple(c) for c in self.pad_colors]
            button_leds = dict(self.button_leds)
            track_leds = list(self.track_leds)
            oled_img = self.canvas.image.copy()
            shift = self._shift_pressed
            alt = self._alt_pressed
            focus = self._focus
            last_event = getattr(self, "_last_event_text", "")

        return _compose_chassis(
            oled_img=oled_img,
            pads=pads,
            button_leds=button_leds,
            track_leds=track_leds,
            shift=shift,
            alt=alt,
            focus=focus,
            last_event=last_event,
            port_name=self.port_name,
        )


# ---------------------------------------------------------------------------
# Pure rendering helpers — no state mutation, safe to call from any thread
# once a state snapshot has been taken.
# ---------------------------------------------------------------------------


def _braille_from_oled(img: Image.Image) -> Text:
    """128x64 1-bit PIL image -> 64x16 Text of Braille cells (2x4 pixels each)."""
    pixels = img.load()
    w, h = img.size
    # Braille dot bit layout (ISO 11548-1):
    #   (0,0)->0  (1,0)->3
    #   (0,1)->1  (1,1)->4
    #   (0,2)->2  (1,2)->5
    #   (0,3)->6  (1,3)->7
    DOT_BITS = (
        (0, 0, 0), (0, 1, 1), (0, 2, 2), (0, 3, 6),
        (1, 0, 3), (1, 1, 4), (1, 2, 5), (1, 3, 7),
    )
    lit = f"{OLED_FG} on {OLED_BG}"
    dim = f"on {OLED_BG}"

    out = Text(no_wrap=True, overflow="ignore")
    for y in range(0, h, 4):
        for x in range(0, w, 2):
            mask = 0
            for dx, dy, bit in DOT_BITS:
                if pixels[x + dx, y + dy] == 0:
                    mask |= 1 << bit
            if mask:
                out.append(chr(0x2800 + mask), style=lit)
            else:
                out.append(" ", style=dim)
        if y + 4 < h:
            out.append("\n")
    return out


def _pad_cell(color: Tuple[int, int, int], focused: bool) -> Text:
    r, g, b = color
    if max(color) < 8:
        if focused:
            return Text("[·]", style="bold reverse grey50")
        return Text(" · ", style="grey27")
    # Pad colors are 0-127 (MIDI range); scale up to 0-255 for truecolor.
    r255, g255, b255 = min(255, r * 2), min(255, g * 2), min(255, b * 2)
    bg = f"rgb({r255},{g255},{b255})"
    if focused:
        return Text(" ◉ ", style=f"bold black on {bg}")
    return Text("   ", style=f"on {bg}")


def _render_pad_grid(pads: List[Tuple[int, int, int]], focus_idx: Optional[int]) -> Text:
    out = Text(no_wrap=True)
    for row in range(4):
        for col in range(16):
            idx = row * 16 + col
            out.append_text(_pad_cell(pads[idx], focus_idx == idx))
            if col < 15:
                out.append(" ")
        if row < 3:
            out.append("\n")
    return out


def _render_knob(name: str, value: float, focused: bool) -> Text:
    bars = "▁▂▃▄▅▆▇█"
    bar_idx = min(len(bars) - 1, max(0, int(value * len(bars))))
    val_bar = bars[bar_idx] * 5
    face = "◉" if focused else "●"
    out = Text(no_wrap=True)
    out.append(f"  {face}  \n", style="bold cyan" if focused else "white")
    out.append(f" {val_bar} \n", style=OLED_FG)
    out.append(f" {name:^5}", style="bold cyan" if focused else "grey70")
    return out


def _render_knobs_row(focus: Tuple[str, int]) -> Table:
    names = ("VOL", "PAN", "FIL", "RES", "SEL")
    # Placeholder values; commit 3 will track real rotary positions.
    values = (0.5, 0.5, 0.5, 0.5, 0.5)
    focused = focus[1] if focus[0] == "rotary" else -1
    t = Table.grid(padding=(0, 2), expand=False)
    for _ in names:
        t.add_column(justify="center")
    t.add_row(
        *(_render_knob(n, v, focused == i) for i, (n, v) in enumerate(zip(names, values)))
    )
    return t


def _render_button(label: str, lit: bool, focused: bool, width: int = 6) -> Text:
    text = f" {label:^{width-2}} "
    if lit and focused:
        style = "bold black on yellow"
    elif lit:
        style = "black on bright_yellow"
    elif focused:
        style = "bold reverse"
    else:
        style = "bright_white on grey23"
    return Text(text, style=style)


def _btn_lit(button_leds: Dict[int, int], button_id: int) -> bool:
    value = button_leds.get(button_id, 0)
    # Any non-zero LED value counts as "lit" for the renderer.
    return value > 0


def _render_button_row(
    labels: List[Tuple[str, int]],  # (label, button_id)
    button_leds: Dict[int, int],
    focus_idx: int,
    width: int = 6,
) -> Text:
    out = Text(no_wrap=True)
    for i, (label, bid) in enumerate(labels):
        out.append_text(_render_button(label, _btn_lit(button_leds, bid), focus_idx == i, width))
        if i < len(labels) - 1:
            out.append(" ")
    return out


def _render_mute_solo_column(
    track_leds: List[int], focus: Tuple[str, int]
) -> Text:
    focused_idx = focus[1] if focus[0] == "mutesolo" else -1
    out = Text(no_wrap=True)
    for i in range(4):
        mute_focused = focused_idx == i * 2
        solo_focused = focused_idx == i * 2 + 1
        lit = track_leds[i] > 0
        out.append_text(_render_button(f"M{i+1}", False, mute_focused, width=4))
        out.append("  ")
        out.append_text(_render_button(f"S{i+1}", lit, solo_focused, width=4))
        if i < 3:
            out.append("\n")
    return out


def _render_pattern_controls(focus: Tuple[str, int]) -> Text:
    idx = focus[1] if focus[0] == "pattern" else -1
    out = Text(no_wrap=True)
    out.append_text(_render_button("<", False, idx == 0, width=4))
    out.append(" ")
    out.append_text(_render_button(">", False, idx == 1, width=4))
    out.append("\n")
    out.append_text(_render_button("▲", False, idx == 2, width=4))
    out.append(" ")
    out.append_text(_render_button("▼", False, idx == 3, width=4))
    return out


def _render_modifier_strip(shift: bool, alt: bool) -> Text:
    out = Text()
    for name, on in (("SHIFT", shift), ("ALT", alt)):
        style = "bold black on yellow" if on else "dim"
        out.append(f" {name} ", style=style)
        out.append(" ")
    return out


def _render_footer(focus: Tuple[str, int], last_event: str) -> Text:
    t = Text()
    t.append(f" focus: {focus[0].upper()} #{focus[1]} ", style="black on cyan")
    t.append("   last: ", style="dim")
    t.append(last_event or "(no events yet)", style="bold")
    t.append("     ")
    for label, action in (
        ("Tab", "region"),
        ("←→↑↓", "nav"),
        ("Enter", "press"),
        ("s/a", "mods"),
        ("Ctrl+Q", "quit"),
    ):
        t.append(label, style="bold")
        t.append(f"={action}  ", style="dim")
    return t


def _compose_chassis(
    *,
    oled_img: Image.Image,
    pads: List[Tuple[int, int, int]],
    button_leds: Dict[int, int],
    track_leds: List[int],
    shift: bool,
    alt: bool,
    focus: Tuple[str, int],
    last_event: str,
    port_name: str,
) -> Group:
    oled_panel = Panel(
        _braille_from_oled(oled_img),
        title="[bold]OLED[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
        width=68,
    )
    knobs_panel = Panel(
        _render_knobs_row(focus),
        title="[bold]knobs[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )
    top_row = Table.grid(expand=False, padding=(0, 2))
    top_row.add_column()
    top_row.add_column()
    top_row.add_row(oled_panel, knobs_panel)

    focus_of = lambda region: focus[1] if focus[0] == region else -1

    button_bar = Table.grid(expand=False, padding=(0, 3))
    button_bar.add_column()
    button_bar.add_column()
    button_bar.add_column()
    button_bar.add_row(
        _render_button_row(_BANK_ROW, button_leds, focus_of("btn_bank")),
        _render_button_row(_MODE_ROW, button_leds, focus_of("btn_mode")),
        _render_button_row(_TRANSPORT_ROW, button_leds, focus_of("btn_transport")),
    )

    pad_panel = Panel(
        _render_pad_grid(pads, focus[1] if focus[0] == "pad" else None),
        title="[bold]pads 16×4[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )
    mute_solo_panel = Panel(
        _render_mute_solo_column(track_leds, focus),
        title="[bold]mute/solo[/]",
        title_align="left",
        border_style=PANEL_BORDER,
        padding=(0, 1),
    )
    pattern_panel = Panel(
        _render_pattern_controls(focus),
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

    mod_strip = Table.grid(expand=False, padding=(0, 4))
    mod_strip.add_column()
    mod_strip.add_column()
    mod_strip.add_row(
        _render_modifier_strip(shift, alt),
        _render_button_row(
            [_BROWSER_BUTTON],
            button_leds,
            focus_of("btn_bottom"),
            width=11,
        ),
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
        _render_footer(focus, last_event),
    )


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
