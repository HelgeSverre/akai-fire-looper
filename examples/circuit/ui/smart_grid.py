"""
Smart, data-driven grid management system.
State-based approach that automatically handles colors, highlights, and updates.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, Callable, Tuple, Optional, Any
from ui.screen_manager import Mode


class PadState(Enum):
    """Logical states a pad can be in."""

    EMPTY = auto()
    ARMED = auto()
    PLAYING = auto()
    SELECTED = auto()
    HAS_CONTENT = auto()
    BEAT_MARKER = auto()


class PadLayer(Enum):
    """Visual layers that can be applied to pads."""

    BASE = auto()
    HIGHLIGHT = auto()
    CURRENT_STEP = auto()
    SELECTION = auto()


@dataclass
class PadData:
    """Data model for a single pad."""

    state: PadState = PadState.EMPTY
    track: Optional[int] = None
    step: Optional[int] = None
    pattern: Optional[int] = None
    velocity: int = 0
    is_current_step: bool = False
    is_selected: bool = False

    def __hash__(self):
        """Make PadData hashable for change detection."""
        return hash(
            (
                self.state,
                self.track,
                self.step,
                self.pattern,
                self.velocity,
                self.is_current_step,
                self.is_selected,
            )
        )


class SmartGridManager:
    """
    Intelligent grid management system.
    Uses declarative rules and change detection for efficient updates.
    """

    def __init__(self, fire_controller):
        self.fire = fire_controller
        self.current_mode = Mode.NOTE

        # Grid dimensions
        self.ROWS = 4
        self.COLS = 16
        self.TOTAL_PADS = self.ROWS * self.COLS

        # State tracking
        self.pad_data = [PadData() for _ in range(self.TOTAL_PADS)]
        self.last_rendered_state = [None] * self.TOTAL_PADS  # For change detection

        # Color constants
        self.TRACK_COLORS = [
            (255, 0, 0),  # Track 1: Red
            (0, 255, 0),  # Track 2: Green
            (0, 0, 255),  # Track 3: Blue
            (255, 255, 0),  # Track 4: Yellow
        ]

        self.BRIGHTNESS = {
            "dim": 25,
            "medium": 75,
            "bright": 127,
        }

        # Declarative color rules
        self.color_rules = self._create_color_rules()

    def _create_color_rules(self) -> Dict[Tuple[Mode, PadState], Callable]:
        """Create declarative color mapping rules."""
        return {
            # NOTE Mode Rules
            (Mode.NOTE, PadState.EMPTY): lambda pad: (0, 0, 0),
            (Mode.NOTE, PadState.BEAT_MARKER): lambda pad: (20, 20, 20),
            (Mode.NOTE, PadState.HAS_CONTENT): lambda pad: self._dim_color(
                self.TRACK_COLORS[pad.track], self.BRIGHTNESS["medium"]
            ),
            (Mode.NOTE, PadState.PLAYING): lambda pad: self.TRACK_COLORS[pad.track],
            # MIXER Mode Rules
            (Mode.MIXER, PadState.EMPTY): lambda pad: (10, 10, 10),
            (Mode.MIXER, PadState.ARMED): lambda pad: (127, 64, 0),  # Orange
            (Mode.MIXER, PadState.PLAYING): lambda pad: (0, 127, 0),  # Green
            # Add more mode rules as needed...
        }

    def _dim_color(
        self, color: Tuple[int, int, int], brightness: int
    ) -> Tuple[int, int, int]:
        """Apply brightness scaling to a color."""
        return tuple(c * brightness // 127 for c in color)

    def pad_index(self, row: int, col: int) -> int:
        """Convert row, col to pad index."""
        return row * self.COLS + col

    def pad_position(self, pad_index: int) -> Tuple[int, int]:
        """Convert pad index to (row, col)."""
        return (pad_index // self.COLS, pad_index % self.COLS)

    def set_pad_state(self, pad_index: int, state: PadState, **kwargs):
        """Set the logical state of a pad."""
        if 0 <= pad_index < self.TOTAL_PADS:
            pad = self.pad_data[pad_index]
            pad.state = state

            # Update additional properties
            for key, value in kwargs.items():
                if hasattr(pad, key):
                    setattr(pad, key, value)

    def set_current_step(self, step: int):
        """Update which step is currently playing."""
        # Clear previous current step
        for pad in self.pad_data:
            pad.is_current_step = False

        # Set new current step (Row 0 = step sequencer)
        if 0 <= step < self.COLS:
            step_pad_index = self.pad_index(0, step)
            self.pad_data[step_pad_index].is_current_step = True

    def update_from_sequencer(self, sequencer_status: Dict[str, Any], **kwargs):
        """Update pad states based on sequencer status - the main entry point."""
        self.current_mode = kwargs.get("mode", Mode.NOTE)

        # Update pad states based on current mode
        if self.current_mode == Mode.NOTE:
            self._update_note_mode_state(sequencer_status, **kwargs)
        elif self.current_mode == Mode.MIXER:
            self._update_mixer_mode_state(sequencer_status, **kwargs)
        # Add other modes...

        # Render only changed pads
        self._render_changes()

    def _update_note_mode_state(self, status: Dict[str, Any], **kwargs):
        """Update pad states for Note Mode."""
        timing = status.get("timing", {})
        tracks = status.get("tracks", [])
        current_track_idx = status.get("current_track", 1) - 1

        # Clear all pad states first
        for pad in self.pad_data:
            pad.state = PadState.EMPTY
            pad.is_current_step = False

        # Row 0: Step sequencer
        current_step = timing.get("step", 0)
        is_playing = timing.get("is_playing", False)

        for step in range(16):
            pad_index = self.pad_index(0, step)
            pad = self.pad_data[pad_index]

            # Determine state based on sequencer data
            if is_playing and step == current_step:
                pad.state = PadState.PLAYING  # Current step takes priority
                pad.is_current_step = True
            elif self._step_has_content(current_track_idx, 0, step, tracks):
                pad.state = PadState.HAS_CONTENT
            elif step % 4 == 0:
                pad.state = PadState.BEAT_MARKER
            else:
                pad.state = PadState.EMPTY

            pad.track = current_track_idx
            pad.step = step

        # Row 1: Track/Pattern controls - simplified for now
        for col in range(16):
            pad_index = self.pad_index(1, col)
            pad = self.pad_data[pad_index]
            if col < 4:  # Track selection
                pad.state = (
                    PadState.HAS_CONTENT if col == current_track_idx else PadState.EMPTY
                )
                pad.track = col

        # Rows 2-3: Scale keyboard - simplified
        # Implementation would go here...

    def _update_mixer_mode_state(self, status: Dict[str, Any], **kwargs):
        """Update pad states for Mixer Mode."""
        # Implementation for mixer mode...
        pass

    def _step_has_content(
        self, track_idx: int, pattern_idx: int, step: int, tracks
    ) -> bool:
        """Check if a step has content (simplified)."""
        # This would check the actual sequencer data
        # For now, return False
        return False

    def _get_pad_color(self, pad: PadData) -> Tuple[int, int, int]:
        """Get the final color for a pad based on its state."""
        rule_key = (self.current_mode, pad.state)

        if rule_key in self.color_rules:
            base_color = self.color_rules[rule_key](pad)
        else:
            base_color = (0, 0, 0)  # Default to off

        # Apply layer modifiers
        final_color = self._apply_layers(base_color, pad)
        return final_color

    def _apply_layers(
        self, base_color: Tuple[int, int, int], pad: PadData
    ) -> Tuple[int, int, int]:
        """Apply visual layers like highlights, selection, etc."""
        color = base_color

        # Current step highlight (brighten)
        if pad.is_current_step:
            color = (127, 127, 127)  # Bright white for current step

        # Selection highlight
        if pad.is_selected:
            # Mix with selection color
            selection_color = (64, 64, 127)  # Blue tint
            color = tuple((c + s) // 2 for c, s in zip(color, selection_color))

        return color

    def _render_changes(self):
        """Only render pads that have actually changed."""
        for i, pad in enumerate(self.pad_data):
            current_state = hash(pad)  # Use hash for quick comparison

            if current_state != self.last_rendered_state[i]:
                # State changed, update hardware
                color = self._get_pad_color(pad)
                self.fire.set_pad_color(i, *color)
                self.last_rendered_state[i] = current_state

    def force_refresh(self):
        """Force a complete refresh of all pads."""
        self.last_rendered_state = [None] * self.TOTAL_PADS
        self._render_changes()
