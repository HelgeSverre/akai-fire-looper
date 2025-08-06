# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library for interfacing with the AKAI Fire MIDI controller, designed for FL Studio. The library provides low-level hardware control (pads, buttons, LEDs, OLED screen) and event handling for building creative applications like sequencers and grooveboxes.

## Development Commands

This project uses `uv` for Python environment and dependency management.

### Setup Environment
```bash
uv venv  # Creates .venv directory
source .venv/bin/activate  # macOS/Linux
uv pip install -r requirements.txt  # Install from requirements.txt
# OR
uv pip sync  # Install from uv.lock for exact reproducibility
```

### Running Tests
```bash
uv run python -m unittest discover tests  # Run all tests
uv run python -m unittest tests.test_akai_fire  # Run specific test
uv run python -m unittest discover -v tests  # Verbose output
```

### Code Formatting
```bash
uv run black .  # Format all Python files
```

### Running Examples
```bash
uv run python examples/hello_world.py  # Basic example
uv run python examples/screen_simple.py  # Screen rendering example
uv run python examples/groovebox/main.py  # Full groovebox application
```

### Managing Dependencies
```bash
uv pip install package-name  # Add new dependency
uv pip freeze > requirements.txt  # Update requirements.txt
uv pip sync  # Sync environment with uv.lock
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

3. **Event System**: Callback-based architecture
   - `on_pad_press/release(pad_idx, velocity)`
   - `on_button_press/release(button_idx)`  
   - `on_encoder_turn(direction)` and `on_encoder_touch/release()`
   - Register handlers with `@fire.on_event` decorators or `add_listener()`

### Key Design Patterns

- **Hardware Abstraction**: All hardware communication goes through MIDI messages
- **Canvas Pattern**: Screen updates use a canvas abstraction that can render to hardware or BMP files
- **Event-Driven**: All user interactions are handled through event callbacks
- **Mock Support**: Can run without hardware using `mock_gui.py` or BMP screen output

### Important Constants

- Default MIDI port: `"FL STUDIO FIRE"`
- Screen dimensions: 128x64 pixels (monochrome)
- Pad grid: 16x4 (64 total pads)
- Pad indices: 0-63 (left-to-right, top-to-bottom)

## Testing Approach

Tests use Python's built-in `unittest` framework with mocked MIDI ports. The test suite includes:
- Hardware communication tests with mocked MIDI
- Canvas drawing operations
- Event handling verification

When adding features, ensure tests mock the MIDI ports to avoid hardware dependencies.

## Common Development Tasks

### Adding New Screen Features
1. Extend the Canvas class with new drawing methods
2. Test using `render_to_bmp()` to visualize without hardware
3. Add unit tests for the new Canvas methods

### Creating New Examples
1. Place in `examples/` directory
2. Import and instantiate `AkaiFire`
3. Use event decorators or listeners for user input
4. Update screen using Canvas operations

### Working with the Groovebox Example
The `examples/groovebox/` directory contains a complete sequencer application demonstrating:
- State machine pattern for UI modes
- Modular view system
- Settings management
- Complex event handling

## Dependencies Note

The `requirements.txt` file may have encoding issues. Core dependencies are:
- `python-rtmidi==1.5.8` - MIDI communication
- `pillow~=11.1.0` - Image manipulation
- `black==25.1.0` - Code formatting
- `transitions~=0.9.2` - State machines
- `tkdial~=0.0.7` - GUI widgets for mock

## Project Documentation

Additional documentation can be found in the `docs/` directory:
- `IMPLEMENTATION_ROADMAP.md` - Current development priorities and plans
- `IMPROVEMENTS.md` - Detailed list of suggested improvements
- `CHANGELOG.md` - Version history and completed features
- `performance_improvements.md` - Performance optimization details