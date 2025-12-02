import re


class MidiUtils:
    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    @staticmethod
    def note_name_to_midi(note: str) -> int:
        """Convert note name (e.g., C4, A#3) to MIDI number."""
        match = re.match(r"([A-Ga-g]#?)(-?\d+)", note)
        if not match:
            raise ValueError(f"Invalid note format: {note}")

        note_name, octave = match.groups()
        note_name = note_name.upper()
        octave = int(octave)

        if note_name not in MidiUtils.NOTE_NAMES:
            raise ValueError(f"Invalid note name: {note_name}")

        note_index = MidiUtils.NOTE_NAMES.index(note_name)
        return (octave + 1) * 12 + note_index

    @staticmethod
    def midi_to_note_name(midi_number: int) -> str:
        """Convert MIDI number to note name (e.g., 60 -> C4)."""
        if not (0 <= midi_number <= 127):
            raise ValueError("MIDI number out of range (0-127)")

        note_index = midi_number % 12
        octave = (midi_number // 12) - 1
        return f"{MidiUtils.NOTE_NAMES[note_index]}{octave}"

    @staticmethod
    def scale_velocity(value: float, min_val: int = 1, max_val: int = 127) -> int:
        """Scale a 0.0-1.0 float to a MIDI velocity value (1-127)."""
        return max(min_val, min(max_val, int(value * (max_val - min_val) + min_val)))

    @staticmethod
    def midi_cc_to_value(cc_value: int, min_val: int = 0, max_val: int = 127) -> int:
        """Scale MIDI CC value (0-127) to a given range."""
        return min_val + ((cc_value / 127) * (max_val - min_val))

    @staticmethod
    def value_to_midi_cc(value: float, min_val: int = 0, max_val: int = 127) -> int:
        """Convert a float (in given range) to MIDI CC (0-127)."""
        return max(0, min(127, int(((value - min_val) / (max_val - min_val)) * 127)))
