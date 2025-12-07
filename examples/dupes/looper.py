import sys
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rtmidi
from akai_fire import get_akai_fire


@dataclass
class Clip:
    midi_messages: List[Tuple[float, List[int]]]
    is_playing: bool = False
    is_recording: bool = False
    start_time: Optional[float] = None
    length: float = 4.0
    quantize_start: bool = True


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
        self.fire = get_akai_fire()
        self.canvas = self.fire.get_canvas()

        # Setup MIDI
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.midi_inputs = []
        self.midi_outputs = []
        self.selected_midi_input = None
        self.selected_midi_output = None

        self._setup_midi()

        # Track global playback state
        self.global_start_time = None  # Reference time for all clips
        self.current_bar = 0
        self.current_step = 0
        self.last_step_time = 0

        # Initialize clips - use None to indicate empty slots
        self.clips = {clip_idx: None for clip_idx in range(16)}
        self.recording_clip = None  # clip index or None
        self.pending_record = None  # clip waiting for quantized start

        self._setup_controls()
        self._init_display()
        print("Initialization complete")

    def _update_timing_params(self):
        """Update timing parameters based on BPM."""
        self.beats_per_bar = 4
        self.steps_per_beat = 4  # 16th notes
        self.total_steps = self.beats_per_bar * self.steps_per_beat

        self.beat_duration = 60.0 / self.bpm
        self.bar_duration = self.beat_duration * self.beats_per_bar
        self.step_duration = self.beat_duration / self.steps_per_beat

    def _setup_midi(self):
        """Setup MIDI connections."""
        self.midi_inputs = self.midi_in.get_ports()
        self.midi_outputs = self.midi_out.get_ports()

        print("Available MIDI inputs:", self.midi_inputs)
        print("Available MIDI outputs:", self.midi_outputs)

        # Try to open first available input/output
        if self.midi_inputs:
            try:
                self.midi_in.open_port(0)
                self.selected_midi_input = 0
                print(f"Opened MIDI input: {self.midi_inputs[0]}")
            except Exception as e:
                print(f"Error opening MIDI input: {e}")

        if self.midi_outputs:
            try:
                self.midi_out.open_port(0)
                self.selected_midi_output = 0
                print(f"Opened MIDI output: {self.midi_outputs[0]}")
            except Exception as e:
                print(f"Error opening MIDI output: {e}")

    def _setup_controls(self):
        """Set up basic control surface handlers."""
        self.fire.add_listener(range(16), self._handle_pad)
        self.fire.add_button_listener(self.fire.BUTTON_REC, self._handle_rec)
        self.fire.add_button_listener(self.fire.BUTTON_STOP, self._handle_stop)
        self.fire.add_rotary_listener(self.fire.ROTARY_VOLUME, self._handle_bpm)

    def _get_quantized_time(self, current_time: float) -> float:
        """Get the next quantized time (start of next bar)."""
        if self.global_start_time is None:
            return current_time

        time_in_loop = (current_time - self.global_start_time) % self.bar_duration
        next_bar_time = current_time + (self.bar_duration - time_in_loop)
        return next_bar_time

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
                self.clips[pad_index].is_recording = True
            else:
                # Queue recording to start at next bar
                self.pending_record = pad_index
                next_start = self._get_quantized_time(current_time)
                self.clips[pad_index].start_time = next_start

            self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_HIGH_RED)

        else:
            # Existing clip - toggle playback or stop recording
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

    def _handle_rec(self, event: str):
        """Record button starts/stops recording of armed clip."""
        if event == "press":
            if self.recording_clip is not None:
                self._stop_recording()

    def _stop_recording(self):
        """Stop recording current clip."""
        if self.recording_clip is not None:
            clip = self.clips[self.recording_clip]

            if not clip.midi_messages:  # No MIDI recorded
                print(f"No MIDI recorded, removing clip {self.recording_clip}")
                self.clips[self.recording_clip] = None
            else:
                clip.is_recording = False
                clip.length = time.time() - clip.start_time
                print(
                    f"Stopped recording clip {self.recording_clip}, length: {clip.length:.2f}s"
                )

            self.recording_clip = None
            self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
            self._update_display()

    def _handle_stop(self, event: str):
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

    def _handle_bpm(self, direction: str, velocity: int):
        """Handle BPM adjustment via volume encoder."""
        if direction == "clockwise":
            self.bpm = min(300, self.bpm + velocity)
        else:
            self.bpm = max(30, self.bpm - velocity)
        self._update_timing_params()
        print(f"BPM: {self.bpm}")

    def _all_notes_off(self):
        """Send note off messages for all notes."""
        if self.selected_midi_output is not None:
            for note in range(128):
                self.midi_out.send_message([0x80, note, 0])

    def _init_display(self):
        """Initialize display state."""
        print("Initializing display...")
        self.fire.clear_all_pads()
        self.fire.clear_all_button_leds()
        self._update_display()

    def _update_display(self):
        """Update pad colors and screen based on clip states and playback position."""
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

        # Second row: Playback position indicators
        any_playing = any(clip and clip.is_playing for clip in self.clips.values())
        if any_playing and self.global_start_time:
            current_time = time.time()
            elapsed = current_time - self.global_start_time
            current_step = int((elapsed % self.bar_duration) / self.step_duration)

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
        else:
            # No clips playing - dim all step indicators
            for step in range(16):
                colors.append((step + 16, 10, 10, 10))

        self.fire.set_multiple_pad_colors(colors)

        # Update screen
        self._update_screen()

    def _update_screen(self):
        """Update the OLED screen with current status."""
        self.canvas.clear(color=0)  # Clear to black background

        # Title
        self.canvas.draw_text("MIDI LOOPER", 2, 2, color=1)

        # BPM
        self.canvas.draw_text(f"BPM: {self.bpm:.0f}", 2, 15, color=1)

        # Recording status
        if self.recording_clip is not None:
            self.canvas.draw_text(f"REC: Clip {self.recording_clip}", 2, 28, color=1)
        elif self.pending_record is not None:
            self.canvas.draw_text(f"ARM: Clip {self.pending_record}", 2, 28, color=1)

        # Playing clips count
        playing_count = sum(
            1 for clip in self.clips.values() if clip and clip.is_playing
        )
        if playing_count > 0:
            self.canvas.draw_text(f"Playing: {playing_count}", 2, 41, color=1)

        # Global timing
        if self.global_start_time:
            current_time = time.time()
            elapsed = current_time - self.global_start_time
            bar = int(elapsed / self.bar_duration) + 1
            self.canvas.draw_text(f"Bar: {bar}", 2, 54, color=1)

        self.fire.render_to_display(self.canvas)

    def _process_midi(self):
        """Handle MIDI input/output with improved timing."""
        current_time = time.time()

        # Check for pending recording start
        if self.pending_record is not None:
            clip = self.clips[self.pending_record]
            if current_time >= clip.start_time:
                self.recording_clip = self.pending_record
                self.pending_record = None
                clip.is_recording = True
                print(f"Starting quantized recording of clip {self.recording_clip}")

        # Record incoming MIDI
        if self.recording_clip is not None and self.selected_midi_input is not None:
            clip = self.clips[self.recording_clip]
            message = self.midi_in.get_message()

            if message:
                midi_data, _ = message

                # Store message with timestamp relative to clip start
                timestamp = current_time - clip.start_time
                clip.midi_messages.append((timestamp, midi_data))
                print(
                    f"Recorded MIDI: {decode_midi_message(midi_data)} at {timestamp:.3f}s"
                )

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
        if self.selected_midi_output is not None:
            for clip_idx, clip in self.clips.items():
                if clip and clip.is_playing and clip.start_time is not None:
                    # Calculate position in clip
                    elapsed = current_time - clip.start_time
                    position = elapsed % clip.length

                    # Play any messages at current position with timing window
                    timing_window = 0.01  # 10ms window for better timing
                    for timestamp, message in clip.midi_messages:
                        # Adjust timestamp for loop position
                        adjusted_time = timestamp % clip.length

                        # Check if message should play in current window
                        if abs(adjusted_time - position) < timing_window:
                            self.midi_out.send_message(message)
                            # Only print on note on messages to reduce spam
                            if message[0] & 0xF0 == 0x90 and message[2] > 0:
                                print(
                                    f"Played from clip {clip_idx}: {decode_midi_message(message)}"
                                )

    def run(self):
        """Main loop."""
        print("Starting looper...")
        try:
            last_display_update = 0
            display_update_interval = 0.1  # Update display every 100ms

            while True:
                current_time = time.time()

                # Process hardware events
                if hasattr(self.fire, "process_events"):
                    if not self.fire.process_events():
                        break

                # Process MIDI
                self._process_midi()

                # Update display periodically
                if current_time - last_display_update > display_update_interval:
                    self._update_display()
                    last_display_update = current_time

                time.sleep(0.001)  # 1ms sleep for tight timing

        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self._cleanup()

    def _cleanup(self):
        """Clean up resources on shutdown."""
        print("Cleaning up...")
        self._all_notes_off()
        self.fire.clear_all_pads()
        self.fire.clear_all_button_leds()

        if self.selected_midi_input is not None:
            self.midi_in.close_port()
        if self.selected_midi_output is not None:
            self.midi_out.close_port()

        self.fire.close()


if __name__ == "__main__":
    looper = MidiLooper(bpm=120)
    looper.run()
