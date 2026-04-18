"""End-to-end verification that every input type dispatches correctly.

Exercises every decorator (``on_pad``, ``on_button``, ``on_rotary_turn``,
``on_rotary_touch``, ``on_solo``), in both global and specific forms, and
logs each event both to stdout and to the 128x64 OLED so you can watch
events arrive live.

It also includes a deliberate slow handler (PAT UP) so you can confirm
that async dispatch keeps the MIDI thread hot while a callback is busy.

Controls on the device:

    Any pad          → log + cycle the pad's color
    Any button       → log + flash the button LED while held
    Any rotary turn  → log direction / velocity; matching track LED blinks
    Any rotary touch → log; the rotary's track LED lights
    Any solo         → log
    SHIFT / ALT      → indicator in OLED header; also modifies pad color
    SELECT rotary    → scroll back (CCW) / forward (CW) through the log
    GRID RIGHT       → jump the log viewport back to the latest entry
    BROWSER          → clear OLED event log + clear all pads + reset scroll
    PAT UP           → "slow handler" demo: sleeps 1s; other events keep working
    STOP             → quit
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


LOG_LINES_ON_OLED = 3      # how many recent events to show
LOG_BUFFER_SIZE = 64       # scroll-back depth for the SELECT rotary
OLED_REFRESH_MIN_INTERVAL = 0.016  # ~60 fps cap — handlers may fire faster

# Small palette used to give each pad press a different color so repeated
# presses visibly cycle.
PAD_PALETTE = [
    (127, 0, 0), (127, 64, 0), (127, 127, 0), (0, 127, 0),
    (0, 127, 127), (0, 0, 127), (64, 0, 127), (127, 0, 127),
]


@dataclass
class Stats:
    pads: int = 0
    buttons: int = 0
    rotaries: int = 0
    rotary_touches: int = 0
    solos: int = 0
    last_event: str = "(waiting for input...)"
    log: deque = field(default_factory=lambda: deque(maxlen=LOG_BUFFER_SIZE))


# ---------------------------------------------------------------------------


def rotary_name(fire, controller_id: int) -> str:
    return {
        fire.ROTARY_VOLUME: "VOL",
        fire.ROTARY_PAN: "PAN",
        fire.ROTARY_FILTER: "FIL",
        fire.ROTARY_RESONANCE: "RES",
        fire.ROTARY_SELECT: "SEL",
    }.get(controller_id, f"0x{controller_id:02X}")


def button_name(fire, button_id: int) -> str:
    # Reverse-lookup the constant name for readable logging.
    for name in dir(fire):
        if name.startswith("BUTTON_") and getattr(fire.__class__, name, None) == button_id:
            return name[len("BUTTON_"):]
    return f"0x{button_id:02X}"


# ---------------------------------------------------------------------------


class EventMonitor:
    def __init__(self) -> None:
        self.fire = get_akai_fire()
        self.canvas = self.fire.get_canvas()
        self.stats = Stats()
        self.pad_press_count = [0] * 64
        self.stopping = threading.Event()

        # Scrollable viewport into the event log. scroll_offset is the index
        # of the *topmost visible* line in the deque (0 = newest). While at 0
        # the view follows new events (auto-scroll); any nonzero offset pins
        # the view and incoming events shift it so the user's content stays
        # on-screen until they explicitly return to the latest.
        self.scroll_offset = 0

        # Serializes state mutations + OLED renders. Handlers run on the
        # dispatcher pool, so without this they'd race on the canvas.
        self._draw_lock = threading.Lock()
        self._last_draw = 0.0

        self.started_at = time.monotonic()

        self._register_handlers()

    # -- helpers -----------------------------------------------------------

    def _log(self, line: str) -> None:
        with self._draw_lock:
            self.stats.log.appendleft(line)
            self.stats.last_event = line
            # If the user has scrolled back into history, keep their view
            # pinned on the same entries by shifting the offset to match
            # the new deque indices. While at offset 0 we "follow" newest.
            if self.scroll_offset > 0:
                self.scroll_offset = min(
                    self.scroll_offset + 1,
                    max(0, len(self.stats.log) - LOG_LINES_ON_OLED),
                )
        print(line, flush=True)
        self._maybe_redraw()

    def _scroll(self, delta: int) -> None:
        """Move the viewport. +delta = older entries; -delta = newer."""
        with self._draw_lock:
            max_offset = max(0, len(self.stats.log) - LOG_LINES_ON_OLED)
            self.scroll_offset = max(0, min(max_offset, self.scroll_offset + delta))
        self._redraw()

    def _scroll_to_latest(self) -> None:
        with self._draw_lock:
            self.scroll_offset = 0
        self._redraw()

    def _maybe_redraw(self) -> None:
        """Rate-limit OLED redraws so a burst of events doesn't queue forever."""
        now = time.monotonic()
        with self._draw_lock:
            if now - self._last_draw < OLED_REFRESH_MIN_INTERVAL:
                return
            self._last_draw = now
        self._redraw()

    def _redraw(self) -> None:
        with self._draw_lock:
            c = self.canvas
            c.clear()

            uptime = int(time.monotonic() - self.started_at)

            # Header: app name + uptime, with modifier flags on the right.
            c.fill_rect(0, 0, c.WIDTH, 11, color=0)
            c.draw_text(f"Events  {uptime:>3}s", 2, 2, color=1)
            if self.fire.is_shift_pressed():
                c.draw_text("S", 90, 2, color=1)
                c.draw_rect(88, 0, 9, 11, color=1)
            if self.fire.is_alt_pressed():
                c.draw_text("A", 110, 2, color=1)
                c.draw_rect(108, 0, 9, 11, color=1)

            # Counters line
            counts = (
                f"P:{self.stats.pads} B:{self.stats.buttons} "
                f"R:{self.stats.rotaries}+{self.stats.rotary_touches} "
                f"S:{self.stats.solos}"
            )
            c.draw_text(counts, 2, 13)

            # Last event (persistent, most visible)
            c.draw_text(self.stats.last_event[:24], 2, 24)

            # Scrolling log viewport. deque is newest-first (appendleft),
            # so log[offset:offset+N] is "N entries, newest on top, starting
            # from `offset` from the newest". At offset=0 we show the 3
            # newest; increasing offset reveals older events.
            log = list(self.stats.log)
            offset = self.scroll_offset
            visible = log[offset : offset + LOG_LINES_ON_OLED]

            # Up-arrow if there are *newer* events above the viewport,
            # down-arrow if there are *older* events below.
            has_newer_above = offset > 0
            has_older_below = offset + LOG_LINES_ON_OLED < len(log)

            for i, entry in enumerate(visible):
                y = 36 + i * 9
                c.draw_text(">", 0, y)
                c.draw_text(entry[:23], 8, y)

            if has_newer_above:
                c.draw_text("^", c.WIDTH - 7, 36)
            if has_older_below:
                c.draw_text("v", c.WIDTH - 7, 36 + (LOG_LINES_ON_OLED - 1) * 9)

            self.fire.render_to_display()

    # -- handler registration ---------------------------------------------

    def _register_handlers(self) -> None:
        fire = self.fire

        # --- pads ---------------------------------------------------------
        @fire.on_pad()
        def any_pad(pad_index: int, velocity: int) -> None:
            self.stats.pads += 1
            mods = []
            if fire.is_shift_pressed():
                mods.append("S")
            if fire.is_alt_pressed():
                mods.append("A")
            mod_str = ("+" + "".join(mods)) if mods else ""
            self._log(f"PAD {pad_index:02d} v{velocity}{mod_str}")

            # Cycle the pad's color on every press; SHIFT dims, ALT brightens.
            palette_idx = self.pad_press_count[pad_index] % len(PAD_PALETTE)
            self.pad_press_count[pad_index] += 1
            r, g, b = PAD_PALETTE[palette_idx]
            if fire.is_shift_pressed():
                r, g, b = r // 3, g // 3, b // 3
            if fire.is_alt_pressed():
                r, g, b = min(127, r + 32), min(127, g + 32), min(127, b + 32)
            fire.set_pad_color(pad_index, r, g, b)

        @fire.on_pad(0)
        def corner_pad(velocity: int) -> None:
            # Specific-handler demo — fires alongside the global one.
            print(f"[specific] corner pad 0 pressed with v{velocity}", flush=True)

        # --- buttons ------------------------------------------------------
        @fire.on_button()
        def any_button(button_id: int, event: str) -> None:
            self.stats.buttons += 1
            self._log(f"BTN {button_name(fire, button_id)} {event}")
            # Light the LED on press, dim on release so you can see it flash.
            try:
                if event == "press":
                    fire.set_button_led(button_id, fire.LED_HIGH_RED)
                else:
                    fire.set_button_led(button_id, fire.LED_OFF)
            except Exception:
                # Some buttons don't accept LED commands — fine to skip.
                pass

        @fire.on_button(fire.BUTTON_BROWSER)
        def clear_log(event: str) -> None:
            if event == "press":
                with self._draw_lock:
                    self.stats.log.clear()
                    self.stats.last_event = "(log cleared)"
                    self.scroll_offset = 0
                fire.clear_all_pads()
                for i in range(64):
                    self.pad_press_count[i] = 0
                self._redraw()

        @fire.on_button(fire.BUTTON_GRID_RIGHT)
        def jump_to_latest(event: str) -> None:
            if event == "press":
                self._scroll_to_latest()

        @fire.on_button(fire.BUTTON_STOP)
        def quit_button(event: str) -> None:
            if event == "press":
                self._log("STOP pressed — quitting")
                self.stopping.set()

        @fire.on_button(fire.BUTTON_PAT_UP)
        def slow_handler(event: str) -> None:
            # Deliberately slow — proves async dispatch is working. While
            # this sleeps, other pad/button/rotary events should keep
            # flowing and their entries should appear in the OLED log.
            if event != "press":
                return
            start = time.monotonic()
            self._log("PAT_UP: slow handler started (1s)")
            time.sleep(1.0)
            elapsed = time.monotonic() - start
            self._log(f"PAT_UP: slept {elapsed:.2f}s")

        # --- rotaries (turn) ---------------------------------------------
        @fire.on_rotary_turn()
        def any_rotary(controller_id: int, direction: str, velocity: int) -> None:
            self.stats.rotaries += 1
            arrow = "+" if direction == "clockwise" else "-"
            self._log(f"ROT {rotary_name(fire, controller_id)} {arrow}{velocity}")

            # Blink a track LED to show rotary activity visually.
            rotary_to_track = {
                fire.ROTARY_VOLUME: 1,
                fire.ROTARY_PAN: 2,
                fire.ROTARY_FILTER: 3,
                fire.ROTARY_RESONANCE: 4,
            }
            track = rotary_to_track.get(controller_id)
            if track is not None:
                led = (
                    fire.RECTANGLE_LED_HIGH_GREEN
                    if direction == "clockwise"
                    else fire.RECTANGLE_LED_HIGH_RED
                )
                fire.set_track_led(track, led)

        @fire.on_rotary_turn(fire.ROTARY_SELECT)
        def select_scrolls_log(direction: str, velocity: int) -> None:
            # CW scrolls toward newer (offset -= velocity),
            # CCW scrolls toward older (offset += velocity).
            step = max(1, min(velocity, LOG_LINES_ON_OLED))
            self._scroll(-step if direction == "clockwise" else +step)

        # --- rotaries (touch) --------------------------------------------
        @fire.on_rotary_touch()
        def any_rotary_touch(controller_id: int, event: str) -> None:
            self.stats.rotary_touches += 1
            self._log(f"TOUCH {rotary_name(fire, controller_id)} {event}")

        @fire.on_rotary_touch(fire.ROTARY_PAN)
        def pan_touch(event: str) -> None:
            print(f"[specific] PAN rotary touch {event}", flush=True)

        # --- solos -------------------------------------------------------
        @fire.on_solo()
        def any_solo(index: int, event: str) -> None:
            self.stats.solos += 1
            self._log(f"SOLO {index} {event}")

        @fire.on_solo(1)
        def solo_one(event: str) -> None:
            print(f"[specific] SOLO 1 {event}", flush=True)

    # -- main loop ---------------------------------------------------------

    def run(self, duration: Optional[float] = None) -> None:
        self.fire.start_listening()
        print("Event Monitor running. Press STOP on the device or Ctrl+C to quit.")
        print("Every input should appear here AND on the OLED.")
        self._redraw()
        deadline = None if duration is None else time.monotonic() + duration
        try:
            while not self.stopping.is_set():
                # Clock tick every 500ms so the uptime counter updates even
                # when no events are arriving.
                self.stopping.wait(timeout=0.5)
                self._maybe_redraw()
                if deadline is not None and time.monotonic() >= deadline:
                    self._log("duration elapsed — quitting")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.fire.clear_all()
            self.fire.close()
            self._dump_summary()

    def _dump_summary(self) -> None:
        print()
        print("--- session summary ---")
        print(
            f"pads={self.stats.pads}  buttons={self.stats.buttons}  "
            f"rotaries={self.stats.rotaries}  "
            f"rotary_touches={self.stats.rotary_touches}  "
            f"solos={self.stats.solos}"
        )
        print(f"unique pads pressed: {sum(1 for c in self.pad_press_count if c > 0)}/64")
        print()
        print("last events (newest first):")
        for entry in self.stats.log:
            print(f"  {entry}")


if __name__ == "__main__":
    duration: Optional[float] = None
    for arg in sys.argv[1:]:
        if arg.startswith("--duration="):
            duration = float(arg.split("=", 1)[1])
    EventMonitor().run(duration=duration)
