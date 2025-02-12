# 🔥 AKAI Fire - Python Library

Python library to interact with the AKAI Fire controller, a MIDI controller for FL Studio.

## Hello World Example: Blinking Pads

Here is a simple example that makes all the pads blink in various colors. Use this as a quick test to ensure your
library and device are working:

```python
from akai_fire import AkaiFire
import time

if __name__ == "__main__":
    # Initialize the AKAI Fire controller
    fire = AkaiFire(port_name="FL STUDIO FIRE")

    # Clear any existing pad colors
    fire.clear_all_pads()

    try:
        while True:
            for r in range(4):  # Red intensity (0-3)
                for g in range(4):  # Green intensity (0-3)
                    for b in range(4):  # Blue intensity (0-3)
                        for pad in range(64):  # Loop through all 64 pads
                            fire.set_pad_color(pad, r, g, b)

                        # Brief delay before the next color
                        time.sleep(0.1)
    except KeyboardInterrupt:
        # Reset pads when exiting
        fire.clear_all_pads()
        fire.close()
```

## Usage Guide

### Connecting to the Device

By default, the library looks for a device named "FL STUDIO FIRE". You can customize this if your device shows up
differently:

```python
# Defaults to "AKAI FIRE"
fire = AkaiFire(port_name="MIDI Port name here")

canvas = fire.get_canvas()
canvas.draw_text("Hello world", 10, 20)

fire.render_to_display()
```

### Basic Device Control

```python
from akai_fire import AkaiFire

# Initialize connection
fire = AkaiFire()

# Control pads
fire.set_pad_color(0, 127, 0, 0)  # Set first pad to bright red
fire.clear_all_pads()  # Turn off all pads

# Control buttons
fire.set_button_led(AkaiFire.BUTTON_PLAY, AkaiFire.LED_HIGH_GREEN)
fire.clear_all_button_leds()

# Clean up when done
fire.close()
```

### Event Handling

```python
from akai_fire import AkaiFire

fire = AkaiFire()


# Handle pad presses
def on_pad_press(pad_index):
    print(f"Pad {pad_index} pressed")
    fire.set_pad_color(pad_index, 127, 0, 0)  # Light up pressed pad


fire.add_global_listener(on_pad_press)


# Handle button events
def on_button_event(button_id, event):
    print(f"Button {button_id} {event}")
    if event == "press":
        fire.set_button_led(button_id, AkaiFire.LED_HIGH_RED)
    else:
        fire.set_button_led(button_id, AkaiFire.LED_OFF)


fire.add_button_listener(AkaiFire.BUTTON_PLAY, on_button_event)


# Handle rotary events
def on_rotary_turn(rotary_id, direction, velocity):
    print(f"Rotary {rotary_id} turned {direction} with velocity {velocity}")


fire.add_rotary_listener(AkaiFire.ROTARY_VOLUME, on_rotary_turn)

# Keep the script running
try:
    input("Press Enter to exit...\n")
finally:
    fire.close()
```

### Screen Control and Emulation

The library now uses a simplified Canvas approach to control the OLED screen.

1. **Direct device control:**

```python
from akai_fire import AkaiFire

fire = AkaiFire()
canvas = fire.new_canvas()

# Draw something on the canvas
canvas.draw_rectangle(0, 0, 128, 64)
canvas.draw_circle(64, 32, 20)
canvas.draw_text("Hello, World!", 10, 10)

# Send to device
fire.render_to_display()
```

2. **Development without device (Screen Emulation):**

```python
from akai_fire import AkaiFire
import os

fire = AkaiFire()
canvas = fire.new_canvas()

# Draw on the canvas
canvas.draw_text("Testing without device", 10, 10)
canvas.draw_rect(0, 0, 128, 64)
canvas.fill_rect(10, 10, 20, 20)

# Save as BMP file
os.makedirs("_screens", exist_ok=True)
fire.render_to_bmp(os.path.join("_screens", "test_screen.bmp"))
```

The simplified Canvas approach is particularly useful for:

- Developing without physical hardware
- Debugging screen layouts
- Creating documentation
- Testing screen designs
- Sharing screen layouts with others

Generated BMP files will be saved in the specified output directory (defaults to "_screens").

## API Reference

### AkaiFire Class

The `AkaiFire` class provides methods to interact with all aspects of the device including pads, buttons, LEDs, and the
OLED screen.

#### Initialization

```python
fire = AkaiFire(port_name="FL STUDIO FIRE")
```

#### Pad Control

- `clear_all_pads()` - Turns off all pad colors
- `set_pad_color(index, red, green, blue)` - Sets the color of a specific pad (0-63)
- `set_multiple_pad_colors(pad_colors)` - Sets colors for multiple pads with a list of (index, red, green, blue) tuples
- `reset_pads(red=0, green=0, blue=0)` - Resets all pads to a specific color

#### Button and LED Control

- `set_button_led(button_id, value)` - Sets the LED state for a specific button
- `set_control_bank_leds(state)` - Controls the bank of control LEDs
- `set_track_led(track_number, value)` - Sets the state of track LEDs (1-4)
- `clear_all_button_leds()` - Turns off all button LEDs
- `clear_all_track_leds()` - Turns off all track LEDs
- `clear_control_bank_leds()` - Turns off all control bank LEDs

#### Input Event Listeners

- `add_button_listener(button_id, callback)` - Listen for button press/release events
- `add_global_listener(callback)` - Listen for all pad press events
- `add_listener(pad_indices, callback)` - Listen for specific pad press events
- `add_rotary_listener(rotary_id, callback)` - Listen for rotary encoder turns
- `add_rotary_touch_listener(rotary_id, callback)` - Listen for rotary encoder touch events

#### Screen Control

The AKAI Fire has a 128x64 OLED display controlled using the simplified Canvas approach:

```python
from akai_fire import AkaiFire

fire = AkaiFire()
canvas = fire.new_canvas()

# Drawing
canvas.draw_text("Hello Fire", 20, 20)
canvas.draw_rect(0, 0, 128, 64)
canvas.fill_rect(10, 10, 20, 20)
canvas.set_pixel(64, 32, 0)

# Render to device
fire.render_to_display()
```

For development without a physical device, save the screen content to BMP files:

```python
import os

fire = AkaiFire()
canvas = fire.new_canvas()
canvas.draw_text("Test Screen", 10, 10)

# Save as BMP
os.makedirs("_screens", exist_ok=True)
fire.render_to_bmp(os.path.join("_screens", "test_screen.bmp"))
```

#### General Methods

- `close()` - Closes the connection to the device
- `get_pad_row(pad_index)` - Returns the row number (1-4) for a given pad index

### Constants

The library provides several constants for working with the device:

#### LED Values

```python
LED_OFF = 0x00
LED_DULL_RED = 0x01
LED_HIGH_RED = 0x02
LED_DULL_GREEN = 0x01
LED_HIGH_GREEN = 0x02
LED_DULL_YELLOW = 0x01
LED_HIGH_YELLOW = 0x02
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
from akai_fire import AkaiFire
import time

fire = AkaiFire()

# Using predefined states
fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_ALL_ON)
time.sleep(1)

fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER)
time.sleep(1)

# Combining fields manually
custom_state = AkaiFire.FIELD_BASE | AkaiFire.FIELD_USER1 | AkaiFire.FIELD_USER2
fire.set_control_bank_leds(custom_state)
time.sleep(1)

# Turn everything off
fire.clear_control_bank_leds()
fire.close()
```

## Examples

The `examples` directory contains several scripts to demonstrate the library's capabilities:

- [blink_random.py](examples/blink_random.py) - Randomly blinks pads
- [control_bank_leds.py](examples/control_bank_leds.py) - Demonstrates control bank LED states
- [events.py](examples/events.py) - Demonstrates event handling with decorators (WIP)
- [hello_world.py](examples/hello_world.py) - All pads lights up in a uniform color
- [hello_worlder.py](examples/hello_worlder.py) - All pads lights up in a uniform color, but brighter
- [looper.py](examples/looper.py) - Old Attempt at building a MIDI clip recorder/looper
- [looper2.py](examples/looper2.py) - Attempt at building a MIDI clip recorder/looper
- [clear_all.py](examples/clear_all.py) - Clears all the LEDs, Buttons, Pads, and Screen
- [pad_color_cycle.py](examples/pad_color_cycle.py) - Lights up one pad at a time, cycling through colors.
- [pad_toggle_on_press.py](examples/pad_toggle_on_press.py) - Showcases how to handle pad press events
- [screen_animated_wave.py](examples/screen_animated_wave.py) - Shows a pleasing animated graphic on the OLED screen.
- [screen_bounce.py](examples/screen_bounce.py) - Bouncing ball animation on the OLED screen.
- [screen_showcase.py](examples/screen_showcase.py) - Demonstrates various animations on the OLED screen.
- [screen_simple.py](examples/screen_simple.py) - Shows "Hello, World!" on the OLED screen.
- [screen_snow.py](examples/screen_snow.py) - Shows static snow on the OLED scree (randomly black and white pixels).
- [track_led_cycle.py](examples/track_led_cycle.py) - Cycles through the track LEDs.
- [track_led_rain.py](examples/track_led_rain.py) - Cycles through each track and lights up the SOLO, Track led, and
  each pad in a sequence.

### Experimental Examples

- [batching.py](experiments/batching.py) - Batched pad color updates
- [batching_animated.py](experiments/batching_animated.py) - Batched pad color updates with animation (smoother)
- [batching_water.py](experiments/batching_water.py) - Batched pad color updates with a water animation and interaction
  with the pads, rotary encoders, and buttons.
- [non_batch_water.py](experiments/non_batch_water.py) - Same-ish but not batched to compare performance.

## Setup for Development

```shell
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the requirements
pip install -r requirements.txt
```

## Code Formatting

```shell
pipx run black .

# or windows after `pip install`
black */**.py
```

### 🧠 Quick-Tips for `requirements.txt`

To automatically generate `requirements.txt`:

```shell
pipx pipreqs . --force

# or the traditional way
pip install pipreqs
pipreqs . --force
```

## Credits

Built upon the work done by others:

- ["Segger - Decoding the AKAI Fire"](https://blog.segger.com/decoding-the-akai-fire-part-1/)
- Uses the [python-rtmidi](https://pypi.org/project/python-rtmidi/) library

