import threading
import time
import rtmidi
from screen import AkaiFireBitmap


class AkaiFire:
    # Rotary Controls
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # Buttons
    BUTTON_SELECT = 0x19
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

    # Rectangle LED Values
    RECTANGLE_LED_OFF = 0x00
    RECTANGLE_LED_DULL_RED = 0x01
    RECTANGLE_LED_DULL_GREEN = 0x02
    RECTANGLE_LED_HIGH_RED = 0x03
    RECTANGLE_LED_HIGH_GREEN = 0x04

    # todo    temporary
    FIELD_BASE = 0x10  # Base flag, must be set for valid combinations
    FIELD_CHANNEL = 0x01
    FIELD_MIXER = 0x02
    FIELD_USER1 = 0x04
    FIELD_USER2 = 0x08

    # Constants for Control Bank LED States
    CONTROL_BANK_ALL_OFF = 0x10
    CONTROL_BANK_ALL_ON = 0x1F
    CONTROL_BANK_CHANNEL = 0x11
    CONTROL_BANK_CHANNEL_AND_MIXER = 0x13
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1 = 0x17
    CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2 = 0x1B
    CONTROL_BANK_CHANNEL_AND_USER1 = 0x15
    CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2 = 0x1D
    CONTROL_BANK_CHANNEL_AND_USER2 = 0x19
    CONTROL_BANK_MIXER = 0x12
    CONTROL_BANK_MIXER_AND_USER1_AND_USER2 = 0x1E
    CONTROL_BANK_MIXER_AND_USER2 = 0x1A
    CONTROL_BANK_USER1 = 0x14
    CONTROL_BANK_USER1_AND_USER2 = 0x1C
    CONTROL_BANK_USER2 = 0x03

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __init__(self, port_name=None):
        self.look_for_port = port_name or "FL STUDIO FIRE"
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.input_port_index, self.output_port_index = self._find_ports()

        if self.output_port_index is None or self.input_port_index is None:
            raise RuntimeError(
                "Akai Fire MIDI ports not found. Ensure it is connected."
            )

        self.midi_out.open_port(self.output_port_index)
        self.midi_in.open_port(self.input_port_index)

        self.listeners = {}
        self.global_listener = None
        self.rotary_listeners = {}
        self.rotary_touch_listeners = {}
        self.button_listeners = {}

        self.listening = False
        self.listening_thread = None

    def start_listening(self):
        """Start the listening thread."""
        if not self.listening:
            self.listening = True
            self.listening_thread = threading.Thread(target=self._listen, daemon=True)
            self.listening_thread.start()

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
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join()

        self.midi_in.close_port()
        self.midi_out.close_port()

    def send_bitmap(self, screen):
        """Send the bitmap to the Akai Fire device."""
        self.midi_out.send_message(screen.get_sysex_message())
        pass

    def clear_bitmap(self):
        """Clear the OLED display."""
        self.send_bitmap(AkaiFireBitmap())
        pass

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
            payload.extend(
                [
                    index & 0x3F,
                    red & 0x7F,
                    green & 0x7F,
                    blue & 0x7F,
                ]
            )

        return sysex_header + [length_high, length_low] + payload + [0xF7]

    def set_pad_color(self, index, red, green, blue):
        """Lights up a single pad with the specified RGB color."""
        if not (0 <= index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        if not all(0 <= c <= 127 for c in (red, green, blue)):
            raise ValueError("Color values must be between 0 and 127")

        sysex_message = self._create_sysex_message([(index, red, green, blue)])
        self.midi_out.send_message(sysex_message)

    def set_multiple_pad_colors(self, pad_colors):
        """Lights up multiple pads with specified colors."""
        sysex_message = self._create_sysex_message(pad_colors)
        self.midi_out.send_message(sysex_message)

    def clear_all_pads(self):
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

    def clear_all_track_leds(self):
        """Turns off all rectangular track LEDs."""
        for led_number in range(1, 4):
            self.clear_track_led(led_number)

    def clear_track_led(self, led_number):
        """
        Turns off a rectangular LED.
        :param led_number: Rectangle LED number (1-4).
        """
        self.set_track_led(led_number, self.RECTANGLE_LED_OFF)

    def set_track_led(self, track_number, value):
        """
        todo: cleanup naming
        Turns on/off or sets the color of a rectangular LED. (The narrow LED between the solo buttons and the pads, one for each track lane 1-4)
        :param track_number: Rectangle LED number (1-4).
        :param value: Brightness or color value:
                      - 0: Off
                      - 1: Dull red
                      - 2: Dull green
                      - 3: High red
                      - 4: High green
        """
        if track_number < 1 or track_number > 4:
            raise ValueError("Rectangle LED number must be between 1 and 4.")

        control_change = 0x28 + (track_number - 1)  # CC 0x28 to 0x2B
        self.midi_out.send_message([0xB0, control_change, value & 0x7F])

    def clear_control_bank_leds(self):
        """Turns off all control bank LEDs."""
        self.set_control_bank_leds(self.CONTROL_BANK_ALL_OFF)

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

        self.start_listening()

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
            self.BUTTON_SELECT,
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

        self.start_listening()

    def add_listener(self, pad_indices, callback):
        """
        Adds a listener for specific pad presses.
        :param pad_indices: List of pad indices to listen for.
        :param callback: Function to call when a pad in the list is pressed.
        """
        for index in pad_indices:
            self.listeners[index] = callback

        self.start_listening()

    def add_global_listener(self, callback):
        """
        Adds a listener for all pad presses.
        :param callback: Function to call when any pad is pressed.
        """
        self.global_listener = callback
        self.start_listening()

    @staticmethod
    def get_pad_row(pad_index):
        """
        Determines which row a pad belongs to (1-4).
        :param pad_index: Pad index (0-63).
        :return: Row number (1-4).
        """
        return (pad_index // 16) + 1

    def _process_message(self, message):
        """Process a single MIDI message."""
        try:
            if not message or not isinstance(message[0], (list, tuple)):
                return

            data, _ = message
            if len(data) < 3:  # Just need minimum length for status/controller/value
                return

            status = data[0]
            controller = data[1]
            value = data[2]

            # Handle everything else exactly as before, no extra validation
            if status in [0x90, 0x80] and controller in self.button_listeners:
                event = "press" if status == 0x90 else "release"
                self.button_listeners[controller](controller, event)

            if status in [0x90, 0x80] and controller in self.rotary_touch_listeners:
                event = "touch" if status == 0x90 else "release"
                self.rotary_touch_listeners[controller](controller, event)

            if status == 0xB0 and controller in self.rotary_listeners:
                direction = "clockwise" if value < 0x40 else "counterclockwise"
                velocity = value if value < 0x40 else (0x80 - value)
                self.rotary_listeners[controller](controller, direction, velocity)

            if status == 0x90 and value > 0:
                pad_index = controller - 54
                if 0 <= pad_index <= 63:
                    if pad_index in self.listeners:
                        self.listeners[pad_index](pad_index)
                    if self.global_listener:
                        self.global_listener(pad_index)

        except Exception:
            # Just silently continue if anything goes wrong
            pass

    def _listen(self):
        """Internal method to listen for MIDI messages."""
        while self.listening:
            message = self.midi_in.get_message()
            if message:
                self._process_message(message)
            time.sleep(0.001)  # 1ms loop interval
