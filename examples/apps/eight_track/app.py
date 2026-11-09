"""Decorator-routed controls and two views of the clock's musical snapshot."""

from akai_fire.constants import (
    BUTTON_BROWSER,
    BUTTON_GRID_LEFT,
    BUTTON_GRID_RIGHT,
    BUTTON_PATTERN,
    BUTTON_PERFORM,
    BUTTON_PLAY,
    BUTTON_REC,
    BUTTON_SELECT,
    BUTTON_STOP,
    ROTARY_FILTER,
    ROTARY_PAN,
    ROTARY_RESONANCE,
    ROTARY_SELECT,
    ROTARY_VOLUME,
)
from akai_fire_framework import (
    AkaiFireApp,
    EncoderMenu,
    GridMixin,
    MenuItem,
    ScreenMixin,
    on,
)

from .engine import Engine
from .model import COLORS, NAMES, QUANTIZE_NAMES


class EightTrackApp(AkaiFireApp, GridMixin, ScreenMixin):
    APP_NAME = "Eight Track"
    FPS = 20

    def __init__(self, fire, *, output=None, threaded=True):
        self.engine = Engine(output)
        self.threaded = threaded
        super().__init__(fire)

    def on_init(self):
        self.selected = 0
        self.view = "perform"
        self.part_cursor = 0
        self.notice = "Bottom: SELECT / MUTE"
        self.notice_left = 6.0
        self.last_snapshot = None
        self.menu = EncoderMenu(
            [
                MenuItem(
                    "Transpose",
                    adjust=lambda d: self.engine.adjust("transpose", d, self.selected),
                ),
                MenuItem(
                    "Mute", activate=lambda: self.engine.toggle_mute(self.selected)
                ),
                MenuItem("Back", activate=self.home),
            ]
        )

    def on_start(self):
        self.fire.clear_all()
        if self.threaded:
            self.engine.start()
        self._draw()

    def notify(self, text):
        self.notice, self.notice_left = text, 2.5

    @on.pad()
    def pad(self, event):
        row, col = self.pad_position(event.pad)
        if self.view == "parts":
            if row == 0 and col < len(self.engine.parts):
                self.part_cursor = col
                self.engine.select_part(col)
            return
        if self.view != "perform" or row != 3:
            return
        track = col // 2
        if col % 2:
            self.engine.toggle_mute(track)
            state = "Muted" if self.engine.snapshot().muted[track] else "On"
            self.notify(f"T{track + 1} {NAMES[track]}: {state}")
        else:
            self.selected = track
            self.notify(f"T{track + 1}: SELECT settings")

    @on.button(BUTTON_PLAY)
    def play(self, event):
        self.engine.play()
        self.notify(
            "Restart after error" if self.engine.snapshot().error else "Playing"
        )

    @on.button(BUTTON_STOP)
    def stop(self, event):
        was_running = self.engine.snapshot().running
        self.engine.stop()
        self.notify("Stopped" if was_running else "Rewound")

    @on.button(BUTTON_REC)
    def recording_info(self, event):
        # This control prototype must not pretend to record a take.
        self.notify("Recording: next stage")

    @on.button(BUTTON_PERFORM)
    def home(self, event=None):
        self.menu.finish_editing()
        self.view = "perform"
        self.notify("Bottom: SELECT / MUTE")

    @on.button(BUTTON_PATTERN)
    def parts(self, event):
        self.menu.finish_editing()
        self.view = "parts"
        s = self.engine.snapshot()
        self.part_cursor = s.pending if s.pending is not None else s.part

    @on.button(BUTTON_BROWSER)
    def help(self, event):
        self.menu.finish_editing()
        self.view = "help" if self.view != "help" else "perform"

    @on.encoder(ROTARY_SELECT)
    def select(self, event):
        if self.view == "settings":
            self.menu.turn(event.delta)
        elif self.view == "parts":
            self.part_cursor = max(
                0, min(len(self.engine.parts) - 1, self.part_cursor + event.delta)
            )
        elif self.view == "perform":
            self.selected = max(0, min(7, self.selected + event.delta))

    @on.button(BUTTON_SELECT)
    def press_select(self, event):
        if self.view == "parts":
            self.engine.select_part(self.part_cursor)
        elif self.view == "settings":
            self.menu.press()
        elif self.view == "perform":
            self.menu.select(0)
            self.view = "settings"

    @on.button((BUTTON_GRID_LEFT, BUTTON_GRID_RIGHT))
    def navigate(self, event):
        delta = 1 if event.button == BUTTON_GRID_RIGHT else -1
        if self.view == "settings":
            self.menu.move(delta, keep_editing=True)
        elif self.view == "parts":
            self.part_cursor = max(
                0, min(len(self.engine.parts) - 1, self.part_cursor + delta)
            )
        elif self.view == "perform":
            self.selected = max(0, min(7, self.selected + delta))

    @on.encoder((ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER, ROTARY_RESONANCE))
    def parameter(self, event):
        if self.view != "perform":
            return
        name = {
            ROTARY_VOLUME: "tempo",
            ROTARY_PAN: "quantize",
            ROTARY_FILTER: "swing",
            ROTARY_RESONANCE: "transpose",
        }[event.encoder]
        self.engine.adjust(name, event.delta, self.selected)
        s = self.engine.snapshot()
        values = {
            "tempo": str(s.bpm),
            "quantize": QUANTIZE_NAMES[s.quantize],
            "swing": f"{s.swing}%",
            "transpose": f"{s.transpose[self.selected]:+d}",
        }
        self.notify(f"{name.title()}: {values[name]}")

    def on_update(self, dt):
        self.notice_left = max(0, self.notice_left - dt)
        self._draw()

    @staticmethod
    def _color(track, level):
        return tuple(round(c * level) for c in COLORS[track])

    def _pads(self, s):
        colors = [(0, 0, 0)] * 64
        if self.view == "parts":
            for i in range(len(self.engine.parts)):
                colors[i] = (
                    (127, 90, 0)
                    if i == s.pending
                    else (10, 127, 30)
                    if i == s.part
                    else (15, 25, 50)
                )
        else:
            length = self.engine.parts[s.part].beats
            for track, notes in enumerate(s.tracks):
                for cell in range(6):
                    occupied = any(
                        cell * length / 6 <= n.beat < (cell + 1) * length / 6
                        for n in notes
                    )
                    level = (0.22 if occupied else 0.03) * (
                        0.2 if s.muted[track] else 1
                    )
                    if s.running and int(s.position / length * 6) == cell:
                        level = (
                            0.08 if s.muted[track] else 1 if s.active[track] else 0.45
                        )
                    row, offset = divmod(cell, 2)
                    colors[self.pad_index(row, track * 2 + offset)] = self._color(
                        track, level
                    )
                colors[48 + track * 2] = (
                    (100, 100, 100)
                    if track == self.selected
                    else self._color(track, 0.18)
                )
                colors[49 + track * 2] = self._color(
                    track, 0.04 if s.muted[track] else 0.75
                )
        self.fire.set_multiple_pad_colors([(i, *rgb) for i, rgb in enumerate(colors)])

    def _draw(self):
        s = self.engine.snapshot()
        self.last_snapshot = s
        self._pads(s)
        self.canvas.clear()
        for button, level in (
            (BUTTON_PLAY, 3 if s.running else 1),
            (BUTTON_STOP, 1 if s.running else 2),
            (BUTTON_PERFORM, 4 if self.view == "perform" else 1),
            (BUTTON_PATTERN, 3 if self.view == "parts" else 1),
            (BUTTON_REC, 0),
            (BUTTON_BROWSER, 2 if self.view == "help" else 0),
        ):
            self.fire.set_button_led(button, level)
        if self.view == "help":
            self.canvas.draw_page(
                "EIGHT TRACK",
                ["Bottom: Select / Mute", "PATTERN: parts", "PERFORM: return"],
            )
            return
        if self.view == "settings":
            value = s.transpose[self.selected]
            if self.menu.editing:
                self.canvas.draw_page(
                    "Edit: Transpose",
                    [
                        f"T{self.selected + 1} {NAMES[self.selected]} {value:+d}",
                        "Turn SELECT: change",
                        "Press SELECT: done",
                    ],
                )
            else:
                self.draw_menu(
                    f"T{self.selected + 1} SETTINGS",
                    [
                        f"Transpose {value:+d}",
                        "Mute: " + ("On" if s.muted[self.selected] else "Off"),
                        "Back",
                    ],
                    self.menu.selected_index,
                )
            return
        if self.view == "parts":
            labels = []
            for i, part in enumerate(self.engine.parts):
                state = "NEXT" if i == s.pending else "NOW" if i == s.part else ""
                labels.append(f"P{i + 1:02} {part.name} {state}")
            self.draw_menu("PART: press SELECT", labels, self.part_cursor)
            return
        self.draw_header(
            f"P{s.part + 1:02} " + ("PLAY" if s.running else "STOP"), str(s.bpm)
        )
        muted = "MUTED" if s.muted[self.selected] else "Preview"
        self.canvas.draw_text_fitted(
            f"T{self.selected + 1} {NAMES[self.selected]} {muted}", 4, 18, width=120
        )
        # Both displays use the same transformed notes and engine playhead.
        notes = s.tracks[self.selected]
        low = min((n.pitch for n in notes), default=60)
        high = max((n.pitch for n in notes), default=60)
        length = self.engine.parts[s.part].beats
        self.canvas.draw_rect(4, 32, 120, 16)
        for note in notes:
            x = 5 + int(note.beat / length * 116)
            y = 44 - round((note.pitch - low) / max(1, high - low) * 9)
            width = max(1, min(122 - x, int(note.duration / length * 116)))
            self.canvas.draw_line(x, y, x + width, y)
        x = 5 + int(s.position / length * 116)
        self.canvas.draw_line(x, 33, x, 46)
        footer = f"BAR {int(s.position // 4) + 1}/4"
        if s.pending is not None:
            footer += f"  NEXT P{s.pending + 1:02}"
        elif self.notice_left:
            footer = self.notice
        if s.error:
            footer = "Output error: STOP"
        self.canvas.draw_text_fitted(footer, 4, 52, width=120)

    def on_stop(self):
        self.engine.close()
