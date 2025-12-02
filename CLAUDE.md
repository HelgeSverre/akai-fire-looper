# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library for interfacing with the AKAI Fire MIDI controller, designed for FL Studio. The library provides low-level hardware control (pads, buttons, LEDs, OLED screen) and event handling for building creative applications like sequencers and grooveboxes.

## Development Commands

This project uses `uv` for Python environment and dependency management, and `just` for common development tasks.

### Setup Environment
```bash
# Quick setup with just
just setup

# Manual setup with uv
uv venv  # Creates .venv directory
source .venv/bin/activate  # macOS/Linux
uv pip install -r requirements.txt  # Install from requirements.txt
```

### Running Tests
```bash
just test  # Run all tests
just test-hardware  # Run tests with comprehensive hardware report
just test-file tests.test_canvas  # Run specific test file

# Manual with uv
uv run python -m unittest discover tests -v
```

### Code Formatting
```bash
just format  # Format all Python files
just format-check  # Check formatting without changes

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
just install  # Install dependencies
just freeze  # Update requirements.txt with current packages

# Manual with uv
uv pip install -r requirements.txt
uv pip freeze > requirements.txt
```

### All Available Commands
```bash
just  # Show all available commands
just status  # Show project status
just clean  # Clean up generated files
```

## Architecture Overview

### Core Components

1. **AkaiFire Class** (`akai_fire.py`): Main interface to the MIDI controller
   - Manages MIDI I/O through `rtmidi`
   - Handles pad colors, button LEDs, and screen updates
   - Event system for pad/button/encoder interactions
   - Supports both global and specific event listeners

2. **Canvas Class** (`akai_fire.py`): Screen abstraction layer
   - 128x64 monochrome display
   - Drawing primitives (pixels, lines, rectangles, circles, text)
   - BMP export for development without hardware

3. **MockAkaiFire Class** (`mock_gui_pygame.py`): Pygame-based hardware simulator
   - Full visual simulation of the AKAI Fire
   - Same API as AkaiFire for seamless development
   - Auto-fallback via `get_akai_fire()` when hardware unavailable

4. **ScreenManager** (`screen_manager.py`): High-level screen management
   - Pre-built screen types: TextScreen, MenuScreen, ProgressScreen, GridScreen, ValueScreen
   - Screen transitions and lifecycle management

5. **Event System**: Callback-based architecture
   - Decorator-based: `@fire.on_pad()`, `@fire.on_button()`, `@fire.on_rotary_turn()`
   - Listener-based: `add_listener()`, `add_button_listener()`, `add_rotary_listener()`

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
- Hardware communication tests with mocked MIDI (`test_akai_fire.py`)
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

Core dependencies (see `requirements.txt`):
- `python-rtmidi==1.5.8` - MIDI communication
- `pillow~=11.1.0` - Image manipulation for Canvas
- `pygame==2.6.1` - Mock GUI rendering
- `black==25.1.0` - Code formatting
- `transitions~=0.9.2` - State machines (used in examples)
