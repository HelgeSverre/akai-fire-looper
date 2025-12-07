"""
Test fixtures and factories for AKAI Fire testing.

This module provides convenient factory functions for creating
pre-configured test objects.

Functions:
    create_test_fire: Create MockAkaiFire with optional MockMidiManager
    create_test_canvas: Create MockCanvas with optional content
    create_test_timing: Create ControllableTimingEngine
"""

from typing import Tuple, Optional, List, Callable, Any

from .mocks import MockAkaiFire, MockCanvas
from .midi import MockMidiManager
from .timing import ControllableTimingEngine


def create_test_fire(
    with_midi: bool = True,
) -> Tuple[MockAkaiFire, Optional[MockMidiManager]]:
    """
    Create a configured MockAkaiFire for testing.

    Args:
        with_midi: If True, also create MockMidiManager

    Returns:
        Tuple of (MockAkaiFire, MockMidiManager) or (MockAkaiFire, None)

    Example:
        >>> fire, midi = create_test_fire()
        >>> fire.simulate_pad_press(5)
        >>> midi.assert_note_on(channel=1, note=60, velocity=100)
    """
    fire = MockAkaiFire()
    midi = MockMidiManager() if with_midi else None
    return fire, midi


def create_test_canvas(
    width: int = 128,
    height: int = 64,
    with_content: Optional[str] = None,
) -> MockCanvas:
    """
    Create a MockCanvas for testing.

    Args:
        width: Canvas width (default 128)
        height: Canvas height (default 64)
        with_content: Optional initial text content

    Returns:
        Configured MockCanvas

    Example:
        >>> canvas = create_test_canvas(with_content="Hello World")
        >>> assert canvas.text_drawn[0][0] == "Hello World"
    """
    canvas = MockCanvas(width=width, height=height)
    if with_content:
        canvas.draw_text(with_content, 10, 10)
    return canvas


def create_test_timing(
    bpm: float = 120.0,
    steps: int = 16,
    auto_start: bool = False,
) -> ControllableTimingEngine:
    """
    Create a ControllableTimingEngine for testing.

    Args:
        bpm: Beats per minute
        steps: Total steps per pattern
        auto_start: If True, start playback immediately

    Returns:
        Configured ControllableTimingEngine

    Example:
        >>> timing = create_test_timing(bpm=140, auto_start=True)
        >>> timing.advance_step()  # Fires callbacks
    """
    timing = ControllableTimingEngine(bpm=bpm, total_steps=steps)
    if auto_start:
        timing.start_playback()
    return timing


def create_test_midi() -> MockMidiManager:
    """
    Create a MockMidiManager for testing.

    Returns:
        Configured MockMidiManager

    Example:
        >>> midi = create_test_midi()
        >>> midi.send_note_on(1, 60, 100)
        >>> assert len(midi.get_notes_on()) == 1
    """
    return MockMidiManager()


def create_test_environment() -> (
    Tuple[MockAkaiFire, MockMidiManager, ControllableTimingEngine]
):
    """
    Create a complete test environment with all components.

    Returns:
        Tuple of (MockAkaiFire, MockMidiManager, ControllableTimingEngine)

    Example:
        >>> fire, midi, timing = create_test_environment()
        >>> # Now you can test sequencer with all components
    """
    fire = MockAkaiFire()
    midi = MockMidiManager()
    timing = ControllableTimingEngine()
    timing.start_playback()
    return fire, midi, timing


class TestHarness:
    """
    Complete test harness with all components wired together.

    Provides a convenient way to set up and tear down test environment.

    Attributes:
        fire: MockAkaiFire instance
        midi: MockMidiManager instance
        timing: ControllableTimingEngine instance
        canvas: Shortcut to fire.get_canvas()

    Example:
        >>> harness = TestHarness()
        >>> harness.fire.simulate_pad_press(0)
        >>> harness.advance(4)  # Advance 4 steps
        >>> harness.assert_notes_played([(60, 100)])
    """

    def __init__(
        self,
        bpm: float = 120.0,
        steps: int = 16,
        auto_start_timing: bool = True,
    ):
        """
        Initialize test harness.

        Args:
            bpm: Timing BPM
            steps: Steps per pattern
            auto_start_timing: Start timing automatically
        """
        self.fire = MockAkaiFire()
        self.midi = MockMidiManager()
        self.timing = ControllableTimingEngine(bpm=bpm, total_steps=steps)

        if auto_start_timing:
            self.timing.start_playback()

    @property
    def canvas(self) -> MockCanvas:
        """Get the canvas from fire controller."""
        return self.fire.get_canvas()

    def advance(self, steps: int = 1) -> List[int]:
        """
        Advance timing by specified steps.

        Args:
            steps: Number of steps to advance

        Returns:
            List of step numbers executed
        """
        return self.timing.advance_steps(steps)

    def advance_bar(self) -> List[int]:
        """Advance one complete bar."""
        return self.timing.advance_one_bar()

    def press_pad(self, pad: int, velocity: int = 100):
        """Simulate pad press."""
        self.fire.simulate_pad_press(pad, velocity)

    def press_button(self, button: int):
        """Simulate button press."""
        self.fire.simulate_button_press(button)

    def turn_rotary(self, rotary: int, direction: str, velocity: int = 1):
        """Simulate rotary turn."""
        self.fire.simulate_rotary_turn(rotary, direction, velocity)

    def reset(self):
        """Reset all state for fresh test."""
        self.fire.clear_all()
        self.fire.reset_event_history()
        self.midi.clear_messages()
        self.timing.reset()
        self.timing.start_playback()

    # Assertion shortcuts
    def assert_notes_played(self, expected: List[Tuple[int, int]]):
        """Assert specific notes were played."""
        actual = self.midi.get_notes_on()
        assert actual == expected, f"Expected notes {expected}, got {actual}"

    def assert_pad_lit(self, pad: int):
        """Assert pad is lit (not black)."""
        self.fire.assert_pad_not_black(pad)

    def assert_screen_shows(self, text: str):
        """Assert screen contains text."""
        for drawn, x, y in self.canvas.text_drawn:
            if text in drawn:
                return
        raise AssertionError(f"Screen doesn't contain '{text}'")


def create_step_recorder() -> Tuple[Callable[[int], None], List[int]]:
    """
    Create a step callback that records all steps.

    Returns:
        Tuple of (callback_function, recorded_steps_list)

    Example:
        >>> callback, steps = create_step_recorder()
        >>> timing.add_step_callback(callback)
        >>> timing.advance_steps(4)
        >>> assert steps == [0, 1, 2, 3]
    """
    recorded: List[int] = []

    def callback(step: int):
        recorded.append(step)

    return callback, recorded


def create_note_recorder(midi: MockMidiManager) -> Callable[[], List[Tuple[int, int]]]:
    """
    Create a function that returns notes played since last call.

    Args:
        midi: MockMidiManager to monitor

    Returns:
        Function that returns new notes since last call

    Example:
        >>> get_new_notes = create_note_recorder(midi)
        >>> midi.send_note_on(1, 60, 100)
        >>> assert get_new_notes() == [(60, 100)]
        >>> midi.send_note_on(1, 64, 100)
        >>> assert get_new_notes() == [(64, 100)]
    """
    last_count = [0]  # Use list for closure mutability

    def get_new_notes() -> List[Tuple[int, int]]:
        all_notes = midi.get_notes_on()
        new_notes = all_notes[last_count[0] :]
        last_count[0] = len(all_notes)
        return new_notes

    return get_new_notes


# =============================================================================
# Pattern Testing Helpers
# =============================================================================


def create_step_pattern(lit_steps: List[int], total_steps: int = 16) -> List[bool]:
    """
    Create a boolean pattern for step assertions.

    Args:
        lit_steps: List of step indices that should be lit
        total_steps: Total steps in pattern

    Returns:
        List of booleans (True = lit, False = off)

    Example:
        >>> pattern = create_step_pattern([0, 4, 8, 12])
        >>> # [True, False, False, False, True, False, ...]
    """
    return [i in lit_steps for i in range(total_steps)]


def create_drum_pattern(
    kick: List[int] = None,
    snare: List[int] = None,
    hihat: List[int] = None,
    steps: int = 16,
) -> dict:
    """
    Create a drum pattern specification.

    Args:
        kick: Steps with kick drum
        snare: Steps with snare
        hihat: Steps with hi-hat
        steps: Total steps

    Returns:
        Dictionary with drum patterns

    Example:
        >>> pattern = create_drum_pattern(
        ...     kick=[0, 8],
        ...     snare=[4, 12],
        ...     hihat=[0, 2, 4, 6, 8, 10, 12, 14]
        ... )
    """
    return {
        "kick": kick or [],
        "snare": snare or [],
        "hihat": hihat or [],
        "total_steps": steps,
    }
