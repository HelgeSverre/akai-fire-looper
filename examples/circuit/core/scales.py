"""
Musical scales for the Circuit sequencer.
Provides scale definitions and note mapping functions.
"""

from typing import Dict, List

# Scale definitions - semitone intervals from root note
SCALES: Dict[str, List[int]] = {
    "MAJOR": [0, 2, 4, 5, 7, 9, 11],
    "NATURAL_MINOR": [0, 2, 3, 5, 7, 8, 10],
    "DORIAN": [0, 2, 3, 5, 7, 9, 10],
    "PHRYGIAN": [0, 1, 3, 5, 7, 8, 10],
    "MIXOLYDIAN": [0, 2, 4, 5, 7, 9, 10],
    "MELODIC_MINOR": [0, 2, 3, 5, 7, 9, 11],
    "HARMONIC_MINOR": [0, 2, 3, 5, 7, 8, 11],
    "BEBOP_DORIAN": [0, 2, 3, 5, 7, 9, 10, 11],
    "BLUES": [0, 3, 5, 6, 7, 10],
    "MINOR_PENTATONIC": [0, 3, 5, 7, 10],
    "HUNGARIAN_MINOR": [0, 2, 3, 6, 7, 8, 11],
    "UKRAINIAN_DORIAN": [0, 2, 3, 6, 7, 9, 10],
    "MARVA": [0, 1, 4, 6, 7, 9, 11],
    "TODI": [0, 1, 3, 6, 7, 8, 11],
    "WHOLE_TONE": [0, 2, 4, 6, 8, 10],
    "CHROMATIC": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
}

# Note names for display
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def get_scale_notes(
    scale_name: str, root_note: int = 60, octaves: int = 2
) -> List[int]:
    """
    Get MIDI note numbers for a scale across specified octaves.

    Args:
        scale_name: Name of the scale
        root_note: MIDI note number for the root (60 = C4)
        octaves: Number of octaves to span

    Returns:
        List of MIDI note numbers in the scale
    """
    if scale_name not in SCALES:
        scale_name = "MAJOR"  # Default fallback

    intervals = SCALES[scale_name]
    notes = []

    base_octave = root_note // 12
    root_offset = root_note % 12

    for octave in range(octaves):
        for interval in intervals:
            note = (base_octave + octave) * 12 + root_offset + interval
            if 0 <= note <= 127:  # Valid MIDI range
                notes.append(note)

    return notes


def map_pad_to_note(
    pad_index: int, scale_name: str = "MAJOR", root_note: int = 60
) -> int:
    """
    Map a pad index (0-31 for rows 3-4) to a MIDI note number in the given scale.

    Args:
        pad_index: Pad index (0-31)
        scale_name: Name of the scale
        root_note: MIDI note number for the root

    Returns:
        MIDI note number
    """
    # Get 2 octaves of scale notes
    scale_notes = get_scale_notes(scale_name, root_note, octaves=3)

    # Map pad to scale note
    if pad_index < len(scale_notes):
        return scale_notes[pad_index]
    else:
        # If we run out of scale notes, continue chromatically
        return root_note + pad_index


def get_note_name(midi_note: int) -> str:
    """
    Get the name of a MIDI note (e.g., C4, F#3).

    Args:
        midi_note: MIDI note number (0-127)

    Returns:
        Note name with octave
    """
    if not (0 <= midi_note <= 127):
        return "---"

    octave = midi_note // 12 - 1
    note_index = midi_note % 12
    return f"{NOTE_NAMES[note_index]}{octave}"


def is_root_note(midi_note: int, root_note: int) -> bool:
    """
    Check if a MIDI note is a root note in any octave.

    Args:
        midi_note: MIDI note to check
        root_note: Root note to compare against

    Returns:
        True if it's a root note
    """
    return (midi_note % 12) == (root_note % 12)
