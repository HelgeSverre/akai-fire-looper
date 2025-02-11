class MidiTimingManager:
    def __init__(self, bpm=120.0):
        self.bpm = bpm
        self._update_timing()
        self.active_notes = set()  # Track currently playing notes

    def _update_timing(self):
        self.beat_duration = 60.0 / self.bpm
        self.bar_duration = self.beat_duration * 4
        self.step_duration = self.beat_duration / 4  # 16th notes

    def quantize_time(self, time_in_seconds, grid="16th"):
        """Quantize time to nearest grid value"""
        if grid == "16th":
            quantum = self.step_duration
        elif grid == "8th":
            quantum = self.step_duration * 2
        elif grid == "4th":
            quantum = self.beat_duration
        else:
            quantum = self.bar_duration

        steps = round(time_in_seconds / quantum)
        return steps * quantum

    def get_bar_position(self, current_time, start_time):
        """Get position within bar (0-1) and current bar number"""
        elapsed = current_time - start_time
        current_bar = int(elapsed / self.bar_duration)
        bar_position = (elapsed % self.bar_duration) / self.bar_duration
        return bar_position, current_bar


class MidiRecorder:
    def __init__(self, midi_out, timing_manager):
        self.midi_out = midi_out
        self.timing = timing_manager
        self.active_notes = set()
        self.recording_buffer = []
        self.start_time = None

    def start_recording(self, current_time):
        self.start_time = current_time
        self.recording_buffer = []
        self.active_notes = set()

    def record_message(self, message, current_time):
        if not self.start_time:
            return

        relative_time = current_time - self.start_time
        self.recording_buffer.append((relative_time, message))

        # Track active notes
        if message[0] & 0xF0 == 0x90 and message[2] > 0:  # Note On
            self.active_notes.add(message[1])
        elif (message[0] & 0xF0 == 0x80) or (
            message[0] & 0xF0 == 0x90 and message[2] == 0
        ):  # Note Off
            self.active_notes.discard(message[1])

    def stop_recording(self, quantize=True):
        """Stop recording and return quantized MIDI data"""
        if not self.recording_buffer:
            return []

        # Send note-offs for any hanging notes
        for note in self.active_notes:
            self.midi_out.send_message([0x80, note, 0])

        if quantize:
            return self._quantize_recording()
        return self.recording_buffer

    def _quantize_recording(self):
        """Quantize recorded MIDI to grid"""
        quantized = []
        for time, message in self.recording_buffer:
            q_time = self.timing.quantize_time(time)
            quantized.append((q_time, message))
        return sorted(quantized)


class MidiPlayer:
    def __init__(self, midi_out, timing_manager):
        self.midi_out = midi_out
        self.timing = timing_manager
        self.playing_clips = {}  # {clip_id: (clip_data, start_time)}
        self.active_notes = {}  # {clip_id: set(notes)}

    def start_clip(self, clip_id, clip_data, current_time):
        """Start playing a clip"""
        self.playing_clips[clip_id] = (clip_data, current_time)
        self.active_notes[clip_id] = set()

    def stop_clip(self, clip_id):
        """Stop a playing clip"""
        if clip_id in self.playing_clips:
            # Send note-offs for any playing notes
            for note in self.active_notes[clip_id]:
                self.midi_out.send_message([0x80, note, 0])
            del self.playing_clips[clip_id]
            del self.active_notes[clip_id]

    def process(self, current_time):
        """Process all playing clips"""
        for clip_id in list(self.playing_clips.keys()):
            clip_data, start_time = self.playing_clips[clip_id]
            if not clip_data:
                continue

            # Calculate clip position
            clip_length = clip_data[-1][0]  # Time of last message
            elapsed = (current_time - start_time) % clip_length

            # Find messages to play in this frame
            window = 0.001  # 1ms timing window
            for time, message in clip_data:
                if abs(time - elapsed) < window:
                    self.midi_out.send_message(message)

                    # Track active notes
                    if message[0] & 0xF0 == 0x90 and message[2] > 0:
                        self.active_notes[clip_id].add(message[1])
                    elif (message[0] & 0xF0 == 0x80) or (
                        message[0] & 0xF0 == 0x90 and message[2] == 0
                    ):
                        self.active_notes[clip_id].discard(message[1])
