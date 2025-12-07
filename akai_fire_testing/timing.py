"""
Timing control utilities for testing sequencers.

This module provides a controllable timing engine that can be manually
advanced for deterministic testing without real-time delays.

Classes:
    ControllableTimingEngine: Timing engine with manual step control
"""

from typing import List, Dict, Callable, Any, Optional
from dataclasses import dataclass


@dataclass
class StepEvent:
    """Recorded step event for debugging."""

    step: int
    callback_count: int


class ControllableTimingEngine:
    """
    A timing engine that can be manually advanced for testing.

    Instead of using real time, this allows tests to control exactly
    when steps occur, making tests deterministic and fast.

    Features:
        - Manual step advancement (no real-time delays)
        - Callbacks work the same as real timing
        - Step history for debugging
        - Compatible API with real timing engines

    Example:
        >>> timing = ControllableTimingEngine(bpm=120)
        >>> steps_fired = []
        >>> timing.add_step_callback(lambda step: steps_fired.append(step))
        >>> timing.start_playback()
        >>> timing.advance_step()  # Step 0
        >>> timing.advance_step()  # Step 1
        >>> timing.advance_step()  # Step 2
        >>> assert steps_fired == [0, 1, 2]
    """

    def __init__(
        self, bpm: float = 120.0, steps_per_beat: int = 4, total_steps: int = 16
    ):
        """
        Initialize timing engine.

        Args:
            bpm: Beats per minute (30-300)
            steps_per_beat: Steps per beat (default 4 for 16th notes)
            total_steps: Total steps in a pattern (default 16)
        """
        self._bpm = max(30.0, min(300.0, bpm))
        self._steps_per_beat = steps_per_beat
        self._total_steps = total_steps
        self._step = 0
        self._playing = False
        self._step_callbacks: List[Callable[[int], None]] = []
        self._beat_callbacks: List[Callable[[int], None]] = []
        self._bar_callbacks: List[Callable[[int], None]] = []
        self._step_history: List[StepEvent] = []

    # =========================================================================
    # BPM Control
    # =========================================================================

    def set_bpm(self, bpm: float):
        """
        Set BPM (clamped to 30-300).

        Args:
            bpm: Beats per minute
        """
        self._bpm = max(30.0, min(300.0, bpm))

    def get_bpm(self) -> float:
        """
        Get current BPM.

        Returns:
            Current BPM
        """
        return self._bpm

    def adjust_bpm(self, delta: float):
        """
        Adjust BPM by delta.

        Args:
            delta: Amount to add (can be negative)
        """
        self.set_bpm(self._bpm + delta)

    # =========================================================================
    # Playback Control
    # =========================================================================

    def start_playback(self):
        """Start playback."""
        self._playing = True

    def stop_playback(self):
        """Stop playback and reset step to 0."""
        self._playing = False
        self._step = 0

    def pause_playback(self):
        """Pause playback without resetting step."""
        self._playing = False

    def toggle_playback(self):
        """Toggle playback state."""
        if self._playing:
            self.stop_playback()
        else:
            self.start_playback()

    def is_playing(self) -> bool:
        """Check if playing."""
        return self._playing

    # =========================================================================
    # Callback Registration
    # =========================================================================

    def add_step_callback(self, callback: Callable[[int], None]):
        """
        Add step callback.

        Args:
            callback: Function called with step number on each step
        """
        self._step_callbacks.append(callback)

    def add_beat_callback(self, callback: Callable[[int], None]):
        """
        Add beat callback.

        Args:
            callback: Function called with beat number on each beat
        """
        self._beat_callbacks.append(callback)

    def add_bar_callback(self, callback: Callable[[int], None]):
        """
        Add bar callback.

        Args:
            callback: Function called with bar number on each bar
        """
        self._bar_callbacks.append(callback)

    def remove_step_callback(self, callback: Callable[[int], None]):
        """Remove a step callback."""
        if callback in self._step_callbacks:
            self._step_callbacks.remove(callback)

    def clear_callbacks(self):
        """Clear all callbacks."""
        self._step_callbacks.clear()
        self._beat_callbacks.clear()
        self._bar_callbacks.clear()

    # =========================================================================
    # Test Control (Manual Advancement)
    # =========================================================================

    def advance_step(self) -> int:
        """
        Manually advance to next step and fire callbacks.

        This is the key method for testing - it advances the sequencer
        one step at a time, synchronously firing all callbacks.

        Returns:
            The step that was executed
        """
        if not self._playing:
            return -1

        current_step = self._step

        # Fire step callbacks
        for callback in self._step_callbacks:
            callback(current_step)

        # Check for beat (every steps_per_beat steps)
        if current_step % self._steps_per_beat == 0:
            beat = current_step // self._steps_per_beat
            for callback in self._beat_callbacks:
                callback(beat)

        # Check for bar (every total_steps)
        if current_step == 0:
            for callback in self._bar_callbacks:
                callback(0)

        # Record history
        self._step_history.append(StepEvent(current_step, len(self._step_callbacks)))

        # Advance to next step
        self._step = (self._step + 1) % self._total_steps

        return current_step

    def advance_steps(self, count: int) -> List[int]:
        """
        Advance multiple steps.

        Args:
            count: Number of steps to advance

        Returns:
            List of step numbers that were executed
        """
        steps_executed = []
        for _ in range(count):
            step = self.advance_step()
            if step >= 0:
                steps_executed.append(step)
        return steps_executed

    def advance_to_step(self, target_step: int) -> List[int]:
        """
        Advance until reaching a specific step.

        Args:
            target_step: Step to advance to (0 to total_steps-1)

        Returns:
            List of steps executed
        """
        steps_executed = []
        max_iterations = self._total_steps * 2  # Safety limit

        for _ in range(max_iterations):
            if self._step == target_step:
                break
            step = self.advance_step()
            if step >= 0:
                steps_executed.append(step)

        return steps_executed

    def advance_one_bar(self) -> List[int]:
        """
        Advance through one complete bar/pattern.

        Returns:
            List of all steps executed
        """
        return self.advance_steps(self._total_steps)

    # =========================================================================
    # State Queries
    # =========================================================================

    def get_current_step(self) -> int:
        """
        Get current step (next step to be played).

        Returns:
            Current step number
        """
        return self._step

    def set_current_step(self, step: int):
        """
        Set current step (for testing).

        Args:
            step: Step number to set
        """
        self._step = step % self._total_steps

    def get_total_steps(self) -> int:
        """Get total steps per pattern."""
        return self._total_steps

    def get_steps_per_beat(self) -> int:
        """Get steps per beat."""
        return self._steps_per_beat

    def get_timing_info(self) -> Dict[str, Any]:
        """
        Get comprehensive timing info.

        Returns:
            Dictionary with all timing state
        """
        return {
            "bpm": self._bpm,
            "step": self._step,
            "is_playing": self._playing,
            "total_steps": self._total_steps,
            "steps_per_beat": self._steps_per_beat,
            "step_duration_ms": self._calculate_step_duration_ms(),
            "beat_duration_ms": self._calculate_step_duration_ms()
            * self._steps_per_beat,
            "bar_duration_ms": self._calculate_step_duration_ms() * self._total_steps,
        }

    def _calculate_step_duration_ms(self) -> float:
        """Calculate step duration in milliseconds."""
        beat_duration_ms = 60000.0 / self._bpm
        return beat_duration_ms / self._steps_per_beat

    # =========================================================================
    # History and Debug
    # =========================================================================

    def get_step_history(self) -> List[int]:
        """
        Get list of all steps that have been executed.

        Returns:
            List of step numbers in order
        """
        return [event.step for event in self._step_history]

    def clear_history(self):
        """Clear step history."""
        self._step_history.clear()

    def reset(self):
        """Reset all state."""
        self._step = 0
        self._playing = False
        self._step_history.clear()

    # =========================================================================
    # Assertion Helpers
    # =========================================================================

    def assert_at_step(self, expected: int):
        """
        Assert current step.

        Args:
            expected: Expected step number

        Raises:
            AssertionError: If step doesn't match
        """
        actual = self._step
        assert actual == expected, f"Expected at step {expected}, but at {actual}"

    def assert_step_history(self, expected: List[int]):
        """
        Assert step history matches expected sequence.

        Args:
            expected: Expected list of step numbers

        Raises:
            AssertionError: If history doesn't match
        """
        actual = self.get_step_history()
        assert actual == expected, f"Expected step history {expected}, got {actual}"
