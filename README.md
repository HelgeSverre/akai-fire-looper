# 🔥 AKAI Fire - MIDI Looper and Python Library

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
    fire.clear_pads()

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
        fire.clear_pads()
        fire.close()
```

## API Quick Reference

### AkaiFire Class

The `AkaiFire` class provides methods to interact with the pads, buttons, and LEDs on the device.

#### Initialization

```python
fire = AkaiFire(port_name="FL STUDIO FIRE")
```

#### Pad and LED Control

- `fire.clear_pads()` - Clears all pad colors.
- `fire.set_pad_color(index, red, green, blue)` - Sets the color of a specific pad.
- `fire.set_multiple_pad_colors(pad_colors)` - Sets colors for multiple pads at once.
- `fire.reset_pads(red=0, green=0, blue=0)` - Resets all pads to a specific color.
- `fire.set_button_led(button_id, value)` - Sets the LED for a specific button.
- `fire.set_control_bank_leds(state)` - Controls the LEDs for the control bank.
- `fire.clear_all_button_leds()` - Turns off all button LEDs.

#### Input Listeners

- `fire.add_button_listener(button_id, callback)` - Listens for button presses.
- `fire.add_global_listener(callback)` - Listens for all input events.
- `fire.add_listener(pad_indices, callback)` - Listens for pad events.
- `fire.add_rotary_listener(rotary_id, callback)` - Listens for rotary knob movements.
- `fire.add_rotary_touch_listener(rotary_id, callback)` - Listens for rotary knob touch events.

#### General

- `fire.close()` - Closes the connection to the device.

### FireBitmap Class

The `FireBitmap` class is used for drawing on the OLED display of the AKAI Fire.

#### Drawing Methods

- `draw_circle(x0: int, y0: int, radius: int, color: int)` - Draws a circle.
- `draw_horizontal_line(x: int, y: int, length: int, color: int)` - Draws a horizontal line.
- `draw_rectangle(x: int, y: int, width: int, height: int, color: int)` - Draws a rectangle.
- `draw_vertical_line(x: int, y: int, length: int, color: int)` - Draws a vertical line.
- `fill_circle(x0: int, y0: int, radius: int, color: int)` - Fills a circle with a color.
- `fill_rectangle(x: int, y: int, width: int, height: int, color: int)` - Fills a rectangle with a color.
- `set_pixel(x: int, y: int, color: int)` - Sets the color of a single pixel.
- `send_bitmap(screen)` - Sends a bitmap to the display.

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
```

### 🧠 Quick-Tips for `requirements.txt`

To not have to manually manage a `requirements.txt` file, you can use `pipreqs` to generate it for you based on the
code's dependencies:

```shell
pipx pipreqs . --force

# or the traditional way
pip install pipreqs

pipreqs . --force
```

### FAQs

- **Why `rtmidi` instead of `mido`?**

  `mido` imposes length restrictions on sysex messages, which can be problematic for certain applications. `rtmidi`
  offers more flexibility and avoids these restrictions.

## Credits

Built upon the work done by others:

- ["Segger - Decoding the AKAI Fire"](https://blog.segger.com/decoding-the-akai-fire-part-1/)
- [Bitmap drawing routine](https://github.com/scjurgen/AkaiFireMapper/blob/master/akaifire.py#L61-L69)