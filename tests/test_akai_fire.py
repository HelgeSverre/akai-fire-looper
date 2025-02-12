import time
import unittest
from unittest.mock import Mock, patch

from akai_fire import AkaiFire


class MockMidiPort:
    """Mock MIDI port for testing"""

    def __init__(self):
        self.messages = []
        self.is_port_open = False

    def send_message(self, message):
        self.messages.append(message)

    def get_message(self):
        return None if not self.messages else (self.messages.pop(0), 0)

    def open_port(self, port):
        self.is_port_open = True

    def close_port(self):
        self.is_port_open = False

    def get_ports(self):
        return ["FL STUDIO FIRE", "Other MIDI Device"]

    def is_port_open(self):
        return self.is_port_open


class TestAkaiFire(unittest.TestCase):
    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        """Set up test case with mocked MIDI ports"""
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()

        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire()

    def tearDown(self):
        """Clean up after each test"""
        self.fire.clear_all()
        self.fire.close()

    def test_initialization(self):
        """Test device initialization"""
        self.assertTrue(self.mock_midi_in.is_port_open)
        self.assertTrue(self.mock_midi_out.is_port_open)

    def test_pad_colors(self):
        """Test setting pad colors"""
        # Test single pad
        self.fire.set_pad_color(0, 127, 0, 0)  # Red
        expected_sysex = [
            0xF0,
            0x47,
            0x7F,
            0x43,
            0x65,  # Header
            0x00,
            0x04,  # Length
            0x00,
            127,
            0,
            0,  # Pad data
            0xF7,  # End of SysEx
        ]
        self.assertEqual(self.mock_midi_out.messages[-1], expected_sysex)

        # Test multiple pads
        self.fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
        sysex = self.mock_midi_out.messages[-1]
        self.assertEqual(len(sysex), 16)  # Header(5) + Length(2) + Data(2*4) + End(1)

    def test_pad_color_validation(self):
        """Test pad color value validation"""
        with self.assertRaises(ValueError):
            self.fire.set_pad_color(-1, 0, 0, 0)  # Invalid pad index
        with self.assertRaises(ValueError):
            self.fire.set_pad_color(64, 0, 0, 0)  # Invalid pad index
        with self.assertRaises(ValueError):
            self.fire.set_pad_color(0, 128, 0, 0)  # Invalid color value

    def test_button_led(self):
        """Test button LED control"""
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
        expected_message = [0xB0, self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN]
        self.assertEqual(self.mock_midi_out.messages[-1], expected_message)

        # Test invalid button ID
        with self.assertRaises(ValueError):
            self.fire.set_button_led(0x99, self.fire.LED_HIGH_GREEN)

        # Test invalid LED value
        with self.assertRaises(ValueError):
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 0xFF)

    def test_track_led(self):
        """Test track LED control"""
        self.fire.set_track_led(1, self.fire.RECTANGLE_LED_HIGH_RED)
        expected_message = [0xB0, 0x28, self.fire.RECTANGLE_LED_HIGH_RED]
        self.assertEqual(self.mock_midi_out.messages[-1], expected_message)

        # Test invalid track number
        with self.assertRaises(ValueError):
            self.fire.set_track_led(0, self.fire.RECTANGLE_LED_HIGH_RED)
        with self.assertRaises(ValueError):
            self.fire.set_track_led(5, self.fire.RECTANGLE_LED_HIGH_RED)

    def test_button_callback_direct(self):
        """Test button callback by directly calling process_message"""
        callback = Mock()
        print("Setting up button handler...")

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler(event):
            print(f"Handler called with event: {event}")  # Debug print
            callback(event)

        print(
            f"Button listeners after setup: {self.fire.button_listeners}"
        )  # Debug print

        # Simulate button press
        message = ([0x90, self.fire.BUTTON_PLAY, 127], 0)
        print(f"Sending message: {message}")  # Debug print
        self.fire._process_message(message)

        callback.assert_called_once_with("press")

    def test_button_callback_threaded(self):
        """Test button callback using the listening thread"""
        callback = Mock()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler(event):
            callback(event)

        self.fire.start_listening()

        try:
            # Simulate button press and wait for processing
            self.mock_midi_in.messages.append([0x90, self.fire.BUTTON_PLAY, 127])
            for _ in range(10):  # Try for up to 100ms
                time.sleep(0.01)
                if callback.call_count > 0:
                    break
            callback.assert_called_once_with("press")

            # Simulate button release
            callback.reset_mock()
            self.mock_midi_in.messages.append([0x80, self.fire.BUTTON_PLAY, 0])
            for _ in range(10):
                time.sleep(0.01)
                if callback.call_count > 0:
                    break
            callback.assert_called_once_with("release")
        finally:
            self.fire.listening = False
            time.sleep(0.01)

    def test_pad_callback(self):
        """Test pad press callbacks"""
        callback = Mock()

        @self.fire.on_pad(0)
        def handler(velocity):
            callback(velocity)

        # Test pad press
        self.fire._process_message(([0x90, 54, 127], 0))  # MIDI note 54 = pad 0
        callback.assert_called_once_with(127)

    def test_rotary_callback(self):
        """Test rotary encoder callbacks"""
        callback = Mock()

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handler(direction, velocity):
            callback(direction, velocity)

        # Test clockwise rotation
        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 1], 0))
        callback.assert_called_once_with("clockwise", 1)

    def test_rotary_touch_callback(self):
        """Test rotary touch callbacks"""
        callback = Mock()

        @self.fire.on_rotary_touch(self.fire.ROTARY_VOLUME)
        def handler(event):
            callback(event)

        # Test touch
        self.fire._process_message(([0x90, self.fire.ROTARY_VOLUME, 127], 0))
        callback.assert_called_once_with("touch")

    def test_concurrent_pad_presses(self):
        """Test handling multiple simultaneous pad presses"""
        callback = Mock()

        @self.fire.on_pad([0, 1, 2])
        def handler(velocity):
            callback(velocity)

        # Simulate multiple pad presses
        messages = [
            ([0x90, 54, 127], 0),  # Pad 0
            ([0x90, 55, 127], 0),  # Pad 1
            ([0x90, 56, 127], 0),  # Pad 2
        ]

        for msg in messages:
            self.fire._process_message(msg)

        self.assertEqual(callback.call_count, 3)

    def test_global_pad_callback(self):
        """Test global pad callback"""
        callback = Mock()

        @self.fire.on_pad()
        def handler(pad_index, velocity):
            callback(pad_index, velocity)

        # Test multiple pad presses
        for i in range(3):
            self.fire._process_message(([0x90, 54 + i, 127], 0))
            callback.assert_called_with(i, 127)
            callback.reset_mock()

    def test_rotary_velocity(self):
        """Test different rotary velocities"""
        callback = Mock()

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handler(direction, velocity):
            callback(direction, velocity)

        # Test slow turn
        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 1], 0))
        callback.assert_called_with("clockwise", 1)

    def test_simultaneous_callbacks(self):
        """Test multiple types of callbacks simultaneously"""
        button_callback = Mock()
        rotary_callback = Mock()
        pad_callback = Mock()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def button_handler(event):
            button_callback(event)

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def rotary_handler(direction, velocity):
            rotary_callback(direction, velocity)

        @self.fire.on_pad(0)
        def pad_handler(velocity):
            pad_callback(velocity)

        messages = [
            ([0x90, self.fire.BUTTON_PLAY, 127], 0),  # Button press
            ([0xB0, self.fire.ROTARY_VOLUME, 1], 0),  # Rotary turn
            ([0x90, 54, 127], 0),  # Pad press
        ]

        for msg in messages:
            self.fire._process_message(msg)

        button_callback.assert_called_once_with("press")
        rotary_callback.assert_called_once_with("clockwise", 1)
        pad_callback.assert_called_once_with(127)

    def test_multiple_handlers_same_button(self):
        """Test multiple handlers for same button work independently"""
        callback1 = Mock()
        callback2 = Mock()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler1(event):
            callback1(event)

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler2(event):
            callback2(event)

        self.fire._process_message(([0x90, self.fire.BUTTON_PLAY, 127], 0))
        callback1.assert_called_once_with("press")
        callback2.assert_called_once_with("press")

    def test_multiple_handlers_same_pad(self):
        """Test multiple handlers for same pad work independently"""
        callback1 = Mock()
        callback2 = Mock()

        @self.fire.on_pad(0)
        def handler1(velocity):
            callback1(velocity)

        @self.fire.on_pad(0)
        def handler2(velocity):
            callback2(velocity)

        self.fire._process_message(([0x90, 54, 127], 0))  # Pad 0
        callback1.assert_called_once_with(127)
        callback2.assert_called_once_with(127)

    def test_multiple_handlers_same_rotary(self):
        """Test multiple handlers for same rotary work independently"""
        callback1 = Mock()
        callback2 = Mock()

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handler1(direction, velocity):
            callback1(direction, velocity)

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handler2(direction, velocity):
            callback2(direction, velocity)

        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 1], 0))
        callback1.assert_called_once_with("clockwise", 1)
        callback2.assert_called_once_with("clockwise", 1)

    def test_mixed_global_and_specific_handlers(self):
        """Test combination of global and specific handlers"""
        global_button = Mock()
        specific_button = Mock()
        global_pad = Mock()
        specific_pad = Mock()
        global_rotary = Mock()
        specific_rotary = Mock()

        @self.fire.on_button()
        def global_button_handler(button_id, event):
            global_button(button_id, event)

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def specific_button_handler(event):
            specific_button(event)

        @self.fire.on_pad()
        def global_pad_handler(pad_index, velocity):
            global_pad(pad_index, velocity)

        @self.fire.on_pad(0)
        def specific_pad_handler(velocity):
            specific_pad(velocity)

        @self.fire.on_rotary_turn()
        def global_rotary_handler(rotary_id, direction, velocity):
            global_rotary(rotary_id, direction, velocity)

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def specific_rotary_handler(direction, velocity):
            specific_rotary(direction, velocity)

        # Test button handlers
        self.fire._process_message(([0x90, self.fire.BUTTON_PLAY, 127], 0))
        global_button.assert_called_once_with(self.fire.BUTTON_PLAY, "press")
        specific_button.assert_called_once_with("press")

        # Test pad handlers
        self.fire._process_message(([0x90, 54, 127], 0))  # Pad 0
        global_pad.assert_called_once_with(0, 127)
        specific_pad.assert_called_once_with(127)

        # Test rotary handlers
        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 1], 0))
        global_rotary.assert_called_once_with(self.fire.ROTARY_VOLUME, "clockwise", 1)
        specific_rotary.assert_called_once_with("clockwise", 1)

    def test_button_listener_registration(self):
        """Test that button listeners are properly registered"""
        callback = Mock()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler(event):
            callback(event)

        # Verify registration
        self.assertIn(self.fire.BUTTON_PLAY, self.fire.button_listeners)
        self.assertEqual(len(self.fire.button_listeners[self.fire.BUTTON_PLAY]), 1)

        # Test the handler directly
        handler("press")
        callback.assert_called_once_with("press")

    def test_handler_error_propagation(self):
        """Test that error in one handler doesn't affect others"""
        good_callback = Mock()
        error_callback = Mock(side_effect=Exception("Test error"))

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def good_handler(event):
            good_callback(event)

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def error_handler(event):
            error_callback(event)

        # Should not raise exception and should still call good handler
        self.fire._process_message(([0x90, self.fire.BUTTON_PLAY, 127], 0))
        good_callback.assert_called_once_with("press")

    def test_multiple_pad_ranges(self):
        """Test handlers for different pad ranges"""
        row1_callback = Mock()
        row2_callback = Mock()
        specific_pads_callback = Mock()

        # Handler for first row (pads 0-15)
        first_row = list(range(16))

        @self.fire.on_pad(first_row)
        def handle_row1(velocity):
            row1_callback(velocity)

        # Handler for second row (pads 16-31)
        second_row = list(range(16, 32))

        @self.fire.on_pad(second_row)
        def handle_row2(velocity):
            row2_callback(velocity)

        # Handler for specific pads across rows
        specific_pads = [0, 16, 32, 48]  # First pad of each row

        @self.fire.on_pad(specific_pads)
        def handle_specific(velocity):
            specific_pads_callback(velocity)

        # Test pad in first row
        self.fire._process_message(([0x90, 54, 127], 0))  # Pad 0
        row1_callback.assert_called_once_with(127)
        specific_pads_callback.assert_called_once_with(127)
        row2_callback.assert_not_called()

    def test_rotary_touch_multiple_handlers(self):
        """Test multiple handlers for rotary touch events"""
        specific_callback = Mock()
        global_callback = Mock()

        @self.fire.on_rotary_touch(self.fire.ROTARY_VOLUME)
        def handle_volume_touch(event):
            specific_callback(event)

        @self.fire.on_rotary_touch()
        def handle_any_touch(rotary_id, event):
            global_callback(rotary_id, event)

        # Test touch event
        self.fire._process_message(([0x90, self.fire.ROTARY_VOLUME, 127], 0))
        specific_callback.assert_called_once_with("touch")
        global_callback.assert_called_once_with(self.fire.ROTARY_VOLUME, "touch")

    def test_rotary_touch_vs_button(self):
        """Test that rotary touch events don't trigger button handlers and vice versa"""
        rotary_callback = Mock()
        button_callback = Mock()

        @self.fire.on_rotary_touch(self.fire.ROTARY_VOLUME)
        def handle_rotary(event):
            rotary_callback(event)

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_button(event):
            button_callback(event)

        # Test rotary touch
        self.fire._process_message(([0x90, self.fire.ROTARY_VOLUME, 127], 0))
        rotary_callback.assert_called_once_with("touch")
        button_callback.assert_not_called()

        # Reset mocks
        rotary_callback.reset_mock()
        button_callback.reset_mock()

        # Test button press
        self.fire._process_message(([0x90, self.fire.BUTTON_PLAY, 127], 0))
        button_callback.assert_called_once_with("press")
        rotary_callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
