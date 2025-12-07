"""
Clip data structure for MIDI Looper.

A clip contains recorded MIDI events with timing information.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
import time


class ClipState(Enum):
    """State of a clip slot."""

    EMPTY = auto()  # No content
    RECORDING = auto()  # Currently recording
    PLAYING = auto()  # Currently playing
    STOPPED = auto()  # Has content, stopped
    ARMED = auto()  # Ready to record on next beat


@dataclass
class MidiEvent:
    """A single MIDI event with timing."""

    time: float  # Time offset from loop start (0.0 - 1.0 normalized)
    note: int  # MIDI note number (0-127)
    velocity: int  # MIDI velocity (0-127)
    duration: float  # Note duration (normalized)

    def __post_init__(self):
        # Clamp values
        self.time = max(0.0, min(1.0, self.time))
        self.note = max(0, min(127, self.note))
        self.velocity = max(0, min(127, self.velocity))
        self.duration = max(0.0, min(1.0, self.duration))


@dataclass
class Clip:
    """
    A clip containing MIDI events.

    Clips are fixed-length loops that can be:
    - Empty (no content)
    - Recording (capturing new events)
    - Playing (looping content)
    - Stopped (has content but not playing)
    """

    events: List[MidiEvent] = field(default_factory=list)
    state: ClipState = ClipState.EMPTY
    length_bars: int = 4  # Length in bars

    # Recording state
    _record_start: float = 0.0
    _pending_notes: dict = field(default_factory=dict)  # note -> (start_time, velocity)

    # Playback state
    _play_position: float = 0.0  # Current position (0.0 - 1.0)
    _last_update: float = 0.0

    def __post_init__(self):
        self._pending_notes = {}

    @property
    def is_empty(self) -> bool:
        """Check if clip has no content."""
        return len(self.events) == 0 and self.state == ClipState.EMPTY

    @property
    def has_content(self) -> bool:
        """Check if clip has recorded events."""
        return len(self.events) > 0

    @property
    def is_playing(self) -> bool:
        """Check if clip is currently playing."""
        return self.state == ClipState.PLAYING

    @property
    def is_recording(self) -> bool:
        """Check if clip is currently recording."""
        return self.state == ClipState.RECORDING

    # =========================================================================
    # Recording
    # =========================================================================

    def start_recording(self, bpm: float = 120.0):
        """Start recording into this clip."""
        self.state = ClipState.RECORDING
        self._record_start = time.time()
        self._pending_notes = {}
        # Clear existing events for fresh recording
        self.events.clear()

    def start_overdub(self, bpm: float = 120.0):
        """Start overdubbing (add to existing content)."""
        self.state = ClipState.RECORDING
        self._record_start = time.time()
        self._pending_notes = {}
        # Keep existing events

    def stop_recording(self):
        """Stop recording and finalize clip."""
        # Complete any pending notes
        now = time.time()
        for note, (start_time, velocity) in self._pending_notes.items():
            duration = now - start_time
            self._add_event(start_time, note, velocity, duration)

        self._pending_notes = {}

        if self.has_content:
            self.state = ClipState.STOPPED
        else:
            self.state = ClipState.EMPTY

    def record_note_on(self, note: int, velocity: int):
        """Record a note-on event."""
        if self.state != ClipState.RECORDING:
            return

        self._pending_notes[note] = (time.time(), velocity)

    def record_note_off(self, note: int):
        """Record a note-off event."""
        if self.state != ClipState.RECORDING:
            return

        if note in self._pending_notes:
            start_time, velocity = self._pending_notes.pop(note)
            duration = time.time() - start_time
            self._add_event(start_time, note, velocity, duration)

    def _add_event(self, abs_time: float, note: int, velocity: int, duration: float):
        """Add an event with absolute timing, converting to normalized time."""
        # Calculate loop length in seconds
        # (simplified: 4 bars at 120 BPM = 8 seconds)
        loop_seconds = self.length_bars * 2.0  # Assuming 120 BPM, 4 beats per bar

        # Convert to normalized time within loop
        elapsed = abs_time - self._record_start
        normalized_time = (elapsed % loop_seconds) / loop_seconds
        normalized_duration = min(duration / loop_seconds, 1.0)

        self.events.append(
            MidiEvent(
                time=normalized_time,
                note=note,
                velocity=velocity,
                duration=normalized_duration,
            )
        )

    # =========================================================================
    # Playback
    # =========================================================================

    def start_playing(self):
        """Start playing this clip."""
        if not self.has_content:
            return

        self.state = ClipState.PLAYING
        self._play_position = 0.0
        self._last_update = time.time()

    def stop_playing(self):
        """Stop playing this clip."""
        if self.has_content:
            self.state = ClipState.STOPPED
        else:
            self.state = ClipState.EMPTY
        self._play_position = 0.0

    def toggle_playback(self):
        """Toggle between playing and stopped."""
        if self.is_playing:
            self.stop_playing()
        elif self.has_content:
            self.start_playing()

    def update(self, bpm: float = 120.0) -> List[MidiEvent]:
        """
        Update playback position and return events that should trigger.

        Call this in your update loop.

        Returns:
            List of events that should be triggered this frame
        """
        if self.state != ClipState.PLAYING:
            return []

        now = time.time()
        dt = now - self._last_update
        self._last_update = now

        # Calculate position advancement
        loop_seconds = self.length_bars * (60.0 / bpm) * 4  # 4 beats per bar
        position_delta = dt / loop_seconds

        old_position = self._play_position
        self._play_position = (self._play_position + position_delta) % 1.0

        # Find events between old and new position
        triggered = []

        # Handle wrap-around
        if self._play_position < old_position:
            # Wrapped around - check end of loop and start
            for event in self.events:
                if event.time >= old_position or event.time < self._play_position:
                    triggered.append(event)
        else:
            # Normal case
            for event in self.events:
                if old_position <= event.time < self._play_position:
                    triggered.append(event)

        return triggered

    # =========================================================================
    # Clip Management
    # =========================================================================

    def clear(self):
        """Clear all content from clip."""
        self.events.clear()
        self.state = ClipState.EMPTY
        self._play_position = 0.0
        self._pending_notes = {}

    def arm(self):
        """Arm clip for recording on next transport start."""
        self.state = ClipState.ARMED

    def get_color(self) -> tuple:
        """Get display color based on state."""
        if self.state == ClipState.EMPTY:
            return (0, 0, 0)  # Off
        elif self.state == ClipState.RECORDING:
            return (127, 0, 0)  # Red
        elif self.state == ClipState.PLAYING:
            return (0, 127, 0)  # Green
        elif self.state == ClipState.STOPPED:
            return (64, 64, 0)  # Dim yellow
        elif self.state == ClipState.ARMED:
            return (64, 0, 0)  # Dim red
        return (0, 0, 0)


class ClipGrid:
    """
    Grid of clips organized by track and slot.

    4 tracks x 16 slots = 64 clips (maps to 64 pads)
    """

    def __init__(self, tracks: int = 4, slots: int = 16):
        self.tracks = tracks
        self.slots = slots
        self.clips: List[List[Clip]] = [
            [Clip() for _ in range(slots)] for _ in range(tracks)
        ]

        # Currently selected clip for recording
        self.selected_track = 0
        self.selected_slot = 0

    def get_clip(self, track: int, slot: int) -> Optional[Clip]:
        """Get clip at position."""
        if 0 <= track < self.tracks and 0 <= slot < self.slots:
            return self.clips[track][slot]
        return None

    def get_clip_by_pad(self, pad_index: int) -> Optional[Clip]:
        """Get clip by pad index (0-63)."""
        track = pad_index // self.slots
        slot = pad_index % self.slots
        return self.get_clip(track, slot)

    def pad_to_position(self, pad_index: int) -> tuple:
        """Convert pad index to (track, slot)."""
        return (pad_index // self.slots, pad_index % self.slots)

    def position_to_pad(self, track: int, slot: int) -> int:
        """Convert (track, slot) to pad index."""
        return track * self.slots + slot

    @property
    def selected_clip(self) -> Clip:
        """Get currently selected clip."""
        return self.clips[self.selected_track][self.selected_slot]

    def select(self, track: int, slot: int):
        """Select a clip."""
        if 0 <= track < self.tracks and 0 <= slot < self.slots:
            self.selected_track = track
            self.selected_slot = slot

    def stop_all(self):
        """Stop all clips."""
        for track in self.clips:
            for clip in track:
                if clip.is_playing or clip.is_recording:
                    clip.stop_playing()

    def update(self, bpm: float = 120.0) -> List[tuple]:
        """
        Update all playing clips.

        Returns:
            List of (track, slot, events) tuples for triggered events
        """
        results = []
        for track_idx, track in enumerate(self.clips):
            for slot_idx, clip in enumerate(track):
                events = clip.update(bpm)
                if events:
                    results.append((track_idx, slot_idx, events))
        return results
