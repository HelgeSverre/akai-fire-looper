import threading

import rtmidi

# Constants
BITMAP_SIZE = 1171  # For OLED 128x64, calculated as ceil(128*64/7)
BITMUTATE = [
    [13, 0, 1, 2, 3, 4, 5, 6],
    [19, 20, 7, 8, 9, 10, 11, 12],
    [25, 26, 27, 14, 15, 16, 17, 18],
    [31, 32, 33, 34, 21, 22, 23, 24],
    [37, 38, 39, 40, 41, 28, 29, 30],
    [43, 44, 45, 46, 47, 48, 35, 36],
    [49, 50, 51, 52, 53, 54, 55, 42],
]


class AkaiFireBitmap:
    def __init__(self):
        self.bitmap = [0] * BITMAP_SIZE

    def clear(self):
        """Clear the bitmap."""
        self.bitmap = [0] * BITMAP_SIZE

    def set_pixel(self, x: int, y: int, color: int):
        """Set a pixel on the OLED display."""
        if 0 <= x < 128 and 0 <= y < 64:
            x = x + int(128 * (y // 8))
            y %= 8
            rb = BITMUTATE[int(x % 7)][y]
            index = int((x // 7) * 8 + (rb // 7))
            if color > 0:
                self.bitmap[index] |= (1 << (rb % 7))
            else:
                self.bitmap[index] &= ~(1 << (rb % 7))

    def get_sysex_message(self):
        """Send the bitmap to the Akai Fire device using MIDI SysEx."""
        chunk_size = BITMAP_SIZE + 4
        sysex_data = [
            0xF0,  # Start of SysEx
            0x47,  # Manufacturer ID (Akai)
            0x7F,  # All-Call address
            0x43,  # Akai Fire product ID
            0x0E,  # OLED Write command
            chunk_size >> 7,  # Payload length (MSB)
            chunk_size & 0x7F,  # Payload length (LSB)
            0, 0x07,  # Start and end band
            0, 0x7F,  # Start and end column
        ]
        sysex_data.extend(self.bitmap)
        sysex_data.append(0xF7)  # End of SysEx
        return sysex_data

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int):
        """Draw a horizontal line."""
        for i in range(length):
            self.set_pixel(x + i, y, color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int):
        """Draw a vertical line."""
        for i in range(length):
            self.set_pixel(x, y + i, color)

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: int):
        """Draw a rectangle."""
        self.draw_horizontal_line(x, y, width, color)
        self.draw_horizontal_line(x, y + height - 1, width, color)
        self.draw_vertical_line(x, y, height, color)
        self.draw_vertical_line(x + width - 1, y, height, color)

    def fill_rectangle(self, x: int, y: int, width: int, height: int, color: int):
        """Fill a rectangle."""
        for i in range(height):
            self.draw_horizontal_line(x, y + i, width, color)

    def draw_circle(self, x0: int, y0: int, radius: int, color: int):
        """Draw a circle using the midpoint circle algorithm."""
        x = radius
        y = 0
        decision_over_2 = 1 - x

        while x >= y:
            self.set_pixel(x0 + x, y0 + y, color)
            self.set_pixel(x0 + y, y0 + x, color)
            self.set_pixel(x0 - y, y0 + x, color)
            self.set_pixel(x0 - x, y0 + y, color)
            self.set_pixel(x0 - x, y0 - y, color)
            self.set_pixel(x0 - y, y0 - x, color)
            self.set_pixel(x0 + y, y0 - x, color)
            self.set_pixel(x0 + x, y0 - y, color)
            y += 1
            if decision_over_2 <= 0:
                decision_over_2 += 2 * y + 1
            else:
                x -= 1
                decision_over_2 += 2 * (y - x) + 1

    def fill_circle(self, x0: int, y0: int, radius: int, color: int):
        """Fill a circle."""
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if x ** 2 + y ** 2 <= radius ** 2:
                    self.set_pixel(x0 + x, y0 + y, color)


class AkaiFire:
    # Rotary Controls
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # Buttons
    BUTTON_STEP = 0x2C
    BUTTON_NOTE = 0x2D
    BUTTON_DRUM = 0x2E
    BUTTON_PERFORM = 0x2F
    BUTTON_SHIFT = 0x30
    BUTTON_ALT = 0x31
    BUTTON_PATTERN = 0x32
    BUTTON_PLAY = 0x33
    BUTTON_STOP = 0x34
    BUTTON_REC = 0x35
    BUTTON_BANK = 0x1A
    BUTTON_BROWSER = 0x21
    BUTTON_SOLO_1 = 0x24
    BUTTON_SOLO_2 = 0x25
    BUTTON_SOLO_3 = 0x26
    BUTTON_SOLO_4 = 0x27
    BUTTON_PAT_UP = 0x1F
    BUTTON_PAT_DOWN = 0x20
    BUTTON_GRID_LEFT = 0x22
    BUTTON_GRID_RIGHT = 0x23

    # LED Values
    LED_OFF = 0x00
    LED_DULL_RED = 0x01
    LED_HIGH_RED = 0x02
    LED_DULL_GREEN = 0x01
    LED_HIGH_GREEN = 0x02
    LED_DULL_YELLOW = 0x01
    LED_HIGH_YELLOW = 0x02

    # Constants for Control Bank LED States
    CONTROL_BANK_OFF = 0x00
    CONTROL_BANK_CHANNEL = 0x01
    CONTROL_BANK_MIXER = 0x02
    CONTROL_BANK_USER1 = 0x03
    CONTROL_BANK_USER2 = 0x04
    CONTROL_BANK_ALL = 0x1F

    def __init__(self, port_name=None):
        self.look_for_port = port_name or "FL STUDIO FIRE"
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.input_port_index, self.output_port_index = self._find_ports()

        if self.output_port_index is None or self.input_port_index is None:
            raise RuntimeError("Akai Fire MIDI ports not found. Ensure it is connected.")

        self.midi_out.open_port(self.output_port_index)
        self.midi_in.open_port(self.input_port_index)

        self.listeners = {}
        self.global_listener = None
        self.rotary_listeners = {}
        self.rotary_touch_listeners = {}
        self.button_listeners = {}
        self.listening_thread = threading.Thread(target=self._listen, daemon=True)
        self.listening = False

    def _find_ports(self):
        """Find the Akai Fire MIDI input and output ports."""
        input_port = None
        output_port = None

        for i, port_name in enumerate(self.midi_in.get_ports()):
            if self.look_for_port in port_name:
                input_port = i
                print(f"Found Akai Fire MIDI INPUT ports: {self.look_for_port}")

        for i, port_name in enumerate(self.midi_out.get_ports()):
            if self.look_for_port in port_name:
                output_port = i
                print(f"Found Akai Fire MIDI OUTPUT ports: {self.look_for_port}")

        return input_port, output_port

    def close(self):
        """Closes the MIDI input and output ports."""
        self.listening = False
        self.listening_thread.join()
        self.midi_in.close_port()
        self.midi_out.close_port()

    @staticmethod
    def _create_sysex_message(pad_colors):
        """
        Constructs a SysEx message to update pads on the Akai Fire.
        :param pad_colors: List of (index, red, green, blue) tuples for the pads to update.
        :return: A SysEx message as a list of bytes.
        """
        sysex_header = [0xF0, 0x47, 0x7F, 0x43, 0x65]

        # Length of payload
        length = len(pad_colors) * 4
        length_high = (length >> 7) & 0x7F
        length_low = length & 0x7F

        # Construct payload for pads
        payload = []
        for index, red, green, blue in pad_colors:
            payload.extend([
                index & 0x3F,
                red & 0x7F,
                green & 0x7F,
                blue & 0x7F,
            ])

        return sysex_header + [length_high, length_low] + payload + [0xF7]

    def set_pad_color(self, index, red, green, blue):
        """Lights up a single pad with the specified RGB color."""
        sysex_message = self._create_sysex_message([(index, red, green, blue)])
        self.midi_out.send_message(sysex_message)

    def set_multiple_pad_colors(self, pad_colors):
        """Lights up multiple pads with specified colors."""
        sysex_message = self._create_sysex_message(pad_colors)
        self.midi_out.send_message(sysex_message)

    def clear_pads(self):
        """Turns off all pads."""
        pad_colors = [(i, 0, 0, 0) for i in range(64)]
        self.set_multiple_pad_colors(pad_colors)

    def reset_pads(self, red=0, green=0, blue=0):
        """Resets all pads to a specific color or turns them off."""
        pad_colors = [(i, red, green, blue) for i in range(64)]
        self.set_multiple_pad_colors(pad_colors)

    def set_button_led(self, button_id, value):
        """
        Sets the LED state for a button.
        :param button_id: One of the BUTTON_LED_* constants.
        :param value: One of the LED_* constants (e.g., LED_OFF, LED_HIGH_RED).
        """
        if button_id not in [
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_PATTERN,
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_BANK,
            self.BUTTON_BROWSER,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ]:
            raise ValueError("Invalid button ID.")
        if not (0x00 <= value <= 0x04):
            raise ValueError("Invalid LED value. Must be between 0x00 and 0x04.")
        self.midi_out.send_message([0xB0, button_id, value])

    def clear_all_button_leds(self):
        """Turns off all button LEDs."""
        for button_id in [
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_PATTERN,
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_BANK,
            self.BUTTON_BROWSER,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ]:
            self.set_button_led(button_id, self.LED_OFF)

    def set_rectangle_led(self, led_number, value):
        """
        Turns on/off or sets the color of a rectangular LED.
        :param led_number: Rectangle LED number (1-4).
        :param value: Brightness or color value:
                      - 0: Off
                      - 1: Dull red
                      - 2: Dull green
                      - 3: High red
                      - 4: High green
        """
        if led_number < 1 or led_number > 4:
            raise ValueError("Rectangle LED number must be between 1 and 4.")

        control_change = 0x28 + (led_number - 1)  # CC 0x28 to 0x2B
        self.midi_out.send_message([0xB0, control_change, value & 0x7F])

    def set_control_bank_leds(self, state):
        """
        Sets the state of the control bank LEDs.
        :param state: One of the CONTROL_BANK_* constants.
        """
        if not (0x00 <= state <= 0x1F):
            raise ValueError("Control bank LED state must be between 0x00 and 0x1F.")
        self.midi_out.send_message([0xB0, 0x1B, state])

    def add_rotary_listener(self, rotary_id, callback):
        """
        Adds a listener for rotary control turn events.
        :param rotary_id: One of the ROTARY_* constants.
        :param callback: Function to call when the rotary control is turned.
                         The callback receives (rotary_id, direction, velocity).
        """
        if rotary_id not in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        ]:
            raise ValueError("Invalid rotary ID.")
        self.rotary_listeners[rotary_id] = callback

        if not self.listening:
            self.listening = True
            self.listening_thread.start()

    def add_rotary_touch_listener(self, rotary_id, callback):
        """
        Adds a listener for rotary control touch events.
        :param rotary_id: One of the ROTARY_* constants.
        :param callback: Function to call when the rotary control is touched or released.
                         The callback receives (rotary_id, event), where `event` is "touch" or "release".
        """
        if rotary_id not in [
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        ]:
            raise ValueError("Invalid rotary ID.")
        self.rotary_touch_listeners[rotary_id] = callback

    def add_button_listener(self, button_id, callback):
        """
        Adds a listener for button press and release events.
        :param button_id: One of the BUTTON_* constants.
        :param callback: Function to call when the button is pressed or released.
                         The callback receives (button_id, event), where `event` is "press" or "release".
        """
        if button_id not in [
            self.BUTTON_STEP,
            self.BUTTON_NOTE,
            self.BUTTON_DRUM,
            self.BUTTON_PERFORM,
            self.BUTTON_SHIFT,
            self.BUTTON_ALT,
            self.BUTTON_PATTERN,
            self.BUTTON_PLAY,
            self.BUTTON_STOP,
            self.BUTTON_REC,
            self.BUTTON_BANK,
            self.BUTTON_BROWSER,
            self.BUTTON_SOLO_1,
            self.BUTTON_SOLO_2,
            self.BUTTON_SOLO_3,
            self.BUTTON_SOLO_4,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ]:
            raise ValueError("Invalid button ID.")
        self.button_listeners[button_id] = callback

        if not self.listening:
            self.listening = True
            self.listening_thread.start()

    def add_listener(self, pad_indices, callback):
        """
        Adds a listener for specific pad presses.
        :param pad_indices: List of pad indices to listen for.
        :param callback: Function to call when a pad in the list is pressed.
        """
        for index in pad_indices:
            self.listeners[index] = callback

        if not self.listening:
            self.listening = True
            self.listening_thread.start()

    def add_global_listener(self, callback):
        """
        Adds a listener for all pad presses.
        :param callback: Function to call when any pad is pressed.
        """
        self.global_listener = callback
        if not self.listening:
            self.listening = True
            self.listening_thread.start()

    @staticmethod
    def get_pad_row(pad_index):
        """
        Determines which row a pad belongs to (1-4).
        :param pad_index: Pad index (0-63).
        :return: Row number (1-4).
        """
        return (pad_index // 16) + 1

    def _listen(self):
        """Internal method to listen for MIDI messages."""
        while self.listening:
            message = self.midi_in.get_message()
            if message:
                data, _ = message
                status = data[0]
                controller = data[1]
                value = data[2]

                # Handle button press/release events
                if status in [0x90, 0x80] and controller in self.button_listeners:
                    event = "press" if status == 0x90 else "release"
                    self.button_listeners[controller](controller, event)

                # Handle rotary touch events
                if status in [0x90, 0x80] and controller in self.rotary_touch_listeners:
                    event = "touch" if status == 0x90 else "release"
                    self.rotary_touch_listeners[controller](controller, event)

                # Handle rotary turn events
                if status == 0xB0 and controller in self.rotary_listeners:
                    # Decode two's complement rotation value
                    direction = "clockwise" if value < 0x40 else "counterclockwise"
                    velocity = value if value < 0x40 else (0x80 - value)
                    self.rotary_listeners[controller](controller, direction, velocity)

                # Check for note_on messages
                if data[0] == 0x90 and data[2] > 0:  # 0x90 = note_on, velocity > 0
                    midi_note = data[1]
                    pad_index = midi_note - 54  # Map MIDI note to pad index

                    if 0 <= pad_index <= 63:
                        # Trigger specific pad listeners
                        if pad_index in self.listeners:
                            self.listeners[pad_index](pad_index)

                        # Trigger global listener
                        if self.global_listener:
                            self.global_listener(pad_index)

    def send_bitmap(self, screen):
        """Send the bitmap to the Akai Fire device."""
        self.midi_out.send_message(screen.get_sysex_message())
        pass
