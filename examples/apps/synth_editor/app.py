"""A four-page JT-4000 CC editor, parameter graph, and audition keyboard."""

import json
import os
import tempfile
from collections import deque
from itertools import pairwise
from pathlib import Path

from PIL import ImageFont

from akai_fire.constants import (
    BUTTON_BROWSER,
    BUTTON_GRID_LEFT,
    BUTTON_GRID_RIGHT,
    BUTTON_NOTE,
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
from akai_fire_framework import AkaiFireApp, on

from .midi import SynthOutput
from .parameters import PAGES, PARAMETERS


class SynthEditorApp(AkaiFireApp):
    APP_NAME = "JT-4000 Editor"

    def __init__(self, fire=None, *, output=None, snapshot_path=None):
        self.output = output
        self._owns_output = output is None
        self.snapshot_path = Path(
            snapshot_path or os.environ.get("SYNTH_SNAPSHOT", "jt4000-snapshot.json")
        )
        try:
            super().__init__(fire)
        except Exception:
            if self._owns_output and self.output is not None:
                self.output.close()
            raise

    def on_init(self):
        self.page = self.selected = 0
        self.keyboard = False
        self.detail = False
        self.values = {cc: None for cc in PARAMETERS}
        self.history = deque([0] * 64, maxlen=64)
        self.notice = "Turn a knob to edit"
        if self.output is None:
            self.output = SynthOutput(
                os.environ.get("SYNTH_MIDI_OUTPUT"),
                int(os.environ.get("SYNTH_MIDI_CHANNEL", "1")),
            )
        self._draw()

    def _set_value(self, index, value):
        parameter = PAGES[self.page][1][index]
        value = max(0, min(127, value))
        self.output.cc(parameter.cc, value)
        self.values[parameter.cc] = value
        if self.selected != index:
            self.history.clear()
        self.selected = index
        self.history.append(value)
        self.notice = f"CC {parameter.cc}: {value}"

    @on.encoder(ROTARY_SELECT)
    def change_page(self, event):
        self._change_page(1 if event.delta > 0 else -1)

    @on.encoder((ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER, ROTARY_RESONANCE))
    def edit_parameter(self, event):
        index = (ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER, ROTARY_RESONANCE).index(
            event.encoder
        )
        value = self.values[PAGES[self.page][1][index].cc]
        # Unknown means no value has been sent, not a presumed synth default.
        start = 64 if value is None else value
        delta = (1 if event.delta > 0 else -1) if event.shift else event.delta
        self._set_value(index, start + delta)

    @on.pad()
    def play_or_set_value(self, event):
        if self.keyboard:
            note = 36 + event.pad
            self.output.audition(note, max(1, min(127, event.velocity)))
            self.notice = f"Note {note} / 300ms"
        else:
            row, column = divmod(event.pad, 16)
            self._set_value(row, round(column * 127 / 15))

    def _change_page(self, delta):
        self.page = (self.page + delta) % len(PAGES)
        self.selected = 0
        self.history.clear()
        self.notice = PAGES[self.page][0]

    @on.button((BUTTON_GRID_LEFT, BUTTON_GRID_RIGHT))
    def navigate(self, event):
        delta = 1 if event.button == BUTTON_GRID_RIGHT else -1
        if event.shift:
            self.output.set_channel(max(1, min(16, self.output.channel + delta)))
        else:
            self._change_page(delta)

    @on.button(BUTTON_NOTE)
    def toggle_keyboard(self, event):
        self.keyboard = not self.keyboard

    @on.button(BUTTON_BROWSER)
    def toggle_detail(self, event):
        self.detail = not self.detail

    @on.button(BUTTON_PLAY)
    def audition_chord(self, event):
        for note in (60, 64, 67):
            self.output.audition(note)

    @on.button(BUTTON_STOP)
    def silence(self, event):
        self.output.panic()
        self.notice = "Notes stopped"

    @on.button((BUTTON_REC, BUTTON_SELECT))
    def snapshot(self, event):
        try:
            if event.button == BUTTON_REC:
                self.save_snapshot()
            else:
                self.load_snapshot()
        except (OSError, ValueError, TypeError) as exc:
            self.notice = "Snapshot error"
            print(f"Snapshot error: {exc}")

    def save_snapshot(self):
        payload = {
            "profile": "jt4000-cc-v1",
            "values": {
                str(cc): value for cc, value in self.values.items() if value is not None
            },
        }
        # Replace only after a complete write so an interrupted save keeps the old file.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.snapshot_path.parent, delete=False
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            temp_path.replace(self.snapshot_path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        self.notice = "Snapshot saved"

    def load_snapshot(self):
        payload = json.loads(self.snapshot_path.read_text())
        if (
            not isinstance(payload, dict)
            or payload.get("profile") != "jt4000-cc-v1"
            or not isinstance(payload.get("values"), dict)
        ):
            raise ValueError("Not a JT-4000 CC snapshot")
        values = payload["values"]
        for key, value in values.items():
            if (
                key not in {str(cc) for cc in PARAMETERS}
                or type(value) is not int
                or not 0 <= value <= 127
            ):
                raise ValueError("Invalid CC or value in snapshot")
        # Validate everything before sending anything to the instrument.
        for key, value in values.items():
            self.output.cc(int(key), value)
            self.values[int(key)] = value
        self.notice = "Snapshot sent"

    def on_update(self, dt):
        self.output.update()
        self._draw()

    def _draw(self):
        canvas = self.canvas
        row_font = ImageFont.load_default(size=9)
        canvas.clear()
        title, parameters = PAGES[self.page]
        mode = "MIDI" if self.output.port_name else "DEMO"
        canvas.draw_text_fitted(f"{title} {mode}", 1, 0)
        canvas.draw_horizontal_line(0, 12, 128)
        if self.detail:
            parameter = parameters[self.selected]
            value = self.values[parameter.cc]
            canvas.draw_text_fitted(
                f"{parameter.name}: {value if value is not None else '?'}", 1, 15
            )
            if self.page in (1, 2):
                # This is a normalized shape, not a measured envelope/time scale.
                a, d, s, r = [self.values[p.cc] or 0 for p in parameters]
                points = [
                    (2, 49),
                    (5 + a // 5, 29),
                    (36 + d // 8, 49 - s * 20 // 127),
                    (90, 49 - s * 20 // 127),
                    (94 + r // 5, 49),
                ]
            else:
                points = [
                    (i * 2, 49 - value * 20 // 127)
                    for i, value in enumerate(self.history)
                ]
            for first, second in pairwise(points):
                canvas.draw_line(*first, *second)
        else:
            for index, parameter in enumerate(parameters):
                value = self.values[parameter.cc]
                y = 14 + index * 10
                canvas.draw_text_fitted(
                    f"{parameter.name} {value if value is not None else '?'}",
                    1,
                    y,
                    font=row_font,
                    width=80,
                )
                if value is not None:
                    canvas.fill_rect(86, y + 3, max(1, value * 40 // 127), 4)
        canvas.draw_text_fitted(
            f"CH{self.output.channel} {self.notice}", 1, 53, font=row_font
        )
        colors = []
        for pad in range(64):
            row, column = divmod(pad, 16)
            if self.keyboard:
                note = 36 + pad
                color = (
                    (127, 90, 0)
                    if note in self.output.notes
                    else (
                        (0, 30, 55) if note % 12 not in (1, 3, 6, 8, 10) else (0, 4, 8)
                    )
                )
            else:
                value = self.values[parameters[row].cc]
                level = -1 if value is None else round(value * 15 / 127)
                color = (0, 70, 45) if column <= level else (0, 3, 2)
                if column == level:
                    color = (90, 127, 100)
            colors.append((pad, *color))
        self.fire.set_multiple_pad_colors(colors)

    def on_stop(self):
        if self._owns_output:
            self.output.close()
        else:
            self.output.panic()


def main():
    print(
        "JT-4000: four knobs edit; rows set values; arrows/SELECT encoder change page."
    )
    print(
        "NOTE keyboard; PLAY audition; STOP silence; BROWSER detail; REC save; SELECT load."
    )
    with SynthEditorApp() as app:
        app.run()
