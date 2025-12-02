# Testing Helpers Module - Planning Document

This document outlines the design for a testing utilities module that can be extracted from the Circuit app test suite and added to the main `akai_fire` library.

## Goals

1. **Zero-dependency testing** - Test applications without hardware or pygame
2. **Visual regression testing** - Screenshot comparison like Playwright
3. **Event simulation** - Programmatically trigger pad/button/rotary events
4. **MIDI verification** - Capture and assert on MIDI output
5. **Timing control** - Step through sequencer timing without real-time delays

## Proposed Package Structure

```
akai_fire/
├── __init__.py              # Main library
├── testing/                 # NEW: Testing utilities subpackage
│   ├── __init__.py          # Public API exports
│   ├── mocks.py             # Mock objects (MockAkaiFire, MockCanvas)
│   ├── midi.py              # MIDI testing utilities (MockMidiManager)
│   ├── assertions.py        # Custom assertion helpers
│   ├── fixtures.py          # Common test fixtures and factories
│   └── screenshots.py       # Screenshot comparison utilities
```

## Components to Extract

### 1. MockAkaiFire

**Purpose**: Lightweight mock of the AkaiFire controller that doesn't require pygame.

**Current location**: `examples/circuit/tests/test_helpers.py`

**Features**:
- All pad/button/LED state tracking
- Event handler registration (same decorator API as real controller)
- Event simulation methods for testing
- Assertion helpers for verifying state

```python
# Example usage
from akai_fire.testing import MockAkaiFire

def test_pad_color_changes():
    fire = MockAkaiFire()

    # Set up handler
    @fire.on_pad()
    def on_pad(pad_index, velocity):
        fire.set_pad_color(pad_index, 127, 0, 0)

    # Simulate event
    fire.simulate_pad_press(5, velocity=100)

    # Assert result
    fire.assert_pad_color(5, (127, 0, 0))
```

**API Surface**:
```python
class MockAkaiFire:
    # State
    pad_colors: List[Tuple[int, int, int]]
    button_leds: Dict[int, int]
    track_leds: Dict[int, int]

    # Recording
    pad_events: List[PadEvent]
    button_events: List[ButtonEvent]
    render_count: int

    # Methods (same as AkaiFire)
    def set_pad_color(pad_index, r, g, b)
    def set_button_led(button_id, value)
    def clear_all_pads()
    def get_canvas() -> MockCanvas
    def render_to_display()

    # Event registration (decorators)
    def on_pad(pad_index=None)
    def on_button(button_id)
    def on_rotary_turn(rotary_id)

    # Simulation (for testing)
    def simulate_pad_press(pad_index, velocity=100)
    def simulate_pad_release(pad_index)
    def simulate_button_press(button_id)
    def simulate_button_release(button_id)
    def simulate_rotary_turn(rotary_id, direction, velocity=1)

    # Assertions
    def assert_pad_color(pad_index, expected_color)
    def assert_pad_not_black(pad_index)
    def assert_button_led(button_id, expected_value)
    def get_lit_pads() -> List[int]
    def get_pad_colors_by_row() -> List[List[Tuple]]
```

### 2. MockCanvas

**Purpose**: Canvas implementation that records drawing operations and can save screenshots without PIL.

**Current location**: `examples/circuit/tests/test_helpers.py`

**Features**:
- All Canvas drawing methods
- Actual pixel buffer (for screenshots)
- Operation recording (for assertions)
- BMP screenshot export (with/without PIL)

```python
# Example usage
from akai_fire.testing import MockCanvas

def test_screen_rendering():
    canvas = MockCanvas()

    # Draw something
    canvas.draw_text("Hello", 10, 10)
    canvas.draw_rect(0, 0, 128, 64)

    # Assert on recorded operations
    assert len(canvas.text_drawn) == 1
    assert canvas.text_drawn[0] == ("Hello", 10, 10)

    # Save screenshot for visual verification
    canvas.save_screenshot("test_output/hello_screen.bmp")
```

**API Surface**:
```python
class MockCanvas:
    # Dimensions
    width: int = 128
    height: int = 64

    # Pixel buffer
    pixels: List[List[int]]

    # Operation recording
    text_drawn: List[Tuple[str, int, int]]
    rects_drawn: List[Tuple[int, int, int, int, bool]]
    lines_drawn: List[Tuple[int, int, int, int]]
    circles_drawn: List[Tuple[int, int, int, bool]]
    clear_count: int

    # Drawing methods (same as Canvas)
    def clear()
    def set_pixel(x, y, color=1)
    def get_pixel(x, y) -> int
    def draw_text(text, x, y, font=None, color=1)
    def draw_rect(x, y, w, h, color=1)
    def fill_rect(x, y, w, h, color=1)
    def draw_line(x0, y0, x1, y1, color=1)
    def draw_circle(cx, cy, radius, color=1)
    def fill_circle(cx, cy, radius, color=1)
    def draw_border(thickness=1, color=1)

    # High-level drawing (same as Canvas)
    def draw_page(title, lines, header_inverted=True)
    def draw_menu(title, items, selected_index)
    def draw_value_page(title, value, unit="", ...)

    # Screenshot methods
    def save_screenshot(path, scale=4) -> str
    def auto_screenshot(directory, prefix="screen") -> str
```

### 3. MockMidiManager

**Purpose**: Capture all MIDI output for verification in tests.

**Current location**: `examples/circuit/tests/test_helpers.py`

**Features**:
- Records all MIDI messages sent
- Provides assertion helpers
- Can verify note sequences, CC values, etc.

```python
# Example usage
from akai_fire.testing import MockMidiManager

def test_sequencer_output():
    midi = MockMidiManager()
    sequencer = Sequencer(midi_manager=midi)

    # Play a note
    sequencer.play_note(60, velocity=100)

    # Verify output
    midi.assert_note_on(channel=1, note=60, velocity=100)
    assert len(midi.get_notes_on()) == 1
```

**API Surface**:
```python
@dataclass
class MidiMessage:
    type: str  # "note_on", "note_off", "cc", "all_notes_off"
    channel: int
    note_or_cc: int
    value: int
    timestamp: float

class MockMidiManager:
    messages: List[MidiMessage]
    output_port: Optional[str]

    # Send methods (same as real MidiManager)
    def send_note_on(channel, note, velocity)
    def send_note_off(channel, note)
    def send_cc(channel, cc, value)
    def send_all_notes_off()

    # Query methods
    def get_status() -> Dict
    def cleanup()

    # Test helpers
    def assert_note_on(channel, note, velocity)
    def assert_note_off(channel, note)
    def get_notes_on(channel=None) -> List[Tuple[int, int]]
    def clear_messages()
```

### 4. ControllableTimingEngine

**Purpose**: Timing engine that can be manually advanced for deterministic tests.

**Current location**: `examples/circuit/tests/test_helpers.py`

**Features**:
- Manual step advancement (no real-time delays)
- Callbacks work the same as real timing
- Deterministic test execution

```python
# Example usage
from akai_fire.testing import ControllableTimingEngine

def test_step_sequencer():
    timing = ControllableTimingEngine(bpm=120)
    steps_fired = []

    timing.add_step_callback(lambda step: steps_fired.append(step))
    timing.start_playback()

    # Manually advance steps
    timing.advance_step()  # Step 0
    timing.advance_step()  # Step 1
    timing.advance_step()  # Step 2

    assert steps_fired == [0, 1, 2]
```

**API Surface**:
```python
class ControllableTimingEngine:
    def __init__(bpm: float = 120.0)

    def set_bpm(bpm: float)
    def get_bpm() -> float
    def start_playback()
    def stop_playback()

    # Test control
    def advance_step()
    def advance_steps(count: int)
    def get_current_step() -> int

    def add_step_callback(callback: Callable[[int], None])
    def get_timing_info() -> Dict
```

### 5. Screenshot Comparison Utilities

**Purpose**: Compare screenshots for visual regression testing.

**New component** (to be implemented)

```python
# Example usage
from akai_fire.testing import ScreenshotComparator

def test_menu_rendering():
    canvas = MockCanvas()
    render_menu(canvas, items=["Option 1", "Option 2"], selected=0)

    # Compare to baseline
    comparator = ScreenshotComparator("tests/baselines")
    result = comparator.compare(canvas, "menu_screen")

    if not result.matches:
        result.save_diff("tests/failures/menu_diff.bmp")
        pytest.fail(f"Screenshot mismatch: {result.diff_percentage}%")
```

**API Surface**:
```python
@dataclass
class ComparisonResult:
    matches: bool
    diff_percentage: float
    diff_pixels: int
    baseline_path: str
    actual_path: str

    def save_diff(path: str)
    def save_actual(path: str)

class ScreenshotComparator:
    def __init__(baseline_dir: str, threshold: float = 0.01)

    def compare(canvas: MockCanvas, name: str) -> ComparisonResult
    def update_baseline(canvas: MockCanvas, name: str)
    def list_baselines() -> List[str]
```

### 6. Test Fixtures and Factories

**Purpose**: Common test setup patterns.

```python
# Example usage
from akai_fire.testing import create_test_fire, create_test_sequencer

def test_with_fixtures():
    fire, midi = create_test_fire()  # Returns configured MockAkaiFire + MockMidiManager
    sequencer = create_test_sequencer(bpm=120, tracks=4)

    # Test code...
```

**API Surface**:
```python
def create_test_fire() -> Tuple[MockAkaiFire, MockMidiManager]
def create_test_sequencer(**kwargs) -> Sequencer
def create_test_pattern(steps: List[int], note: int = 60) -> Pattern
def create_test_track(name: str, channel: int) -> Track
```

## Implementation Plan

### Phase 1: Core Mocks (Immediate)
1. Extract `MockAkaiFire` to `akai_fire/testing/mocks.py`
2. Extract `MockCanvas` to `akai_fire/testing/mocks.py`
3. Create `akai_fire/testing/__init__.py` with public exports
4. Add tests for the testing module itself

### Phase 2: MIDI Testing
1. Extract `MockMidiManager` to `akai_fire/testing/midi.py`
2. Add message filtering and query helpers
3. Add assertion helpers

### Phase 3: Timing Control
1. Extract `ControllableTimingEngine` to `akai_fire/testing/timing.py`
2. Ensure API compatibility with real timing engine
3. Add step-by-step debugging capabilities

### Phase 4: Screenshot Comparison
1. Implement `ScreenshotComparator` in `akai_fire/testing/screenshots.py`
2. Add baseline management
3. Add diff visualization

### Phase 5: Fixtures and Integration
1. Create common fixtures in `akai_fire/testing/fixtures.py`
2. Add pytest plugin for auto-discovery
3. Documentation and examples

## Usage Patterns

### Pattern 1: Unit Testing Mode Handlers

```python
from akai_fire.testing import MockAkaiFire, MockMidiManager

class TestNoteMode(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.midi = MockMidiManager()
        self.mode = NoteMode(self.fire, self.midi)

    def test_pad_plays_note(self):
        self.mode.handle_pad_press(32, velocity=100)
        self.midi.assert_note_on(channel=1, note=60, velocity=100)

    def test_track_selection_updates_display(self):
        self.mode.select_track(2)
        self.fire.assert_pad_color(17, (0, 127, 0))  # Track 2 lit
```

### Pattern 2: Visual Regression Testing

```python
from akai_fire.testing import MockAkaiFire, ScreenshotComparator

class TestScreenRendering(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.comparator = ScreenshotComparator("tests/baselines")

    def test_menu_screen(self):
        render_menu(self.fire.get_canvas(), ["A", "B", "C"], selected=1)
        result = self.comparator.compare(self.fire.get_canvas(), "menu_selected_b")
        self.assertTrue(result.matches, f"Diff: {result.diff_percentage}%")
```

### Pattern 3: Integration Testing with Timing

```python
from akai_fire.testing import (
    MockAkaiFire, MockMidiManager, ControllableTimingEngine
)

class TestSequencerPlayback(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.midi = MockMidiManager()
        self.timing = ControllableTimingEngine(bpm=120)
        self.sequencer = Sequencer(self.fire, self.midi, self.timing)

    def test_plays_pattern(self):
        # Add notes at steps 0 and 4
        self.sequencer.add_note(step=0, note=60)
        self.sequencer.add_note(step=4, note=64)

        # Start and advance
        self.sequencer.play()
        self.timing.advance_steps(5)

        # Verify notes were played
        notes = self.midi.get_notes_on()
        self.assertEqual(notes, [(60, 100), (64, 100)])
```

## Backward Compatibility

- The testing module is optional - main library works without it
- All mock classes have same API as real classes
- No changes required to existing application code

## Dependencies

The testing module should have minimal dependencies:
- `unittest` (stdlib) - for test infrastructure
- `struct` (stdlib) - for BMP writing
- `PIL` (optional) - for enhanced screenshots

## Open Questions

1. **Should we include pytest integration?**
   - Fixtures as pytest fixtures
   - Custom assertions as pytest plugins
   - Automatic screenshot on failure

2. **Should MockCanvas support color modes?**
   - Currently only monochrome (like OLED)
   - Could add RGB mode for future hardware

3. **Should we add recording/playback?**
   - Record real hardware interactions
   - Replay for automated testing

4. **Should assertion failures save debug info?**
   - Auto-save screenshot on assertion failure
   - Dump pad/button state

## References

- Circuit app test suite: `examples/circuit/tests/`
- Main library tests: `tests/`
- Playwright screenshot testing: https://playwright.dev/docs/screenshots
