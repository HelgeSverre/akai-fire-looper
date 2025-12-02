"""
MIDI testing utilities for AKAI Fire applications.

This module provides mock MIDI objects for testing sequencers and
other MIDI-enabled components without hardware.

Classes:
    MidiMessage: Recorded MIDI message data
    MockMidiManager: Mock MIDI manager that records all output
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import time


@dataclass
class MidiMessage:
    """
    Recorded MIDI message.

    Attributes:
        type: Message type ("note_on", "note_off", "cc", "all_notes_off", "program_change")
        channel: MIDI channel (1-16)
        note_or_cc: Note number or CC number
        value: Velocity or CC value
        timestamp: When the message was recorded
    """
    type: str
    channel: int
    note_or_cc: int
    value: int
    timestamp: float = field(default_factory=time.time)

    def __repr__(self):
        if self.type == "note_on":
            return f"NoteOn(ch={self.channel}, note={self.note_or_cc}, vel={self.value})"
        elif self.type == "note_off":
            return f"NoteOff(ch={self.channel}, note={self.note_or_cc})"
        elif self.type == "cc":
            return f"CC(ch={self.channel}, cc={self.note_or_cc}, val={self.value})"
        elif self.type == "program_change":
            return f"ProgramChange(ch={self.channel}, prog={self.note_or_cc})"
        elif self.type == "all_notes_off":
            return f"AllNotesOff(ch={self.channel})"
        return f"MidiMessage({self.type}, ch={self.channel})"


class MockMidiManager:
    """
    Mock MIDI manager that records all MIDI output.

    Useful for verifying that sequencers and other components send
    correct MIDI messages without needing actual MIDI hardware.

    Features:
        - Records all MIDI messages sent
        - Provides assertion helpers for testing
        - Query methods for filtering messages
        - Same API as real MidiManager for drop-in replacement

    Example:
        >>> midi = MockMidiManager()
        >>> sequencer = Sequencer(midi_manager=midi)
        >>> sequencer.play_note(60, velocity=100)
        >>> midi.assert_note_on(channel=1, note=60, velocity=100)
        >>> assert len(midi.get_notes_on()) == 1
    """

    def __init__(self):
        """Initialize mock MIDI manager."""
        self.messages: List[MidiMessage] = []
        self.output_port: Optional[str] = None
        self.input_port: Optional[str] = None
        self._ports_refreshed = False

    # =========================================================================
    # Port Management (Mock)
    # =========================================================================

    def refresh_ports(self) -> Tuple[List[str], List[str]]:
        """
        Return mock port lists.

        Returns:
            Tuple of (input_ports, output_ports)
        """
        self._ports_refreshed = True
        return (["Mock Input"], ["Mock Output"])

    def set_output_port(self, port_name: str):
        """Set mock output port."""
        self.output_port = port_name

    def set_input_port(self, port_name: str):
        """Set mock input port."""
        self.input_port = port_name

    def get_status(self) -> Dict[str, Any]:
        """
        Return mock status.

        Returns:
            Dictionary with connection status
        """
        return {
            "output_port": self.output_port,
            "input_port": self.input_port,
            "connected": self.output_port is not None,
            "message_count": len(self.messages),
        }

    def cleanup(self):
        """Mock cleanup - clears messages."""
        self.messages.clear()

    # =========================================================================
    # Send Methods (Record Messages)
    # =========================================================================

    def send_note_on(self, channel: int, note: int, velocity: int):
        """
        Record a note on message.

        Args:
            channel: MIDI channel (1-16)
            note: Note number (0-127)
            velocity: Note velocity (0-127)
        """
        self.messages.append(MidiMessage("note_on", channel, note, velocity))

    def send_note_off(self, channel: int, note: int):
        """
        Record a note off message.

        Args:
            channel: MIDI channel (1-16)
            note: Note number (0-127)
        """
        self.messages.append(MidiMessage("note_off", channel, note, 0))

    def send_cc(self, channel: int, cc: int, value: int):
        """
        Record a CC (Control Change) message.

        Args:
            channel: MIDI channel (1-16)
            cc: CC number (0-127)
            value: CC value (0-127)
        """
        self.messages.append(MidiMessage("cc", channel, cc, value))

    def send_program_change(self, channel: int, program: int):
        """
        Record a program change message.

        Args:
            channel: MIDI channel (1-16)
            program: Program number (0-127)
        """
        self.messages.append(MidiMessage("program_change", channel, program, 0))

    def send_all_notes_off(self, channel: Optional[int] = None):
        """
        Record all notes off message.

        Args:
            channel: Specific channel, or None for all channels
        """
        if channel is not None:
            self.messages.append(MidiMessage("all_notes_off", channel, 0, 0))
        else:
            for ch in range(1, 17):
                self.messages.append(MidiMessage("all_notes_off", ch, 0, 0))

    def send_raw(self, data: bytes):
        """
        Record a raw MIDI message.

        Args:
            data: Raw MIDI bytes
        """
        # Parse common message types
        if len(data) >= 1:
            status = data[0]
            msg_type = status & 0xF0
            channel = (status & 0x0F) + 1

            if msg_type == 0x90 and len(data) >= 3:  # Note On
                self.send_note_on(channel, data[1], data[2])
            elif msg_type == 0x80 and len(data) >= 3:  # Note Off
                self.send_note_off(channel, data[1])
            elif msg_type == 0xB0 and len(data) >= 3:  # CC
                self.send_cc(channel, data[1], data[2])

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_notes_on(self, channel: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        Get all note-on messages as (note, velocity) tuples.

        Args:
            channel: Filter by channel, or None for all channels

        Returns:
            List of (note, velocity) tuples
        """
        return [
            (msg.note_or_cc, msg.value)
            for msg in self.messages
            if msg.type == "note_on" and (channel is None or msg.channel == channel)
        ]

    def get_notes_off(self, channel: Optional[int] = None) -> List[int]:
        """
        Get all note-off messages as note numbers.

        Args:
            channel: Filter by channel, or None for all channels

        Returns:
            List of note numbers
        """
        return [
            msg.note_or_cc
            for msg in self.messages
            if msg.type == "note_off" and (channel is None or msg.channel == channel)
        ]

    def get_cc_values(self, channel: Optional[int] = None, cc: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        Get CC messages as (cc_number, value) tuples.

        Args:
            channel: Filter by channel, or None for all channels
            cc: Filter by CC number, or None for all CCs

        Returns:
            List of (cc_number, value) tuples
        """
        return [
            (msg.note_or_cc, msg.value)
            for msg in self.messages
            if msg.type == "cc"
            and (channel is None or msg.channel == channel)
            and (cc is None or msg.note_or_cc == cc)
        ]

    def get_messages_by_type(self, msg_type: str) -> List[MidiMessage]:
        """
        Get all messages of a specific type.

        Args:
            msg_type: Message type string

        Returns:
            List of matching MidiMessage objects
        """
        return [msg for msg in self.messages if msg.type == msg_type]

    def get_messages_by_channel(self, channel: int) -> List[MidiMessage]:
        """
        Get all messages on a specific channel.

        Args:
            channel: MIDI channel (1-16)

        Returns:
            List of matching MidiMessage objects
        """
        return [msg for msg in self.messages if msg.channel == channel]

    def clear_messages(self):
        """Clear all recorded messages."""
        self.messages.clear()

    # =========================================================================
    # Assertion Helpers
    # =========================================================================

    def assert_note_on(self, channel: int, note: int, velocity: int):
        """
        Assert a note on was sent.

        Args:
            channel: Expected channel
            note: Expected note number
            velocity: Expected velocity

        Raises:
            AssertionError: If matching note_on not found
        """
        for msg in self.messages:
            if (msg.type == "note_on" and
                msg.channel == channel and
                msg.note_or_cc == note and
                msg.value == velocity):
                return
        raise AssertionError(
            f"Expected note_on(ch={channel}, note={note}, vel={velocity}) not found. "
            f"Messages: {[m for m in self.messages if m.type == 'note_on']}"
        )

    def assert_note_off(self, channel: int, note: int):
        """
        Assert a note off was sent.

        Args:
            channel: Expected channel
            note: Expected note number

        Raises:
            AssertionError: If matching note_off not found
        """
        for msg in self.messages:
            if (msg.type == "note_off" and
                msg.channel == channel and
                msg.note_or_cc == note):
                return
        raise AssertionError(
            f"Expected note_off(ch={channel}, note={note}) not found. "
            f"Messages: {[m for m in self.messages if m.type == 'note_off']}"
        )

    def assert_cc(self, channel: int, cc: int, value: int):
        """
        Assert a CC message was sent.

        Args:
            channel: Expected channel
            cc: Expected CC number
            value: Expected value

        Raises:
            AssertionError: If matching CC not found
        """
        for msg in self.messages:
            if (msg.type == "cc" and
                msg.channel == channel and
                msg.note_or_cc == cc and
                msg.value == value):
                return
        raise AssertionError(
            f"Expected cc(ch={channel}, cc={cc}, val={value}) not found. "
            f"Messages: {[m for m in self.messages if m.type == 'cc']}"
        )

    def assert_no_notes(self):
        """
        Assert no note messages were sent.

        Raises:
            AssertionError: If any note_on or note_off found
        """
        notes = [m for m in self.messages if m.type in ("note_on", "note_off")]
        assert len(notes) == 0, f"Expected no notes, but found: {notes}"

    def assert_message_count(self, expected: int):
        """
        Assert total message count.

        Args:
            expected: Expected number of messages

        Raises:
            AssertionError: If count doesn't match
        """
        actual = len(self.messages)
        assert actual == expected, f"Expected {expected} messages, got {actual}"

    def assert_note_sequence(self, expected: List[Tuple[int, int]], channel: Optional[int] = None):
        """
        Assert a specific sequence of notes was played.

        Args:
            expected: List of (note, velocity) tuples in expected order
            channel: Optional channel filter

        Raises:
            AssertionError: If sequence doesn't match
        """
        actual = self.get_notes_on(channel)
        assert actual == expected, f"Expected note sequence {expected}, got {actual}"

    def dump_messages(self) -> str:
        """
        Get a human-readable dump of all messages.

        Returns:
            Formatted string of all messages
        """
        if not self.messages:
            return "No MIDI messages recorded"

        lines = ["MIDI Messages:"]
        for i, msg in enumerate(self.messages):
            lines.append(f"  {i}: {msg}")
        return "\n".join(lines)
