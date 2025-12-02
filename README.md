# AKAI Fire - Python Library

Python library to interact with the AKAI Fire controller, a MIDI controller for FL Studio.

## Hello World Example: Blinking Pads

Here is a simple example that makes all the pads blink in various colors. Use this as a quick test to ensure your
library and device are working:

```python
from akai_fire import get_akai_fire
import time

if __name__ == "__main__":
    # Initialize the AKAI Fire controller (auto-detects hardware or falls back to mock GUI)
    with get_akai_fire() as fire:
        fire.clear_all_pads()

        try:
            while True:
                for r in range(4):  # Red intensity (0-3)
                    for g in range(4):  # Green intensity (0-3)
                        for b in range(4):  # Blue intensity (0-3)
                            for pad in range(64):  # Loop through all 64 pads
                                fire.set_pad_color(pad, r * 42, g * 42, b * 42)
                            time.sleep(0.1)
        except KeyboardInterrupt:
            pass  # Context manager handles cleanup
```

## Usage Guide

### Connecting to the Device

By default, the library looks for a device named "FL STUDIO FIRE". You can customize this if your device shows up
differently:

```python
from akai_fire import AkaiFire

# Defaults to "FL STUDIO FIRE"
fire = AkaiFire(port_name="MIDI Port name here")

canvas = fire.get_canvas()
canvas.draw_text("Hello world", 10, 20)

fire.render_to_display()
fire.close()
```

### Using the Mock GUI (No Hardware Required)

The library includes a Pygame-based mock GUI that simulates the AKAI Fire hardware visually. This allows you to develop and test without the physical device:

```python
from mock_gui_pygame import MockAkaiFire

# Create mock controller
fire = MockAkaiFire()

# Use exactly the same API as real hardware
fire.set_pad_color(0, 127, 0, 0)  # Red pad
canvas = fire.get_canvas()
canvas.draw_text("Mock Mode", 10, 10)
fire.render_to_display()
```

### Auto-Detection (Recommended)

For scripts that should work with both hardware and mock, use `get_akai_fire()`:

```python
from akai_fire import get_akai_fire

# Auto-detects: uses hardware if available, falls back to mock GUI
with get_akai_fire() as fire:
    fire.set_pad_color(0, 127, 0, 0)
    canvas = fire.get_canvas()
    canvas.draw_text("Works everywhere!", 10, 10)
    fire.render_to_display()
```

### Basic Device Control

```python
from akai_fire import get_akai_fire

with get_akai_fire() as fire:
    # Control pads
    fire.set_pad_color(0, 127, 0, 0)  # Set first pad to bright red
    fire.clear_all_pads()  # Turn off all pads

    # Control buttons
    fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
    fire.clear_all_button_leds()
```

### Event Handling

```python
from akai_fire import get_akai_fire

with get_akai_fire() as fire:
    # Handle pad presses with decorators
    @fire.on_pad()
    def on_any_pad(pad_index, velocity):
        print(f"Pad {pad_index} pressed with velocity {velocity}")
        fire.set_pad_color(pad_index, 127, 0, 0)

    # Handle specific button
    @fire.on_button(fire.BUTTON_PLAY)
    def on_play(event):
        print(f"Play button {event}")
        if event == "press":
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
        else:
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_OFF)

    # Handle rotary encoder
    @fire.on_rotary_turn(fire.ROTARY_VOLUME)
    def on_volume(direction, velocity):
        print(f"Volume turned {direction} with velocity {velocity}")

    # Keep running
    input("Press Enter to exit...\n")
```

### Screen Control

The library uses a Canvas approach to control the 128x64 OLED screen:

```python
from akai_fire import get_akai_fire

with get_akai_fire() as fire:
    canvas = fire.get_canvas()

    # Drawing operations
    canvas.clear()
    canvas.draw_text("Hello Fire", 20, 20)
    canvas.draw_rect(0, 0, 128, 64)
    canvas.fill_rect(10, 10, 20, 20)
    canvas.draw_circle(64, 32, 15)
    canvas.set_pixel(64, 32, 0)

    # Render to device/mock
    fire.render_to_display()
```

For development without a device, save the screen content to BMP files:

```python
import os
from akai_fire import AkaiFire

fire = AkaiFire()
canvas = fire.new_canvas()
canvas.draw_text("Test Screen", 10, 10)

# Save as BMP
os.makedirs("_screens", exist_ok=True)
fire.render_to_bmp(os.path.join("_screens", "test_screen.bmp"))
```

## API Reference

### AkaiFire Class

The `AkaiFire` class provides methods to interact with all aspects of the device including pads, buttons, LEDs, and the
OLED screen.

#### Initialization

```python
from akai_fire import AkaiFire, get_akai_fire

# Direct connection (requires hardware)
fire = AkaiFire(port_name="FL STUDIO FIRE")

# Auto-detect with mock fallback (recommended)
fire = get_akai_fire()
```

#### Pad Control

- `clear_all_pads()` - Turns off all pad colors
- `set_pad_color(index, red, green, blue)` - Sets the color of a specific pad (0-63)
- `set_multiple_pad_colors(pad_colors)` - Sets colors for multiple pads with a list of (index, red, green, blue) tuples
- `set_all_pads((red, green, blue))` - Sets all pads to the same color

#### Button and LED Control

- `set_button_led(button_id, value)` - Sets the LED state for a specific button
- `set_control_bank_leds(state)` - Controls the bank of control LEDs
- `set_track_led(track_number, value)` - Sets the state of track LEDs (1-4)
- `clear_all_button_leds()` - Turns off all button LEDs
- `clear_all_track_leds()` - Turns off all track LEDs
- `clear_control_bank_leds()` - Turns off all control bank LEDs

#### Event Decorators

- `@fire.on_pad(pad_index)` - Listen for specific pad press events
- `@fire.on_pad()` - Listen for all pad press events (receives pad_index, velocity)
- `@fire.on_button(button_id)` - Listen for button press/release events
- `@fire.on_rotary_turn(rotary_id)` - Listen for rotary encoder turns
- `@fire.on_rotary_touch(rotary_id)` - Listen for rotary encoder touch events
- `@fire.on_solo(solo_number)` - Listen for solo button events (1-4)

#### Screen Control

```python
canvas = fire.get_canvas()  # Get current canvas
canvas = fire.new_canvas()  # Create fresh canvas

# Drawing methods
canvas.clear()
canvas.draw_text("text", x, y)
canvas.draw_rect(x, y, width, height)
canvas.fill_rect(x, y, width, height)
canvas.draw_circle(x, y, radius)
canvas.fill_circle(x, y, radius)
canvas.draw_line(x1, y1, x2, y2)
canvas.set_pixel(x, y, color)
canvas.draw_border(thickness=1)

# Render
fire.render_to_display()  # Send to device
fire.render_to_bmp("file.bmp")  # Save to file
```

#### General Methods

- `close()` - Closes the connection to the device
- `get_pad_row(pad_index)` - Returns the row number (1-4) for a given pad index

### Constants

#### LED Values

```python
LED_OFF = 0x00
LED_DULL_RED = 0x01
LED_HIGH_RED = 0x02
LED_DULL_GREEN = 0x01
LED_HIGH_GREEN = 0x02
```

#### Button IDs

```python
BUTTON_PLAY, BUTTON_STOP, BUTTON_REC
BUTTON_PATTERN, BUTTON_BROWSER, BUTTON_GRID_LEFT, BUTTON_GRID_RIGHT
BUTTON_MUTE_1 through BUTTON_MUTE_4
BUTTON_SOLO_1 through BUTTON_SOLO_4
BUTTON_SELECT, BUTTON_STEP, BUTTON_NOTE, BUTTON_DRUM, BUTTON_PERFORM
BUTTON_SHIFT, BUTTON_ALT
```

#### Rotary Encoders

```python
ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER, ROTARY_RESONANCE, ROTARY_SELECT
```

#### Control Bank States

| Field           | Value  | Description          |
|-----------------|--------|----------------------|
| `FIELD_BASE`    | `0x10` | Base flag (required) |
| `FIELD_CHANNEL` | `0x01` | Channel LED          |
| `FIELD_MIXER`   | `0x02` | Mixer LED            |
| `FIELD_USER1`   | `0x04` | User 1 LED           |
| `FIELD_USER2`   | `0x08` | User 2 LED           |

### Control Bank Examples

```python
from akai_fire import get_akai_fire
import time

with get_akai_fire() as fire:
    # Using predefined states
    fire.set_control_bank_leds(fire.CONTROL_BANK_ALL_ON)
    time.sleep(1)

    # Combining fields manually
    custom_state = fire.FIELD_BASE | fire.FIELD_USER1 | fire.FIELD_USER2
    fire.set_control_bank_leds(custom_state)
    time.sleep(1)

    fire.clear_control_bank_leds()
```

## Examples

The `examples` directory contains scripts demonstrating the library's capabilities:

### Getting Started
- `display_hello_world.py` - Smooth color fading across all pads
- `clear_all.py` - Clears all LEDs, buttons, pads, and screen
- `pad_color_cycle.py` - Cycles through pad colors one at a time
- `pad_toggle_on_press.py` - Toggle pad colors on press

### Event Handling
- `event_handling_basic.py` - Basic event handling with decorators
- `event_handling_comprehensive.py` - Complete event handling examples

### Animations
- `animation_pad_blink_random.py` - Random pad blinking
- `animation_water_ripple_interactive.py` - Interactive water ripple effect
- `batch_animation.py` - Smooth animations using batch updates
- `batch_performance.py` - Performance comparison of batch vs single updates

### Screen Examples
- `screen_animated_wave.py` - Animated wave on OLED screen
- `screen_bounce.py` - Bouncing ball animation
- `screen_showcase.py` - Various screen drawing demos
- `screen_snow.py` - Static snow effect
- `screen_pages.py` - Multi-page screen navigation

### LED Control
- `control_bank_leds.py` - Control bank LED states
- `track_led_cycle.py` - Cycle through track LEDs
- `track_led_rain.py` - Track LED rain animation

### Music Applications
- `music_sequencer.py` - Basic step sequencer with state machine
- `music_groovebox.py` - Complete groovebox application
- `music_looper_advanced.py` - Advanced MIDI looper
- `music_circuit_sequencer.py` - Circuit Tracks style sequencer

### Run an Example

```bash
# Using just
just example display_hello_world

# Or directly with uv
uv run python examples/display_hello_world.py
```

## Setup for Development

This project uses [`uv`](https://github.com/astral-sh/uv) for Python package management and [`just`](https://github.com/casey/just) for development commands.

### Quick Setup

```shell
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (if not already installed)
# macOS: brew install just
# Other platforms: https://github.com/casey/just#installation

# Setup development environment
just setup

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux

# See all available commands
just
```

### Manual Setup

```shell
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
```

### Development Commands

```shell
just format        # Format code with black
just test          # Run all tests
just test-hardware # Run tests with hardware report
just example NAME  # Run specific example
just examples      # List all examples
just check         # Check code quality
just clean         # Clean up generated files
```

## Mock GUI Features

The mock GUI (`mock_gui_pygame.py`) provides:
- Visual representation of all 64 RGB pads
- Working OLED display with green phosphor simulation
- All buttons with LED feedback
- 5 rotary encoders with mouse control
- Track LEDs and control bank LEDs
- Full API compatibility with the hardware library

### Mock GUI Controls
- **Click pads** to trigger press events
- **Click and drag rotary encoders** to turn them
- **Click buttons** to press them
- All visual feedback updates in real-time
- Close the window to exit

**macOS Note**: On macOS, the Pygame GUI must run on the main thread. The examples handle this correctly.

## Code Formatting

```shell
just format       # Format all Python files
just format-check # Check formatting without changes
```

## Credits

Built upon the work done by others:

- ["Segger - Decoding the AKAI Fire"](https://blog.segger.com/decoding-the-akai-fire-part-1/)
- Uses the [python-rtmidi](https://pypi.org/project/python-rtmidi/) library
