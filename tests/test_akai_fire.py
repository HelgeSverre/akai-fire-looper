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

        self.fire = AkaiFire(async_handlers=False)

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

    def test_set_pad_color_sends_after_cycle(self):
        # Regression: historical set-like cache used to return True for the
        # third call because "0:127:0:0" was still present, leaving the pad
        # green on hardware.
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.set_pad_color(0, 0, 127, 0)
        self.fire.set_pad_color(0, 127, 0, 0)
        self.assertEqual(len(self.mock_midi_out.messages), 3)

    def test_set_pad_color_same_color_short_circuits(self):
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.set_pad_color(0, 127, 0, 0)
        self.assertEqual(len(self.mock_midi_out.messages), 1)

    def test_clear_all_pads_invalidates_cache(self):
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.clear_all_pads()
        self.fire.set_pad_color(0, 127, 0, 0)
        # color + clear + color must all hit the wire
        self.assertEqual(len(self.mock_midi_out.messages), 3)

    def test_set_all_pads_invalidates_cache(self):
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.set_all_pads((0, 127, 0))  # cached-message path
        # After all pads are green, setting pad 0 red must send.
        self.fire.set_pad_color(0, 127, 0, 0)
        # Setting pad 0 green again should short-circuit.
        self.fire.set_pad_color(0, 0, 127, 0)
        self.fire.set_pad_color(0, 0, 127, 0)
        # initial red + set_all_pads + pad0 red + pad0 green = 4
        self.assertEqual(len(self.mock_midi_out.messages), 4)

    def test_multi_pad_and_single_pad_cache_coherent(self):
        self.fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
        # Same color should short-circuit via single-pad path.
        self.fire.set_pad_color(0, 127, 0, 0)
        self.fire.set_pad_color(1, 0, 127, 0)
        self.assertEqual(len(self.mock_midi_out.messages), 1)

    def test_fast_path_updates_cache(self):
        self.fire.set_pad_color_fast(0, 127, 0, 0)
        # Slow path after fast path must short-circuit for the same color.
        self.fire.set_pad_color(0, 127, 0, 0)
        self.assertEqual(len(self.mock_midi_out.messages), 1)


class TestEventSystem(unittest.TestCase):
    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        """Set up test case with mocked MIDI ports"""
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()

        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

        self.fire = AkaiFire(async_handlers=False)
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

        self.fire = AkaiFire(async_handlers=False)

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

        self.fire = AkaiFire(async_handlers=False)

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
        self.fire = AkaiFire(async_handlers=False)

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


class TestModifierOrdering(unittest.TestCase):
    """Modifier state must be coherent before handlers observe it.

    After a SHIFT press, a pad handler reading is_shift_pressed() must
    see True. This invariant is what future async handler dispatch
    relies on — modifier-key state is now updated inline in
    _process_message before any handler fires.
    """

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire(async_handlers=False)

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_pad_handler_sees_shift_pressed(self):
        observed = []

        @self.fire.on_pad()
        def pad_handler(pad_index, velocity):
            observed.append(self.fire.is_shift_pressed())

        self.fire._process_message([[0x90, self.fire.BUTTON_SHIFT, 127], 0])
        self.fire._process_message([[0x90, 54, 100], 0])
        self.fire._process_message([[0x80, self.fire.BUTTON_SHIFT, 0], 0])
        self.fire._process_message([[0x90, 54, 100], 0])

        self.assertEqual(observed, [True, False])

    def test_pad_handler_sees_alt_pressed(self):
        observed = []

        @self.fire.on_pad()
        def pad_handler(pad_index, velocity):
            observed.append(self.fire.is_alt_pressed())

        self.fire._process_message([[0x90, self.fire.BUTTON_ALT, 127], 0])
        self.fire._process_message([[0x90, 54, 100], 0])
        self.fire._process_message([[0x80, self.fire.BUTTON_ALT, 0], 0])
        self.fire._process_message([[0x90, 54, 100], 0])

        self.assertEqual(observed, [True, False])

    def test_shift_button_listener_sees_latched_state(self):
        # A handler registered for the SHIFT button itself should see
        # the already-latched state when called on "press".
        observed = []

        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def shift_handler(event):
            observed.append((event, self.fire.is_shift_pressed()))

        self.fire._process_message([[0x90, self.fire.BUTTON_SHIFT, 127], 0])
        self.fire._process_message([[0x80, self.fire.BUTTON_SHIFT, 0], 0])

        self.assertEqual(observed, [("press", True), ("release", False)])


class TestMessageParsing(unittest.TestCase):
    """Malformed MIDI messages must be logged, not silently printed to stderr."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire(async_handlers=False)

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


class TestAsyncDispatch(unittest.TestCase):
    """Async handler dispatch must isolate slow handlers and absorb overload."""

    def setUp(self):
        # @patch on setUp only covers setUp itself; these tests construct
        # AkaiFire inside the test methods, so the patches must live for
        # the whole method via start()/stop().
        self._in_patcher = patch("rtmidi.MidiIn")
        self._out_patcher = patch("rtmidi.MidiOut")
        mock_midi_in = self._in_patcher.start()
        mock_midi_out = self._out_patcher.start()
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

    def tearDown(self):
        self._in_patcher.stop()
        self._out_patcher.stop()

    def _wait_until(self, predicate, timeout=2.0, interval=0.005):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(interval)
        return False

    def test_slow_handler_does_not_block_polling(self):
        """A slow handler must not stall dispatch of subsequent events."""
        fire = AkaiFire(async_handlers=True, max_workers=4)
        try:
            slow_finished = threading.Event()
            fast_count = [0]

            @fire.on_pad(0)
            def slow(velocity):
                time.sleep(0.15)
                slow_finished.set()

            @fire.on_pad(1)
            def fast(velocity):
                fast_count[0] += 1

            start = time.time()
            # Queue a slow event, then a fast event
            fire._process_message([[0x90, 54, 100], 0])  # pad 0 -> slow
            fire._process_message([[0x90, 55, 100], 0])  # pad 1 -> fast
            dispatch_time = time.time() - start

            # Dispatch submission must return quickly (<50ms), not wait on slow
            self.assertLess(dispatch_time, 0.05)

            # Fast handler should complete well before slow finishes
            self.assertTrue(self._wait_until(lambda: fast_count[0] == 1, timeout=0.1))

            # Slow handler eventually completes
            self.assertTrue(slow_finished.wait(timeout=1.0))
        finally:
            fire.close()

    def test_caller_runs_when_queue_saturated(self):
        """Caller-runs backpressure: oversubscribed events still execute."""
        fire = AkaiFire(async_handlers=True, max_workers=1, handler_queue_size=2)
        try:
            counts = [0]
            block = threading.Event()

            @fire.on_pad()
            def handler(pad_index, velocity):
                # First few events will block workers
                if pad_index < 3:
                    block.wait(timeout=2.0)
                counts[0] += 1

            # Saturate the queue. Sized 2 + 1 worker = 3 in-flight, then
            # caller-runs kicks in for subsequent events.
            with self.assertLogs("akai_fire", level="WARNING"):
                for i in range(6):
                    fire._process_message([[0x90, 54 + i, 100], 0])

            block.set()
            # All 6 events must eventually be counted (nothing dropped).
            self.assertTrue(self._wait_until(lambda: counts[0] == 6, timeout=3.0))
        finally:
            fire.close()

    def test_async_handlers_false_stays_serial(self):
        """With async_handlers=False, handlers run inline on the caller's thread."""
        fire = AkaiFire(async_handlers=False)
        try:
            caller_thread_id = threading.get_ident()
            observed = []

            @fire.on_pad()
            def handler(pad_index, velocity):
                observed.append(threading.get_ident())

            fire._process_message([[0x90, 54, 100], 0])
            self.assertEqual(observed, [caller_thread_id])
        finally:
            fire.close()

    def test_raising_handler_in_async_mode_logs(self):
        fire = AkaiFire(async_handlers=True, max_workers=1)
        try:
            done = threading.Event()

            @fire.on_pad()
            def bad(pad_index, velocity):
                done.set()
                raise RuntimeError("boom")

            with self.assertLogs("akai_fire", level="ERROR"):
                fire._process_message([[0x90, 54, 100], 0])
                done.wait(timeout=1.0)
                # Give the pool a moment to log the exception
                time.sleep(0.05)
        finally:
            fire.close()


class TestListenLoop(unittest.TestCase):
    """Polling thread must stop promptly regardless of _lock contention."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire(async_handlers=False)

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_stop_without_rlock_contention(self):
        self.fire.start_listening()

        hog_released = threading.Event()

        def lock_hog():
            with self.fire._lock:
                hog_released.wait(timeout=1.0)

        hog = threading.Thread(target=lock_hog, daemon=True)
        hog.start()
        time.sleep(0.01)  # let the hog grab the lock

        start = time.time()
        self.fire._stop_event.set()
        self.fire.listening_thread.join(timeout=1.0)
        elapsed = time.time() - start

        hog_released.set()
        hog.join(timeout=1.0)

        self.assertFalse(self.fire.listening_thread.is_alive())
        # Without the RLock dance in _listen, stop should be fast even while the lock is held.
        self.assertLess(elapsed, 0.2)


class TestReconnect(unittest.TestCase):
    """reconnect() must restart the listener if it was active pre-close."""

    def setUp(self):
        self._in_patcher = patch("rtmidi.MidiIn")
        self._out_patcher = patch("rtmidi.MidiOut")
        mock_midi_in = self._in_patcher.start()
        mock_midi_out = self._out_patcher.start()
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

    def tearDown(self):
        self._in_patcher.stop()
        self._out_patcher.stop()

    def test_reconnect_restarts_listener_when_previously_listening(self):
        fire = AkaiFire(async_handlers=False)
        try:
            fire.start_listening()
            self.assertTrue(fire.listening)
            self.assertTrue(fire.reconnect())
            self.assertTrue(fire.listening)
        finally:
            fire.close()

    def test_reconnect_does_not_start_listener_when_not_listening(self):
        fire = AkaiFire(async_handlers=False)
        try:
            self.assertFalse(fire.listening)
            self.assertTrue(fire.reconnect())
            self.assertFalse(fire.listening)
        finally:
            fire.close()

    def test_reconnect_rebuilds_async_dispatcher(self):
        fire = AkaiFire(async_handlers=True, max_workers=2)
        try:
            fire.start_listening()
            self.assertIsNotNone(fire._dispatcher)
            self.assertTrue(fire.reconnect())
            self.assertTrue(fire.listening)
            # close() set the dispatcher to None; reconnect must rebuild it.
            self.assertIsNotNone(fire._dispatcher)
        finally:
            fire.close()


class TestAsyncDispatchInvariants(unittest.TestCase):
    """Documented dispatch guarantees, proven for async_handlers=True.

    CLAUDE.md promises: modifier state is latched before any handler
    runs (even under async dispatch), and max_workers=1 preserves FIFO
    ordering. These invariants were previously only tested on the
    serial path.
    """

    def setUp(self):
        # @patch on setUp only covers setUp itself; AkaiFire is
        # constructed inside the test methods, so the patches must live
        # for the whole method via start()/stop().
        self._in_patcher = patch("rtmidi.MidiIn")
        self._out_patcher = patch("rtmidi.MidiOut")
        mock_midi_in = self._in_patcher.start()
        mock_midi_out = self._out_patcher.start()
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out

    def tearDown(self):
        self._in_patcher.stop()
        self._out_patcher.stop()

    def _wait_until(self, predicate, timeout=2.0, interval=0.005):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(interval)
        return False

    def test_modifier_latched_before_async_pad_handler_runs(self):
        """Pad handlers see coherent SHIFT state even with async dispatch."""
        fire = AkaiFire(async_handlers=True, max_workers=4)
        try:
            observed = []
            done = threading.Event()

            @fire.on_pad(3)
            def handler(velocity):
                observed.append(fire.is_shift_pressed())
                done.set()

            # Latching happens inline in _dispatch_button before the
            # handler is submitted to the pool, so this is deterministic
            # even though the handler itself runs on a worker thread.
            fire._process_message([[0x90, fire.BUTTON_SHIFT, 127], 0.0])
            fire._process_message([[0x90, 54 + 3, 100], 0.0])

            self.assertTrue(done.wait(2.0), "pad handler never ran")
            self.assertEqual(observed, [True])
        finally:
            fire.close()

    def test_max_workers_one_preserves_fifo_ordering(self):
        """With max_workers=1, events reach handlers in arrival order."""
        fire = AkaiFire(async_handlers=True, max_workers=1)
        try:
            received = []

            @fire.on_pad()
            def handler(pad_index, velocity):
                received.append(pad_index)

            total = 25
            for i in range(total):
                fire._process_message([[0x90, 54 + i, 100], 0.0])

            self.assertTrue(
                self._wait_until(lambda: len(received) >= total),
                f"only {len(received)}/{total} events delivered",
            )
            self.assertEqual(received, list(range(total)))
        finally:
            fire.close()

    def test_reconnect_rebuilds_dispatcher_even_when_not_listening(self):
        """A later start_listening() must not silently dispatch inline.

        Regression: reconnect() only rebuilt the dispatcher when the
        listener had been running pre-close, leaving async_handlers=True
        devices with inline-only dispatch after reconnect-then-listen.
        """
        fire = AkaiFire(async_handlers=True)
        try:
            self.assertFalse(fire.listening)  # never started listening
            self.assertTrue(fire.reconnect())
            self.assertIsNotNone(fire._dispatcher)
            fire.start_listening()
            self.assertIsNotNone(fire._dispatcher)
        finally:
            fire.close()


class TestMidiSendRetry(unittest.TestCase):
    """Retry delay defaults must not block the caller for hundreds of ms."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire(async_handlers=False)

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_retry_delay_is_short_by_default(self):
        attempts = [0]

        def flaky_send(message):
            attempts[0] += 1
            if attempts[0] == 1:
                raise RuntimeError("transient")

        self.mock_midi_out.send_message = flaky_send

        start = time.time()
        ok = self.fire._send_midi_safe([0xB0, 0x33, 0x02])
        elapsed = time.time() - start

        self.assertTrue(ok)
        self.assertEqual(attempts[0], 2)
        # One retry at ~10ms — well under the old 300ms worst case.
        self.assertLess(elapsed, 0.05)


class TestHandlerMutation(unittest.TestCase):
    """Contract: a handler may unregister itself during dispatch."""

    @patch("rtmidi.MidiIn")
    @patch("rtmidi.MidiOut")
    def setUp(self, mock_midi_out, mock_midi_in):
        self.mock_midi_in = MockMidiPort()
        self.mock_midi_out = MockMidiPort()
        mock_midi_in.return_value = self.mock_midi_in
        mock_midi_out.return_value = self.mock_midi_out
        self.fire = AkaiFire(async_handlers=False)

    def tearDown(self):
        if hasattr(self, "fire"):
            self.fire.close()

    def test_handler_can_remove_itself(self):
        calls = []

        def once(event):
            calls.append(event)
            # Remove self from the listener list. Safe to mutate during
            # dispatch because _process_message snapshots the list under
            # self._lock before iterating.
            with self.fire._lock:
                self.fire.button_listeners[self.fire.BUTTON_PLAY].remove(once)

        self.fire.add_button_listener(self.fire.BUTTON_PLAY, once)

        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])
        self.fire._process_message([[0x90, self.fire.BUTTON_PLAY, 127], 0])

        self.assertEqual(calls, ["press"])


if __name__ == "__main__":
    unittest.main()
