"""
MIDI I/O management for hardware synthesizer communication.
Handles all MIDI input/output for the sequencer.
"""

import rtmidi
import time
import threading
from typing import List, Dict, Callable, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class MidiMessage:
    """A MIDI message with timestamp."""

    channel: int
    data: List[int]
    timestamp: float
    note: Optional[int] = None
    velocity: Optional[int] = None


class MidiManager:
    """
    Manages MIDI I/O for hardware synthesizer communication.
    Handles note output, CC messages, and optional input recording.
    """

    def __init__(self):
        self.midi_out = None
        self.midi_in = None

        # MIDI ports
        self.output_port_name = ""
        self.input_port_name = ""
        self.output_port_index = -1
        self.input_port_index = -1

        # Message handling
        self.input_callback = None
        self.note_callbacks: Dict[int, List[Callable]] = (
            {}
        )  # Channel -> list of callbacks

        # Active notes tracking (for proper note-off timing)
        self.active_notes: Dict[Tuple[int, int], float] = (
            {}
        )  # (channel, note) -> start_time

        # MIDI activity tracking for visual feedback
        self.channel_activity: Dict[int, float] = {}  # Channel -> last_activity_time
        self.channel_velocities: Dict[int, int] = {}  # Channel -> last_velocity

        # Thread safety
        self.lock = threading.Lock()

        self._initialize_midi()

    def _initialize_midi(self):
        """Initialize MIDI input and output."""
        try:
            # Initialize MIDI output
            self.midi_out = rtmidi.MidiOut()

            # Initialize MIDI input (optional, for recording)
            self.midi_in = rtmidi.MidiIn()

            # Get available ports
            self.refresh_ports()

        except Exception as e:
            print(f"MIDI initialization error: {e}")

    def refresh_ports(self) -> Tuple[List[str], List[str]]:
        """Get available MIDI input and output ports."""
        input_ports = []
        output_ports = []

        try:
            if self.midi_in:
                input_ports = self.midi_in.get_ports()
            if self.midi_out:
                output_ports = self.midi_out.get_ports()
        except Exception as e:
            print(f"Error refreshing MIDI ports: {e}")

        return input_ports, output_ports

    def set_output_port(self, port_name: str) -> bool:
        """Set the MIDI output port."""
        try:
            if not self.midi_out:
                return False

            # Close current port if open
            if self.midi_out.is_port_open():
                self.midi_out.close_port()

            # Find port index
            output_ports = self.midi_out.get_ports()
            port_index = -1

            for i, port in enumerate(output_ports):
                if port == port_name:
                    port_index = i
                    break

            if port_index >= 0:
                self.midi_out.open_port(port_index)
                self.output_port_name = port_name
                self.output_port_index = port_index
                print(f"MIDI output connected to: {port_name}")
                return True
            else:
                print(f"MIDI output port not found: {port_name}")
                return False

        except Exception as e:
            print(f"Error setting MIDI output port: {e}")
            return False

    def set_input_port(self, port_name: str) -> bool:
        """Set the MIDI input port."""
        try:
            if not self.midi_in:
                return False

            # Close current port if open
            if self.midi_in.is_port_open():
                self.midi_in.close_port()

            # Find port index
            input_ports = self.midi_in.get_ports()
            port_index = -1

            for i, port in enumerate(input_ports):
                if port == port_name:
                    port_index = i
                    break

            if port_index >= 0:
                self.midi_in.open_port(port_index)
                self.input_port_name = port_name
                self.input_port_index = port_index

                # Set up input callback
                self.midi_in.set_callback(self._handle_midi_input)
                print(f"MIDI input connected to: {port_name}")
                return True
            else:
                print(f"MIDI input port not found: {port_name}")
                return False

        except Exception as e:
            print(f"Error setting MIDI input port: {e}")
            return False

    def _handle_midi_input(self, message_data, data=None):
        """Handle incoming MIDI messages."""
        try:
            message, timestamp = message_data

            if len(message) >= 2:
                status = message[0]
                channel = (status & 0x0F) + 1  # Convert to 1-16

                # Parse different message types
                if (status & 0xF0) == 0x90:  # Note On
                    note = message[1]
                    velocity = message[2] if len(message) > 2 else 0

                    if velocity > 0:
                        self._track_activity(channel, velocity)
                        midi_msg = MidiMessage(
                            channel, message, timestamp, note, velocity
                        )

                        # Call registered callbacks
                        if self.input_callback:
                            self.input_callback(midi_msg)

                elif (status & 0xF0) == 0x80:  # Note Off
                    note = message[1]
                    midi_msg = MidiMessage(channel, message, timestamp, note, 0)

                    if self.input_callback:
                        self.input_callback(midi_msg)

        except Exception as e:
            print(f"Error handling MIDI input: {e}")

    def _track_activity(self, channel: int, velocity: int):
        """Track MIDI activity for visual feedback."""
        with self.lock:
            self.channel_activity[channel] = time.time()
            self.channel_velocities[channel] = velocity

    def send_note_on(self, channel: int, note: int, velocity: int):
        """Send a MIDI Note On message."""
        try:
            if self.midi_out and self.midi_out.is_port_open():
                # Ensure valid ranges
                channel = max(1, min(16, channel))
                note = max(0, min(127, note))
                velocity = max(0, min(127, velocity))

                message = [0x90 + (channel - 1), note, velocity]
                self.midi_out.send_message(message)

                # Track active note
                with self.lock:
                    self.active_notes[(channel, note)] = time.time()
                    self._track_activity(channel, velocity)

        except Exception as e:
            print(f"Error sending MIDI Note On: {e}")

    def send_note_off(self, channel: int, note: int):
        """Send a MIDI Note Off message."""
        try:
            if self.midi_out and self.midi_out.is_port_open():
                # Ensure valid ranges
                channel = max(1, min(16, channel))
                note = max(0, min(127, note))

                message = [0x80 + (channel - 1), note, 0]
                self.midi_out.send_message(message)

                # Remove from active notes
                with self.lock:
                    self.active_notes.pop((channel, note), None)

        except Exception as e:
            print(f"Error sending MIDI Note Off: {e}")

    def send_cc(self, channel: int, cc_number: int, value: int):
        """Send a MIDI Control Change message."""
        try:
            if self.midi_out and self.midi_out.is_port_open():
                # Ensure valid ranges
                channel = max(1, min(16, channel))
                cc_number = max(0, min(127, cc_number))
                value = max(0, min(127, value))

                message = [0xB0 + (channel - 1), cc_number, value]
                self.midi_out.send_message(message)

        except Exception as e:
            print(f"Error sending MIDI CC: {e}")

    def send_all_notes_off(self, channel: int = None):
        """Send All Notes Off to one or all channels."""
        try:
            if self.midi_out and self.midi_out.is_port_open():
                if channel is not None:
                    # Single channel
                    channel = max(1, min(16, channel))
                    message = [0xB0 + (channel - 1), 123, 0]  # All Notes Off
                    self.midi_out.send_message(message)
                else:
                    # All channels
                    for ch in range(1, 17):
                        message = [0xB0 + (ch - 1), 123, 0]
                        self.midi_out.send_message(message)

                # Clear active notes tracking
                with self.lock:
                    if channel is not None:
                        self.active_notes = {
                            k: v
                            for k, v in self.active_notes.items()
                            if k[0] != channel
                        }
                    else:
                        self.active_notes.clear()

        except Exception as e:
            print(f"Error sending All Notes Off: {e}")

    def get_channel_activity(
        self, channel: int, max_age: float = 0.5
    ) -> Tuple[bool, int]:
        """
        Get MIDI activity status for a channel.
        Returns (is_active, last_velocity).
        """
        with self.lock:
            last_time = self.channel_activity.get(channel, 0)
            last_velocity = self.channel_velocities.get(channel, 0)
            is_active = (time.time() - last_time) < max_age
            return is_active, last_velocity

    def get_active_notes_for_channel(self, channel: int) -> List[int]:
        """Get list of currently active notes for a channel."""
        with self.lock:
            return [note for (ch, note) in self.active_notes.keys() if ch == channel]

    def set_input_callback(self, callback: Callable[[MidiMessage], None]):
        """Set callback for incoming MIDI messages."""
        self.input_callback = callback

    def cleanup(self):
        """Clean up MIDI resources."""
        try:
            # Send all notes off
            self.send_all_notes_off()

            # Close MIDI ports
            if self.midi_out and self.midi_out.is_port_open():
                self.midi_out.close_port()

            if self.midi_in and self.midi_in.is_port_open():
                self.midi_in.close_port()

            print("MIDI cleanup completed")

        except Exception as e:
            print(f"Error during MIDI cleanup: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current MIDI manager status."""
        return {
            "output_port": self.output_port_name,
            "input_port": self.input_port_name,
            "output_connected": self.midi_out and self.midi_out.is_port_open(),
            "input_connected": self.midi_in and self.midi_in.is_port_open(),
            "active_notes_count": len(self.active_notes),
            "recent_channels": list(self.channel_activity.keys()),
        }
