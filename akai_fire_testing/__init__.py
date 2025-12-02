"""
AKAI Fire Testing Utilities

A comprehensive testing toolkit for applications built with the akai_fire library.
Provides mock objects, assertion helpers, and utilities for headless testing.

Features:
    - Zero-dependency testing (no hardware or pygame required)
    - Visual regression testing with screenshot comparison
    - Event simulation for pad/button/rotary interactions
    - MIDI output verification
    - Timing control for deterministic sequencer tests

Basic Usage:
    >>> from akai_fire_testing import MockAkaiFire, MockMidiManager
    >>>
    >>> def test_pad_handler():
    ...     fire = MockAkaiFire()
    ...     midi = MockMidiManager()
    ...
    ...     @fire.on_pad()
    ...     def handle_pad(pad_index, velocity):
    ...         midi.send_note_on(1, 60 + pad_index, velocity)
    ...
    ...     fire.simulate_pad_press(5, velocity=100)
    ...     midi.assert_note_on(channel=1, note=65, velocity=100)

Advanced Usage with TestHarness:
    >>> from akai_fire_testing import TestHarness
    >>>
    >>> def test_sequencer():
    ...     harness = TestHarness(bpm=120)
    ...     # Wire up your sequencer...
    ...     harness.advance(16)  # Advance 16 steps
    ...     harness.assert_notes_played([(60, 100), (64, 100)])

Visual Regression Testing:
    >>> from akai_fire_testing import MockCanvas, ScreenshotComparator
    >>>
    >>> def test_menu_screen():
    ...     canvas = MockCanvas()
    ...     render_menu(canvas, ["Option A", "Option B"])
    ...
    ...     comparator = ScreenshotComparator("tests/baselines")
    ...     result = comparator.compare(canvas, "menu_screen")
    ...     assert result.matches, f"Diff: {result.diff_percentage}%"
"""

# Version
__version__ = "0.1.0"

# =============================================================================
# Exception Classes (re-exported from akai_fire for testing error handling)
# =============================================================================

try:
    from akai_fire import (
        AkaiFireError,
        MIDIConnectionError,
        MIDISendError,
        InvalidParameterError,
        HardwareError,
        StateError,
    )
except ImportError:
    # Define stub exceptions if akai_fire not available
    class AkaiFireError(Exception):
        """Base exception for AKAI Fire library."""
        pass

    class MIDIConnectionError(AkaiFireError):
        """Raised when MIDI connection fails."""
        pass

    class MIDISendError(AkaiFireError):
        """Raised when sending MIDI message fails."""
        pass

    class InvalidParameterError(AkaiFireError):
        """Raised when invalid parameters are provided."""
        pass

    class HardwareError(AkaiFireError):
        """Raised when hardware communication fails."""
        pass

    class StateError(AkaiFireError):
        """Raised when operation is invalid for current state."""
        pass

# =============================================================================
# Core Mock Classes
# =============================================================================

from .mocks import (
    MockAkaiFire,
    MockCanvas,
    PadEvent,
    ButtonEvent,
)

# =============================================================================
# MIDI Testing
# =============================================================================

from .midi import (
    MockMidiManager,
    MidiMessage,
)

# =============================================================================
# Timing Control
# =============================================================================

from .timing import (
    ControllableTimingEngine,
)

# =============================================================================
# Screenshot Comparison
# =============================================================================

from .screenshots import (
    ScreenshotComparator,
    ComparisonResult,
)

# =============================================================================
# Assertions
# =============================================================================

from .assertions import (
    # Pad assertions
    assert_pad_grid,
    assert_row_pattern,
    assert_column_pattern,
    assert_step_indicator,
    # Button assertions
    assert_button_state,
    assert_transport_state,
    # Screen assertions
    assert_screen_contains,
    assert_screen_title,
    assert_screen_empty,
    assert_menu_selection,
    # MIDI assertions
    assert_notes_in_order,
    assert_chord,
    # State snapshots
    snapshot_pad_state,
    assert_pad_state_changed,
    assert_pad_state_unchanged,
)

# =============================================================================
# Fixtures and Factories
# =============================================================================

from .fixtures import (
    # Factory functions
    create_test_fire,
    create_test_canvas,
    create_test_timing,
    create_test_midi,
    create_test_environment,
    # Test harness
    TestHarness,
    # Recorder utilities
    create_step_recorder,
    create_note_recorder,
    # Pattern helpers
    create_step_pattern,
    create_drum_pattern,
)

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Version
    "__version__",

    # Exceptions (for testing error handling)
    "AkaiFireError",
    "MIDIConnectionError",
    "MIDISendError",
    "InvalidParameterError",
    "HardwareError",
    "StateError",

    # Core Mocks
    "MockAkaiFire",
    "MockCanvas",
    "PadEvent",
    "ButtonEvent",

    # MIDI
    "MockMidiManager",
    "MidiMessage",

    # Timing
    "ControllableTimingEngine",

    # Screenshots
    "ScreenshotComparator",
    "ComparisonResult",

    # Assertions - Pads
    "assert_pad_grid",
    "assert_row_pattern",
    "assert_column_pattern",
    "assert_step_indicator",

    # Assertions - Buttons
    "assert_button_state",
    "assert_transport_state",

    # Assertions - Screen
    "assert_screen_contains",
    "assert_screen_title",
    "assert_screen_empty",
    "assert_menu_selection",

    # Assertions - MIDI
    "assert_notes_in_order",
    "assert_chord",

    # Assertions - State
    "snapshot_pad_state",
    "assert_pad_state_changed",
    "assert_pad_state_unchanged",

    # Fixtures
    "create_test_fire",
    "create_test_canvas",
    "create_test_timing",
    "create_test_midi",
    "create_test_environment",
    "TestHarness",
    "create_step_recorder",
    "create_note_recorder",
    "create_step_pattern",
    "create_drum_pattern",
]
