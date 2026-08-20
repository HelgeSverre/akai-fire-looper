# AKAI Fire — Python Library

Python library for the [AKAI Fire](https://www.akaipro.com/fire) MIDI controller: 64 RGB pads, button and track LEDs, a 128×64 OLED display, and an event-driven API for building sequencers, grooveboxes, and other controller software.

Works against real hardware over MIDI, or against one of three built-in mocks (interactive pygame window, terminal UI, or headless) so you can develop without the device plugged in.

## Requirements

- Python **3.12+**
- AKAI Fire controller (optional — mocks cover hardware-free development)
- A system that exposes the device as a MIDI port named `FL STUDIO FIRE` (the default; configurable)

## Installation

The library is not on PyPI. Install from a clone of this repository:

```shell
git clone https://github.com/HelgeSverre/akai-fire-looper.git
cd akai-fire-looper

# Install with uv (recommended)
uv sync --all-extras

# Or with pip
pip install -e ".[pygame,tui]"
```

Extras: `pygame` (interactive mock), `tui` (terminal mock), `examples` (state-machine dependency used by some examples), `dev` (black).

## Quickstart

Blink all 64 pads through the color space. Auto-detects hardware and falls back to the pygame mock when no device is found:

```python
from akai_fire import get_akai_fire
import time

if __name__ == "__main__":
    with get_akai_fire() as fire:
        fire.clear_all_pads()
        try:
            while True:
                for r in range(4):
                    for g in range(4):
                        for b in range(4):
                            for pad in range(64):
                                fire.set_pad_color(pad, r * 42, g * 42, b * 42)
                            time.sleep(0.1)
        except KeyboardInterrupt:
            pass  # the context manager clears LEDs and closes the connection
```

Run it:

```shell
just example pad_color_cycle   # or any example by name
```

## Connecting

### Auto-detection (recommended)

`get_akai_fire()` tries hardware first, then falls back to the pygame mock:

```python
from akai_fire import get_akai_fire

with get_akai_fire() as fire:
    ...  # identical code path for hardware and mock
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

fire = AkaiFire(port_name="FIRE")
```

## Device Control

### Pads

Pad indices are `0–63`, left-to-right, top-to-bottom. Colors are RGB, each channel `0–127`.

```python
fire.set_pad_color(0, 127, 0, 0)          # pad 0 bright red
fire.set_pad_color_fast(0, 127, 0, 0)     # skips validation (tight loops)
fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
fire.set_all_pads((127, 127, 127))        # everything white
fire.clear_pad(0)
fire.clear_all_pads()
```

Invalid indices raise `InvalidParameterError`. Values are clamped to valid ranges.

Geometry helpers treat the grid as 16 columns × 4 rows:

```python
fire.pad_position(16)     # (row=1, col=0)
fire.get_pad_column(15)   # 16 (one-indexed)
fire.get_pad_row(16)      # 2  (one-indexed)
```

### Button LEDs

```python
fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
fire.set_button_led(fire.BUTTON_PLAY, fire.LED_OFF)
fire.clear_all_button_leds()
```

LED values: `LED_OFF` (0), `LED_DULL_RED`/`LED_DULL_GREEN`/`LED_DULL_YELLOW` (1), `LED_HIGH_RED`/`LED_HIGH_GREEN`/`LED_HIGH_YELLOW` (2).

### Track LEDs

The four rectangular LEDs take values `0–4` (`RECTANGLE_LED_*` constants):

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
fire.clear_all()   # pads + button LEDs + track LEDs + control bank + OLED
```

## Event Handling

Register handlers with decorators or plain listener calls. Handlers run on a background thread pool by default (see [Threading](#threading)), exceptions are logged and isolated per handler.

```python
with get_akai_fire() as fire:
    @fire.on_pad()                    # every pad → (pad_index, velocity)
    def on_any_pad(pad_index, velocity):
        print(f"pad {pad_index} velocity {velocity}")

    @fire.on_pad(0)                   # one pad → (velocity,)
    def on_pad_zero(velocity):
        ...

    @fire.on_pad([0, 1, 2])           # several pads → (pad_index, velocity)
    def on_first_row(pad_index, velocity):
        ...

    @fire.on_button(fire.BUTTON_PLAY) # press/release events
    def on_play(event):
        ...

    @fire.on_rotary_turn(fire.ROTARY_VOLUME)  # ("clockwise"|"counterclockwise", velocity)
    def on_volume(direction, velocity):
        ...

    @fire.on_rotary_touch(fire.ROTARY_VOLUME) # "touch"/"release"
    def on_volume_touch(event):
        ...

    @fire.on_solo(2)                  # solo button 2
    def on_solo_two(event):
        ...

    input("Press Enter to exit...\n")
```

Non-decorator equivalents, plus removal — safe to call from inside a handler; takes effect on the next event:

```python
def handler(velocity): ...

fire.add_listener(0, handler)             # specific pad(s)
fire.add_global_listener(handler)         # every pad
fire.add_button_listener(fire.BUTTON_PLAY, handler)
fire.add_rotary_listener(fire.ROTARY_VOLUME, handler)
fire.add_rotary_touch_listener(fire.ROTARY_VOLUME, handler)

fire.remove_listener(0, handler)
fire.remove_global_listener(handler)
fire.remove_button_listener(fire.BUTTON_PLAY, handler)
fire.remove_rotary_listener(fire.ROTARY_VOLUME, handler)
fire.remove_rotary_touch_listener(fire.ROTARY_VOLUME, handler)
```

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
canvas.draw_text("Hello Fire", 20, 20)
canvas.draw_rect(0, 0, 128, 64)        # outline
canvas.fill_rect(10, 10, 20, 20)       # filled
canvas.draw_circle(64, 32, 15)
canvas.fill_circle(64, 32, 10)
canvas.draw_line(0, 0, 127, 63)
canvas.draw_horizontal_line(0, 32, 128)
canvas.draw_vertical_line(64, 0, 64)
canvas.set_pixel(64, 32, 0)
canvas.get_pixel(64, 32)               # None when out of bounds

fire.render_to_display()               # push to device/mock
```

Higher-level layouts are built in:

```python
canvas.draw_page("Title", ["line one", "line two"])
canvas.draw_menu("Settings", ["BPM", "Swing", "MIDI"], selected_index=1)
canvas.draw_value_page("Volume", 64, min_val=0, max_val=127)
canvas.draw_split_screen("Title", ["a", "b"], ["c", "d"])
canvas.draw_grid_info("Grid", rows=4, cols=16, cell_info=[(0, 0, "C")])
```

Render to a file instead of hardware (useful for development and visual regression tests):

```python
fire.render_to_bmp("_screens/test.bmp")
```

## Threading

The MIDI polling loop runs on a daemon thread (~1 ms poll). Every decoded event goes through dispatch that:

1. Latches SHIFT/ALT inline **before** any handler runs.
2. Submits handlers to a thread pool (`async_handlers=True`, `max_workers=4`) so a slow handler can't stall input.
3. Isolates exceptions per handler — one raising listener never blocks its siblings.
4. Applies caller-runs backpressure: when the bounded queue (`handler_queue_size=64`) is full, the polling thread runs the handler inline. Events are never dropped.

Tune it:

```python
fire = AkaiFire(async_handlers=False)          # strict serial dispatch on the polling thread
fire = AkaiFire(max_workers=1)                 # async offload, FIFO ordering preserved
```

Keep handlers short (<5 ms); offload heavy work to your own threads.

## Mocks

Three interchangeable implementations share the same base class and are covered by contract tests, so code written against one runs against all:

| Implementation | Import | Use case |
|---|---|---|
| Hardware | `from akai_fire import AkaiFire` | The real device |
| Pygame mock | `from mock_gui_pygame import MockAkaiFire` | Clickable window: pads, buttons, rotaries, OLED |
| Terminal mock | `from mock_gui_tui import MockAkaiFire` | rich-based TUI, keyboard-driven, `headless=True` for CI |
| Testing mock | `from akai_fire_testing import MockAkaiFire` | Headless; event recording, `simulate_*` injection, assertions |

Pygame mock controls: click pads/buttons to press them, drag rotaries to turn them. On macOS it must run on the main thread — the examples handle this.

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

All exceptions derive from `akai_fire.AkaiFireError`:

| Exception | Raised when |
|---|---|
| `MIDIConnectionError` | Ports can't be found or opened |
| `MIDISendError` | An OLED SysEx send fails |
| `InvalidParameterError` | Bad pad index or button ID |
| `HardwareError` | Port enumeration fails |
| `StateError` | Operation invalid for current state |

```python
from akai_fire import AkaiFire, MIDIConnectionError

try:
    fire = AkaiFire()
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

Primitives: `clear(color=1)`, `set_pixel(x, y, color=0)`, `get_pixel(x, y)`, `draw_text(text, x, y, font=None, color=0)`, `draw_rect`, `fill_rect`, `draw_rectangle`, `fill_rectangle`, `draw_border(thickness=1)`, `draw_line`, `draw_horizontal_line`, `draw_vertical_line`, `draw_circle`, `fill_circle`, `clone()`

Layouts: `draw_page(title, lines, header_inverted=True)`, `draw_menu(title, items, selected_index)`, `draw_value_page(title, value, min_val=None, max_val=None, show_bar=True)`, `draw_grid_info(title, rows, cols, cell_info)`, `draw_split_screen(title, left_content, right_content)`

### Constants

Button IDs: `BUTTON_PLAY`, `BUTTON_STOP`, `BUTTON_REC`, `BUTTON_PATTERN`, `BUTTON_BROWSER`, `BUTTON_BANK`, `BUTTON_SELECT`, `BUTTON_STEP`, `BUTTON_NOTE`, `BUTTON_DRUM`, `BUTTON_PERFORM`, `BUTTON_SHIFT`, `BUTTON_ALT`, `BUTTON_GRID_LEFT`, `BUTTON_GRID_RIGHT`, `BUTTON_PAT_UP`, `BUTTON_PAT_DOWN`, `BUTTON_SOLO_1`–`BUTTON_SOLO_4`

Rotaries: `ROTARY_VOLUME`, `ROTARY_PAN`, `ROTARY_FILTER`, `ROTARY_RESONANCE`, `ROTARY_SELECT`

Button LEDs: `LED_OFF`, `LED_DULL_RED`, `LED_HIGH_RED`, `LED_DULL_GREEN`, `LED_HIGH_GREEN`, `LED_DULL_YELLOW`, `LED_HIGH_YELLOW`

Track LEDs: `RECTANGLE_LED_OFF` (0), `RECTANGLE_LED_DULL_RED` (1), `RECTANGLE_LED_DULL_GREEN` (2), `RECTANGLE_LED_HIGH_RED` (3), `RECTANGLE_LED_HIGH_GREEN` (4)

Control bank fields: `FIELD_BASE` (required), `FIELD_CHANNEL`, `FIELD_MIXER`, `FIELD_USER1`, `FIELD_USER2` — combined with `|`. Predefined states: `CONTROL_BANK_ALL_OFF`, `CONTROL_BANK_ALL_ON`, `CONTROL_BANK_CHANNEL`, `CONTROL_BANK_MIXER`, `CONTROL_BANK_USER1`, `CONTROL_BANK_USER2`, and combinations (see `akai_fire/constants.py`).

Grid: `PAD_COUNT = 64`, `PAD_NOTE_BASE = 54` (pad N is note `54 + N`)

## Examples

Run any of them with `just example NAME` (or `uv run python examples/NAME.py`). Without hardware they open the pygame mock.

**Getting started** — `display_hello_world`, `clear_all`, `pad_color_cycle`, `pad_toggle_on_press`

**Events** — `event_handling_basic`, `event_handling_comprehensive`

**Animations** — `animation_pad_blink_random`, `animation_water_ripple_interactive`, `batch_animation`, `batch_performance`

**Screen** — `screen_animated_wave`, `screen_bounce`, `screen_showcase`, `screen_snow`, `screen_pages`

**LEDs** — `control_bank_leds`, `track_led_cycle`, `track_led_rain`

**Music applications** — `music_sequencer`, `music_groovebox`, `music_looper_advanced`, `music_circuit_sequencer`, plus full apps under `examples/apps/` and `examples/circuit/`

See `examples/README.md` for descriptions.

## Development

Uses [`uv`](https://github.com/astral-sh/uv) for dependencies and [`just`](https://github.com/casey/just) for task running. Dev Python is pinned to 3.12 via `.python-version`.

```shell
just            # list all recipes
just setup      # create .venv and sync all extras
just test       # run the test suite (unittest)
just lint       # black --check
just format     # black
just check      # lint + test — pre-commit gate
just clean      # remove caches and generated output
```

### Project layout

```
akai_fire/               core package (lazy imports: rtmidi/PIL load only on use)
├── constants.py         authoritative MIDI constants
├── errors.py            exception hierarchy
├── canvas.py            OLED canvas abstraction
├── device.py            shared base: listeners, dispatch, modifiers
└── hardware.py          rtmidi I/O, SysEx encoding, polling thread

akai_fire_framework/     app framework (app, grid, mode, screen, transport)
akai_fire_testing/       headless mocks, event simulation, screenshot comparison
mock_gui_pygame.py       interactive pygame mock
mock_gui_tui.py          terminal-UI mock
screen_manager.py        TextScreen / MenuScreen / ProgressScreen / GridScreen / ValueScreen
tests/                   unittest suite incl. cross-implementation contract tests
docs/                    ARCHITECTURE.md, CHANGELOG.md, ROADMAP.md, TROUBLESHOOTING.md
```

### Testing

271 tests, no hardware required — MIDI ports are mocked throughout:

- `test_sysex_encoder.py` — golden vectors for the OLED bitmap encoder
- `test_device_contract.py` — parity contract across all four implementations
- `test_akai_fire.py` — dispatch threading, reconnect, message parsing
- plus canvas, screen manager, pygame/TUI/testing-mock suites

Pygame-dependent tests skip automatically when pygame's font module is unavailable (e.g. Python ≥ 3.14 with pygame 2.6.1).

## Troubleshooting

- **Device not found** — check `fire.list_midi_ports()` output; pass a matching `port_name` substring. On Linux you may need udev rules for MIDI access.
- **macOS pygame window frozen** — run the mock on the main thread (the examples do).
- More in `docs/TROUBLESHOOTING.md`.

## Credits

Built upon the work of others:

- ["Decoding the AKAI Fire"](https://blog.segger.com/decoding-the-akai-fire-part-1/) — Segger's reverse-engineering write-ups of the SysEx protocol
- [python-rtmidi](https://pypi.org/project/python-rtmidi/) — MIDI I/O
