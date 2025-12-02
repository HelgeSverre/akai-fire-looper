"""
Pattern and Step data structures for MIDI sequencing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import copy


@dataclass
class Step:
    """
    A single step in a pattern containing MIDI data.
    Each step can contain multiple notes (polyphonic).
    """

    notes: List[int] = field(default_factory=list)  # MIDI note numbers (polyphonic)
    velocities: List[int] = field(default_factory=list)  # Per-note velocities
    gate_length: float = 0.75  # 0.0-1.0 (percentage of step)
    probability: float = 1.0  # 0.0-1.0 (trigger probability)
    micro_timing: int = 0  # -6 to +6 (micro-step offset)
    enabled: bool = True  # Step on/off

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary for saving."""
        return {
            "name": self.name,
            "length": self.length,
            "steps": [
                {
                    "notes": step.notes.copy(),
                    "velocities": step.velocities.copy(),
                    "gate_length": step.gate_length,
                    "probability": step.probability,
                    "micro_timing": step.micro_timing,
                    "enabled": step.enabled,
                }
                for step in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        """Create pattern from dictionary data."""
        pattern = cls(name=data.get("name", "Pattern"), length=data.get("length", 16))

        steps_data = data.get("steps", [])
        pattern.steps = []

        for step_data in steps_data:
            step = Step(
                notes=step_data.get("notes", []),
                velocities=step_data.get("velocities", []),
                gate_length=step_data.get("gate_length", 0.75),
                probability=step_data.get("probability", 1.0),
                micro_timing=step_data.get("micro_timing", 0),
                enabled=step_data.get("enabled", True),
            )
            pattern.steps.append(step)

        return pattern
