# Device API

For a runnable first application, start with the [README](../README.md). These snippets show individual operations on an existing `fire` connection.

## Connecting

### Auto-detection (recommended)

From a repository checkout, `get_akai_fire()` tries hardware first, then falls back to the pygame mock. Install the interactive backends with `uv sync --all-extras`.

In an installed-library project, use `AkaiFire()` for hardware or `akai_fire_testing.MockAkaiFire` for headless tests. The pygame/TUI modules are not included in the wheel.

```python
from akai_fire import get_akai_fire

with get_akai_fire() as fire:
    fire.set_pad_color(0, 127, 0, 0)
```

Force a specific backend with `use_mock`:

| Call | Behavior |
|---|---|
| `get_akai_fire()` | Hardware if available, else pygame mock |
| `get_akai_fire(use_mock=False)` | Hardware only — raises `MIDIConnectionError` if absent |
| `get_akai_fire(use_mock=True)` | Pygame mock (clickable window) |
| `get_akai_fire(use_mock="tui")` | Terminal-UI mock (rich) |
| `AkaiFire(port_name="...")` | Hardware directly, custom port name substring |

### Custom port name

The library matches ports whose name *contains* the given string (default `"FL STUDIO FIRE"`):

```python
from akai_fire import AkaiFire

with AkaiFire(port_name="FIRE") as fire:
    fire.set_pad_color(0, 127, 0, 0)
```

## Device Control

### Pads

Pad indices are `0–63`, left-to-right, top-to-bottom. Colors are RGB, each channel `0–127`.

```python
fire.set_pad_color(0, 127, 0, 0)  # pad 0 bright red
fire.set_pad_color_fast(0, 127, 0, 0)  # skips validation (tight loops)
fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
fire.set_all_pads((127, 127, 127))  # everything white
fire.clear_pad(0)
fire.clear_all_pads()
```

On hardware, `set_pad_color()` requires an integer index in 0–63 and integer RGB values; it raises `InvalidParameterError` for invalid arguments and clamps RGB to 0–127. `set_multiple_pad_colors()` skips entries with the wrong length or an out-of-range index and returns `False` when nothing can be sent. Pass valid integer tuples: batch validation is not identical across backends. `set_pad_color_fast()` assumes valid inputs and skips those checks.

Pad setters return a boolean indicating whether the update succeeded. An unchanged cached hardware pad color also returns `True` without another MIDI send.

Geometry helpers treat the grid as 16 columns × 4 rows:

```python
fire.pad_position(16)  # (row=1, col=0)
fire.get_pad_column(15)  # 16 (one-indexed)
fire.get_pad_row(16)  # 2  (one-indexed)
```

### Button LEDs

```python
fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
fire.set_button_led(fire.BUTTON_PLAY, fire.LED_OFF)
fire.clear_all_button_leds()
```

Button values select brightness, not hue: `LED_OFF` is 0, all `LED_DULL_*` aliases are 1, and all `LED_HIGH_*` aliases are 2. The physical button determines the color. For example, `LED_HIGH_RED` on PLAY still lights its green LED.

### Track LEDs

Tracks are numbered **1–4**. Their rectangular LEDs take values `0–4` (`RECTANGLE_LED_*` constants). The hardware setter returns `False` for an invalid track number:

```python
fire.set_track_led(1, fire.RECTANGLE_LED_HIGH_GREEN)
fire.clear_track_led(1)
fire.clear_all_track_leds()
```

### Control bank LEDs

```python
fire.set_control_bank_leds(fire.CONTROL_BANK_ALL_ON)

# or combine field flags yourself
state = fire.FIELD_BASE | fire.FIELD_USER1 | fire.FIELD_USER2
fire.set_control_bank_leds(state)
fire.clear_control_bank_leds()
```

Note: `CONTROL_BANK_USER2` is a documented hardware exception (`0x03`, not `FIELD_BASE | FIELD_USER2`) — use the predefined constant.

### Everything at once

```python
fire.clear_all()  # all LEDs, plus the OLED on hardware
```

`clear_all()` on the headless testing mock clears LEDs but leaves its canvas intact. Use `clear_display()` explicitly when your code needs to clear the OLED on every backend. The hardware context manager clears the display and closes MIDI ports; it does not clear LEDs. `close()` alone releases the connection without clearing outputs.

## Event Handling

Register handlers with decorators or plain listener calls. Handlers run on a background thread pool by default (see [Threading](#threading)), exceptions are logged and isolated per handler.

```python
import time
from akai_fire import get_akai_fire

with get_akai_fire() as fire:

    @fire.on_pad()  # every pad → (pad_index, velocity)
    def on_any_pad(pad_index, velocity):
        print(f"pad {pad_index} velocity {velocity}")

    @fire.on_pad(0)  # one pad → (velocity,)
    def on_pad_zero(velocity): ...

    @fire.on_pad([0, 1, 2])  # several pads → (pad_index, velocity)
    def on_first_row(pad_index, velocity): ...

    @fire.on_button(fire.BUTTON_PLAY)  # press/release events
    def on_play(event): ...

    @fire.on_rotary_turn(
        fire.ROTARY_VOLUME
    )  # ("clockwise"|"counterclockwise", velocity)
    def on_volume(direction, velocity): ...

    @fire.on_rotary_touch(fire.ROTARY_VOLUME)  # "touch"/"release"
    def on_volume_touch(event): ...

    @fire.on_solo(2)  # solo button 2
    def on_solo_two(event): ...

    # Keep the mock window responsive while waiting for input.
    try:
        while True:
            if hasattr(fire, "process_events") and not fire.process_events():
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
```

Global decorators prepend the control ID: `on_button()` receives `(button_id, event)`, `on_rotary_turn()` receives `(rotary_id, direction, velocity)`, `on_rotary_touch()` receives `(rotary_id, event)`, and `on_solo()` receives `(solo_index, event)`. Solo indices are 1–4. Rotary touch is available for the four main knobs; SELECT has a button press instead.

Plain listener calls use the following signatures. Unlike `on_pad([0, 1])`, `add_listener([0, 1], callback)` passes only velocity:

```python
def on_pad_velocity(velocity):
    print(velocity)


def on_any_pad(pad, velocity):
    print(pad, velocity)


def on_play(event):
    print(event)


def on_volume(direction, velocity):
    print(direction, velocity)


fire.add_listener([0, 1], on_pad_velocity)
fire.add_global_listener(on_any_pad)
fire.add_button_listener(fire.BUTTON_PLAY, on_play)
fire.add_rotary_listener(fire.ROTARY_VOLUME, on_volume)

# Remove the same callbacks when their owner stops using the device.
fire.remove_listener([0, 1], on_pad_velocity)
fire.remove_global_listener(on_any_pad)
fire.remove_button_listener(fire.BUTTON_PLAY, on_play)
fire.remove_rotary_listener(fire.ROTARY_VOLUME, on_volume)
```

Registration/removal is safe inside a handler. Changes affect later dispatch snapshots; removal does not cancel callbacks already queued by the hardware executor. Rotary-touch listeners likewise have matching `add_rotary_touch_listener` and `remove_rotary_touch_listener` methods and receive a single event string.

### Modifier keys

SHIFT/ALT state is latched before any handler runs, so handlers always see coherent state for the event they're processing:

```python
@fire.on_pad()
def on_pad(pad_index, velocity):
    if fire.is_shift_pressed():
        ...
```

## OLED Display

The screen is a 128×64 monochrome canvas. Convention: pixel value `0` is **lit** on hardware (a black PIL pixel = an ON OLED pixel); a fresh canvas starts all-unlit.

```python
canvas = fire.get_canvas()

canvas.clear()
canvas.draw_text_fitted("Hello Fire", 20, 20)
canvas.draw_rect(0, 0, 128, 64)  # outline
canvas.fill_rect(10, 10, 20, 20)  # filled
canvas.draw_circle(64, 32, 15)
canvas.fill_circle(64, 32, 10)
canvas.draw_line(0, 0, 127, 63)
canvas.draw_horizontal_line(0, 32, 128)
canvas.draw_vertical_line(64, 0, 64)
canvas.set_pixel(64, 32, 0)
canvas.get_pixel(64, 32)  # None when out of bounds

fire.render_to_display()  # push to device/mock
```

`draw_text_fitted(text, x, y, width=...)` shortens a single line with an ellipsis using the actual font width. Without `width`, it leaves a two-pixel right margin. Raw `draw_text()` keeps its unbounded behavior for scrolling and custom layouts. Neither method wraps text.

Higher-level layouts are built in. These are alternatives for a screen; clear the canvas before drawing a new layout and render it afterward:

```python
canvas.clear()
canvas.draw_page("Title", ["line one", "line two"])
fire.render_to_display()

# Other available layouts:
canvas.draw_menu("Settings", ["BPM", "Swing", "MIDI"], selected_index=1)
canvas.draw_value_page("Volume", 64, min_val=0, max_val=127)
canvas.draw_split_screen("Title", ["a", "b"], ["c", "d"])
canvas.draw_grid_info("Grid", rows=4, cols=16, cell_info=[(0, 0, "C")])
```

Pages and menus fit three full content rows below their header. Menus scroll around the selected item; split screens fit four lines per column. Grid labels are fitted to their cells and omitted when a cell is too short for text. Layout methods do not clear previous content automatically.

Render to a file instead of hardware (useful for development and visual regression tests):

```python
from pathlib import Path

Path("_screens").mkdir(exist_ok=True)
fire.render_to_bmp("_screens/test.bmp")
```

## Threading

The MIDI polling loop runs on a daemon thread (~1 ms poll). Every decoded event goes through dispatch that:

1. Latches SHIFT/ALT inline **before** any handler runs.
2. Submits handlers to a thread pool (`async_handlers=True`, `max_workers=4`) so ordinary short handlers can run without blocking polling.
3. Isolates exceptions per handler — one raising listener never blocks its siblings.
4. Applies backpressure when the bounded queue (`handler_queue_size=64`) is full. With multiple workers the polling thread can run the handler inline; with one worker it waits for capacity to preserve FIFO order. Either case can delay polling. Accepted events are not discarded merely because the queue is full.

Tune it:

```python
from akai_fire import AkaiFire

with AkaiFire(max_workers=1) as fire:
    ...  # Async offload with FIFO ordering.

# Alternatively, async_handlers=False runs callbacks on the MIDI polling thread.
```

Keep handlers short; offload blocking I/O or expensive work. Multiple workers do not guarantee arrival-order execution. See the [framework guide](FRAMEWORK.md#input) for moving state changes to the frame thread.

## Mocks

Four implementations share a device base class. Contract tests cover common operations, but rendering, threading, validation and cleanup differ:

| Implementation | Import | Use case |
|---|---|---|
| Hardware | `from akai_fire import AkaiFire` | The real device |
| Pygame mock | `from mock_gui_pygame import MockAkaiFire` | Clickable window: pads, buttons, rotaries, OLED |
| Terminal mock | `from mock_gui_tui import MockAkaiFire` | rich-based TUI, keyboard-driven, `headless=True` for CI |
| Testing mock | `from akai_fire_testing import MockAkaiFire` | Headless; event recording, `simulate_*` injection, assertions |

Pygame mock controls: click pads/buttons to press them, drag rotaries to turn them. On macOS it must run on the main thread — the examples handle this.

The testing mock's `MockCanvas` records drawing operations and supports pixel assertions, but it does not reproduce all Pillow drawing. For pixel-accurate rendering tests, assign a real `Canvas` to `fire.canvas` before constructing the app. A mock test does not verify MIDI encoding, callback concurrency or physical hardware behavior.

Testing mock in action:

```python
from akai_fire_testing import MockAkaiFire

fire = MockAkaiFire()


@fire.on_pad()
def on_pad(pad_index, velocity):
    fire.set_pad_color(pad_index, 127, 0, 0)


fire.simulate_pad_press(5, velocity=100)
fire.assert_pad_color(5, (127, 0, 0))
```

## Error Handling

The device library exports the following `AkaiFireError` subclasses. Not every failure raises: hardware pad and LED setters generally return `False` on send failure, while OLED sends raise `MIDISendError`. Check return values where delivery matters.

| Exception | Raised when |
|---|---|
| `MIDIConnectionError` | Ports can't be found or opened |
| `MIDISendError` | An OLED SysEx send fails |
| `InvalidParameterError` | Invalid single-pad setter arguments or button ID |
| `HardwareError` | Port enumeration fails |
| `StateError` | Exported state-error type; the application runtime uses `RuntimeError` for a repeated or post-shutdown `run()` |

```python
from akai_fire import AkaiFire, MIDIConnectionError

try:
    with AkaiFire() as fire:
        fire.set_pad_color(0, 127, 0, 0)
except MIDIConnectionError as e:
    print(f"No device: {e}")
```

## API Reference

### AkaiFire

**Pads** — `set_pad_color(index, r, g, b)`, `set_pad_color_fast(...)`, `set_multiple_pad_colors([...])`, `set_all_pads((r, g, b))`, `reset_pads(r=0, g=0, b=0)`, `clear_pad(index)`, `clear_all_pads()`

**LEDs** — `set_button_led(button_id, value)`, `set_track_led(track, value)`, `set_control_bank_leds(state)`, `clear_track_led(track)`, `clear_all_button_leds()`, `clear_all_track_leds()`, `clear_control_bank_leds()`, `clear_all()`

**Events** — decorators `on_pad`, `on_button`, `on_rotary_turn`, `on_rotary_touch`, `on_solo`; listeners `add_listener`, `add_global_listener`, `add_button_listener`, `add_rotary_listener`, `add_rotary_touch_listener`; matching `remove_*` methods

**Display** — `get_canvas()`, `new_canvas()`, `render_to_display(canvas=None)`, `render_to_bmp(filename, image_format="BMP")`, `clear_display()`

**Lifecycle** — `start_listening()`, `listening`, `close()`, `reconnect()`, `is_connected()`, `list_midi_ports()`, context-manager (`with`) support

**Modifiers** — `is_shift_pressed()`, `is_alt_pressed()`, `.shift_pressed`, `.alt_pressed`

**Geometry** — `pad_position(index) -> (row, col)`, `get_pad_column(index)`, `get_pad_row(index)`, `get_solo_index(button_id)`

### Canvas

Primitives: `clear(color=1)`, `set_pixel(x, y, color=0)`, `get_pixel(x, y)`, `draw_text(text, x, y, font=None, color=0)`, `draw_text_fitted(text, x, y, font=None, color=0, *, width=None)`, `fit_text(text, width, font=None)`, `draw_rect`, `fill_rect`, `draw_rectangle`, `fill_rectangle`, `draw_border(thickness=1)`, `draw_line`, `draw_horizontal_line`, `draw_vertical_line`, `draw_circle`, `fill_circle`, `clone()`

Layouts: `draw_page(title, lines, header_inverted=True)`, `draw_menu(title, items, selected_index)`, `draw_value_page(title, value, min_val=None, max_val=None, show_bar=True)`, `draw_grid_info(title, rows, cols, cell_info)`, `draw_split_screen(title, left_content, right_content)`

### Constants

Button IDs: `BUTTON_PLAY`, `BUTTON_STOP`, `BUTTON_REC`, `BUTTON_PATTERN`, `BUTTON_BROWSER`, `BUTTON_BANK`, `BUTTON_SELECT`, `BUTTON_STEP`, `BUTTON_NOTE`, `BUTTON_DRUM`, `BUTTON_PERFORM`, `BUTTON_SHIFT`, `BUTTON_ALT`, `BUTTON_GRID_LEFT`, `BUTTON_GRID_RIGHT`, `BUTTON_PAT_UP`, `BUTTON_PAT_DOWN`, `BUTTON_SOLO_1`–`BUTTON_SOLO_4`

Rotaries: `ROTARY_VOLUME`, `ROTARY_PAN`, `ROTARY_FILTER`, `ROTARY_RESONANCE`, `ROTARY_SELECT`

Button LEDs: `LED_OFF`, `LED_DULL_RED`, `LED_HIGH_RED`, `LED_DULL_GREEN`, `LED_HIGH_GREEN`, `LED_DULL_YELLOW`, `LED_HIGH_YELLOW`

Track LEDs: `RECTANGLE_LED_OFF` (0), `RECTANGLE_LED_DULL_RED` (1), `RECTANGLE_LED_DULL_GREEN` (2), `RECTANGLE_LED_HIGH_RED` (3), `RECTANGLE_LED_HIGH_GREEN` (4)

Control bank fields: `FIELD_BASE` (required), `FIELD_CHANNEL`, `FIELD_MIXER`, `FIELD_USER1`, `FIELD_USER2` — combined with `|`. Predefined states: `CONTROL_BANK_ALL_OFF`, `CONTROL_BANK_ALL_ON`, `CONTROL_BANK_CHANNEL`, `CONTROL_BANK_MIXER`, `CONTROL_BANK_USER1`, `CONTROL_BANK_USER2`, and combinations (see `akai_fire/constants.py`).

Grid: `PAD_COUNT = 64`, `PAD_NOTE_BASE = 54` (pad N is note `54 + N`)
