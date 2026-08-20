# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library for interfacing with the AKAI Fire MIDI controller, designed for FL Studio. The library provides low-level hardware control (pads, buttons, LEDs, OLED screen) and event handling for building creative applications like sequencers and grooveboxes.

## Development Commands

This project uses `uv` for Python environment and dependency management, and `just` for common development tasks. Run `just` to see all recipes.

### Setup Environment
```bash
just setup          # or: uv sync --all-extras
```

Dev Python is pinned to 3.12 via `.python-version` — pygame 2.6.1's
font module is broken on Python 3.14 and would take the pygame-mock
tests down with it.

### Running Tests
```bash
just test                        # Run all tests
just test-file tests.test_canvas # Run specific test module

# Manual with uv
uv run python -m unittest discover tests -v
```

### Code Formatting
```bash
just format        # Format all Python files
just check         # format-check + test (pre-commit gate)

# Manual with uv
uv run black .
```

### Running Examples
```bash
just example display_hello_world  # Run specific example
just examples  # List all available examples

# Manual with uv
uv run python examples/display_hello_world.py
```

### Managing Dependencies
```bash
just setup  # Sync the venv from pyproject.toml / uv.lock

# Manual with uv
uv sync --all-extras
```

`requirements.txt` is a curated mirror of `pyproject.toml` for
pip-only environments — update both together, never `uv pip freeze`.

### All Available Commands
```bash
just  # Show all available commands
just clean  # Clean up generated files
```

## Architecture Overview

### Core Components

The core library lives in the `akai_fire/` package:

1. **Constants** (`akai_fire/constants.py`): Authoritative MIDI constants
   - Every implementation inherits them via the `@install` class decorator
   - Never redefine button/rotary/LED IDs locally

2. **Errors** (`akai_fire/errors.py`): Exception hierarchy
   - `AkaiFireError` base; `MIDIConnectionError`, `MIDISendError`,
     `InvalidParameterError`, `HardwareError`, `StateError`

3. **Canvas** (`akai_fire/canvas.py`): Screen abstraction layer
   - 128x64 monochrome display (pixel 0 = lit on hardware)
   - Drawing primitives (pixels, lines, rectangles, circles, text)
   - BMP export for development without hardware

4. **AkaiFireDevice** (`akai_fire/device.py`): Shared abstract base
   - Listener registries, decorators (`on_pad`, `on_button`, ...),
     removal methods, and `_dispatch_*` helpers — authored once
   - Modifier-key latching and pad-geometry utilities

5. **AkaiFire** (`akai_fire/hardware.py`): Hardware implementation
   - Manages MIDI I/O through `rtmidi`
   - Handles pad colors, button LEDs, and OLED SysEx updates
   - Async handler dispatch thread pool + MIDI polling thread

`akai_fire/__init__.py` re-exports the public surface lazily —
importing `akai_fire` pulls neither rtmidi nor Pillow until an
`AkaiFire`/`Canvas` is actually used.

### Mocks and Support Packages

- **akai_fire_testing**: headless mock + assertions for CI
  (`MockAkaiFire`, `MockCanvas`, event simulation, screenshots)
- **akai_fire_framework**: app framework (`AkaiFireApp`, modes,
  grid, screens, transport)
- **mock_gui_pygame.py**: interactive pygame mock (dev convenience,
  auto-fallback of `get_akai_fire()`)
- **mock_gui_tui.py**: terminal-UI mock via rich
- **screen_manager.py**: TextScreen, MenuScreen, ProgressScreen,
  GridScreen, ValueScreen
   - Screen transitions and lifecycle management

5. **Event System**: Callback-based architecture
   - Decorator-based: `@fire.on_pad()`, `@fire.on_button()`, `@fire.on_rotary_turn()`
   - Listener-based: `add_listener()`, `add_button_listener()`, `add_rotary_listener()`

### Event Dispatch Threading

The MIDI polling loop runs on a dedicated daemon thread, reading messages
roughly every 1 ms via `rtmidi.MidiIn.get_message()`. Every decoded event
passes through `_process_message`, which:

1. **Latches modifier state inline.** `_shift_pressed` / `_alt_pressed`
   are updated *before* any user handler runs, so `is_shift_pressed()`
   inside a pad handler always returns a coherent value.
2. **Dispatches user handlers via a thread pool** (`async_handlers=True`
   by default, `max_workers=4`). A slow handler can no longer stall MIDI
   input or starve other handlers.
3. **Isolates exceptions per handler.** A raised exception is logged via
   `logger.exception` and never prevents sibling handlers from running.
4. **Applies caller-runs backpressure.** When the bounded submit queue is
   full (`handler_queue_size=64` by default), the MIDI thread runs the
   handler inline and logs a warning. No event is ever dropped.

Opt out of async dispatch with `AkaiFire(async_handlers=False)` if you
need strict serial ordering on the polling thread. Use `max_workers=1`
if you want async offload but preserve FIFO ordering.

**Handler contract:**

- Keep handlers short (target <5 ms). Offload heavy work (file I/O,
  long OLED redraws, network calls) to your own thread.
- Registering or removing listeners from inside a handler is safe; the
  change takes effect on the next event.
- Exceptions are logged, not swallowed silently; check your logger.

### Key Design Patterns

- **Hardware Abstraction**: All hardware communication goes through MIDI messages
- **Canvas Pattern**: Screen updates use a canvas abstraction that can render to hardware or BMP files
- **Event-Driven**: All user interactions are handled through event callbacks
- **Mock Support**: Can run without hardware using `mock_gui_pygame.py` or BMP screen output
- **Auto-Detection**: `get_akai_fire()` automatically falls back to mock when hardware unavailable

### Important Constants

- Default MIDI port: `"FL STUDIO FIRE"`
- Screen dimensions: 128x64 pixels (monochrome)
- Pad grid: 16x4 (64 total pads)
- Pad indices: 0-63 (left-to-right, top-to-bottom)

## Testing Approach

Tests use Python's built-in `unittest` framework with mocked MIDI ports. The test suite includes:
- Hardware communication, dispatch threading, and reconnect behavior (`test_akai_fire.py`)
- OLED SysEx encoder golden vectors (`test_sysex_encoder.py`)
- Cross-implementation parity contract (`test_device_contract.py`) — every
  AkaiFire implementation (hardware, pygame mock, TUI mock, testing mock)
  must expose the same surface, return types, and error contracts
- Canvas drawing operations (`test_canvas.py`)
- Screen manager and screen types (`test_screen_manager.py`)

When adding features, ensure tests mock the MIDI ports to avoid hardware dependencies. Use `@patch("rtmidi.MidiIn")` and `@patch("rtmidi.MidiOut")` decorators.

## Common Development Tasks

### Adding New Screen Features
1. Extend the Canvas class with new drawing methods
2. Test using `render_to_bmp()` to visualize without hardware
3. Add unit tests for the new Canvas methods

### Creating New Examples
1. Place in `examples/` directory
2. Use `get_akai_fire()` for auto-detection of hardware/mock
3. Use context manager pattern: `with get_akai_fire() as fire:`
4. Use event decorators or listeners for user input
5. Update screen using Canvas operations

### Working with the Groovebox Example
The `examples/groovebox/` directory contains a complete sequencer application demonstrating:
- State machine pattern for UI modes
- Modular view system
- Settings management
- Complex event handling

## Dependencies

Core dependencies (see `pyproject.toml`):
- `python-rtmidi>=1.5.8` - MIDI communication
- `pillow>=11.1.0` - Image manipulation for Canvas

Optional extras:
- `pygame>=2.6.0` - interactive mock GUI (`[pygame]`)
- `rich>=13` - terminal-UI mock (`[tui]`)
- `transitions>=0.9.2` - state machines, used by examples (`[examples]`)
- `black>=25.1.0` - code formatting (`[dev]`)
