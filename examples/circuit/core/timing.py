"""
Timing engine for precise MIDI sequencing.
Handles BPM, swing, quantization, and step timing calculations.
"""

import time
import threading
from typing import Callable, Optional, List
from enum import Enum


class QuantizationMode(Enum):
    """Quantization options for recording and playback."""

    OFF = "OFF"
    QUARTER = "1/4"
    EIGHTH = "1/8"
    SIXTEENTH = "1/16"
    THIRTY_SECOND = "1/32"


class TimingEngine:
    """
    Manages timing for MIDI sequencing with precise BPM control.
    Handles swing, quantization, and step timing calculations.
    """

    def __init__(self, bpm: float = 120.0):
        self.bpm = bpm
        self.swing = 0.0  # 0.0 to 0.75 (0% to 75%)
        self.quantization = QuantizationMode.SIXTEENTH

        # Timing calculations
        self._update_timing_values()

        # Playback state
        self.is_playing = False
        self.start_time = 0.0
        self.current_step = 0
        self.step_callbacks: list[Callable[[int], None]] = []

        # Internal timer thread
        self._timer_thread = None
        self._stop_timer = threading.Event()
        self._lock = threading.Lock()

        # Tap tempo state
        self._tap_times: list[float] = []
        self._tap_timeout = 2.0  # Seconds before tap history resets
        self._max_taps = 5  # Number of taps to average

    def _update_timing_values(self):
        """Update internal timing calculations when BPM or swing changes."""
        # Basic timing calculations
        self.beat_duration = 60.0 / self.bpm  # Duration of one quarter note in seconds
        self.step_duration = self.beat_duration / 4.0  # 16th note duration
        self.bar_duration = self.beat_duration * 4.0  # 4/4 bar duration

        # Swing timing (applies to off-beats)
        self.swing_offset = self.step_duration * self.swing

    def set_bpm(self, bpm: float):
        """Set the BPM (30-300 range)."""
        self.bpm = max(30.0, min(300.0, bpm))
        self._update_timing_values()

    def get_bpm(self) -> float:
        """Get current BPM."""
        return self.bpm

    def set_swing(self, swing: float):
        """Set swing amount (0.0 to 0.75)."""
        self.swing = max(0.0, min(0.75, swing))
        self._update_timing_values()

    def get_swing(self) -> float:
        """Get current swing amount."""
        return self.swing

    def tap_tempo(self) -> Optional[float]:
        """
        Register a tap for tap tempo detection.
        Returns the calculated BPM if enough taps have been registered, None otherwise.

        Usage: Call this method each time the user taps. After 2+ taps,
        it will calculate and set the BPM based on the average interval.
        """
        current_time = time.time()

        # Clear old taps if too much time has passed
        if self._tap_times and (current_time - self._tap_times[-1]) > self._tap_timeout:
            self._tap_times.clear()

        # Add current tap
        self._tap_times.append(current_time)

        # Keep only the last N taps
        if len(self._tap_times) > self._max_taps:
            self._tap_times.pop(0)

        # Need at least 2 taps to calculate BPM
        if len(self._tap_times) < 2:
            return None

        # Calculate average interval between taps
        intervals = []
        for i in range(1, len(self._tap_times)):
            intervals.append(self._tap_times[i] - self._tap_times[i - 1])

        avg_interval = sum(intervals) / len(intervals)

        # Convert to BPM (interval is in seconds, for quarter notes)
        if avg_interval > 0:
            new_bpm = 60.0 / avg_interval
            # Clamp to valid range
            new_bpm = max(30.0, min(300.0, new_bpm))
            self.set_bpm(new_bpm)
            return new_bpm

        return None

    def reset_tap_tempo(self):
        """Clear tap tempo history."""
        self._tap_times.clear()

    def set_quantization(self, quantization: QuantizationMode):
        """Set quantization mode."""
        self.quantization = quantization

    def get_quantization(self) -> QuantizationMode:
        """Get current quantization mode."""
        return self.quantization

    def get_step_time(self, step_number: int, pattern_length: int = 16) -> float:
        """
        Get the precise time offset for a step within a pattern.
        Takes swing into account for off-beat steps.
        """
        base_time = (step_number % pattern_length) * self.step_duration

        # Apply swing to off-beat steps (steps 1, 3, 5, 7, 9, 11, 13, 15)
        if self.swing > 0.0 and (step_number % 2) == 1:
            base_time += self.swing_offset

        return base_time

    def get_current_playback_time(self) -> float:
        """Get the current playback time since start."""
        if not self.is_playing:
            return 0.0
        return time.time() - self.start_time

    def get_current_step_info(self, pattern_length: int = 16) -> tuple[int, float]:
        """
        Get current step number and position within step.
        Returns (step_number, step_position) where step_position is 0.0-1.0.
        """
        if not self.is_playing:
            return 0, 0.0

        current_time = self.get_current_playback_time()

        # Calculate which step we're in
        step_number = 0
        accumulated_time = 0.0

        for step in range(pattern_length * 4):  # Check multiple loops
            step_duration = self.get_step_duration(step)
            if accumulated_time + step_duration > current_time:
                # Found the current step
                step_position = (current_time - accumulated_time) / step_duration
                return step % pattern_length, step_position
            accumulated_time += step_duration

        # Fallback
        return 0, 0.0

    def get_step_duration(self, step_number: int) -> float:
        """Get the duration of a specific step (accounting for swing)."""
        if self.swing > 0.0 and (step_number % 2) == 0:
            # On-beat steps are shortened by swing amount
            return self.step_duration - (self.swing_offset / 2)
        elif self.swing > 0.0 and (step_number % 2) == 1:
            # Off-beat steps are lengthened by swing amount
            return self.step_duration + (self.swing_offset / 2)
        else:
            # No swing or straight timing
            return self.step_duration

    def quantize_time_to_step(self, time_offset: float) -> int:
        """Quantize a time offset to the nearest step boundary."""
        if self.quantization == QuantizationMode.OFF:
            return 0

        # Get step resolution based on quantization
        steps_per_beat = {
            QuantizationMode.QUARTER: 1,
            QuantizationMode.EIGHTH: 2,
            QuantizationMode.SIXTEENTH: 4,
            QuantizationMode.THIRTY_SECOND: 8,
        }.get(self.quantization, 4)

        step_duration = self.beat_duration / steps_per_beat
        return round(time_offset / step_duration)

    def get_next_quantized_time(self, current_time: float) -> float:
        """Get the next quantized time boundary."""
        if self.quantization == QuantizationMode.OFF:
            return current_time

        # Get step resolution
        steps_per_beat = {
            QuantizationMode.QUARTER: 1,
            QuantizationMode.EIGHTH: 2,
            QuantizationMode.SIXTEENTH: 4,
            QuantizationMode.THIRTY_SECOND: 8,
        }.get(self.quantization, 4)

        step_duration = self.beat_duration / steps_per_beat
        next_step = int(current_time / step_duration) + 1
        return next_step * step_duration

    def start_playback(self):
        """Start the timing engine."""
        with self._lock:
            if not self.is_playing:
                self.is_playing = True
                self.start_time = time.time()
                self.current_step = 0
                self._stop_timer.clear()

                # Start timer thread
                self._timer_thread = threading.Thread(
                    target=self._timer_loop, daemon=True
                )
                self._timer_thread.start()

    def stop_playback(self):
        """Stop the timing engine."""
        with self._lock:
            if self.is_playing:
                self.is_playing = False
                self._stop_timer.set()

                if self._timer_thread:
                    self._timer_thread.join(timeout=1.0)
                    self._timer_thread = None

    def _timer_loop(self):
        """Internal timer loop that triggers step callbacks."""
        last_step = -1

        while not self._stop_timer.is_set():
            if self.is_playing:
                current_step, _ = self.get_current_step_info()

                # Trigger callbacks when step changes
                if current_step != last_step:
                    last_step = current_step
                    self._trigger_step_callbacks(current_step)

            # Sleep for high precision timing (1ms resolution)
            time.sleep(0.001)

    def _trigger_step_callbacks(self, step: int):
        """Trigger all registered step callbacks."""
        for callback in self.step_callbacks:
            try:
                callback(step)
            except Exception as e:
                print(f"Error in step callback: {e}")

    def add_step_callback(self, callback: Callable[[int], None]):
        """Add a callback that gets called on each step."""
        if callback not in self.step_callbacks:
            self.step_callbacks.append(callback)

    def remove_step_callback(self, callback: Callable[[int], None]):
        """Remove a step callback."""
        if callback in self.step_callbacks:
            self.step_callbacks.remove(callback)

    def get_bar_info(self) -> tuple[int, int, float]:
        """
        Get current bar, beat, and beat position.
        Returns (bar_number, beat_number, beat_position).
        """
        if not self.is_playing:
            return 1, 1, 0.0

        current_time = self.get_current_playback_time()

        # Calculate bar and beat
        bar_number = int(current_time // self.bar_duration) + 1
        time_in_bar = current_time % self.bar_duration
        beat_number = int(time_in_bar // self.beat_duration) + 1
        beat_position = (time_in_bar % self.beat_duration) / self.beat_duration

        return bar_number, beat_number, beat_position

    def get_timing_info(self) -> dict:
        """Get comprehensive timing information."""
        if self.is_playing:
            bar, beat, beat_pos = self.get_bar_info()
            step, step_pos = self.get_current_step_info()
            playback_time = self.get_current_playback_time()
        else:
            bar = beat = step = 1
            beat_pos = step_pos = playback_time = 0.0

        return {
            "bpm": self.bpm,
            "swing": self.swing,
            "quantization": self.quantization.value,
            "is_playing": self.is_playing,
            "bar": bar,
            "beat": beat,
            "beat_position": beat_pos,
            "step": step,
            "step_position": step_pos,
            "playback_time": playback_time,
        }
