"""
Scene management for live performance.
Scenes store snapshots of pattern assignments across all tracks.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Scene:
    """
    A scene stores a snapshot of which patterns are active on each track.
    Used for live performance and song arrangement.
    """

    name: str = "Scene"  # Scene name
    pattern_assignments: Dict[int, int] = field(
        default_factory=dict
    )  # Track -> Pattern mapping (track_id -> pattern_id)
    track_states: Dict[int, bool] = field(
        default_factory=dict
    )  # Track enabled states (track_id -> enabled)

    def set_pattern_for_track(self, track_id: int, pattern_id: int):
        """Set which pattern should play for a specific track."""
        if 0 <= track_id < 4 and 0 <= pattern_id < 8:  # 4 tracks, 8 patterns each
            self.pattern_assignments[track_id] = pattern_id

    def get_pattern_for_track(self, track_id: int) -> int:
        """Get the pattern assignment for a track."""
        return self.pattern_assignments.get(track_id, 0)  # Default to pattern 0

    def set_track_enabled(self, track_id: int, enabled: bool):
        """Set whether a track should be enabled in this scene."""
        if 0 <= track_id < 4:
            self.track_states[track_id] = enabled

    def is_track_enabled(self, track_id: int) -> bool:
        """Check if a track is enabled in this scene."""
        return self.track_states.get(track_id, True)  # Default to enabled

    def copy_current_state(self, tracks):
        """Copy the current state of all tracks into this scene."""
        self.pattern_assignments.clear()
        self.track_states.clear()

        for i, track in enumerate(tracks):
            self.pattern_assignments[i] = track.current_pattern
            self.track_states[i] = track.enabled

    def apply_to_tracks(self, tracks):
        """Apply this scene's settings to the provided tracks."""
        for track_id, pattern_id in self.pattern_assignments.items():
            if track_id < len(tracks):
                tracks[track_id].set_current_pattern(pattern_id)

        for track_id, enabled in self.track_states.items():
            if track_id < len(tracks):
                tracks[track_id].enabled = enabled

    def has_content(self) -> bool:
        """Check if this scene has any assignments."""
        return bool(self.pattern_assignments or self.track_states)

    def clear(self):
        """Clear all assignments from this scene."""
        self.pattern_assignments.clear()
        self.track_states.clear()

    def get_summary(self) -> str:
        """Get a text summary of this scene's assignments."""
        if not self.has_content():
            return "Empty scene"

        parts = []
        for track_id in range(4):
            pattern_id = self.get_pattern_for_track(track_id)
            enabled = self.is_track_enabled(track_id)
            status = "ON" if enabled else "OFF"
            parts.append(f"T{track_id+1}:P{pattern_id+1}({status})")

        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert scene to dictionary for saving."""
        return {
            "name": self.name,
            "pattern_assignments": self.pattern_assignments.copy(),
            "track_states": self.track_states.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create scene from dictionary data."""
        return cls(
            name=data.get("name", "Scene"),
            pattern_assignments=data.get("pattern_assignments", {}),
            track_states=data.get("track_states", {}),
        )
