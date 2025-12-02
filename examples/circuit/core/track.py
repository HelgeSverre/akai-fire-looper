"""
Track management for MIDI sequencing.
Each track represents one MIDI channel output stream.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any
from core.pattern import Pattern


@dataclass
class Track:
    """
    A MIDI track containing patterns and MIDI routing configuration.
    Each track outputs to a specific MIDI channel and can control external hardware synths.
    """

    name: str = "Track"  # Track name
    color: Tuple[int, int, int] = (127, 127, 127)  # RGB color (0-127)
    midi_channel: int = 1  # 1-16 MIDI channel
    midi_port: str = ""  # MIDI port name
    patterns: List[Pattern] = field(
        default_factory=lambda: [Pattern(name=f"Pattern {i+1}") for i in range(8)]
    )  # 8 patterns per track
    current_pattern: int = 0  # Currently playing pattern (0-7)
    pattern_chain: List[int] = field(default_factory=list)  # Pattern chain sequence
    enabled: bool = True  # Track MIDI output enabled/disabled
    soloed: bool = False  # Track solo state (disables other tracks)
    scale: str = "MAJOR"  # Musical scale for input
    root_note: int = 60  # Root note (MIDI note number, 60 = C4)
    octave: int = 0  # Octave offset (-5 to +5)
    note_range: Tuple[int, int] = (0, 127)  # MIDI note range limits (min, max)
    cc_assignments: Dict[str, int] = field(
        default_factory=dict
    )  # CC mappings for hardware control

    def __post_init__(self):
        """Initialize default CC assignments."""
        if not self.cc_assignments:
            self.cc_assignments = {
                "volume": 7,  # CC7 - Channel Volume
                "pan": 10,  # CC10 - Pan
                "expression": 11,  # CC11 - Expression
                "filter": 74,  # CC74 - Filter Cutoff (common)
            }

    def get_current_pattern(self) -> Pattern:
        """Get the currently selected pattern."""
        if 0 <= self.current_pattern < len(self.patterns):
            return self.patterns[self.current_pattern]
        return Pattern()  # Return empty pattern if invalid

    def set_current_pattern(self, pattern_index: int):
        """Set the current pattern by index (0-7)."""
        if 0 <= pattern_index < len(self.patterns):
            self.current_pattern = pattern_index

    def get_pattern(self, index: int) -> Pattern:
        """Get a pattern by index."""
        if 0 <= index < len(self.patterns):
            return self.patterns[index]
        return Pattern()

    def set_pattern_chain(self, chain: List[int]):
        """Set the pattern chain sequence."""
        # Validate chain contains only valid pattern indices
        valid_chain = [idx for idx in chain if 0 <= idx < len(self.patterns)]
        # Ensure consecutive chaining (Circuit Tracks style)
        if valid_chain:
            # Check if chain is consecutive
            for i in range(1, len(valid_chain)):
                if valid_chain[i] != valid_chain[i - 1] + 1:
                    # If not consecutive, just use the first pattern
                    valid_chain = [valid_chain[0]]
                    break
        self.pattern_chain = valid_chain

    def get_next_pattern_in_chain(self) -> int:
        """Get the next pattern index in the chain."""
        if not self.pattern_chain:
            return self.current_pattern

        try:
            current_idx = self.pattern_chain.index(self.current_pattern)
            next_idx = (current_idx + 1) % len(self.pattern_chain)
            return self.pattern_chain[next_idx]
        except ValueError:
            # Current pattern not in chain, return first pattern in chain
            return self.pattern_chain[0]

    def is_pattern_chained(self) -> bool:
        """Check if this track has a pattern chain active."""
        return len(self.pattern_chain) > 1

    def clear_pattern(self, pattern_index: int):
        """Clear all steps in a specific pattern."""
        if 0 <= pattern_index < len(self.patterns):
            self.patterns[pattern_index].clear_all_steps()

    def copy_pattern(self, from_index: int, to_index: int):
        """Copy one pattern to another."""
        if 0 <= from_index < len(self.patterns) and 0 <= to_index < len(self.patterns):
            # Deep copy the pattern
            import copy

            self.patterns[to_index] = copy.deepcopy(self.patterns[from_index])
            self.patterns[to_index].name = f"Pattern {to_index + 1}"

    def has_content(self) -> bool:
        """Check if any patterns in this track have content."""
        return any(pattern.has_content() for pattern in self.patterns)

    def get_root_note_in_octave(self) -> int:
        """Get the root note adjusted for current octave."""
        return max(0, min(127, self.root_note + (self.octave * 12)))

    def is_note_in_range(self, midi_note: int) -> bool:
        """Check if a MIDI note is within the track's allowed range."""
        return self.note_range[0] <= midi_note <= self.note_range[1]

    def constrain_note_to_range(self, midi_note: int) -> int:
        """Constrain a MIDI note to the track's allowed range."""
        return max(self.note_range[0], min(self.note_range[1], midi_note))

    def get_cc_value(self, cc_name: str) -> int:
        """Get the CC number for a named control."""
        return self.cc_assignments.get(cc_name, 0)

    def set_cc_assignment(self, cc_name: str, cc_number: int):
        """Set a CC assignment for hardware control."""
        if 0 <= cc_number <= 127:
            self.cc_assignments[cc_name] = cc_number

    def to_dict(self) -> Dict[str, Any]:
        """Convert track to dictionary for saving."""
        return {
            "name": self.name,
            "color": list(self.color),
            "midi_channel": self.midi_channel,
            "midi_port": self.midi_port,
            "patterns": [pattern.to_dict() for pattern in self.patterns],
            "current_pattern": self.current_pattern,
            "pattern_chain": self.pattern_chain.copy(),
            "enabled": self.enabled,
            "soloed": self.soloed,
            "scale": self.scale,
            "root_note": self.root_note,
            "octave": self.octave,
            "note_range": list(self.note_range),
            "cc_assignments": self.cc_assignments.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        """Create track from dictionary data."""
        track = cls(
            name=data.get("name", "Track"),
            color=tuple(data.get("color", [127, 127, 127])),
            midi_channel=data.get("midi_channel", 1),
            midi_port=data.get("midi_port", ""),
            current_pattern=data.get("current_pattern", 0),
            pattern_chain=data.get("pattern_chain", []),
            enabled=data.get("enabled", True),
            soloed=data.get("soloed", False),
            scale=data.get("scale", "MAJOR"),
            root_note=data.get("root_note", 60),
            octave=data.get("octave", 0),
            note_range=tuple(data.get("note_range", [0, 127])),
            cc_assignments=data.get("cc_assignments", {}),
        )

        # Load patterns
        patterns_data = data.get("patterns", [])
        track.patterns = []
        for i, pattern_data in enumerate(patterns_data):
            pattern = Pattern.from_dict(pattern_data)
            track.patterns.append(pattern)

        # Ensure we have 8 patterns
        while len(track.patterns) < 8:
            track.patterns.append(Pattern(name=f"Pattern {len(track.patterns) + 1}"))

        return track
