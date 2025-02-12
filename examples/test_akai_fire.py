import unittest
from unittest.mock import Mock, patch, call
import time
import rtmidi
from PIL import Image, ImageDraw, ImageFont

from akai_fire import AkaiFire
from screen import AkaiFireBitmap
from canvas import Canvas, FireRenderer


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
    @patch('rtmidi.MidiIn')
    @patch('rtmidi.MidiOut')
    def setUp(self, mock_midi_out, mock_midi_in):
        """Set up test case with mocked MIDI ports"""
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()

        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire()

    def tearDown(self):
        """Clean up after each test"""
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
            0xF0, 0x47, 0x7F, 0x43, 0x65,  # Header
            0x00, 0x04,  # Length
            0x00, 127, 0, 0,  # Pad data
            0xF7  # End of SysEx
        ]
        self.assertEqual(self.mock_midi_out.messages[-1], expected_sysex)

        # Test multiple pads
        self.fire.set_multiple_pad_colors([
            (0, 127, 0, 0),
            (1, 0, 127, 0)
        ])
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
        self.fire.add_button_listener(self.fire.BUTTON_PLAY, callback)

        # Simulate button press
        self.fire._process_message(([0x90, self.fire.BUTTON_PLAY, 127], 0))
        callback.assert_called_with(self.fire.BUTTON_PLAY, "press")

        # Simulate button release
        self.fire._process_message(([0x80, self.fire.BUTTON_PLAY, 0], 0))
        callback.assert_called_with(self.fire.BUTTON_PLAY, "release")

    def test_button_callback_threaded(self):
        """Test button callback using the listening thread"""
        callback = Mock()
        self.fire.add_button_listener(self.fire.BUTTON_PLAY, callback)

        # Start listening thread
        self.fire.start_listening()

        try:
            # Simulate button press and wait for processing
            self.mock_midi_in.messages.append([0x90, self.fire.BUTTON_PLAY, 127])
            for _ in range(10):  # Try for up to 100ms
                time.sleep(0.01)
                if callback.call_count > 0:
                    break
            callback.assert_called_with(self.fire.BUTTON_PLAY, "press")
            callback.reset_mock()

            # Simulate button release and wait for processing
            self.mock_midi_in.messages.append([0x80, self.fire.BUTTON_PLAY, 0])
            for _ in range(10):  # Try for up to 100ms
                time.sleep(0.01)
                if callback.call_count > 0:
                    break
            callback.assert_called_with(self.fire.BUTTON_PLAY, "release")
        finally:
            # Clean up
            self.fire.listening = False
            time.sleep(0.01)  # Give thread time to stop

    def test_rotary_callback(self):
        """Test rotary encoder callbacks"""
        callback = Mock()
        self.fire.add_rotary_listener(self.fire.ROTARY_VOLUME, callback)

        # Test clockwise rotation
        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 1], 0))
        callback.assert_called_with(self.fire.ROTARY_VOLUME, "clockwise", 1)

        # Test counter-clockwise rotation
        self.fire._process_message(([0xB0, self.fire.ROTARY_VOLUME, 65], 0))
        callback.assert_called_with(self.fire.ROTARY_VOLUME, "counterclockwise", 63)

    def test_rotary_touch_callback(self):
        """Test rotary touch callbacks"""
        callback = Mock()
        self.fire.add_rotary_touch_listener(self.fire.ROTARY_VOLUME, callback)

        # Test touch
        self.fire._process_message(([0x90, self.fire.ROTARY_VOLUME, 127], 0))
        callback.assert_called_with(self.fire.ROTARY_VOLUME, "touch")

        # Test release
        self.fire._process_message(([0x80, self.fire.ROTARY_VOLUME, 0], 0))
        callback.assert_called_with(self.fire.ROTARY_VOLUME, "release")

    def test_pad_callback(self):
        """Test pad press callbacks"""
        callback = Mock()
        self.fire.add_listener([0], callback)

        # Test pad press
        self.fire._process_message(([0x90, 54, 127], 0))  # MIDI note 54 = pad 0
        callback.assert_called_with(0)

        # Test pad with no callback
        callback.reset_mock()
        self.fire._process_message(([0x90, 55, 127], 0))  # Pad 1
        callback.assert_not_called()

    def test_global_pad_callback(self):
        """Test global pad callback"""
        callback = Mock()
        self.fire.add_global_listener(callback)

        # Test multiple pad presses
        for i in range(3):
            self.fire._process_message(([0x90, 54 + i, 127], 0))
            callback.assert_called_with(i)
            callback.reset_mock()

    def test_clear_functions(self):
        """Test clear functions"""
        # Test clear all pads
        self.fire.clear_all_pads()
        last_message = self.mock_midi_out.messages[-1]
        self.assertEqual(last_message[0], 0xF0)  # SysEx
        self.assertEqual(len(last_message), 264)  # Header(5) + Length(2) + Data(64*4) + End(1)

        # Test clear all button LEDs
        self.fire.clear_all_button_leds()
        # Should have one message per button
        self.assertTrue(len(self.mock_midi_out.messages) >= 20)

        # Test clear all track LEDs
        self.fire.clear_all_track_leds()
        # Should have one message per track
        self.assertTrue(len(self.mock_midi_out.messages) >= 4)


class TestCanvas(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()

    def test_clear(self):
        """Test canvas clear operation"""
        self.canvas.draw_rect(0, 0, 10, 10)  # Draw something
        self.canvas.clear()
        # Check some pixels are white (1)
        self.assertEqual(self.canvas.image.getpixel((0, 0)), 1)
        self.assertEqual(self.canvas.image.getpixel((5, 5)), 1)

    def test_draw_operations(self):
        """Test basic drawing operations"""
        # Test rectangle
        self.canvas.draw_rect(0, 0, 10, 10)
        self.assertEqual(self.canvas.image.getpixel((0, 0)), 0)  # Border should be black (0)

        # Test filled rectangle
        self.canvas.fill_rect(20, 20, 10, 10)
        self.assertEqual(self.canvas.image.getpixel((25, 25)), 0)  # Inside should be black

        # Test text
        self.canvas.draw_text("Test", 40, 40)
        # Text verification would need more sophisticated image analysis


class TestFireRenderer(unittest.TestCase):
    @patch('rtmidi.MidiIn')
    @patch('rtmidi.MidiOut')
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire()
        self.canvas = Canvas()
        self.renderer = FireRenderer(self.fire)

    def test_render(self):
        """Test rendering canvas to Fire display"""
        self.canvas.draw_text("Test", 0, 0)
        self.renderer.render_canvas(self.canvas)

        # Verify SysEx message was sent
        last_message = self.mock_midi_out.messages[-1]
        self.assertEqual(last_message[0], 0xF0)  # SysEx start
        self.assertEqual(last_message[4], 0x0E)  # OLED Write command


if __name__ == '__main__':
    unittest.main()
