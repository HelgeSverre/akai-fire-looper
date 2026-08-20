"""
Tests for the akai_fire_testing module.

This test suite validates that the testing utilities work correctly
and serve as documentation for how to use them.
"""

import unittest
import os
import sys
import tempfile
import shutil

# Add project root to path for direct execution
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from akai_fire_testing import (
    # Core mocks
    MockAkaiFire,
    MockCanvas,
    PadEvent,
    ButtonEvent,
    # MIDI
    MockMidiManager,
    MidiMessage,
    # Timing
    ControllableTimingEngine,
    # Screenshots
    ScreenshotComparator,
    ComparisonResult,
    # Assertions
    assert_pad_grid,
    assert_row_pattern,
    assert_column_pattern,
    assert_button_state,
    assert_screen_contains,
    assert_screen_title,
    assert_notes_in_order,
    snapshot_pad_state,
    assert_pad_state_changed,
    assert_pad_state_unchanged,
    # Fixtures
    create_test_fire,
    create_test_canvas,
    create_test_timing,
    create_test_environment,
    TestHarness,
    create_step_recorder,
    create_step_pattern,
)


class TestMockCanvas(unittest.TestCase):
    """Tests for MockCanvas."""

    def test_create_canvas_default_size(self):
        """Canvas has correct default dimensions."""
        canvas = MockCanvas()
        self.assertEqual(canvas.width, 128)
        self.assertEqual(canvas.height, 64)

    def test_create_canvas_custom_size(self):
        """Canvas can be created with custom dimensions."""
        canvas = MockCanvas(width=256, height=128)
        self.assertEqual(canvas.width, 256)
        self.assertEqual(canvas.height, 128)

    def test_clear_resets_pixels(self):
        """Clear resets all pixels to white (1) by default, matching real Canvas."""
        canvas = MockCanvas()
        canvas.set_pixel(10, 10, 0)  # Set to black
        canvas.clear()  # Default clears to white (1)
        self.assertEqual(canvas.get_pixel(10, 10), 1)  # Now white
        self.assertEqual(canvas.clear_count, 1)

        # Can also clear to black explicitly
        canvas.clear(0)
        self.assertEqual(canvas.get_pixel(10, 10), 0)

    def test_set_and_get_pixel(self):
        """Pixels can be set and retrieved."""
        canvas = MockCanvas()
        canvas.set_pixel(50, 30, 1)
        self.assertEqual(canvas.get_pixel(50, 30), 1)

    def test_pixel_out_of_bounds_ignored(self):
        """Out of bounds writes are ignored; reads return None like real Canvas."""
        canvas = MockCanvas()
        canvas.set_pixel(-1, 0, 0)  # Should not raise
        canvas.set_pixel(200, 0, 0)  # Should not raise
        self.assertIsNone(canvas.get_pixel(-1, 0))
        self.assertIsNone(canvas.get_pixel(200, 0))

    def test_draw_text_records_operation(self):
        """Drawing text records the operation."""
        canvas = MockCanvas()
        canvas.draw_text("Hello", 10, 20)
        self.assertEqual(len(canvas.text_drawn), 1)
        self.assertEqual(canvas.text_drawn[0], ("Hello", 10, 20))

    def test_draw_rect_records_operation(self):
        """Drawing rectangles records the operation."""
        canvas = MockCanvas()
        canvas.draw_rect(0, 0, 50, 30)
        self.assertEqual(len(canvas.rects_drawn), 1)
        self.assertEqual(canvas.rects_drawn[0], (0, 0, 50, 30, False))

    def test_fill_rect_records_operation(self):
        """Filled rectangles are recorded correctly."""
        canvas = MockCanvas()
        canvas.fill_rect(0, 0, 50, 30)
        self.assertEqual(canvas.rects_drawn[0], (0, 0, 50, 30, True))

    def test_draw_line_records_operation(self):
        """Lines are recorded."""
        canvas = MockCanvas()
        canvas.draw_line(0, 0, 50, 50)
        self.assertEqual(len(canvas.lines_drawn), 1)
        self.assertEqual(canvas.lines_drawn[0], (0, 0, 50, 50))

    def test_draw_circle_records_operation(self):
        """Circles are recorded."""
        canvas = MockCanvas()
        canvas.draw_circle(64, 32, 10)
        self.assertEqual(len(canvas.circles_drawn), 1)
        self.assertEqual(canvas.circles_drawn[0], (64, 32, 10, False))

    def test_screenshot_creates_file(self):
        """Screenshots can be saved to BMP files."""
        canvas = MockCanvas()
        canvas.draw_text("Test", 10, 10)
        canvas.fill_rect(0, 0, 20, 20)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.bmp")
            result = canvas.save_screenshot(path)
            self.assertTrue(os.path.exists(result))
            # Check it's a valid BMP (starts with BM)
            with open(result, "rb") as f:
                magic = f.read(2)
                self.assertEqual(magic, b"BM")


class TestMockAkaiFire(unittest.TestCase):
    """Tests for MockAkaiFire."""

    def test_initial_state(self):
        """Controller starts with all pads black."""
        fire = MockAkaiFire()
        self.assertEqual(len(fire.pad_colors), 64)
        self.assertTrue(all(c == (0, 0, 0) for c in fire.pad_colors))

    def test_set_pad_color(self):
        """Setting pad color updates state and records event."""
        fire = MockAkaiFire()
        fire.set_pad_color(10, 127, 64, 32)
        self.assertEqual(fire.pad_colors[10], (127, 64, 32))
        self.assertEqual(len(fire.pad_events), 1)
        self.assertEqual(fire.pad_events[0].pad_index, 10)

    def test_clear_all_pads(self):
        """Clear all pads sets all to black."""
        fire = MockAkaiFire()
        fire.set_pad_color(5, 127, 0, 0)
        fire.set_pad_color(10, 0, 127, 0)
        fire.clear_all_pads()
        self.assertTrue(all(c == (0, 0, 0) for c in fire.pad_colors))

    def test_set_button_led(self):
        """Button LEDs can be set."""
        fire = MockAkaiFire()
        fire.set_button_led(MockAkaiFire.BUTTON_PLAY, 2)
        self.assertEqual(fire.button_leds[MockAkaiFire.BUTTON_PLAY], 2)

    def test_event_decorator_on_pad(self):
        """Pad event decorator registers handler."""
        fire = MockAkaiFire()
        events_received = []

        @fire.on_pad()
        def handler(pad_index, velocity):
            events_received.append((pad_index, velocity))

        fire.simulate_pad_press(5, velocity=100)
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0], (5, 100))

    def test_event_decorator_on_button(self):
        """Button event decorator registers handler."""
        fire = MockAkaiFire()
        events_received = []

        @fire.on_button(MockAkaiFire.BUTTON_PLAY)
        def handler(action):
            events_received.append(action)

        fire.simulate_button_press(MockAkaiFire.BUTTON_PLAY)
        self.assertEqual(events_received, ["press"])

    def test_assert_pad_color(self):
        """Assertion helper works correctly."""
        fire = MockAkaiFire()
        fire.set_pad_color(5, 127, 0, 0)
        fire.assert_pad_color(5, (127, 0, 0))  # Should not raise

        with self.assertRaises(AssertionError):
            fire.assert_pad_color(5, (0, 127, 0))

    def test_get_lit_pads(self):
        """Get lit pads returns correct indices."""
        fire = MockAkaiFire()
        fire.set_pad_color(0, 127, 0, 0)
        fire.set_pad_color(15, 0, 127, 0)
        fire.set_pad_color(63, 0, 0, 127)
        lit = fire.get_lit_pads()
        self.assertEqual(sorted(lit), [0, 15, 63])

    def test_context_manager(self):
        """Controller can be used as context manager."""
        with MockAkaiFire() as fire:
            fire.set_pad_color(0, 127, 0, 0)
        self.assertTrue(fire._closed)


class TestMockMidiManager(unittest.TestCase):
    """Tests for MockMidiManager."""

    def test_send_note_on(self):
        """Note on messages are recorded."""
        midi = MockMidiManager()
        midi.send_note_on(1, 60, 100)
        self.assertEqual(len(midi.messages), 1)
        msg = midi.messages[0]
        self.assertEqual(msg.type, "note_on")
        self.assertEqual(msg.channel, 1)
        self.assertEqual(msg.note_or_cc, 60)
        self.assertEqual(msg.value, 100)

    def test_send_note_off(self):
        """Note off messages are recorded."""
        midi = MockMidiManager()
        midi.send_note_off(1, 60)
        msg = midi.messages[0]
        self.assertEqual(msg.type, "note_off")
        self.assertEqual(msg.note_or_cc, 60)

    def test_send_cc(self):
        """CC messages are recorded."""
        midi = MockMidiManager()
        midi.send_cc(1, 7, 127)  # Volume
        msg = midi.messages[0]
        self.assertEqual(msg.type, "cc")
        self.assertEqual(msg.note_or_cc, 7)
        self.assertEqual(msg.value, 127)

    def test_get_notes_on(self):
        """Get notes on returns correct tuples."""
        midi = MockMidiManager()
        midi.send_note_on(1, 60, 100)
        midi.send_note_on(1, 64, 80)
        midi.send_note_off(1, 60)
        notes = midi.get_notes_on()
        self.assertEqual(notes, [(60, 100), (64, 80)])

    def test_get_notes_on_filter_by_channel(self):
        """Notes can be filtered by channel."""
        midi = MockMidiManager()
        midi.send_note_on(1, 60, 100)
        midi.send_note_on(2, 64, 80)
        notes = midi.get_notes_on(channel=1)
        self.assertEqual(notes, [(60, 100)])

    def test_assert_note_on(self):
        """Assert note on works correctly."""
        midi = MockMidiManager()
        midi.send_note_on(1, 60, 100)
        midi.assert_note_on(1, 60, 100)  # Should not raise

        with self.assertRaises(AssertionError):
            midi.assert_note_on(1, 60, 50)  # Wrong velocity

    def test_clear_messages(self):
        """Messages can be cleared."""
        midi = MockMidiManager()
        midi.send_note_on(1, 60, 100)
        midi.clear_messages()
        self.assertEqual(len(midi.messages), 0)


class TestControllableTimingEngine(unittest.TestCase):
    """Tests for ControllableTimingEngine."""

    def test_initial_state(self):
        """Engine starts stopped at step 0."""
        timing = ControllableTimingEngine()
        self.assertFalse(timing.is_playing())
        self.assertEqual(timing.get_current_step(), 0)

    def test_start_stop_playback(self):
        """Playback can be started and stopped."""
        timing = ControllableTimingEngine()
        timing.start_playback()
        self.assertTrue(timing.is_playing())
        timing.stop_playback()
        self.assertFalse(timing.is_playing())
        self.assertEqual(timing.get_current_step(), 0)

    def test_advance_step_fires_callbacks(self):
        """Advancing steps fires callbacks."""
        timing = ControllableTimingEngine()
        steps_received = []
        timing.add_step_callback(lambda s: steps_received.append(s))
        timing.start_playback()

        timing.advance_step()
        timing.advance_step()
        timing.advance_step()

        self.assertEqual(steps_received, [0, 1, 2])

    def test_advance_steps_multiple(self):
        """Multiple steps can be advanced at once."""
        timing = ControllableTimingEngine()
        steps_received = []
        timing.add_step_callback(lambda s: steps_received.append(s))
        timing.start_playback()

        timing.advance_steps(4)
        self.assertEqual(steps_received, [0, 1, 2, 3])

    def test_step_wraps_at_total_steps(self):
        """Steps wrap around at total_steps."""
        timing = ControllableTimingEngine(total_steps=16)
        timing.start_playback()
        timing.advance_steps(16)
        self.assertEqual(timing.get_current_step(), 0)  # Wrapped

    def test_bpm_clamped(self):
        """BPM is clamped to valid range."""
        timing = ControllableTimingEngine()
        timing.set_bpm(500)  # Too high
        self.assertEqual(timing.get_bpm(), 300)
        timing.set_bpm(10)  # Too low
        self.assertEqual(timing.get_bpm(), 30)

    def test_no_callbacks_when_stopped(self):
        """No callbacks fire when not playing."""
        timing = ControllableTimingEngine()
        steps_received = []
        timing.add_step_callback(lambda s: steps_received.append(s))
        # Not started!
        timing.advance_step()
        self.assertEqual(steps_received, [])


class TestScreenshotComparator(unittest.TestCase):
    """Tests for ScreenshotComparator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_baseline_on_first_run(self):
        """First comparison creates baseline and passes."""
        comparator = ScreenshotComparator(self.tmpdir)
        canvas = MockCanvas()
        canvas.draw_text("Test", 10, 10)

        result = comparator.compare(canvas, "test_screen")

        self.assertTrue(result.matches)
        self.assertTrue(os.path.exists(result.baseline_path))

    def test_matches_identical_content(self):
        """Identical content matches baseline."""
        comparator = ScreenshotComparator(self.tmpdir)

        # Create baseline
        canvas1 = MockCanvas()
        canvas1.draw_text("Test", 10, 10)
        canvas1.fill_rect(0, 0, 20, 20)
        comparator.compare(canvas1, "test_screen")

        # Compare identical content
        canvas2 = MockCanvas()
        canvas2.draw_text("Test", 10, 10)
        canvas2.fill_rect(0, 0, 20, 20)
        result = comparator.compare(canvas2, "test_screen")

        self.assertTrue(result.matches)
        self.assertEqual(result.diff_percentage, 0.0)

    def test_detects_differences(self):
        """Different content is detected."""
        comparator = ScreenshotComparator(self.tmpdir)

        # Create baseline
        canvas1 = MockCanvas()
        canvas1.draw_text("Original", 10, 10)
        comparator.compare(canvas1, "test_screen")

        # Compare different content
        canvas2 = MockCanvas()
        canvas2.draw_text("Different", 10, 10)
        result = comparator.compare(canvas2, "test_screen")

        self.assertFalse(result.matches)
        self.assertGreater(result.diff_percentage, 0)

    def test_list_baselines(self):
        """Can list all baselines."""
        comparator = ScreenshotComparator(self.tmpdir)

        canvas = MockCanvas()
        comparator.update_baseline(canvas, "screen1")
        comparator.update_baseline(canvas, "screen2")

        baselines = comparator.list_baselines()
        self.assertEqual(sorted(baselines), ["screen1", "screen2"])


class TestAssertionHelpers(unittest.TestCase):
    """Tests for assertion helper functions."""

    def test_assert_pad_grid(self):
        """assert_pad_grid works correctly."""
        fire = MockAkaiFire()
        fire.set_pad_color(0, 127, 0, 0)
        fire.set_pad_color(5, 0, 127, 0)

        # Should pass
        assert_pad_grid(fire, expected_lit=[0, 5])

        # Should fail
        with self.assertRaises(AssertionError):
            assert_pad_grid(fire, expected_lit=[0, 1])

    def test_assert_row_pattern(self):
        """assert_row_pattern works correctly."""
        fire = MockAkaiFire()
        # Light every other pad in row 0
        for i in range(0, 16, 2):
            fire.set_pad_color(i, 127, 0, 0)

        pattern = [i % 2 == 0 for i in range(16)]
        assert_row_pattern(fire, 0, pattern)  # Should pass

    def test_assert_screen_contains(self):
        """assert_screen_contains works correctly."""
        canvas = MockCanvas()
        canvas.draw_text("Hello World", 10, 10)

        assert_screen_contains(canvas, "Hello")  # Should pass

        with self.assertRaises(AssertionError):
            assert_screen_contains(canvas, "Goodbye")

    def test_snapshot_and_assert_changed(self):
        """Pad state snapshot comparison works."""
        fire = MockAkaiFire()
        fire.set_pad_color(5, 127, 0, 0)

        snapshot = snapshot_pad_state(fire)

        fire.set_pad_color(10, 0, 127, 0)

        assert_pad_state_changed(fire, snapshot, changed_pads=[10])

    def test_assert_pad_state_unchanged(self):
        """assert_pad_state_unchanged works correctly."""
        fire = MockAkaiFire()
        fire.set_pad_color(5, 127, 0, 0)

        snapshot = snapshot_pad_state(fire)

        assert_pad_state_unchanged(fire, snapshot)  # Should pass

        fire.set_pad_color(10, 0, 127, 0)

        with self.assertRaises(AssertionError):
            assert_pad_state_unchanged(fire, snapshot)


class TestFixtures(unittest.TestCase):
    """Tests for fixture functions."""

    def test_create_test_fire(self):
        """create_test_fire returns correct types."""
        fire, midi = create_test_fire()
        self.assertIsInstance(fire, MockAkaiFire)
        self.assertIsInstance(midi, MockMidiManager)

        fire2, midi2 = create_test_fire(with_midi=False)
        self.assertIsInstance(fire2, MockAkaiFire)
        self.assertIsNone(midi2)

    def test_create_test_canvas(self):
        """create_test_canvas works correctly."""
        canvas = create_test_canvas()
        self.assertIsInstance(canvas, MockCanvas)

        canvas_with_content = create_test_canvas(with_content="Hello")
        self.assertEqual(len(canvas_with_content.text_drawn), 1)

    def test_create_test_timing(self):
        """create_test_timing works correctly."""
        timing = create_test_timing(bpm=140, auto_start=True)
        self.assertEqual(timing.get_bpm(), 140)
        self.assertTrue(timing.is_playing())

    def test_create_test_environment(self):
        """create_test_environment returns all components."""
        fire, midi, timing = create_test_environment()
        self.assertIsInstance(fire, MockAkaiFire)
        self.assertIsInstance(midi, MockMidiManager)
        self.assertIsInstance(timing, ControllableTimingEngine)

    def test_create_step_recorder(self):
        """create_step_recorder captures steps."""
        callback, steps = create_step_recorder()
        timing = ControllableTimingEngine()
        timing.add_step_callback(callback)
        timing.start_playback()
        timing.advance_steps(3)
        self.assertEqual(steps, [0, 1, 2])

    def test_create_step_pattern(self):
        """create_step_pattern generates correct pattern."""
        pattern = create_step_pattern([0, 4, 8, 12])
        self.assertEqual(len(pattern), 16)
        self.assertTrue(pattern[0])
        self.assertFalse(pattern[1])
        self.assertTrue(pattern[4])


class TestTestHarness(unittest.TestCase):
    """Tests for TestHarness."""

    def test_harness_has_all_components(self):
        """TestHarness provides all required components."""
        harness = TestHarness()
        self.assertIsInstance(harness.fire, MockAkaiFire)
        self.assertIsInstance(harness.midi, MockMidiManager)
        self.assertIsInstance(harness.timing, ControllableTimingEngine)
        self.assertIsInstance(harness.canvas, MockCanvas)

    def test_harness_advance(self):
        """TestHarness advance method works."""
        harness = TestHarness()
        steps = []
        harness.timing.add_step_callback(lambda s: steps.append(s))
        harness.advance(4)
        self.assertEqual(steps, [0, 1, 2, 3])

    def test_harness_press_pad(self):
        """TestHarness pad press simulation works."""
        harness = TestHarness()
        events = []

        @harness.fire.on_pad()
        def handler(pad, vel):
            events.append((pad, vel))

        harness.press_pad(5, velocity=100)
        self.assertEqual(events, [(5, 100)])

    def test_harness_reset(self):
        """TestHarness reset clears all state."""
        harness = TestHarness()
        harness.fire.set_pad_color(5, 127, 0, 0)
        harness.midi.send_note_on(1, 60, 100)
        harness.timing.advance_steps(4)

        harness.reset()

        self.assertTrue(all(c == (0, 0, 0) for c in harness.fire.pad_colors))
        self.assertEqual(len(harness.midi.messages), 0)
        self.assertEqual(harness.timing.get_current_step(), 0)


class TestMockAkaiFireNewFeatures(unittest.TestCase):
    """Tests for new MockAkaiFire features."""

    def test_connection_simulation(self):
        """Connection simulation controls LED operations."""
        fire = MockAkaiFire()

        # Initially connected
        self.assertTrue(fire.is_connected())
        self.assertTrue(fire.set_pad_color(0, 127, 0, 0))

        # Disconnect
        fire.disconnect()
        self.assertFalse(fire.is_connected())
        self.assertFalse(fire.set_pad_color(1, 127, 0, 0))
        self.assertEqual(fire.get_connection_error(), "Simulated disconnection")

        # Reconnect
        fire.reconnect()
        self.assertTrue(fire.is_connected())
        self.assertTrue(fire.set_pad_color(2, 127, 0, 0))

    def test_bulk_pad_methods(self):
        """Bulk pad methods work correctly."""
        fire = MockAkaiFire()

        # set_all_pads
        fire.set_all_pads((127, 0, 0))
        self.assertTrue(all(c == (127, 0, 0) for c in fire.pad_colors))

        # reset_pads
        fire.reset_pads(0, 0, 127)
        self.assertTrue(all(c == (0, 0, 127) for c in fire.pad_colors))

        # set_multiple_pad_colors
        fire.clear_all_pads()
        fire.set_multiple_pad_colors(
            [
                (0, 127, 0, 0),
                (5, 0, 127, 0),
                (10, 0, 0, 127),
            ]
        )
        self.assertEqual(fire.pad_colors[0], (127, 0, 0))
        self.assertEqual(fire.pad_colors[5], (0, 127, 0))
        self.assertEqual(fire.pad_colors[10], (0, 0, 127))

    def test_modifier_state(self):
        """Modifier state tracking works."""
        fire = MockAkaiFire()

        # Initial state
        self.assertFalse(fire.is_shift_pressed())
        self.assertFalse(fire.is_alt_pressed())
        self.assertFalse(fire.shift_pressed)
        self.assertFalse(fire.alt_pressed)

        # Simulate shift press
        fire.simulate_button_press(fire.BUTTON_SHIFT)
        self.assertTrue(fire.is_shift_pressed())

        # Release shift
        fire.simulate_button_release(fire.BUTTON_SHIFT)
        self.assertFalse(fire.is_shift_pressed())

        # Simulate alt press
        fire.simulate_button_press(fire.BUTTON_ALT)
        self.assertTrue(fire.is_alt_pressed())

    def test_utility_methods(self):
        """Utility methods work correctly."""
        # pad_position
        row, col = MockAkaiFire.pad_position(17)  # Second row, second column
        self.assertEqual(col, 1)
        self.assertEqual(row, 1)

        # get_pad_column (1-indexed)
        self.assertEqual(MockAkaiFire.get_pad_column(0), 1)
        self.assertEqual(MockAkaiFire.get_pad_column(15), 16)

        # get_pad_row (1-indexed)
        self.assertEqual(MockAkaiFire.get_pad_row(0), 1)
        self.assertEqual(MockAkaiFire.get_pad_row(48), 4)

        # list_midi_ports
        ports = MockAkaiFire.list_midi_ports()
        self.assertIn("input", ports)
        self.assertIn("output", ports)

    def test_get_solo_index(self):
        """get_solo_index converts button ID to index."""
        fire = MockAkaiFire()

        self.assertEqual(fire.get_solo_index(fire.BUTTON_SOLO_1), 1)
        self.assertEqual(fire.get_solo_index(fire.BUTTON_SOLO_4), 4)
        self.assertIsNone(fire.get_solo_index(fire.BUTTON_PLAY))

    def test_global_listeners(self):
        """Global listeners receive all events."""
        fire = MockAkaiFire()
        pad_events = []
        button_events = []

        fire.add_global_listener(lambda p, v: pad_events.append((p, v)))

        @fire.on_button()  # Global button handler
        def handle_button(button_id, event):
            button_events.append((button_id, event))

        fire.simulate_pad_press(5, 100)
        fire.simulate_pad_press(10, 80)
        fire.simulate_button_press(fire.BUTTON_PLAY)

        self.assertEqual(pad_events, [(5, 100), (10, 80)])
        self.assertEqual(button_events, [(fire.BUTTON_PLAY, "press")])

    def test_rotary_touch_simulation(self):
        """Rotary touch simulation works."""
        fire = MockAkaiFire()
        events = []

        @fire.on_rotary_touch(fire.ROTARY_VOLUME)
        def handle_touch(event):
            events.append(event)

        fire.simulate_rotary_touch(fire.ROTARY_VOLUME)
        fire.simulate_rotary_release(fire.ROTARY_VOLUME)

        self.assertEqual(events, ["touch", "release"])

    def test_solo_simulation(self):
        """Solo button simulation works."""
        fire = MockAkaiFire()
        events = []

        @fire.on_solo(1)
        def handle_solo(event):
            events.append(event)

        fire.simulate_solo_press(1)
        fire.simulate_solo_release(1)

        self.assertEqual(events, ["press", "release"])

    def test_button_constants_match_real(self):
        """Button constants use real hex values."""
        # Key constants should match real AkaiFire
        self.assertEqual(MockAkaiFire.BUTTON_PLAY, 0x33)
        self.assertEqual(MockAkaiFire.BUTTON_STOP, 0x34)
        self.assertEqual(MockAkaiFire.BUTTON_REC, 0x35)
        self.assertEqual(MockAkaiFire.BUTTON_SHIFT, 0x30)
        self.assertEqual(MockAkaiFire.BUTTON_ALT, 0x31)


class TestMockCanvasNewFeatures(unittest.TestCase):
    """Tests for new MockCanvas features."""

    def test_canvas_constants(self):
        """Canvas has typography constants."""
        self.assertEqual(MockCanvas.WIDTH, 128)
        self.assertEqual(MockCanvas.HEIGHT, 64)
        self.assertEqual(MockCanvas.HEADER_HEIGHT, 16)
        self.assertEqual(MockCanvas.TEXT_MARGIN_Y, 3)
        self.assertEqual(MockCanvas.CONTENT_GAP, 2)
        self.assertEqual(MockCanvas.CONTENT_START, 18)

    def test_render_to_bmp(self):
        """render_to_bmp method works via MockAkaiFire."""
        fire = MockAkaiFire()
        canvas = fire.get_canvas()
        canvas.draw_text("Test", 10, 10)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.bmp")
            result = fire.render_to_bmp(path)
            self.assertTrue(os.path.exists(result))


class TestMockParity(unittest.TestCase):
    """Both mock classes must latch shift/alt state identically.

    The headless ``akai_fire_testing.MockAkaiFire`` and the interactive
    ``mock_gui_pygame.MockAkaiFire`` serve different purposes but must
    agree on observable state so code ported between dev and CI behaves
    the same.
    """

    @classmethod
    def setUpClass(cls):
        # Pygame needs a video driver even in headless unit tests; SDL's
        # "dummy" driver gives us a working window surface we never show.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    def test_headless_mock_latches_shift_on_press(self):
        fire = MockAkaiFire()
        self.assertFalse(fire.is_shift_pressed())
        fire.simulate_button_press(fire.BUTTON_SHIFT)
        self.assertTrue(fire.is_shift_pressed())
        fire.simulate_button_release(fire.BUTTON_SHIFT)
        self.assertFalse(fire.is_shift_pressed())

    def test_headless_mock_latches_alt_on_press(self):
        fire = MockAkaiFire()
        self.assertFalse(fire.is_alt_pressed())
        fire.simulate_button_press(fire.BUTTON_ALT)
        self.assertTrue(fire.is_alt_pressed())
        fire.simulate_button_release(fire.BUTTON_ALT)
        self.assertFalse(fire.is_alt_pressed())

    def test_pygame_mock_latches_shift_on_mouse_down(self):
        from mock_gui_pygame import MockAkaiFire as PygameMock

        fire = PygameMock()
        try:
            self.assertFalse(fire.is_shift_pressed())
            pos = fire.button_rects[fire.BUTTON_SHIFT].center

            class FakeEvent:
                pass

            down = FakeEvent()
            down.pos = pos
            fire._handle_mouse_down(down)
            self.assertTrue(fire.is_shift_pressed())

            up = FakeEvent()
            up.pos = pos
            fire._handle_mouse_up(up)
            self.assertFalse(fire.is_shift_pressed())
        finally:
            fire.close()

    def test_pygame_mock_latches_alt_on_mouse_down(self):
        from mock_gui_pygame import MockAkaiFire as PygameMock

        fire = PygameMock()
        try:
            self.assertFalse(fire.is_alt_pressed())
            pos = fire.button_rects[fire.BUTTON_ALT].center

            class FakeEvent:
                pass

            down = FakeEvent()
            down.pos = pos
            fire._handle_mouse_down(down)
            self.assertTrue(fire.is_alt_pressed())

            up = FakeEvent()
            up.pos = pos
            fire._handle_mouse_up(up)
            self.assertFalse(fire.is_alt_pressed())
        finally:
            fire.close()

    # -- TUI mock parity ----------------------------------------------
    # Skipped when rich is unavailable; its toggle semantics match the
    # pygame mock's press/release cycle, just driven by keyboard input.

    def _tui_available(self):
        try:
            import rich  # noqa: F401
            import mock_gui_tui  # noqa: F401

            return True
        except ImportError:
            return False

    def test_tui_mock_latches_shift_via_inject(self):
        if not self._tui_available():
            self.skipTest("rich / mock_gui_tui not available")
        from mock_gui_tui import MockAkaiFire as TuiMock

        fire = TuiMock(headless=True)
        try:
            self.assertFalse(fire.is_shift_pressed())
            fire.inject_key("s")
            self.assertTrue(fire.is_shift_pressed())
            fire.inject_key("s")
            self.assertFalse(fire.is_shift_pressed())
        finally:
            fire.close()

    def test_tui_mock_latches_alt_via_inject(self):
        if not self._tui_available():
            self.skipTest("rich / mock_gui_tui not available")
        from mock_gui_tui import MockAkaiFire as TuiMock

        fire = TuiMock(headless=True)
        try:
            self.assertFalse(fire.is_alt_pressed())
            fire.inject_key("a")
            self.assertTrue(fire.is_alt_pressed())
            fire.inject_key("a")
            self.assertFalse(fire.is_alt_pressed())
        finally:
            fire.close()


if __name__ == "__main__":
    unittest.main()
