"""
LCD screen manager for real-time MIDI information display.
Handles all screen content and layout for the AKAI Fire OLED display.
"""

import sys
import os
from typing import Dict, List, Optional, Any
from enum import Enum

# Add parent directory to path to import akai_fire
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from akai_fire import Canvas
except ImportError:
    # Fallback for development
    class Canvas:
        def __init__(self, width=128, height=64):
            self.width = width
            self.height = height

        def clear(self):
            pass

        def draw_text(self, x, y, text, font_size=1):
            pass

        def draw_line(self, x1, y1, x2, y2):
            pass

        def draw_rect(self, x, y, w, h, filled=False):
            pass


from core.scales import get_note_name


class Mode(Enum):
    """Display modes for different sequencer views."""

    NOTE = "NOTE"
    MIXER = "MIXER"
    PATTERN = "PATTERN"
    STEP_EDIT = "STEP_EDIT"
    SETTINGS = "SETTINGS"


class ScreenManager:
    """
    Manages the AKAI Fire OLED screen display.
    Renders different modes with real-time MIDI and sequencer information.
    """

    def __init__(self, canvas: Canvas):
        self.canvas = canvas
        self.current_mode = Mode.NOTE

        # Display state
        self.last_notes_played = {}  # Track -> list of recent notes
        self.last_update_time = 0

        # Typography constants (consistent with existing codebase)
        self.HEADER_HEIGHT = 16
        self.TEXT_MARGIN_Y = 3
        self.CONTENT_GAP = 2
        self.CONTENT_START = self.HEADER_HEIGHT + self.CONTENT_GAP
        self.LINE_HEIGHT = 12

    def set_mode(self, mode: Mode):
        """Set the current display mode."""
        self.current_mode = mode

    def update_display(self, sequencer_status: Dict[str, Any], **kwargs):
        """Update the display based on current mode and sequencer status."""
        self.canvas.clear()

        if self.current_mode == Mode.NOTE:
            self._draw_note_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.MIXER:
            self._draw_mixer_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.PATTERN:
            self._draw_pattern_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.STEP_EDIT:
            self._draw_step_edit_mode(sequencer_status, **kwargs)
        elif self.current_mode == Mode.SETTINGS:
            self._draw_settings_mode(sequencer_status, **kwargs)

    def _draw_header(self, title: str, status: str = ""):
        """Draw the standard header with inverted background."""
        # Fill header background (inverted)
        self.canvas.fill_rect(0, 0, 128, self.HEADER_HEIGHT, 0)

        # Draw title text (inverted - white on black background)
        self.canvas.draw_text(title, 4, self.TEXT_MARGIN_Y, color=1)

        # Draw status on right side if provided
        if status:
            status_width = len(status) * 6  # Approximate width
            self.canvas.draw_text(status, 128 - status_width - 4, self.TEXT_MARGIN_Y, color=1)

        # Draw separator line
        self.canvas.draw_line(0, self.HEADER_HEIGHT, 128, self.HEADER_HEIGHT)

    def _draw_note_mode(self, status: Dict[str, Any], **kwargs):
        """Draw Note Mode display with track info and real-time note display."""
        timing = status.get("timing", {})
        tracks = status.get("tracks", [])
        current_track_idx = status.get("current_track", 1) - 1

        # Header with transport state
        transport_state = status.get("transport_state", "STOPPED")
        bpm = timing.get("bpm", 120)
        header_status = f"{transport_state} {bpm:.1f}BPM"

        # Get current track info
        if 0 <= current_track_idx < len(tracks):
            track_info = tracks[current_track_idx]
            track_name = track_info.get("name", f"Track {current_track_idx + 1}")
            midi_ch = track_info.get("midi_channel", 1)
            header_title = f"{track_name} Ch:{midi_ch}"
        else:
            header_title = "No Track Selected"

        self._draw_header(header_title, header_status)

        # Pattern and timing info
        y = self.CONTENT_START
        if 0 <= current_track_idx < len(tracks):
            track_info = tracks[current_track_idx]
            pattern_num = track_info.get("current_pattern", 1)
            pattern_chain = track_info.get("pattern_chain", [])

            if pattern_chain:
                chain_str = "→".join(str(p) for p in pattern_chain)
                pattern_text = f"Pattern Chain: {chain_str}"
            else:
                pattern_text = f"Pattern: {pattern_num}"

            self.canvas.draw_text(pattern_text, 4, y)
            y += self.LINE_HEIGHT

        # Timing and swing info
        swing = timing.get("swing", 0) * 100  # Convert to percentage
        quantization = timing.get("quantization", "1/16")
        timing_text = f"Swing: {swing:.0f}%  Quant: {quantization}"
        self.canvas.draw_text(timing_text, 4, y)
        y += self.LINE_HEIGHT

        # Real-time note display
        current_notes = kwargs.get("current_notes", [])
        if current_notes:
            notes_text = "Notes: " + ", ".join(
                get_note_name(note) for note in current_notes
            )
            self.canvas.draw_text(notes_text[:20], 4, y)  # Limit length
        else:
            self.canvas.draw_text("No notes playing", 4, y)
        y += self.LINE_HEIGHT

        # Scale and root note info (from kwargs)
        scale = kwargs.get("current_scale", "MAJOR")
        root_note = kwargs.get("root_note", 60)
        root_name = get_note_name(root_note)
        scale_text = f"Scale: {root_name} {scale}"
        self.canvas.draw_text(scale_text, 4, y)

        # Control assignments at bottom
        y = 64 - self.LINE_HEIGHT
        controls_text = "[Vol:BPM] [Filt:Swing] [Pan:Quant]"
        self.canvas.draw_text(controls_text, 4, y)  # Smaller font

    def _draw_mixer_mode(self, status: Dict[str, Any], **kwargs):
        """Draw Mixer Mode with MIDI track control and activity."""
        self._draw_header("MIXER - MIDI Track Control")

        tracks = status.get("tracks", [])
        midi_activity = kwargs.get("midi_activity", {})

        y = self.CONTENT_START

        # Track status display
        for i, track_info in enumerate(tracks[:4]):  # 4 tracks max
            track_name = track_info.get("name", f"T{i+1}")[:6]  # Limit name length
            midi_ch = track_info.get("midi_channel", 1)
            enabled = track_info.get("enabled", True)
            soloed = track_info.get("soloed", False)

            # Get MIDI activity for visual feedback
            activity = midi_activity.get(i, {"active": False, "velocity": 0})
            activity_bars = (
                "█" * (activity.get("velocity", 0) // 32)
                if activity.get("active", False)
                else ""
            )

            # Status indicators
            status_char = "S" if soloed else ("◆" if enabled else "◇")

            track_text = f"{status_char}{track_name} Ch{midi_ch:2d} {activity_bars:<4}"
            self.canvas.draw_text(track_text, 4, y)
            y += self.LINE_HEIGHT

        # Scene info
        current_scene = status.get("current_scene", 1)
        scene_text = f"Scene: {current_scene}"
        self.canvas.draw_text(scene_text, 4, y)
        y += self.LINE_HEIGHT

        # CC values display
        cc_values = kwargs.get("cc_values", {})
        if cc_values:
            cc_text = "  ".join(
                f"CC{cc}:{val}" for cc, val in list(cc_values.items())[:3]
            )
            self.canvas.draw_text(cc_text, 4, y)

        # Control assignments
        y = 64 - self.LINE_HEIGHT
        controls_text = "[Vol:CC7] [Filt:CC74] [Pan:CC10]"
        self.canvas.draw_text(controls_text, 4, y)

    def _draw_pattern_mode(self, status: Dict[str, Any], **kwargs):
        """Draw Pattern Mode for pattern chaining and arrangement."""
        self._draw_header("PATTERN - Song Arrangement")

        tracks = status.get("tracks", [])
        y = self.CONTENT_START

        # Show pattern assignments for each track
        for i, track_info in enumerate(tracks[:4]):
            track_name = track_info.get("name", f"Track {i+1}")[:8]
            current_pattern = track_info.get("current_pattern", 1)
            pattern_chain = track_info.get("pattern_chain", [])

            if pattern_chain:
                chain_str = "→".join(str(p) for p in pattern_chain)
                pattern_text = f"{track_name}: {chain_str}"
            else:
                pattern_text = f"{track_name}: Pattern {current_pattern}"

            self.canvas.draw_text(pattern_text, 4, y)
            y += self.LINE_HEIGHT

        # Instructions
        y += self.CONTENT_GAP
        self.canvas.draw_text("Sequential pads = chain", 4, y)
        y += self.LINE_HEIGHT - 2
        self.canvas.draw_text("[Clear] [Duplicate] [Select]", 4, y)

    def _draw_step_edit_mode(self, status: Dict[str, Any], **kwargs):
        """Draw Step Edit Mode for detailed parameter editing."""
        step_info = kwargs.get("step_info", {})
        step_num = step_info.get("step", 1)
        track_name = step_info.get("track_name", "Track")

        self._draw_header(f"Step {step_num} Edit - {track_name}")

        y = self.CONTENT_START

        # Notes in step
        notes = step_info.get("notes", [])
        if notes:
            notes_text = "Notes: " + ", ".join(
                get_note_name(note) for note in notes[:3]
            )
            self.canvas.draw_text(notes_text, 4, y)
        else:
            self.canvas.draw_text("No notes in step", 4, y)
        y += self.LINE_HEIGHT

        # Step parameters
        velocity = step_info.get("velocity", 85)
        gate = step_info.get("gate", 0.75) * 100
        probability = step_info.get("probability", 1.0) * 100
        micro = step_info.get("micro_timing", 0)

        self.canvas.draw_text(f"Velocity: {velocity}/127  Gate: {gate:.0f}%", 4, y)
        y += self.LINE_HEIGHT
        self.canvas.draw_text(
            f"Probability: {probability:.0f}%  Micro: {micro:+d}", 4, y
        )
        y += self.LINE_HEIGHT

        # Current parameter being edited
        edit_param = kwargs.get("edit_parameter", "velocity")
        self.canvas.draw_text(f"Editing: {edit_param.title()}", 4, y)

        # Controls
        y = 64 - self.LINE_HEIGHT
        controls_text = "[Vel] [Gate] [Prob] [Micro]"
        self.canvas.draw_text(controls_text, 4, y)

    def _draw_settings_mode(self, status: Dict[str, Any], **kwargs):
        """Draw Settings Mode using built-in menu renderer."""
        menu_items = kwargs.get("menu_items", [])
        selected_index = kwargs.get("selected_index", 0)
        menu_title = kwargs.get("menu_title", "Settings")

        # Use built-in menu renderer - handles scrolling, highlighting automatically
        self.canvas.draw_menu(menu_title, menu_items, selected_index)

    def draw_startup_screen(self, version: str = "1.0"):
        """Draw startup/boot screen."""
        self.canvas.clear()

        # Title
        self.canvas.draw_text("CIRCUIT SEQUENCER", 32, 15)

        # Version
        self.canvas.draw_text(f"v{version}", 48, 30)

        # Hardware info
        self.canvas.draw_text("4-Track MIDI Sequencer", 20, 45)

    def draw_error_screen(self, error_msg: str):
        """Draw error screen."""
        self.canvas.clear()
        self._draw_header("ERROR")

        # Wrap error message
        words = error_msg.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line + word) < 20:  # Approximate char limit
                current_line += word + " "
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + " "

        if current_line:
            lines.append(current_line.strip())

        # Draw error lines
        y = self.CONTENT_START
        for line in lines[:3]:  # Max 3 lines
            self.canvas.draw_text(line, 4, y)
            y += self.LINE_HEIGHT

    def update_note_activity(self, track_idx: int, notes: List[int]):
        """Update the recent note activity for a track."""
        if track_idx not in self.last_notes_played:
            self.last_notes_played[track_idx] = []

        # Add new notes and keep last 5
        self.last_notes_played[track_idx].extend(notes)
        self.last_notes_played[track_idx] = self.last_notes_played[track_idx][-5:]

    def get_display_info(self) -> Dict[str, Any]:
        """Get current display information."""
        return {
            "mode": self.current_mode.value,
            "last_notes": self.last_notes_played.copy(),
        }
