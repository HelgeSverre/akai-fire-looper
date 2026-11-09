"""Immutable musical material shared by the playback engine and both displays."""

from dataclasses import dataclass

COLORS = (
    (127, 30, 8),
    (127, 85, 8),
    (110, 110, 20),
    (15, 127, 45),
    (10, 110, 127),
    (30, 55, 127),
    (95, 30, 127),
    (127, 30, 85),
)
NAMES = ("Kick", "Snare", "Hi-hat", "Bass", "Keys", "Arp", "Lead", "Pad")
QUANTIZE = (0, 0.5, 0.25)
QUANTIZE_NAMES = ("Off", "1/8", "1/16")


@dataclass(frozen=True)
class Note:
    beat: float
    pitch: int
    duration: float
    velocity: int = 90


@dataclass(frozen=True)
class Part:
    name: str
    tracks: tuple[tuple[Note, ...], ...]
    beats: float = 16.0


def demo_parts():
    """Three four-bar phrases, with independent drums, bass and melodic layers."""
    parts = []
    for name, root, busy in (
        ("Neon", 45, False),
        ("Lift", 48, True),
        ("Afterglow", 41, False),
    ):
        tracks = [[], [], [], [], [], [], [], []]
        for beat in range(16):
            tracks[0].append(Note(beat, 36, 0.18, 110))
            if beat % 4 in (1, 3):
                tracks[1].append(Note(beat, 38, 0.22, 94))
            for half in (0, 0.5):
                tracks[2].append(Note(beat + half, 42, 0.09, 60 if half else 82))
            bass = root + (7 if beat % 8 >= 6 else 0)
            tracks[3].append(Note(beat, bass, 0.7, 100))
            if beat % 4 == 0:
                for interval in (12, 15, 19):
                    tracks[4].append(Note(beat, root + interval, 1.4, 65))
            tracks[5].append(
                Note(beat + 0.5, root + 24 + (0, 3, 7, 10)[beat % 4], 0.3, 65)
            )
            if busy or beat % 2 == 0:
                tracks[6].append(
                    Note(beat + 0.25, root + 24 + (7, 3, 0, 10)[beat % 4], 0.65, 70)
                )
            if beat % 8 == 0:
                for interval in (12, 19):
                    tracks[7].append(Note(beat, root + interval, 7.5, 45))
        parts.append(Part(name, tuple(tuple(track) for track in tracks)))
    return tuple(parts)
