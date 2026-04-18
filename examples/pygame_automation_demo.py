"""Interactive verification that the pygame mock GUI dispatches real events.

Opens the pygame MockAkaiFire window and then drives it programmatically
via pygame.event.post(...) — synthetic mouse clicks at the pad, button,
and rotary screen positions. Every registered handler should fire, LEDs
and pad colors should light up in the window, and the script exits on
its own with a PASS/FAIL summary.

Run:
    uv run python examples/pygame_automation_demo.py

Press Ctrl+C at any time to abort.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import List

# Keep the window on-screen for visual confirmation. Set to "dummy" for
# headless CI (tests/test_pygame_mock.py already does that).
# os.environ["SDL_VIDEODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402
from mock_gui_pygame import MockAkaiFire  # noqa: E402


@dataclass
class Recorder:
    pads: List = field(default_factory=list)
    buttons: List = field(default_factory=list)
    rotaries: List = field(default_factory=list)


def post_click(pos, button=1):
    """Post a left-click (down+up) at `pos`."""
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button}))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": pos, "button": button}))


def post_drag(start_pos, end_pos, steps=6):
    """Post a mouse-drag from start to end."""
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": start_pos, "button": 1}))
    sx, sy = start_pos
    ex, ey = end_pos
    for i in range(1, steps + 1):
        nx = sx + (ex - sx) * i // steps
        ny = sy + (ey - sy) * i // steps
        rel = (nx - sx - (ex - sx) * (i - 1) // steps,
               ny - sy - (ey - sy) * (i - 1) // steps)
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEMOTION, {"pos": (nx, ny), "rel": rel, "buttons": (1, 0, 0)}
        ))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": end_pos, "button": 1}))


def pump(fire, duration=0.25):
    """Run the mock's event loop for `duration` seconds."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if not fire.process_events():
            break
        time.sleep(0.01)


def main() -> int:
    print("Spinning up pygame mock (watch the window)...")
    fire = MockAkaiFire()
    rec = Recorder()

    @fire.on_pad()
    def on_pad(pad_index, velocity):
        rec.pads.append((pad_index, velocity))
        fire.set_pad_color(pad_index, 0, 127, 0)

    @fire.on_button()
    def on_button(button_id, event):
        rec.buttons.append((button_id, event))
        if event == "press":
            fire.set_button_led(button_id, fire.LED_HIGH_GREEN)
        else:
            fire.set_button_led(button_id, fire.LED_OFF)

    @fire.on_rotary_turn()
    def on_rotary(rotary_id, direction, velocity):
        rec.rotaries.append((rotary_id, direction, velocity))

    # Let the window open and settle
    pump(fire, 0.5)

    script = []

    # Click a sampling of pads across each row
    pad_targets = [0, 5, 15, 16, 31, 32, 47, 63]
    for idx in pad_targets:
        script.append(("pad", idx, fire.pad_rects[idx].center))

    # Click a sampling of buttons
    btn_targets = [
        fire.BUTTON_PLAY, fire.BUTTON_STOP, fire.BUTTON_REC,
        fire.BUTTON_STEP, fire.BUTTON_NOTE, fire.BUTTON_DRUM,
        fire.BUTTON_PERFORM, fire.BUTTON_BROWSER,
        fire.BUTTON_PAT_UP, fire.BUTTON_PAT_DOWN,
    ]
    for bid in btn_targets:
        script.append(("btn", bid, fire.button_rects[bid].center))

    # Rotary drags — one per rotary
    for rid in (fire.ROTARY_VOLUME, fire.ROTARY_PAN, fire.ROTARY_FILTER, fire.ROTARY_RESONANCE):
        pos = fire.rotary_data[rid]["pos"]
        script.append(("rot", rid, pos))

    # Execute the script
    for kind, target, pos in script:
        if kind == "pad":
            print(f"  click pad {target} at {pos}")
            post_click(pos)
        elif kind == "btn":
            print(f"  click button 0x{target:02X} at {pos}")
            post_click(pos)
        elif kind == "rot":
            x, y = pos
            print(f"  drag rotary 0x{target:02X} CW then CCW")
            post_drag((x, y), (x, y - 30), steps=6)
            pump(fire, 0.1)
            post_drag((x, y), (x, y + 30), steps=6)
        pump(fire, 0.2)

    # Final drain
    pump(fire, 0.5)

    # Report
    pads_expected = set(pad_targets)
    pads_seen = {p[0] for p in rec.pads}
    buttons_seen = {b[0] for b in rec.buttons if b[1] == "press"}
    rotaries_seen = {r[0] for r in rec.rotaries}

    def check(name, expected, seen):
        missing = expected - seen
        ok = not missing
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: expected {len(expected)}, got {len(seen)}"
              + (f" (missing {sorted(missing)})" if missing else ""))
        return ok

    print()
    print("Results:")
    pads_ok = check("pads", pads_expected, pads_seen)
    buttons_ok = check("buttons", set(btn_targets), buttons_seen)
    rotaries_ok = check(
        "rotaries",
        {fire.ROTARY_VOLUME, fire.ROTARY_PAN, fire.ROTARY_FILTER, fire.ROTARY_RESONANCE},
        rotaries_seen,
    )

    # Keep the window open briefly so the user can see the final state
    print("\nHolding window open for 2s...")
    pump(fire, 2.0)
    fire.close()

    overall = pads_ok and buttons_ok and rotaries_ok
    print(f"\nOverall: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
