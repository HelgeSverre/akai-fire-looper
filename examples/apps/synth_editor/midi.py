"""Instrument output, separate from the Fire's controller connection."""

import time

import rtmidi


class SynthOutput:
    def __init__(self, port_name=None, channel=1):
        if not 1 <= channel <= 16:
            raise ValueError("MIDI channel must be 1–16")
        self.channel = channel
        self.port_name = None
        self.port = rtmidi.MidiOut()
        self.notes = {}
        self.closed = False
        try:
            ports = self.port.get_ports()
            if port_name is None:
                matches = [p for p in ports if "jt-4000" in p.lower()]
                port_name = matches[0] if len(matches) == 1 else None
            if port_name:
                if "fire" in port_name.lower() or port_name not in ports:
                    raise ValueError(f"Choose an instrument output from {ports!r}")
                self.port.open_port(ports.index(port_name))
                self.port_name = port_name
            print(
                f"Synth output: {self.port_name or 'PREVIEW (no MIDI output)'}; channel {channel}"
            )
            print(f"Available outputs: {ports}")
        except Exception:
            self.port.close_port()
            raise

    def send(self, message):
        if self.closed:
            raise RuntimeError("Synth output is closed")
        if self.port_name is not None:
            self.port.send_message(message)

    def cc(self, number, value):
        self.send([0xB0 | (self.channel - 1), number, value])

    def audition(self, note, velocity=90):
        # Fire pad-release events are not exposed by the driver. Short, bounded
        # auditions avoid hanging notes and never pretend to be a held keyboard.
        if note in self.notes:
            self._note_off(note)
        elif len(self.notes) >= 4:
            self._note_off(next(iter(self.notes)))
        self.send([0x90 | (self.channel - 1), note, velocity])
        self.notes[note] = time.monotonic() + 0.3

    def _note_off(self, note):
        try:
            self.send([0x80 | (self.channel - 1), note, 0])
        finally:
            self.notes.pop(note, None)

    def update(self):
        now = time.monotonic()
        for note, deadline in list(self.notes.items()):
            if now >= deadline:
                self._note_off(note)

    def panic(self):
        error = None
        for note in list(self.notes):
            try:
                self._note_off(note)
            except Exception as exc:  # noqa: BLE001 - finish cleanup, then re-raise
                if error is None:
                    error = exc
        if error is not None:
            raise error

    def set_channel(self, channel):
        if not 1 <= channel <= 16:
            raise ValueError("MIDI channel must be 1–16")
        self.panic()
        self.channel = channel

    def close(self):
        if self.closed:
            return
        try:
            self.panic()
        finally:
            self.closed = True
            self.port.close_port()
