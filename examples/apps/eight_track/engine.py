"""Clock-owned playback; UI frames only issue commands and read snapshots.

This first stage plays immutable demo parts. Recording will be added separately;
it must not inherit the display loop's input timing.
"""

import logging
import math
import threading
import time
from dataclasses import dataclass

from .model import QUANTIZE, Note, demo_parts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    part: int
    pending: int | None
    position: float
    running: bool
    bpm: int
    muted: tuple[bool, ...]
    transpose: tuple[int, ...]
    quantize: int
    swing: int
    active: tuple[bool, ...]
    tracks: tuple[tuple[Note, ...], ...]
    error: str


class Engine:
    def __init__(self, output=None):
        self.parts = demo_parts()
        self.output = output
        self._lock = threading.RLock()
        self._halt = threading.Event()
        self._thread = None
        self.part = 0
        self.pending = None
        self.position = 0.0
        self.running = False
        self.bpm = 120
        self.muted = [False] * 8
        self.transpose = [0] * 8
        self.quantize = 0
        self.swing = 0
        self.error = ""
        self._active = {}
        self._closed = False

    def _material(self):
        tracks = []
        length = self.parts[self.part].beats
        step = QUANTIZE[self.quantize]
        for track, notes in enumerate(self.parts[self.part].tracks):
            transformed = []
            for note in notes:
                beat = round(note.beat / step) * step if step else note.beat
                if int(beat * 2) % 2:
                    beat += self.swing / 100 * 0.25
                beat = min(length - 0.01, beat)
                transformed.append(
                    Note(
                        beat,
                        max(0, min(127, note.pitch + self.transpose[track])),
                        min(note.duration, length - beat),
                        note.velocity,
                    )
                )
            tracks.append(tuple(transformed))
        return tuple(tracks)

    def snapshot(self):
        with self._lock:
            return Snapshot(
                self.part,
                self.pending,
                self.position,
                self.running,
                self.bpm,
                tuple(self.muted),
                tuple(self.transpose),
                self.quantize,
                self.swing,
                tuple(any(key[0] == i for key in self._active) for i in range(8)),
                self._material(),
                self.error,
            )

    def _fail_output(self, exc):
        self.running = False
        self.pending = None
        self.error = f"Output failed: {exc}"
        self._active.clear()
        self._halt.set()
        if self.output:
            try:
                self.output.stop()
            except Exception:
                logger.exception("Preview output also failed during cleanup")

    def _send(self, method, *args):
        if self.output:
            try:
                getattr(self.output, method)(*args)
            except Exception as exc:  # noqa: BLE001 - all sink calls share the failure transition
                self._fail_output(exc)

    def _off(self, key):
        if key not in self._active:
            return
        pitch = self._active.pop(key)
        # Two overlapping events on one track may share a pitch.
        if self.output and not any(
            k[0] == key[0] and p == pitch for k, p in self._active.items()
        ):
            self._send("note_off", key[0], pitch)

    def _silence(self, track=None):
        for key in list(self._active):
            if track is None or key[0] == track:
                self._off(key)

    def _on(self, key, note):
        if self.error or self._closed or self.muted[key[0]] or key in self._active:
            return
        already = any(
            k[0] == key[0] and p == note.pitch for k, p in self._active.items()
        )
        self._active[key] = note.pitch
        if self.output and not already:
            self._send("note_on", key[0], note.pitch, note.velocity)

    def _resume_notes(self):
        for track, notes in enumerate(self._material()):
            for i, note in enumerate(notes):
                if note.beat <= self.position < note.beat + note.duration:
                    self._on((track, i), note)

    def play(self):
        with self._lock:
            if self._closed or self.running or self.error:
                return
            self.running = True
            self._resume_notes()

    def stop(self):
        with self._lock:
            if not self.running:
                self.position = 0.0
            self.running = False
            self.pending = None
            self._silence()

    def select_part(self, index):
        if not 0 <= index < len(self.parts):
            raise IndexError(index)
        with self._lock:
            if self.running:
                self.pending = index if index != self.part else None
            else:
                self._silence()
                self.part, self.pending, self.position = index, None, 0.0

    def toggle_mute(self, track):
        with self._lock:
            self.muted[track] = not self.muted[track]
            if self.muted[track]:
                self._silence(track)
            elif self.running:
                self._resume_notes()

    def adjust(self, name, delta, track=0):
        with self._lock:
            if name == "tempo":
                self.bpm = max(40, min(240, self.bpm + delta))
                return
            self._silence()
            if name == "quantize":
                self.quantize = max(0, min(2, self.quantize + delta))
            elif name == "swing":
                self.swing = max(0, min(100, self.swing + delta))
            elif name == "transpose":
                self.transpose[track] = max(-24, min(24, self.transpose[track] + delta))
            else:
                raise ValueError(name)
            if self.running:
                self._resume_notes()

    def _segment(self, end):
        events = []
        for track, notes in enumerate(self._material()):
            for i, note in enumerate(notes):
                key = (track, i)
                if self.position < note.beat <= end:
                    events.append((note.beat, 1, key, note))
                if self.position < note.beat + note.duration <= end:
                    events.append((note.beat + note.duration, 0, key, note))
        # Release before attack at identical positions.
        for _, action, key, note in sorted(events):
            if action:
                self._on(key, note)
            elif key in self._active:
                self._off(key)
        self.position = end

    def advance(self, seconds):
        """Advance musical time; deterministic tests use this without a thread."""
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("seconds must be finite and non-negative")
        with self._lock:
            if not self.running or self._closed:
                return
            beats = seconds * self.bpm / 60
            # After a stall, skip expired attacks instead of firing a burst.
            late = seconds > 0.1
            if late:
                self._silence()
                distance = self.parts[self.part].beats - self.position
                if beats >= distance:
                    beats -= distance
                    self.position = 0.0
                    if self.pending is not None:
                        self.part, self.pending = self.pending, None
                self.position = (self.position + beats) % self.parts[self.part].beats
                self._resume_notes()
                return
            while beats > 0:
                length = self.parts[self.part].beats
                distance = min(beats, length - self.position)
                end = self.position + distance
                self._segment(end)
                beats -= distance
                if self.position >= length:
                    self._silence()
                    self.position = 0.0
                    if self.pending is not None:
                        self.part, self.pending = self.pending, None
                    self._resume_notes()

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Engine is closed")
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run, name="eight-track-clock", daemon=True
            )
            self._thread.start()

    def _run(self):
        previous = time.monotonic()
        try:
            while not self._halt.wait(0.005):
                now = time.monotonic()
                self.advance(now - previous)
                previous = now
        except Exception as exc:  # noqa: BLE001 - contain output failures at the worker boundary
            with self._lock:
                self._fail_output(exc)

    def close(self):
        self._halt.set()
        if self._thread is not None:
            self._thread.join()
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self.running = False
            try:
                self._silence()
            finally:
                self._send("stop")
