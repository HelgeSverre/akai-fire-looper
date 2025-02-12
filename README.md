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

By default, the library looks for a device named "FL STUDIO FIRE". You can customize this if your device shows up differently:

```python
# Default connection
fire = AkaiFire()  # Looks for "FL STUDIO FIRE"

# Custom device name
fire = AkaiFire(port_name="YOUR DEVICE NAME")

# Check available MIDI ports
import rtmidi
midi_in = rtmidi.MidiIn()
midi_out = rtmidi.MidiOut()
print("Available MIDI inputs:", midi_in.get_ports())
print("Available MIDI outputs:", midi_out.get_ports())
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

The library provides two ways to work with the OLED screen:

1. Direct device control:
```python
from akai_fire import AkaiFire, AkaiFireBitmap

fire = AkaiFire()
bitmap = AkaiFireBitmap()

# Draw something
bitmap.draw_rectangle(0, 0, 128, 64, 1)
bitmap.draw_circle(64, 32, 20, 1)

# Send to device
fire.send_bitmap(bitmap)
```

2. Development without device (Screen Emulation):
```python
from canvas import Canvas, BMPRenderer

# Create canvas and BMP renderer
canvas = Canvas()
renderer = BMPRenderer(output_dir="_screens")

# Draw your content
canvas.draw_text("Testing without device", 10, 10)
canvas.draw_rect(0, 0, 128, 64)
canvas.fill_rect(10, 10, 20, 20)

# Save as BMP file instead of sending to device
renderer.render_canvas(canvas, "test_screen.bmp")
```

The BMPRenderer is particularly useful for:
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

The AKAI Fire has a 128x64 OLED display that can be controlled in two ways:

1. Direct Bitmap Control:

```python
from akai_fire import AkaiFire, AkaiFireBitmap

fire = AkaiFire()
bitmap = AkaiFireBitmap()

# Draw directly on the bitmap
bitmap.set_pixel(x, y, color)
bitmap.draw_horizontal_line(x, y, length, color)
bitmap.draw_vertical_line(x, y, length, color)
bitmap.draw_rectangle(x, y, width, height, color)
bitmap.fill_rectangle(x, y, width, height, color)
bitmap.draw_circle(x0, y0, radius, color)
bitmap.fill_circle(x0, y0, radius, color)

# Send to device
fire.send_bitmap(bitmap)
```

2. High-Level Canvas API:

```python
from akai_fire import AkaiFire
from canvas import Canvas, FireRenderer

# Create canvas and renderer
canvas = Canvas()
renderer = FireRenderer(fire)

# Draw using high-level methods
canvas.draw_text("Hello Fire", 20, 20)
canvas.draw_rect(0, 0, 128, 64)
canvas.fill_rect(10, 10, 20, 20)
canvas.set_pixel(64, 32, 1)

# Render to device
renderer.render_canvas(canvas)
```

#### Screen Debugging

For development without a physical device, you can render the screen content to BMP files:

```python
from canvas import Canvas, BMPRenderer

canvas = Canvas()
renderer = BMPRenderer(output_dir="_screens")

# Draw your content
canvas.draw_text("Test Screen", 10, 10)

# Save as BMP
renderer.render_canvas(canvas, "test_screen.bmp")
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

### Predefined Combinations

| Constant                                   | Value  | Active LEDs               |
|--------------------------------------------|--------|---------------------------|
| `CONTROL_BANK_ALL_OFF`                     | `0x10` | None                      |
| `CONTROL_BANK_ALL_ON`                      | `0x1F` | All                       |
| `CONTROL_BANK_CHANNEL`                     | `0x11` | Channel                   |
| `CONTROL_BANK_MIXER`                       | `0x12` | Mixer                     |
| `CONTROL_BANK_USER1`                       | `0x14` | User 1                    |
| `CONTROL_BANK_USER2`                       | `0x18` | User 2                    |
| `CONTROL_BANK_CHANNEL_AND_MIXER`           | `0x13` | Channel + Mixer           |
| `CONTROL_BANK_CHANNEL_AND_USER1`           | `0x15` | Channel + User 1          |
| `CONTROL_BANK_CHANNEL_AND_USER2`           | `0x19` | Channel + User 2          |
| `CONTROL_BANK_MIXER_AND_USER2`             | `0x1A` | Mixer + User 2            |
| `CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1` | `0x17` | Channel + Mixer + User 1  |
| `CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2` | `0x1B` | Channel + Mixer + User 2  |
| `CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2` | `0x1D` | Channel + User 1 + User 2 |
| `CONTROL_BANK_MIXER_AND_USER1_AND_USER2`   | `0x1E` | Mixer + User 1 + User 2   |

### Control Bank Examples

```python
from akai_fire import AkaiFire
import time

fire = AkaiFire()

# Using predefined states
fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_ALL_ON)  # Turn all LEDs on
time.sleep(1)

fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER)  # Channel + Mixer only
time.sleep(1)

# Combining fields manually
custom_state = AkaiFire.FIELD_BASE | AkaiFire.FIELD_USER1 | AkaiFire.FIELD_USER2  # Both USER LEDs
fire.set_control_bank_leds(custom_state)
time.sleep(1)

# Cycling through different combinations
combinations = [
    AkaiFire.CONTROL_BANK_CHANNEL,
    AkaiFire.CONTROL_BANK_MIXER,
    AkaiFire.CONTROL_BANK_USER1,
    AkaiFire.CONTROL_BANK_USER2
]

for state in combinations:
    fire.set_control_bank_leds(state)
    time.sleep(0.5)

# Turn everything off
fire.clear_control_bank_leds()
fire.close()
```

#### Rotary Controls

```python
ROTARY_VOLUME = 0x10
ROTARY_PAN = 0x11
ROTARY_FILTER = 0x12
ROTARY_RESONANCE = 0x13
ROTARY_SELECT = 0x76
```

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
- [Bitmap drawing routine](https://github.com/scjurgen/AkaiFireMapper/blob/master/akaifire.py#L61-L69)
- Uses the [python-rtmidi](https://pypi.org/project/python-rtmidi/) library 