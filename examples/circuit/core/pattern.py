"""
Pattern and Step data structures for MIDI sequencing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import copy
import random


class PlayOrder(Enum):
    """Pattern playback order modes."""
    FORWARD = "forward"      # Play steps 0 -> length-1
    REVERSE = "reverse"      # Play steps length-1 -> 0
    PING_PONG = "ping_pong"  # Play 0 -> length-1 -> 0 ...
    RANDOM = "random"        # Random step order


class SyncRate(Enum):
    """Pattern sync rates relative to BPM (step duration multipliers)."""
    QUARTER = "1/4"          # 4x slower (quarter notes)
    QUARTER_T = "1/4T"       # Quarter triplets
    EIGHTH = "1/8"           # 2x slower (eighth notes)
    EIGHTH_T = "1/8T"        # Eighth triplets
    SIXTEENTH = "1/16"       # Default (sixteenth notes)
    SIXTEENTH_T = "1/16T"    # Sixteenth triplets
    THIRTY_SECOND = "1/32"   # 2x faster
    THIRTY_SECOND_T = "1/32T"  # Thirty-second triplets

    def get_multiplier(self) -> float:
        """Get the step duration multiplier for this sync rate."""
        multipliers = {
            SyncRate.QUARTER: 4.0,
            SyncRate.QUARTER_T: 4.0 * 2/3,
            SyncRate.EIGHTH: 2.0,
            SyncRate.EIGHTH_T: 2.0 * 2/3,
            SyncRate.SIXTEENTH: 1.0,
            SyncRate.SIXTEENTH_T: 1.0 * 2/3,
            SyncRate.THIRTY_SECOND: 0.5,
            SyncRate.THIRTY_SECOND_T: 0.5 * 2/3,
        }
        return multipliers.get(self, 1.0)


@dataclass
class Step:
    """
    A single step in a pattern containing MIDI data.
    Each step can contain multiple notes (polyphonic).
    """

    notes: List[int] = field(default_factory=list)  # MIDI note numbers (polyphonic)
    velocities: List[int] = field(default_factory=list)  # Per-note velocities
    gate_length: float = 1.0  # Duration in steps (0.167 = 1/6 step, 16.0 = tie across 16 steps)
    probability: float = 1.0  # 0.0-1.0 (trigger probability)
    micro_timing: int = 0  # -6 to +6 (micro-step offset)
    enabled: bool = True  # Step on/off
    tie_forward: bool = False  # If True, note ties to next step (legato)

    def add_note(self, note: int, velocity: int = 85):
        """Add a MIDI note to this step."""
        if note not in self.notes:
            self.notes.append(note)
            self.velocities.append(velocity)
        else:
            # Update velocity if note already exists
            idx = self.notes.index(note)
            self.velocities[idx] = velocity

    def remove_note(self, note: int):
        """Remove a MIDI note from this step."""
        if note in self.notes:
            idx = self.notes.index(note)
            self.notes.pop(idx)
            self.velocities.pop(idx)

    def clear_notes(self):
        """Clear all notes from this step."""
        self.notes.clear()
        self.velocities.clear()

    def has_notes(self) -> bool:
        """Check if this step has any notes."""
        return len(self.notes) > 0 and self.enabled

    def get_notes_with_velocities(self) -> List[tuple]:
        """Get list of (note, velocity) tuples."""
        return list(zip(self.notes, self.velocities))


@dataclass
class Pattern:
    """
    A pattern containing multiple steps for MIDI sequencing.
    Can be 1-32 steps long with configurable properties.
    """

    steps: List[Step] = field(default_factory=lambda: [Step() for _ in range(16)])
    length: int = 16  # Actual pattern length (1-32)
    name: str = "Pattern"  # User-definable pattern name
    start_point: int = 0  # Step to start playback from (0 to length-1)
    end_point: Optional[int] = None  # Step to end playback at (None = length-1)
    play_order: PlayOrder = PlayOrder.FORWARD  # Playback direction
    sync_rate: SyncRate = SyncRate.SIXTEENTH  # Step timing relative to BPM

    # Ping-pong state tracking (not serialized)
    _ping_pong_direction: int = field(default=1, repr=False)

    def __post_init__(self):
        """Ensure we have the correct number of steps."""
        if len(self.steps) < self.length:
            # Add missing steps
            while len(self.steps) < self.length:
                self.steps.append(Step())
        elif len(self.steps) > self.length:
            # Trim excess steps (but keep the data in case length increases later)
            pass

    def set_length(self, new_length: int):
        """Change the pattern length (1-32 steps)."""
        new_length = max(1, min(32, new_length))

        if new_length > len(self.steps):
            # Add new steps
            while len(self.steps) < new_length:
                self.steps.append(Step())

        self.length = new_length

    def get_step(self, step_index: int) -> Step:
        """Get a step by index (0-based)."""
        if 0 <= step_index < len(self.steps):
            return self.steps[step_index]
        return Step()  # Return empty step for invalid index

    def clear_step(self, step_index: int):
        """Clear all notes from a specific step."""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].clear_notes()

    def clear_all_steps(self):
        """Clear all notes from all steps."""
        for step in self.steps:
            step.clear_notes()

    def copy_step(self, from_index: int, to_index: int):
        """Copy one step to another."""
        if 0 <= from_index < len(self.steps) and 0 <= to_index < len(self.steps):
            self.steps[to_index] = copy.deepcopy(self.steps[from_index])

    def has_content(self) -> bool:
        """Check if pattern has any notes in any steps."""
        return any(step.has_notes() for step in self.steps[: self.length])

    def get_active_steps(self) -> List[int]:
        """Get list of step indices that have notes."""
        return [
            i for i, step in enumerate(self.steps[: self.length]) if step.has_notes()
        ]

    def get_effective_end_point(self) -> int:
        """Get the effective end point (end_point if set, otherwise length-1)."""
        if self.end_point is not None:
            return min(self.end_point, self.length - 1)
        return self.length - 1

    def get_playback_length(self) -> int:
        """Get the number of steps in the playback range."""
        return self.get_effective_end_point() - self.start_point + 1

    def get_next_step(self, current_step: int) -> int:
        """
        Get the next step to play based on play_order.

        Args:
            current_step: The current step index

        Returns:
            The next step index to play
        """
        start = self.start_point
        end = self.get_effective_end_point()
        playback_length = end - start + 1

        if self.play_order == PlayOrder.FORWARD:
            next_step = current_step + 1
            if next_step > end:
                return start
            return next_step

        elif self.play_order == PlayOrder.REVERSE:
            next_step = current_step - 1
            if next_step < start:
                return end
            return next_step

        elif self.play_order == PlayOrder.PING_PONG:
            next_step = current_step + self._ping_pong_direction
            if next_step > end:
                self._ping_pong_direction = -1
                return end - 1 if end > start else start
            elif next_step < start:
                self._ping_pong_direction = 1
                return start + 1 if start < end else end
            return next_step

        elif self.play_order == PlayOrder.RANDOM:
            return random.randint(start, end)

        return start  # Fallback

    def get_first_step(self) -> int:
        """Get the first step for playback based on play_order."""
        if self.play_order == PlayOrder.REVERSE:
            return self.get_effective_end_point()
        return self.start_point

    def mutate(self):
        """
        Shuffle notes/hits to different steps while preserving note data.
        All step parameters are reassigned (micro-timing, gate, probability, etc).
        """
        start = self.start_point
        end = self.get_effective_end_point()

        # Get steps in the playback range that have content
        active_indices = [
            i for i in range(start, end + 1)
            if self.steps[i].has_notes()
        ]

        if len(active_indices) < 2:
            return  # Nothing to mutate

        # Collect the step data from active steps
        active_steps = [copy.deepcopy(self.steps[i]) for i in active_indices]

        # Shuffle the step data
        random.shuffle(active_steps)

        # Reassign to the same indices
        for idx, step_data in zip(active_indices, active_steps):
            self.steps[idx] = step_data

    def reset_ping_pong(self):
        """Reset ping-pong direction to forward."""
        self._ping_pong_direction = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary for saving."""
        return {
            "name": self.name,
            "length": self.length,
            "start_point": self.start_point,
            "end_point": self.end_point,
            "play_order": self.play_order.value,
            "sync_rate": self.sync_rate.value,
            "steps": [
                {
                    "notes": step.notes.copy(),
                    "velocities": step.velocities.copy(),
                    "gate_length": step.gate_length,
                    "probability": step.probability,
                    "micro_timing": step.micro_timing,
                    "enabled": step.enabled,
                    "tie_forward": step.tie_forward,
                }
                for step in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        """Create pattern from dictionary data."""
        # Parse play_order from string
        play_order_str = data.get("play_order", "forward")
        try:
            play_order = PlayOrder(play_order_str)
        except ValueError:
            play_order = PlayOrder.FORWARD

        # Parse sync_rate from string
        sync_rate_str = data.get("sync_rate", "1/16")
        try:
            sync_rate = SyncRate(sync_rate_str)
        except ValueError:
            sync_rate = SyncRate.SIXTEENTH

        pattern = cls(
            name=data.get("name", "Pattern"),
            length=data.get("length", 16),
            start_point=data.get("start_point", 0),
            end_point=data.get("end_point"),  # Can be None
            play_order=play_order,
            sync_rate=sync_rate,
        )

        steps_data = data.get("steps", [])
        pattern.steps = []

        for step_data in steps_data:
            step = Step(
                notes=step_data.get("notes", []),
                velocities=step_data.get("velocities", []),
                gate_length=step_data.get("gate_length", 1.0),
                probability=step_data.get("probability", 1.0),
                micro_timing=step_data.get("micro_timing", 0),
                enabled=step_data.get("enabled", True),
                tie_forward=step_data.get("tie_forward", False),
            )
            pattern.steps.append(step)

        return pattern
