import time
import rtmidi
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from akai_fire import AkaiFire


@dataclass
class Clip:
    midi_messages: List[Tuple[float, List[int]]]  # [(timestamp, midi_message), ...]
    is_playing: bool = False
    is_recording: bool = False
    start_time: Optional[float] = None
    length: float = 4.0  # Length in bars
    quantize_start: bool = True  # Whether to quantize clip start to next bar


def decode_midi_message(message: List[int]) -> str:
    """Decode MIDI message into human-readable format."""
    if not message:
        return "Empty message"

    status = message[0] & 0xF0
    channel = message[0] & 0x0F

    if status == 0x80:  # Note Off
        return f"Note Off: ch{channel + 1} note={message[1]} vel={message[2]}"
    elif status == 0x90:  # Note On
        if message[2] == 0:  # Note On with velocity 0 is Note Off
            return f"Note Off: ch{channel + 1} note={message[1]} (vel=0)"
        return f"Note On: ch{channel + 1} note={message[1]} vel={message[2]}"
    elif status == 0xB0:  # Control Change
        return f"CC: ch{channel + 1} ctrl={message[1]} val={message[2]}"
    elif status == 0xE0:  # Pitch Bend
        value = (message[2] << 7) + message[1]
        return f"Pitch Bend: ch{channel + 1} val={value}"
    elif status == 0xA0:  # Aftertouch
        return f"Aftertouch: ch{channel + 1} note={message[1]} val={message[2]}"
    elif status == 0xD0:  # Channel Pressure
        return f"Channel Pressure: ch{channel + 1} val={message[1]}"
    elif status == 0xC0:  # Program Change
        return f"Program Change: ch{channel + 1} program={message[1]}"
    else:
        return f"Unknown: {' '.join(hex(b)[2:].zfill(2) for b in message)}"


class MidiLooper:
    def __init__(self, bpm: float = 120.0):
        print("Initializing looper...")
        self.bpm = bpm
        self._update_timing_params()

        # Initialize Fire controller
        self.fire = AkaiFire()

        # Setup MIDI for Virus
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self._setup_midi()

        # Track global playback state
        self.global_start_time = None  # Reference time for all clips
        self.current_bar = 0
        self.current_step = 0
        self.last_step_time = 0

        # Just track 1 for now (16 clips)
        self.clips = {clip: None for clip in range(16)}
        self.recording_clip = None  # clip index or None
        self.pending_record = None  # clip waiting for quantized start

        self._setup_controls()
        self._init_display()
        print("Initialization complete")

    def _setup_midi(self):
        """Setup MIDI connections for Virus on port 2."""
        in_ports = self.midi_in.get_ports()
        out_ports = self.midi_out.get_ports()

        print("Available MIDI inputs:", in_ports)
        print("Available MIDI outputs:", out_ports)

        try:
            for i, port_name in enumerate(in_ports):
                if "Express  128: Port 2" in port_name:
                    self.midi_in.open_port(i)
                    print(f"Found Virus on input port {i}: {port_name}")

            for i, port_name in enumerate(out_ports):
                if "Express  128: Port 2" in port_name:
                    self.midi_out.open_port(i)
                    print(f"Found Virus on output port {i}: {port_name}")

        except Exception as e:
            print(f"Error connecting to MIDI ports: {e}")
            raise

    def _setup_controls(self):
        """Set up basic control surface handlers."""
        # Use first row of pads (16 clips)
        self.fire.add_listener(range(16), self._handle_pad)

        # Record and stop buttons
        self.fire.add_button_listener(self.fire.BUTTON_REC, self._handle_rec)
        self.fire.add_button_listener(self.fire.BUTTON_STOP, self._handle_stop)

        # Volume encoder for BPM control
        self.fire.add_rotary_listener(self.fire.ROTARY_VOLUME, self._handle_bpm)

    def _update_timing_params(self) -> None:
        """Update all timing-related parameters based on current BPM."""
        self.beats_per_bar = 4
        self.steps_per_beat = 4  # 16th notes
        self.total_steps = self.beats_per_bar * self.steps_per_beat

        self.beat_duration = 60.0 / self.bpm
        self.bar_duration = self.beat_duration * self.beats_per_bar
        self.step_duration = self.beat_duration / self.steps_per_beat
        self.beats_per_bar = 4
        self.steps_per_beat = 4  # 16th notes
        self.total_steps = self.beats_per_bar * self.steps_per_beat

    def _get_quantized_time(self, current_time: float) -> float:
        """Get the next quantized time (start of next bar)."""
        if self.global_start_time is None:
            return current_time

        time_in_loop = (current_time - self.global_start_time) % self.bar_duration
        next_bar_time = current_time + (self.bar_duration - time_in_loop)
        return next_bar_time

    def _handle_bpm(self, encoder_id: int, direction, velocity):
        """Handle BPM changes from volume encoder."""

        if direction == "counterclockwise":
            diff = 1.0 * velocity * -1
        else:
            diff = 1.0 * velocity

        # Limit BPM to 30-300 range
        self.bpm = max(30.0, min(300.0, self.bpm + diff))
        self._update_timing_params()
        print(f"BPM: {self.bpm:.1f}")

    def _handle_pad(self, pad_index: int):
        """Handle pad press for clip arm/launch."""
        if pad_index >= 16:  # Only handle first row
            return

        current_time = time.time()
        print(f"Pad pressed: clip {pad_index}")

        if self.clips[pad_index] is None:
            # Empty slot - arm for recording
            print(f"Armed clip {pad_index}")
            self.clips[pad_index] = Clip(midi_messages=[])

            if self.global_start_time is None:
                # First clip - start immediately
                self.recording_clip = pad_index
                self.clips[pad_index].start_time = current_time
                self.global_start_time = current_time
            else:
                # Queue recording to start at next bar
                self.pending_record = pad_index
                next_start = self._get_quantized_time(current_time)
                self.clips[pad_index].start_time = next_start

            self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_HIGH_RED)

        else:
            # Existing clip - toggle playback
            if self.recording_clip == pad_index:
                self._stop_recording()
            else:
                clip = self.clips[pad_index]
                clip.is_playing = not clip.is_playing

                if clip.is_playing:
                    if self.global_start_time is None:
                        # First clip playing - set global time reference
                        self.global_start_time = current_time
                        clip.start_time = current_time
                    else:
                        # Quantize start to next bar
                        clip.start_time = self._get_quantized_time(current_time)
                    print(f"Started clip {pad_index}")
                else:
                    self._all_notes_off()  # Stop any hanging notes
                    print(f"Stopped clip {pad_index}")

        self._update_display()

    def _handle_rec(self, button_id: int, event: str):
        """Record button starts/stops recording of armed clip."""
        if event == "press":
            if self.recording_clip is not None:
                self._stop_recording()

    def _stop_recording(self):
        """Stop recording current clip."""
        if self.recording_clip is not None:
            clip = self.clips[self.recording_clip]

            if not clip.midi_messages:  # No MIDI recorded
                self.clips[self.recording_clip] = None
            else:
                clip.is_recording = False

                # Quantize recorded MIDI to steps
                quantized_messages = []
                for timestamp, message in clip.midi_messages:
                    # Quantize to nearest step
                    step = round(timestamp / self.step_duration)
                    quantized_time = step * self.step_duration

                    # Only keep messages within clip length
                    if quantized_time < clip.length * self.bar_duration:
                        quantized_messages.append((quantized_time, message))

                clip.midi_messages = sorted(quantized_messages)

            print(f"Stopped recording clip {self.recording_clip}")
            self.recording_clip = None
            self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
            self._update_display()

    def _handle_stop(self, button_id: int, event: str):
        """Stop all clips, recording, and reset global timing."""
        if event == "press":
            print("Stopping all clips")
            self._all_notes_off()

            self.global_start_time = None
            self.current_bar = 0
            self.current_step = 0

            for clip in self.clips.values():
                if clip:
                    clip.is_playing = False
                    clip.start_time = None

            if self.recording_clip is not None:
                clip = self.clips[self.recording_clip]
                if not clip.midi_messages:
                    self.clips[self.recording_clip] = None
                self.recording_clip = None

            self.pending_record = None
            self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
            self._update_display()

    def _all_notes_off(self):
        """Send note off messages for all notes."""
        for note in range(128):
            self.midi_out.send_message([0x80, note, 0])

    def _init_display(self):
        """Initialize display state."""
        print("Initializing display...")
        self.fire.clear_pads()
        self.fire.clear_all_button_leds()
        self._update_display()

    def _update_display(self):
        """Update pad colors based on clip states and playback position."""
        colors = []

        # First row: Clip states
        for clip_idx in range(16):
            clip = self.clips.get(clip_idx)

            if clip is None:
                color = (10, 10, 10)  # Empty: dim white
            elif clip_idx == self.recording_clip:
                color = (127, 0, 0)  # Recording: red
            elif clip.is_playing:
                color = (0, 127, 0)  # Playing: bright green
            else:
                color = (0, 0, 127)  # Has content: blue

            colors.append((clip_idx, *color))

        # Second row: Playback position
        any_playing = any(clip and clip.is_playing for clip in self.clips.values())
        if any_playing:
            current_time = time.time()
            # Find the earliest start time of playing clips
            start_time = min(
                (clip.start_time for clip in self.clips.values()
                 if clip and clip.is_playing and clip.start_time is not None)
            )
            elapsed = current_time - start_time

            # Calculate position
            total_steps = self.beats_per_bar * self.steps_per_beat
            step_duration = self.beat_duration / self.steps_per_beat
            current_step = int((elapsed % (self.beats_per_bar * self.beat_duration)) / step_duration)
            current_bar = int(elapsed / (self.beats_per_bar * self.beat_duration))

            # Update step indicators (pads 16-31)
            for step in range(16):
                pad_idx = step + 16  # Second row
                if step == current_step:
                    color = (127, 127, 0)  # Yellow for current step
                elif step % self.steps_per_beat == 0:
                    color = (64, 64, 64)  # Medium gray for beat markers
                else:
                    color = (20, 20, 20)  # Dim gray for other steps
                colors.append((pad_idx, *color))

            # Show current bar number on the last pad
            print(f"Bar: {current_bar + 1}")
        else:
            # No clips playing - dim all step indicators
            for step in range(16):
                colors.append((step + 16, 20, 20, 20))

        self.fire.set_multiple_pad_colors(colors)

    def _process_midi(self):
        """Handle MIDI input/output with improved timing."""
        current_time = time.time()

        # Check for pending recording start
        if self.pending_record is not None:
            clip = self.clips[self.pending_record]
            if current_time >= clip.start_time:
                self.recording_clip = self.pending_record
                self.pending_record = None
                print(f"Starting quantized recording of clip {self.recording_clip}")

        # Record incoming MIDI
        if self.recording_clip is not None:
            clip = self.clips[self.recording_clip]
            message = self.midi_in.get_message()

            if message:
                midi_data, delta = message
                if not clip.is_recording:
                    clip.is_recording = True
                    print("Recording started")

                # Store message with timestamp relative to clip start
                timestamp = current_time - clip.start_time
                if timestamp < clip.length * self.bar_duration:  # Only record within clip length
                    clip.midi_messages.append((timestamp, midi_data))
                    print(f"Recorded MIDI: {decode_midi_message(midi_data)} at {timestamp:.3f}s")
                else:
                    self._stop_recording()

        # Update global timing
        if self.global_start_time is not None:
            elapsed = current_time - self.global_start_time
            new_step = int((elapsed % self.bar_duration) / self.step_duration)

            if new_step != self.current_step:
                self.current_step = new_step
                self.last_step_time = current_time
                self._update_display()  # Update step indicators

            # Calculate current bar
            self.current_bar = int(elapsed / self.bar_duration)

        # Handle playback with improved timing
        for clip_idx, clip in self.clips.items():
            if clip and clip.is_playing and clip.start_time is not None:
                # Calculate position in clip considering quantization
                elapsed = current_time - clip.start_time
                clip_duration = clip.length * self.bar_duration
                position = elapsed % clip_duration

                # Play any messages at current position with timing window
                timing_window = 0.001  # 1ms window
                for timestamp, message in clip.midi_messages:
                    # Adjust timestamp for loop position
                    adjusted_time = timestamp % clip_duration

                    # Check if message should play in current window
                    if abs(adjusted_time - position) < timing_window:
                        self.midi_out.send_message(message)
                        print(f"Played from clip {clip_idx}: {decode_midi_message(message)}")

    def run(self):
        """Main loop."""
        print("Starting looper...")
        try:
            target_interval = 0.001  # 1ms target interval
            while True:
                loop_start = time.time()

                self._process_midi()

                # Calculate sleep time to maintain consistent timing
                elapsed = time.time() - loop_start
                sleep_time = max(0, target_interval - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            print("Cleaning up...")
            self._all_notes_off()
            self.fire.clear_pads()
            self.fire.clear_all_button_leds()
            self.midi_in.close_port()
            self.midi_out.close_port()
            self.fire.close()


if __name__ == "__main__":
    looper = MidiLooper(bpm=120)
    looper.run()
