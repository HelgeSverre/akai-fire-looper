"""Live Fire input monitor: event log, encoder traces, and pad activity."""

import csv
import os
import threading
import time
from collections import deque
from itertools import pairwise
from pathlib import Path

from akai_fire_framework import AkaiFireApp


class MidiScopeApp(AkaiFireApp):
    APP_NAME = "MIDI Scope"

    def on_init(self):
        self._state_lock = threading.RLock()
        self.started = time.monotonic()
        self.events = deque(maxlen=512)
        self.trace = deque([64] * 64, maxlen=64)
        self.values = [64] * 5
        self.activity = [0.0] * 64
        self.counts = [0] * 64
        self.selected_encoder = 0
        self.frozen = False
        self.show_log = False
        self.notice = "PLAY freeze / REC CSV"

    def _record(self, kind, control, value):
        if not self.frozen:
            self.events.append(
                (round(time.monotonic() - self.started, 4), kind, control, value)
            )

    def on_pad_press(self, pad, velocity):
        with self._state_lock:
            if not self.frozen:
                self.activity[pad] = 1.0
                self.counts[pad] += 1
                self._record("pad", pad, velocity)
                self.notice = f"Pad {pad}: {velocity}"

    def on_encoder_turn(self, encoder_id, direction, velocity):
        encoders = [
            self.fire.ROTARY_VOLUME,
            self.fire.ROTARY_PAN,
            self.fire.ROTARY_FILTER,
            self.fire.ROTARY_RESONANCE,
            self.fire.ROTARY_SELECT,
        ]
        with self._state_lock:
            if self.frozen or encoder_id not in encoders:
                return
            index = encoders.index(encoder_id)
            delta = velocity if direction == "clockwise" else -velocity
            self.values[index] = max(0, min(127, self.values[index] + delta))
            if self.selected_encoder != index:
                self.trace.clear()
            self.selected_encoder = index
            self.trace.append(self.values[index])
            self._record("encoder", encoder_id, delta)
            self.notice = f"Encoder {index + 1}: {delta:+}"

    def on_button_press(self, button_id, event):
        with self._state_lock:
            self._record("button", button_id, event)
            if event != "press":
                return
            if button_id == self.fire.BUTTON_PLAY:
                self.frozen = not self.frozen
            elif button_id == self.fire.BUTTON_BROWSER:
                self.show_log = not self.show_log
            elif button_id == self.fire.BUTTON_STOP:
                self.events.clear()
                self.counts = [0] * 64
                self.activity = [0.0] * 64
                self.trace.clear()
            elif button_id == self.fire.BUTTON_REC:
                try:
                    self.export_csv(
                        Path(os.environ.get("MIDI_SCOPE_CSV", "midi-scope.csv"))
                    )
                    self.notice = "CSV saved"
                except OSError as exc:
                    self.notice = "CSV error"
                    print(f"CSV export failed: {exc}")

    def export_csv(self, path):
        with self._state_lock, Path(path).open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("seconds", "kind", "control", "value"))
            writer.writerows(self.events)

    def on_update(self, dt):
        with self._state_lock:
            if not self.frozen:
                self.activity = [max(0, level - dt * 1.5) for level in self.activity]
            canvas = self.canvas
            canvas.clear()
            canvas.draw_text(
                f"SCOPE {'HOLD' if self.frozen else 'LIVE'} {len(self.events)}", 1, 0
            )
            canvas.draw_horizontal_line(0, 12, 128)
            if self.show_log:
                for index, (timestamp, kind, control, value) in enumerate(
                    list(self.events)[-4:]
                ):
                    canvas.draw_text(
                        f"{kind[:3]} {control} {value}"[:24], 1, 15 + index * 9
                    )
            else:
                canvas.draw_text(
                    f"Encoder {self.selected_encoder + 1}: {self.values[self.selected_encoder]}",
                    1,
                    15,
                )
                points = [
                    (2 * i, 48 - value * 20 // 127)
                    for i, value in enumerate(self.trace)
                ]
                for first, second in pairwise(points):
                    canvas.draw_line(*first, *second)
                canvas.draw_horizontal_line(0, 49, 128)
            canvas.draw_text(self.notice[:24], 1, 54)
            self.fire.set_multiple_pad_colors(
                [
                    (
                        pad,
                        int(level * 127),
                        int(level * 90),
                        min(30, self.counts[pad] * 3),
                    )
                    for pad, level in enumerate(self.activity)
                ]
            )


def main():
    print(
        "MIDI Scope: turn knobs / press pads. PLAY freeze; BROWSER log; STOP clear; REC export CSV."
    )
    with MidiScopeApp() as app:
        app.run()


if __name__ == "__main__":
    main()
