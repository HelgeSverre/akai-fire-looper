"""
Test Helpers for Circuit Sequencer

This module re-exports testing utilities from akai_fire_testing.
Kept for backwards compatibility with existing tests.

For new tests, import directly from akai_fire_testing:
    from akai_fire_testing import MockAkaiFire, MockMidiManager, ...
"""

import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
circuit_dir = os.path.dirname(current_dir)
examples_dir = os.path.dirname(circuit_dir)
project_root = os.path.dirname(examples_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, circuit_dir)

# Re-export from akai_fire_testing
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
    # Fixtures
    create_test_fire,
    create_test_canvas,
    create_test_timing,
    create_test_environment,
    TestHarness,
    create_step_recorder,
)

# =============================================================================
# Circuit-specific test factories
# =============================================================================


def create_test_pattern_with_notes(steps, note=60, velocity=100):
    """
    Create a pattern with notes at specified steps.

    Args:
        steps: List of step indices that should have notes
        note: MIDI note number
        velocity: Note velocity

    Returns:
        Pattern with notes at specified steps
    """
    from core.pattern import Pattern

    pattern = Pattern()
    for step_idx in steps:
        if 0 <= step_idx < pattern.length:
            step = pattern.get_step(step_idx)
            step.add_note(note, velocity)

    return pattern


def create_test_track(name="Test Track", channel=1, color=(127, 0, 0)):
    """
    Create a track for testing.

    Args:
        name: Track name
        channel: MIDI channel
        color: RGB color tuple (0-127)

    Returns:
        Configured Track instance
    """
    from core.track import Track

    return Track(
        name=name,
        color=color,
        midi_channel=channel,
    )


def run_circuit_tests():
    """Run all circuit tests and return results."""
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(__file__), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    run_circuit_tests()
