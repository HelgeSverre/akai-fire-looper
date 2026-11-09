"""Circuit's OLED layouts: one header and four bounded content rows."""

from enum import Enum
from typing import Any

from akai_fire import Canvas
from akai_fire_framework import ScreenMixin
from examples.apps.circuit.core.scales import get_note_name


class Mode(Enum):
    NOTE = "NOTE"
    MIXER = "MIXER"
    PATTERN = "PATTERN"
    STEP_EDIT = "STEP_EDIT"
    SETTINGS = "SETTINGS"


class ScreenManager(ScreenMixin):
    # Four 12-pixel rows fit below this compact header, ending at pixel 62.
    HEADER_HEIGHT = 12
    TEXT_MARGIN_Y = 1
    CONTENT_START = 15
    LINE_HEIGHT = 12

    def __init__(self, canvas: Canvas):
        self.canvas = canvas
        self.current_mode = Mode.NOTE
        self.last_notes_played = {}
        self.last_update_time = 0

    def set_mode(self, mode: Mode):
        self.current_mode = mode

    def update_display(self, sequencer_status: dict[str, Any], **kwargs):
        self.canvas.clear()
        renderers = {
            Mode.NOTE: self._draw_note_mode,
            Mode.MIXER: self._draw_mixer_mode,
            Mode.PATTERN: self._draw_pattern_mode,
            Mode.STEP_EDIT: self._draw_step_edit_mode,
            Mode.SETTINGS: self._draw_settings_mode,
        }
        renderers[self.current_mode](sequencer_status, **kwargs)

    def _draw_header(self, title: str, status: str = ""):
        self.draw_header(title, status)

    def _rows(self, lines):
        self.draw_content_lines(lines[:4])

    def _draw_note_mode(self, status: dict[str, Any], **kwargs):
        timing = status.get("timing", {})
        tracks = status.get("tracks", [])
        index = status.get("current_track", 1) - 1
        track = tracks[index] if 0 <= index < len(tracks) else {}
        transport = {"STOPPED": "STOP", "PLAYING": "PLAY", "RECORDING": "REC"}
        state = transport.get(status.get("transport_state"), "STOP")
        self._draw_header(f"NOTE T{index + 1}", f"{state} {timing.get('bpm', 120):.0f}")
        chain = track.get("pattern_chain", [])
        pattern = (
            "Chain " + ">".join(map(str, chain))
            if chain
            else f"Pattern {track.get('current_pattern', 1)}"
        )
        notes = kwargs.get("current_notes", [])
        scale = kwargs.get("current_scale", "MAJOR")
        root = get_note_name(kwargs.get("root_note", 60))
        self._rows(
            [
                f"{track.get('name', 'No track')} Ch{track.get('midi_channel', 1)}",
                pattern,
                f"Sw {timing.get('swing', 0) * 100:.0f}%  Q {timing.get('quantization', '1/16')}",
                "Notes " + " ".join(get_note_name(note) for note in notes)
                if notes
                else f"{root} {scale}",
            ]
        )

    def _draw_mixer_mode(self, status: dict[str, Any], **kwargs):
        self._draw_header("MIXER", f"Scene {status.get('current_scene', 1)}")
        activity = kwargs.get("midi_activity", {})
        for index, track in enumerate(status.get("tracks", [])[:4]):
            y = self.CONTENT_START + index * self.LINE_HEIGHT
            flag = (
                "-"
                if track.get("muted", False) or not track.get("enabled", True)
                else "S"
                if track.get("soloed")
                else "+"
            )
            # Keep channel and activity visible even when track names are long.
            name = Canvas.fit_text(track.get("name", f"T{index + 1}"), 40)
            self.canvas.draw_text_fitted(f"{flag}{index + 1} {name}", 4, y, width=64)
            self.canvas.draw_text_fitted(
                f"Ch{track.get('midi_channel', 1)}", 72, y, width=30
            )
            event = activity.get(index, {})
            if event.get("active"):
                width = max(1, min(16, event.get("velocity", 0) * 16 // 127))
                self.canvas.fill_rect(108, y + 3, width, 5)

    def _draw_pattern_mode(self, status: dict[str, Any], **kwargs):
        self._draw_header("PATTERNS", f"Scene {status.get('current_scene', 1)}")
        lines = []
        for index, track in enumerate(status.get("tracks", [])[:4]):
            chain = track.get("pattern_chain", [])
            pattern = (
                ">".join(map(str, chain))
                if chain
                else str(track.get("current_pattern", 1))
            )
            lines.append(f"T{index + 1}  P{pattern}")
        self._rows(lines)

    def _draw_step_edit_mode(self, status: dict[str, Any], **kwargs):
        step = kwargs.get("step_info", {})
        self._draw_header(
            f"STEP {step.get('step', 1)}", step.get("track_name", "Track")
        )
        notes = step.get("notes", [])
        self._rows(
            [
                "Notes " + " ".join(get_note_name(note) for note in notes)
                if notes
                else "No notes",
                f"Vel {step.get('velocity', 85)}  Gate {step.get('gate', 0.75) * 100:.0f}%",
                f"Prob {step.get('probability', 1) * 100:.0f}%  Micro {step.get('micro_timing', 0):+d}",
                f"Edit: {kwargs.get('edit_parameter', 'velocity').title()}",
            ]
        )

    def _draw_settings_mode(self, status: dict[str, Any], **kwargs):
        self.canvas.draw_menu(
            kwargs.get("menu_title", "Settings"),
            kwargs.get("menu_items", []),
            kwargs.get("selected_index", 0),
        )

    def draw_startup_screen(self, version: str = "1.0"):
        self.canvas.clear()
        self._draw_header("CIRCUIT", f"v{version}")
        self._rows(
            ["4-track sequencer", "NOTE / STEP / MIXER", "PLAY starts transport"]
        )

    def draw_error_screen(self, error_msg: str):
        self.canvas.clear()
        self._draw_header("ERROR")
        # Wrap by measured width so long port names cannot run off the OLED.
        words, lines, line = error_msg.split(), [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if Canvas.fit_text(candidate, 120) != candidate and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        self._rows(lines)

    def update_note_activity(self, track_idx: int, notes: list[int]):
        self.last_notes_played.setdefault(track_idx, []).extend(notes)
        self.last_notes_played[track_idx] = self.last_notes_played[track_idx][-5:]

    def get_display_info(self) -> dict[str, Any]:
        return {
            "mode": self.current_mode.value,
            "last_notes": self.last_notes_played.copy(),
        }
