import time
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
from collections import defaultdict
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import AkaiFire, get_akai_fire, discover_akai_fire, InvalidParameterError


class MockMidiPort:
    """Mock MIDI port for testing"""

    def __init__(self):
        self.messages = []
        self.is_port_open = False
        self.port_name = None

    def send_message(self, message):
        self.messages.append(message)

    def get_message(self):
        return None if not self.messages else (self.messages.pop(0), 0)

    def open_port(self, port):
        self.is_port_open = True
        self.port_name = port

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
        if hasattr(self, "fire"):
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
        with self.assertRaises(InvalidParameterError):
            self.fire.set_pad_color(-1, 0, 0, 0)  # Invalid pad index
        with self.assertRaises(InvalidParameterError):
            self.fire.set_pad_color(64, 0, 0, 0)  # Invalid pad index
        # Color values are clamped, not rejected
        result = self.fire.set_pad_color(0, 128, 0, 0)  # Should clamp to 127
        self.assertTrue(result)

    def test_button_led(self):
        """Test button LED control"""
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
        expected_message = [0xB0, self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN]
        self.assertEqual(self.mock_midi_out.messages[-1], expected_message)

        # Test invalid button ID
        with self.assertRaises(InvalidParameterError):
            self.fire.set_button_led(0x99, self.fire.LED_HIGH_GREEN)

    def test_track_leds(self):
        """Test track LED control"""
        self.fire.set_track_led(1, self.fire.RECTANGLE_LED_HIGH_GREEN)
        # Should send control change message
        self.assertEqual(len(self.mock_midi_out.messages), 1)
        msg = self.mock_midi_out.messages[-1]
        self.assertEqual(msg[0], 0xB0)  # Control change

    def test_clear_operations(self):
        """Test clear operations"""
        # Set some colors
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)

        # Clear all
        self.fire.clear_all()

        # Should have sent clear messages
        self.assertTrue(len(self.mock_midi_out.messages) > 2)

    def test_batch_operations(self):
        """Test batch pad color updates"""
        colors = [(i, i % 128, 0, 0) for i in range(16)]
        self.fire.set_multiple_pad_colors(colors)

        # Should send one SysEx message
        sysex = self.mock_midi_out.messages[-1]
        self.assertEqual(sysex[0], 0xF0)  # SysEx start
        self.assertEqual(sysex[-1], 0xF7)  # SysEx end

    def test_performance_optimizations(self):
        """Test performance optimization methods"""
        # Test fast path
        self.fire.set_pad_color_fast(0, 127, 0, 0)
        self.assertTrue(len(self.mock_midi_out.messages) > 0)

        # Test set_all_pads
        self.fire.set_all_pads((64, 64, 64))
        sysex = self.mock_midi_out.messages[-1]
        self.assertEqual(sysex[0], 0xF0)  # Should be SysEx


class TestEventSystem(unittest.TestCase):
    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        """Set up test case with mocked MIDI ports"""
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()

        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire()
        self.events_received = []

    def tearDown(self):
        """Clean up after each test"""
        self.fire.close()

    def test_button_decorator(self):
        """Test button event decorator"""

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            self.events_received.append(("play", event))

        # Simulate button press
        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])
        self.assertEqual(len(self.events_received), 1)
        self.assertEqual(self.events_received[0], ("play", "press"))

        # Simulate button release
        self.fire._process_message([[0x80, self.fire.BUTTON_PLAY, 0], 0])
        self.assertEqual(len(self.events_received), 2)
        self.assertEqual(self.events_received[1], ("play", "release"))

    def test_pad_decorator(self):
        """Test pad event decorator"""

        @self.fire.on_pad(0)
        def handle_pad_0(velocity):
            self.events_received.append(("pad_0", velocity))

        # Simulate pad press
        self.fire._process_message([[0x90, 54, 100], 0])  # Pad 0 = note 54
        self.assertEqual(len(self.events_received), 1)
        self.assertEqual(self.events_received[0], ("pad_0", 100))

    def test_global_pad_handler(self):
        """Test global pad handler"""

        @self.fire.on_pad()
        def handle_any_pad(pad_index, velocity):
            self.events_received.append(("any_pad", pad_index, velocity))

        # Simulate pad presses
        self.fire._process_message([[0x90, 54, 100], 0])  # Pad 0
        self.fire._process_message([[0x90, 55, 80], 0])  # Pad 1

        self.assertEqual(len(self.events_received), 2)
        self.assertEqual(self.events_received[0], ("any_pad", 0, 100))
        self.assertEqual(self.events_received[1], ("any_pad", 1, 80))

    def test_rotary_decorator(self):
        """Test rotary event decorator"""

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_volume(direction, velocity):
            self.events_received.append(("volume", direction, velocity))

        # Simulate rotary turn clockwise
        self.fire._process_message([[0xB0, self.fire.ROTARY_VOLUME, 1], 0])
        self.assertEqual(len(self.events_received), 1)
        self.assertEqual(self.events_received[0][0], "volume")
        self.assertEqual(self.events_received[0][1], "clockwise")

    def test_rotary_touch_decorator(self):
        """Test rotary touch event decorator"""

        @self.fire.on_rotary_touch(self.fire.ROTARY_VOLUME)
        def handle_volume_touch(event):
            self.events_received.append(("volume_touch", event))

        # Simulate rotary touch
        self.fire._process_message([[0x90, self.fire.ROTARY_VOLUME, 127], 0])
        self.assertEqual(len(self.events_received), 1)
        self.assertEqual(self.events_received[0], ("volume_touch", "touch"))

    def test_solo_button_decorator(self):
        """Test solo button decorator"""

        @self.fire.on_solo(1)
        def handle_solo_1(event):
            self.events_received.append(("solo_1", event))

        # Simulate solo button press
        self.fire._process_message([[0x90, self.fire.BUTTON_SOLO_1, 127], 0])
        self.assertEqual(len(self.events_received), 1)
        self.assertEqual(self.events_received[0], ("solo_1", "press"))

    def test_multiple_listeners(self):
        """Test multiple listeners for same event"""

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler1(event):
            self.events_received.append(("handler1", event))

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler2(event):
            self.events_received.append(("handler2", event))

        # Both handlers should be called
        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])
        self.assertEqual(len(self.events_received), 2)


class TestThreadSafety(unittest.TestCase):
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
        self.fire.close()

    def test_concurrent_listener_registration(self):
        """Test thread-safe listener registration"""
        results = []
        errors = []

        def register_listeners(thread_id):
            try:
                for i in range(10):

                    @self.fire.on_pad(i)
                    def handler(velocity):
                        results.append((thread_id, i, velocity))

            except Exception as e:
                errors.append(e)

        # Start multiple threads registering listeners
        threads = []
        for i in range(5):
            t = threading.Thread(target=register_listeners, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have no errors
        self.assertEqual(len(errors), 0)

    def test_concurrent_event_processing(self):
        """Test thread-safe event processing"""
        counter = {"value": 0}
        lock = threading.Lock()

        @self.fire.on_pad()
        def count_pads(pad_index, velocity):
            with lock:
                counter["value"] += 1

        # Simulate rapid events from multiple threads
        def send_events():
            for i in range(10):
                self.fire._process_message([[0x90, 54 + i, 100], 0])

        threads = []
        for _ in range(3):
            t = threading.Thread(target=send_events)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All events should be processed
        self.assertEqual(counter["value"], 30)  # 3 threads * 10 events

    def test_listener_modification_during_event(self):
        """Test modifying listeners while processing events"""
        self.processed = []

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handler1(event):
            self.processed.append("handler1")

            # Add another listener during event processing
            @self.fire.on_button(self.fire.BUTTON_PLAY)
            def handler2(event):
                self.processed.append("handler2")

        # Process event
        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])

        # Only handler1 should have been called
        self.assertEqual(self.processed, ["handler1"])

        # Process another event
        self.processed.clear()
        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])

        # Now both handlers should be called
        self.assertEqual(sorted(self.processed), ["handler1", "handler2"])


class TestUtilityFunctions(unittest.TestCase):
    def test_discover_akai_fire(self):
        """Test device discovery"""
        with patch("rtmidi.MidiIn") as mock_midi_in:
            mock_port = Mock()
            mock_port.get_ports.return_value = ["FL STUDIO FIRE", "Other Device"]
            mock_midi_in.return_value = mock_port

            port = discover_akai_fire()
            self.assertEqual(port, "FL STUDIO FIRE")

    def test_discover_no_device(self):
        """Test discovery when no device found"""
        with patch("rtmidi.MidiIn") as mock_midi_in:
            mock_port = Mock()
            mock_port.get_ports.return_value = ["Other Device"]
            mock_midi_in.return_value = mock_port

            port = discover_akai_fire()
            self.assertIsNone(port)

    @patch("akai_fire.discover_akai_fire")
    def test_get_akai_fire_auto(self, mock_discover):
        """Test get_akai_fire auto detection"""
        # Test when hardware is found
        mock_discover.return_value = "FL STUDIO FIRE"

        # Mock MIDI to simulate hardware presence
        with patch("rtmidi.MidiIn") as mock_in, patch("rtmidi.MidiOut") as mock_out:
            # Configure mocks to simulate finding AKAI Fire
            mock_in_instance = Mock()
            mock_out_instance = Mock()
            mock_in.return_value = mock_in_instance
            mock_out.return_value = mock_out_instance

            mock_in_instance.get_ports.return_value = ["FL STUDIO FIRE"]
            mock_out_instance.get_ports.return_value = ["FL STUDIO FIRE"]
            mock_in_instance.open_port = Mock()
            mock_out_instance.open_port = Mock()
            mock_out_instance.send_message = Mock()

            device = get_akai_fire()
            self.assertIsInstance(device, AkaiFire)

    @patch("akai_fire.discover_akai_fire")
    def test_get_akai_fire_fallback_to_mock(self, mock_discover):
        """Test get_akai_fire falls back to mock"""
        # Test when hardware is not found
        mock_discover.return_value = None
        device = get_akai_fire()
        # Should return mock (if available) or raise exception
        self.assertIsNotNone(device)


class TestHelperMethods(unittest.TestCase):
    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        """Set up test case with mocked MIDI ports"""
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()

        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire()

    def test_is_shift_pressed(self):
        """Test shift state detection"""
        # Initially should be False
        self.assertFalse(self.fire.is_shift_pressed())

        # Simulate shift press
        self.fire._process_message([[0x90, self.fire.BUTTON_SHIFT, 127], 0])
        self.assertTrue(self.fire.is_shift_pressed())

        # Simulate shift release
        self.fire._process_message([[0x80, self.fire.BUTTON_SHIFT, 0], 0])
        self.assertFalse(self.fire.is_shift_pressed())

    def test_is_alt_pressed(self):
        """Test alt state detection"""
        self.assertFalse(self.fire.is_alt_pressed())

        self.fire._process_message([[0x90, self.fire.BUTTON_ALT, 127], 0])
        self.assertTrue(self.fire.is_alt_pressed())

    def test_get_solo_index(self):
        """Test solo button index mapping"""
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_1), 1)
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_2), 2)
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_3), 3)
        self.assertEqual(self.fire.get_solo_index(self.fire.BUTTON_SOLO_4), 4)
        self.assertIsNone(self.fire.get_solo_index(0x99))  # Invalid button

    def test_list_midi_ports(self):
        """Test MIDI port listing"""
        ports = AkaiFire.list_midi_ports()
        self.assertIn("input", ports)
        self.assertIn("output", ports)
        self.assertIsInstance(ports["input"], list)
        self.assertIsInstance(ports["output"], list)


class TestHandlerIsolation(unittest.TestCase):
    """A throwing handler must not prevent subsequent handlers from running."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire()

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_raising_pad_handler_does_not_block_others(self):
        calls = []

        @self.fire.on_pad()
        def bad(pad_index, velocity):
            calls.append("bad")
            raise RuntimeError("boom")

        @self.fire.on_pad()
        def good(pad_index, velocity):
            calls.append("good")

        with self.assertLogs("akai_fire", level="ERROR"):
            self.fire._process_message([[0x90, 54, 100], 0])

        self.assertIn("good", calls)
        self.assertEqual(calls.count("bad"), 1)

    def test_raising_button_handler_does_not_block_global(self):
        calls = []

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def specific(event):
            calls.append(("specific", event))
            raise RuntimeError("boom")

        @self.fire.on_button()
        def global_handler(button_id, event):
            calls.append(("global", button_id, event))

        with self.assertLogs("akai_fire", level="ERROR"):
            self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])

        # Global handler ran despite specific throwing
        self.assertTrue(any(c[0] == "global" for c in calls))
        self.assertTrue(any(c[0] == "specific" for c in calls))

    def test_raising_rotary_handler_does_not_block_others(self):
        calls = []

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def bad(direction, velocity):
            calls.append("bad")
            raise RuntimeError("boom")

        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def good(direction, velocity):
            calls.append("good")

        with self.assertLogs("akai_fire", level="ERROR"):
            self.fire._process_message([[0xB0, self.fire.ROTARY_VOLUME, 0x01], 0])

        self.assertIn("good", calls)
        self.assertIn("bad", calls)


class TestMessageParsing(unittest.TestCase):
    """Malformed MIDI messages must be logged, not silently printed to stderr."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire()

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_none_message_is_ignored_silently(self):
        # No raise, no log noise for well-formed "empty" input
        self.fire._process_message(None)
        self.fire._process_message([])

    def test_short_data_is_ignored_silently(self):
        # Covered by early-return (len(data) < 3) before the narrow try scope
        self.fire._process_message([[0x90], 0])

    def test_wrong_inner_type_is_ignored(self):
        # Inner is not a list/tuple — early return, no log
        self.fire._process_message(["not-a-list", 0])

    def test_unpacking_error_is_logged_and_swallowed(self):
        # A message shape that passes isinstance checks but fails unpacking
        # triggers the narrow (ValueError/IndexError/TypeError) branch.
        class TrickyList(list):
            def __iter__(self):
                raise TypeError("synthetic unpack failure")

        msg = TrickyList([[0x90, 54, 100], 0])
        # isinstance(msg, (list, tuple)) is True; data, _ = msg raises TypeError
        with self.assertLogs("akai_fire", level="WARNING"):
            self.fire._process_message(msg)


if __name__ == "__main__":
    unittest.main()
