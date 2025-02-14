import random
import threading
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import rtmidi
from akai_fire import AkaiFire


class PlayState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    RECORDING = "recording"


class ScreenMode(Enum):
    MAIN = "main"
    NOTES = "notes"
    STEP = "step"
    EUCLIDEAN = "euclidean"
    MIDI_MONITOR = "midi_monitor"
    MIDI_CONFIG = "midi_config"


class ClipType(Enum):
    EMPTY = auto()
    RECORDED = auto()
    STEP = auto()
    EUCLIDEAN = auto()


class EditMode(Enum):
    CLIP = auto()
    STEP = auto()
    EUCLIDEAN = auto()


@dataclass
class MidiMessage:
    timestamp: float
    data: List[int]
    length: Optional[float] = None  # For note length tracking


@dataclass
class StepParameters:
    active: bool = False
    note: int = 60  # Middle C
    velocity: int = 100
    gate: float = 0.5  # 0.0-1.0
    probability: float = 1.0  # 0.0-1.0
    slide: bool = False
    accent: bool = False
    repeat: int = 1  # Number of repeats


@dataclass
class StepSequence:
    steps: List[StepParameters]
    length: int = 16
    swing: float = 0.5  # 0.5 = no swing
    scale: List[int] = field(
        default_factory=lambda: [0, 2, 4, 5, 7, 9, 11]
    )  # Major scale
    root_note: int = 60  # Middle C


@dataclass
class EuclideanPattern:
    note: int = 60
    steps: int = 16
    pulses: int = 4
    offset: int = 0
    velocity: int = 100
    gate: float = 0.5
    probability: float = 1.0
    parameter_type: str = "note"  # "note" or "cc"
    cc_number: Optional[int] = None
    value_min: int = 0
    value_max: int = 127


@dataclass
class Clip:
    type: ClipType = ClipType.EMPTY
    midi_messages: List[MidiMessage] = field(default_factory=list)
    step_sequence: Optional[StepSequence] = None
    euclidean: Optional[EuclideanPattern] = None
    length: float = 4.0  # Length in bars
    quantize: bool = True
    is_playing: bool = False
    loop_enabled: bool = True


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class Groovebox:
    def __init__(self):
        # Hardware setup
        self.fire = AkaiFire()
        self.canvas = self.fire.get_canvas()

        # Core state
        self.play_state = PlayState.STOPPED
        self.edit_mode = EditMode.CLIP
        self.selected_track = -1
        self.current_step = 0
        self.tempo = 120.0
        self.swing = 0.5
        self.current_page = 0
        self.shift_held = False
        self.alt_held = False

        # Track/clip management
        self.tracks: List[List[Clip]] = [[Clip() for _ in range(16)] for _ in range(4)]
        self.track_solos = [False, False, False, False]
        self.track_mutes = [False, False, False, False]

        # MIDI setup
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.midi_in.set_callback(self._handle_midi_input)

        # MIDI monitoring
        self.midi_monitor_messages = []
        self.max_monitor_messages = 20

        # Recording state
        self.recording_clip: Optional[tuple[int, int]] = None  # (track, clip)
        self.active_notes: Dict[int, MidiMessage] = {}  # note -> start message
        self.quantize_record = True

        # Step sequencing state
        self.step_edit_page = 0
        self.step_edit_param = "note"  # Which parameter we're editing
        self.step_param_values = {
            "note": 60,
            "velocity": 100,
            "gate": 0.5,
            "probability": 1.0,
        }

        # Visual feedback
        self.pad_colors = {
            ClipType.EMPTY: (10, 10, 10),
            ClipType.RECORDED: (0, 0, 127),
            ClipType.STEP: (0, 127, 0),
            ClipType.EUCLIDEAN: (127, 0, 0),
        }

        self.setup_handlers()
        self.update_display()
        self.update_pads()

    def _handle_midi_input(self, message, timestamp):
        """Process incoming MIDI messages"""
        if not message:
            return

        status = message[0] & 0xF0
        channel = message[0] & 0x0F
        note = message[1] if len(message) > 1 else None
        velocity = message[2] if len(message) > 2 else None

        # Note handling for recording
        if self.play_state == PlayState.RECORDING and self.recording_clip:
            track, clip = self.recording_clip
            if status == 0x90 and velocity > 0:  # Note On
                msg = MidiMessage(timestamp=time.time(), data=message, length=None)
                self.active_notes[note] = msg

            elif status == 0x80 or (status == 0x90 and velocity == 0):  # Note Off
                if note in self.active_notes:
                    start_msg = self.active_notes[note]
                    start_msg.length = time.time() - start_msg.timestamp
                    self.tracks[track][clip].midi_messages.append(start_msg)
                    del self.active_notes[note]

        # Always pass through MIDI
        self.midi_out.send_message(message)

    def setup_handlers(self):
        """Set up all button and control handlers"""

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.play_state == PlayState.STOPPED:
                    self.play_state = PlayState.PLAYING
                    self.current_step = 0
                else:
                    self.play_state = PlayState.STOPPED
                self.update_transport_leds()

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.play_state = PlayState.STOPPED
                self.current_step = 0
                self.stop_all_notes()
                self.update_transport_leds()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_record(event):
            if event == "press":
                if self.recording_clip:
                    self._stop_recording()
                else:
                    self._start_recording()

        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def handle_shift(event):
            self.shift_held = event == "press"

        @self.fire.on_button(self.fire.BUTTON_ALT)
        def handle_alt(event):
            self.alt_held = event == "press"

        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            track = pad_index // 16
            clip = pad_index % 16

            if self.shift_held:
                # Shift + pad = Copy/paste
                self._handle_copy_paste(track, clip)
            elif self.alt_held:
                # Alt + pad = Clear clip
                self._clear_clip(track, clip)
            else:
                # Normal pad press depends on mode
                self._handle_pad_press(track, clip, velocity)

        # Volume knob controls tempo
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_tempo(direction, velocity):
            if direction == "clockwise":
                self.tempo = min(300.0, self.tempo + velocity * 0.5)
            else:
                self.tempo = max(20.0, self.tempo - velocity * 0.5)
            self.update_display()

        # Pan knob controls step parameter values
        @self.fire.on_rotary_turn(self.fire.ROTARY_PAN)
        def handle_param_value(direction, velocity):
            if self.edit_mode == EditMode.STEP:
                if direction == "clockwise":
                    self._adjust_step_param(velocity)
                else:
                    self._adjust_step_param(-velocity)
                self.update_display()

        # Filter knob controls pattern length
        @self.fire.on_rotary_turn(self.fire.ROTARY_FILTER)
        def handle_length(direction, velocity):
            if self.edit_mode in [EditMode.STEP, EditMode.EUCLIDEAN]:
                clip = self.tracks[self.selected_track][self.selected_clip]
                if self.edit_mode == EditMode.STEP and clip.step_sequence:
                    if direction == "clockwise":
                        clip.step_sequence.length = min(
                            64, clip.step_sequence.length + 1
                        )
                    else:
                        clip.step_sequence.length = max(
                            1, clip.step_sequence.length - 1
                        )
                elif self.edit_mode == EditMode.EUCLIDEAN and clip.euclidean:
                    if direction == "clockwise":
                        clip.euclidean.steps = min(32, clip.euclidean.steps + 1)
                    else:
                        clip.euclidean.steps = max(1, clip.euclidean.steps - 1)
                self.update_pads()
                self.update_display()

        # Resonance knob controls swing amount
        @self.fire.on_rotary_turn(self.fire.ROTARY_RESONANCE)
        def handle_swing(direction, velocity):
            if direction == "clockwise":
                self.swing = min(0.75, self.swing + 0.01 * velocity)
            else:
                self.swing = max(0.5, self.swing - 0.01 * velocity)
            self.update_display()

        @self.fire.on_button(self.fire.BUTTON_STEP)
        def handle_step_mode(event):
            if event == "press":
                if self.selected_track >= 0 and self.selected_clip >= 0:
                    # Toggle between step mode and clip mode
                    if self.edit_mode == EditMode.STEP:
                        self.edit_mode = EditMode.CLIP
                    else:
                        self._enter_step_mode()
                        self.update_pads()
                        self.update_display()

        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_note_mode(event):
            if event == "press" and self.edit_mode == EditMode.STEP:
                self.step_edit_param = "note"
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_PATTERN)
        def handle_euclidean_mode(event):
            if event == "press":
                if self.selected_track >= 0 and self.selected_clip >= 0:
                    # Toggle between euclidean mode and clip mode
                    if self.edit_mode == EditMode.EUCLIDEAN:
                        self.edit_mode = EditMode.CLIP
                    else:
                        self._enter_euclidean_mode()
                    self.update_pads()
                    self.update_display()

        # Track control buttons
        for i in range(4):
            button = getattr(self.fire, f"BUTTON_SOLO_{i + 1}")

            @self.fire.on_button(button)
            def handle_solo(event, track=i):
                if event == "press":
                    self.track_solos[track] = not self.track_solos[track]
                    self.update_transport_leds()

    def _handle_copy_paste(self, track: int, clip: int):
        """Handle copying/pasting clips"""
        if self.selected_track == -1:  # No source selected
            # Select source clip
            self.selected_track = track
            self.selected_clip = clip
            # Set pads to copy mode visual feedback
            self.update_pads()
        else:
            # Copy source to destination
            source = self.tracks[self.selected_track][self.selected_clip]
            self.tracks[track][clip] = self._copy_clip(source)
            # Reset selection
            self.selected_track = -1
            self.selected_clip = -1
            self.update_pads()

    def _clear_clip(self, track: int, clip: int):
        """Clear a clip back to empty state"""
        self.tracks[track][clip] = Clip()  # Reset to empty clip
        self.update_pads()

    def _toggle_clip_playback(self, track: int, clip: int):
        """Toggle clip playback state"""
        clip_obj = self.tracks[track][clip]
        if clip_obj.type != ClipType.EMPTY:
            clip_obj.is_playing = not clip_obj.is_playing
            # Start global playback if needed
            if clip_obj.is_playing and self.play_state == PlayState.STOPPED:
                self.play_state = PlayState.PLAYING
                self.current_step = 0
            # Stop global playback if no clips playing
            elif not clip_obj.is_playing and not any(
                    c.is_playing for t in self.tracks for c in t
            ):
                self.play_state = PlayState.STOPPED
            self.update_transport_leds()

    def _enter_euclidean_mode(self):
        """Initialize and enter euclidean pattern mode"""
        if self.selected_track >= 0 and self.selected_clip >= 0:
            clip = self.tracks[self.selected_track][self.selected_clip]
            if clip.type != ClipType.EUCLIDEAN:
                clip.type = ClipType.EUCLIDEAN
                clip.euclidean = EuclideanPattern()
            self.edit_mode = EditMode.EUCLIDEAN

    def _handle_pad_press(self, track: int, clip: int, velocity: int):
        """Route pad press based on current mode"""
        if self.edit_mode == EditMode.CLIP:
            # Handle clip mode pad press
            if self.selected_track == track and self.selected_clip == clip:
                self._toggle_clip_playback(track, clip)
            else:
                self.selected_track = track
                self.selected_clip = clip

        elif self.edit_mode == EditMode.STEP:
            # Handle step sequencer pad press
            if track < 4:  # Use rows for different parameters
                step = clip + (self.step_edit_page * 16)
                self._edit_step_param(track, step)

        elif self.edit_mode == EditMode.EUCLIDEAN:
            # Handle euclidean pattern pad press
            self._edit_euclidean_param(track, clip)

        self.update_pads()
        self.update_display()

    def _edit_step_param(self, row: int, step: int):
        """Edit step sequencer parameter based on row"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        clip = self.tracks[self.selected_track][self.selected_clip]
        if not clip.step_sequence:
            return

        params = clip.step_sequence.steps[step]

        if row == 0:  # Note on/off
            params.active = not params.active
        elif row == 1:  # Velocity
            params.velocity = self.step_param_values["velocity"]
        elif row == 2:  # Gate length
            params.gate = self.step_param_values["gate"]
        elif row == 3:  # Probability
            params.probability = self.step_param_values["probability"]

    def _handle_clip_selection(self, track: int, clip: int):
        """Handle pad press in clip mode"""
        if self.selected_track == track and self.selected_clip == clip:
            # Toggle playback
            self._toggle_clip_playback(track, clip)
        else:
            # Just select
            self.selected_track = track
            self.selected_clip = clip

    def _handle_step_edit(self, track: int, clip: int):
        """Handle pad press in step sequence mode"""
        if track < 4:  # Use rows for different parameters
            self._edit_step_param(track, clip)

    def _handle_euclidean_edit(self, track: int, clip: int):
        """Handle pad press in euclidean mode"""
        self._edit_euclidean_param(track, clip)

    def _edit_euclidean_param(self, row: int, value: int):
        """Edit euclidean parameters based on row"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        pattern = self.tracks[self.selected_track][self.selected_clip].euclidean
        if not pattern:
            return

        if row == 0:  # Steps (1-16)
            pattern.steps = value + 1
            pattern.pulses = min(pattern.pulses, pattern.steps)
        elif row == 1:  # Pulses (1-steps)
            pattern.pulses = min(value + 1, pattern.steps)
        elif row == 2:  # Offset (0-steps)
            pattern.offset = value % pattern.steps
        elif row == 3:  # Root note (C2-C6)
            pattern.note = 36 + value

    def _handle_normal_pad(self, track: int, clip: int):
        """Handle regular pad press"""
        if self.edit_mode == EditMode.CLIP:
            # Toggle clip playback
            clip_obj = self.tracks[track][clip]
            if clip_obj.type != ClipType.EMPTY:
                clip_obj.is_playing = not clip_obj.is_playing
                if clip_obj.is_playing and self.play_state == PlayState.STOPPED:
                    self.play_state = PlayState.PLAYING

        elif self.edit_mode == EditMode.STEP:
            if track == self.selected_track and clip == self.selected_clip:
                step = clip + (self.step_edit_page * 16)
                if step < self.tracks[track][clip].step_sequence.length:
                    self._edit_step(track, clip, step)

        elif self.edit_mode == EditMode.EUCLIDEAN:
            if track == self.selected_track and clip == self.selected_clip:
                self._edit_euclidean(track, clip, clip)

        self.update_pads()
        self.update_display()

    def _handle_shift_pad(self, track: int, clip: int):

        """Handle pad press with shift held (copy/paste)"""
        if self.selected_track == -1:  # No source selected
            self.selected_track = track
            self.selected_clip = clip
        else:
            # Copy clip
            source = self.tracks[self.selected_track][self.selected_clip]
            self.tracks[track][clip] = self._copy_clip(source)
            self.selected_track = -1
        self.update_pads()

    def _handle_alt_pad(self, track: int, clip: int):
        """Handle pad press with alt held (enter euclidean mode)"""
        self.selected_track = track
        self.selected_clip = clip

        clip_obj = self.tracks[track][clip]
        if clip_obj.type != ClipType.EUCLIDEAN:
            clip_obj.type = ClipType.EUCLIDEAN
            clip_obj.euclidean = EuclideanPattern()

        self.edit_mode = EditMode.EUCLIDEAN
        self.update_pads()
        self.update_display()

    def _edit_step(self, track: int, clip: int, step: int):
        """Edit step sequencer parameters"""
        seq = self.tracks[track][clip].step_sequence
        params = seq.steps[step]

        if self.step_edit_param == "note":
            params.active = not params.active
        elif self.step_edit_param == "velocity":
            params.velocity = self.step_param_values["velocity"]
        elif self.step_edit_param == "gate":
            params.gate = self.step_param_values["gate"]
        elif self.step_edit_param == "probability":
            params.probability = self.step_param_values["probability"]

    def _edit_euclidean(self, track: int, clip: int, pad: int):
        """Edit euclidean pattern parameters"""
        pattern = self.tracks[track][clip].euclidean
        row = pad // 16

        if row == 0:  # Length
            pattern.steps = pad + 1
        elif row == 1:  # Pulses
            pattern.pulses = min(pad + 1, pattern.steps)
        elif row == 2:  # Offset
            pattern.offset = pad % pattern.steps
        elif row == 3:  # Parameter value range
            relative_pos = (pad % 16) / 15.0
            if pattern.parameter_type == "note":
                pattern.note = int(36 + (relative_pos * 60))
            else:
                pattern.value_max = int(relative_pos * 127)

    def _start_recording(self):
        """Start recording MIDI into current clip"""
        if self.selected_track >= 0 and self.selected_clip >= 0:
            clip = self.tracks[self.selected_track][self.selected_clip]
            clip.type = ClipType.RECORDED
            clip.midi_messages = []
            self.recording_clip = (self.selected_track, self.selected_clip)
            self.play_state = PlayState.RECORDING
            if not any(c.is_playing for t in self.tracks for c in t):
                self.current_step = 0
        self.update_transport_leds()

    def _stop_recording(self):
        """Stop recording and process recorded MIDI"""
        if self.recording_clip:
            track, clip = self.recording_clip
            clip_obj = self.tracks[track][clip]

            # Quantize if enabled
            if self.quantize_record:
                self._quantize_clip(clip_obj)

            self.recording_clip = None
            self.play_state = PlayState.PLAYING
            clip_obj.is_playing = True

        self.update_transport_leds()

    def _quantize_clip(self, clip: Clip):
        """Quantize recorded MIDI to grid"""
        step_duration = 60.0 / (self.tempo * 4)  # 16th note duration
        quantized_messages = []

        for msg in clip.midi_messages:
            # Find nearest step
            step = round(msg.timestamp / step_duration)
            msg.timestamp = step * step_duration
            quantized_messages.append(msg)

        clip.midi_messages = sorted(quantized_messages, key=lambda m: m.timestamp)

    def _copy_clip(self, source: Clip) -> Clip:
        """Create a deep copy of a clip"""
        new_clip = Clip(
            type=source.type,
            length=source.length,
            quantize=source.quantize,
            loop_enabled=source.loop_enabled,
        )

        if source.type == ClipType.RECORDED:
            new_clip.midi_messages = [
                MidiMessage(m.timestamp, m.data.copy(), m.length)
                for m in source.midi_messages
            ]
        elif source.type == ClipType.STEP:
            new_clip.step_sequence = StepSequence(
                steps=[StepParameters(**vars(p)) for p in source.step_sequence.steps],
                length=source.step_sequence.length,
                swing=source.step_sequence.swing,
                scale=source.step_sequence.scale.copy(),
                root_note=source.step_sequence.root_note,
            )
        elif source.type == ClipType.EUCLIDEAN:
            new_clip.euclidean = EuclideanPattern(**vars(source.euclidean))

        return new_clip

    def update_pads(self):
        """Update pad colors based on current mode and state"""
        if self.edit_mode == EditMode.CLIP:
            self._update_clip_view()
        elif self.edit_mode == EditMode.STEP:
            self._update_step_view()
        elif self.edit_mode == EditMode.EUCLIDEAN:
            self._update_euclidean_view()

    def _update_clip_view(self):
        """Update pads for clip overview mode"""
        colors = []
        for track in range(4):
            for clip in range(16):
                pad_idx = track * 16 + clip
                clip_obj = self.tracks[track][clip]

                # Base color from clip type
                base_color = self.pad_colors[clip_obj.type]

                # Modify based on state
                if clip_obj.is_playing:
                    # Brighter when playing
                    color = tuple(min(127, c * 2) for c in base_color)
                else:
                    color = base_color

                # Highlight current step if playing
                if (
                        clip_obj.is_playing
                        and self.play_state != PlayState.STOPPED
                        and clip == self.current_step % 16
                ):
                    color = (127, 127, 127)  # White flash

                # Highlight selected clip
                if track == self.selected_track and clip == self.selected_clip:
                    color = tuple(min(127, c + 40) for c in color)

                colors.append((pad_idx, *color))

        self.fire.set_multiple_pad_colors(colors)

    def _update_step_view(self):
        """Update pads for step sequencer view"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        clip = self.tracks[self.selected_track][self.selected_clip]
        if not clip.step_sequence:
            return

        colors = []
        page_offset = self.step_edit_page * 16

        # Top row: Steps on/off + current step indicator
        for i in range(16):
            step_idx = i + page_offset
            if step_idx >= clip.step_sequence.length:
                colors.append((i, 0, 0, 0))  # Off
                continue

            params = clip.step_sequence.steps[step_idx]
            playing = step_idx == self.current_step

            if params.active:
                if playing:
                    colors.append((i, 127, 127, 127))  # White for playing step
                else:
                    vel_scaled = (params.velocity * 127) // 127
                    colors.append((i, vel_scaled, params.accent and 127 or 0, 0))
            else:
                colors.append((i, playing and 40 or 10, 0, 0))  # Dim for inactive

        # Second row: Note selection
        for i in range(16, 32):
            step_idx = (i - 16) + page_offset
            if step_idx >= clip.step_sequence.length:
                colors.append((i, 0, 0, 0))
                continue

            params = clip.step_sequence.steps[step_idx]
            note_scaled = ((params.note - 36) * 127) // 60  # Scale note range to color
            colors.append((i, 0, 0, note_scaled))

        # Third row: Gate length
        for i in range(32, 48):
            step_idx = (i - 32) + page_offset
            if step_idx >= clip.step_sequence.length:
                colors.append((i, 0, 0, 0))
                continue

            params = clip.step_sequence.steps[step_idx]
            gate_scaled = int(params.gate * 127)
            colors.append((i, 0, gate_scaled, gate_scaled))

        # Bottom row: Step modifiers (slide, repeat, probability)
        for i in range(48, 64):
            step_idx = (i - 48) + page_offset
            if step_idx >= clip.step_sequence.length:
                colors.append((i, 0, 0, 0))
                continue

            params = clip.step_sequence.steps[step_idx]
            r = 127 if params.slide else 0
            g = int(params.probability * 127)
            b = (params.repeat - 1) * 30
            colors.append((i, r, g, b))

        self.fire.set_multiple_pad_colors(colors)

    def _update_euclidean_view(self):
        """Update pads for euclidean pattern editor"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        clip = self.tracks[self.selected_track][self.selected_clip]
        if not clip.euclidean:
            return

        pattern = clip.euclidean
        euclidean_steps = self.calculate_euclidean_pattern(
            pattern.pulses, pattern.steps, pattern.offset
        )

        colors = []

        # Top row: Pattern visualization
        for i in range(16):
            if i >= pattern.steps:
                colors.append((i, 0, 0, 0))
            else:
                active = euclidean_steps[i]
                playing = i == self.current_step % pattern.steps
                colors.append(
                    (
                        i,
                        127 if playing else (80 if active else 0),
                        80 if active else 0,
                        0,
                    )
                )

        # Second row: Steps setting
        for i in range(16, 32):
            step_num = i - 15
            active = step_num <= pattern.steps
            colors.append((i, 0, active and 80 or 0, 0))

        # Third row: Pulses setting
        for i in range(32, 48):
            pulse_num = i - 31
            active = pulse_num <= pattern.pulses
            colors.append((i, 0, 0, active and 80 or 0))

        # Bottom row: Parameter values
        for i in range(48, 64):
            if pattern.parameter_type == "note":
                note_scaled = ((pattern.note - 36) * 127) // 60
                colors.append((i, note_scaled, note_scaled, 0))
            else:
                val_scaled = (pattern.value_max * 127) // 127
                colors.append((i, val_scaled, 0, val_scaled))

        self.fire.set_multiple_pad_colors(colors)

    def calculate_euclidean_pattern(
            self, pulses: int, steps: int, offset: int
    ) -> List[bool]:
        """Calculate euclidean rhythm boolean pattern using Bjorklund's algorithm"""
        if pulses > steps:
            return [True] * steps
        if pulses == 0:
            return [False] * steps

        pattern = [False] * steps
        for i in range(pulses):
            index = (i * steps // pulses + offset) % steps
            pattern[index] = True
        return pattern

    def update_display(self):
        """Update the OLED display"""
        self.canvas.clear()

        # Draw header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        header = f"BPM: {self.tempo:.1f} - {self.edit_mode.name}"
        self.canvas.draw_text(header, 2, 2, color=1)

        # Draw mode-specific content
        if self.edit_mode == EditMode.CLIP:
            self._draw_clip_display()
        elif self.edit_mode == EditMode.STEP:
            self._draw_step_display()
        elif self.edit_mode == EditMode.EUCLIDEAN:
            self._draw_euclidean_display()

        self.fire.render_to_display()

    def _draw_clip_display(self):
        """Draw clip overview display"""
        y = 15

        # Show current track/clip info
        if 0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16:
            clip = self.tracks[self.selected_track][self.selected_clip]
            self.canvas.draw_text(f"Track {self.selected_track + 1}", 2, y)
            y += 12
            self.canvas.draw_text(
                f"Clip {self.selected_clip + 1}: {clip.type.name}", 2, y
            )
            y += 12

        # Show playback position
        beat = (self.current_step // 4) + 1
        tick = (self.current_step % 4) + 1
        self.canvas.draw_text(f"Beat {beat}.{tick}", 2, y)

    def _draw_step_display(self):
        """Draw step sequencer display"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        clip = self.tracks[self.selected_track][self.selected_clip]
        if not clip.step_sequence:
            return

        y = 15
        self.canvas.draw_text(f"Step Edit: Page {self.step_edit_page + 1}", 2, y)
        y += 12
        self.canvas.draw_text(f"Param: {self.step_edit_param}", 2, y)
        y += 12
        self.canvas.draw_text(
            f"Value: {self.step_param_values[self.step_edit_param]}", 2, y
        )

    def _draw_euclidean_display(self):
        """Draw euclidean pattern display"""
        if not (0 <= self.selected_track < 4 and 0 <= self.selected_clip < 16):
            return

        clip = self.tracks[self.selected_track][self.selected_clip]
        if not clip.euclidean:
            return

        y = 15
        pattern = clip.euclidean
        self.canvas.draw_text(f"Steps: {pattern.steps}", 2, y)
        y += 12
        self.canvas.draw_text(f"Pulses: {pattern.pulses}", 2, y)
        y += 12
        self.canvas.draw_text(f"Offset: {pattern.offset}", 2, y)

    def run(self):
        """Main loop"""
        try:
            last_step_time = time.time()

            while True:
                if self.play_state != PlayState.STOPPED:
                    current_time = time.time()
                    step_duration = 60.0 / (self.tempo * 4)  # 16th notes

                    if current_time - last_step_time >= step_duration:
                        self._process_step()
                        last_step_time = current_time

                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop_all_notes()
            self.fire.clear_all()
            self.fire.close()

    def _process_step(self):
        """Process one step of sequencer playback"""
        # Advance step counter
        self.current_step = (self.current_step + 1) % 64

        # Process each track
        for track_idx, track in enumerate(self.tracks):
            if self.track_mutes[track_idx]:
                continue
            if any(self.track_solos) and not self.track_solos[track_idx]:
                continue

            # Process each clip
            for clip_idx, clip in enumerate(track):
                if not clip.is_playing:
                    continue

                self._process_clip(clip, track_idx, clip_idx)

        self.update_pads()
        self.update_display()

    def _process_clip(self, clip: Clip, track: int, clip_idx: int):
        """Process a single clip at current step"""
        if clip.type == ClipType.RECORDED:
            self._process_recorded_clip(clip)
        elif clip.type == ClipType.STEP:
            self._process_step_clip(clip)
        elif clip.type == ClipType.EUCLIDEAN:
            self._process_euclidean_clip(clip)

    def _process_recorded_clip(self, clip: Clip):
        """Process recorded MIDI clip"""
        step_duration = 60.0 / (self.tempo * 4)
        current_time = self.current_step * step_duration

        for msg in clip.midi_messages:
            # Check if message should play at this step
            if abs(msg.timestamp - current_time) < (step_duration / 2):
                self.midi_out.send_message(msg.data)

            # Handle note-offs
            if msg.length and abs((msg.timestamp + msg.length) - current_time) < (
                    step_duration / 2
            ):
                # Create note-off message
                note_off = msg.data.copy()
                note_off[0] = 0x80  # Note-off status
                note_off[2] = 0  # Zero velocity
                self.midi_out.send_message(note_off)

    def _process_step_clip(self, clip: Clip):
        """Process step sequencer clip"""
        if not clip.step_sequence:
            return

        step_idx = self.current_step % clip.step_sequence.length
        params = clip.step_sequence.steps[step_idx]

        if params.active and params.probability >= random.random():
            # Send note-on
            self.midi_out.send_message([0x90, params.note, params.velocity])

            # Schedule note-off
            def send_note_off():
                if self.play_state != PlayState.STOPPED:
                    self.midi_out.send_message([0x80, params.note, 0])

            gate_time = 60.0 / (self.tempo * 4) * params.gate
            threading.Timer(gate_time, send_note_off).start()

    def _process_euclidean_clip(self, clip: Clip):
        """Process euclidean pattern clip"""
        if not clip.euclidean:
            return

        pattern = clip.euclidean
        euclidean_steps = self.calculate_euclidean_pattern(
            pattern.pulses, pattern.steps, pattern.offset
        )

        step_idx = self.current_step % pattern.steps
        if euclidean_steps[step_idx]:
            if pattern.parameter_type == "note":
                # Send note-on
                self.midi_out.send_message([0x90, pattern.note, pattern.velocity])

                # Schedule note-off
                def send_note_off():
                    if self.play_state != PlayState.STOPPED:
                        self.midi_out.send_message([0x80, pattern.note, 0])

                gate_time = 60.0 / (self.tempo * 4) * pattern.gate
                threading.Timer(gate_time, send_note_off).start()
            else:
                # Send CC message
                self.midi_out.send_message(
                    [
                        0xB0,
                        pattern.cc_number,
                        pattern.value_min
                        + (pattern.value_max - pattern.value_min) * random.random(),
                    ]
                )

    def _enter_step_mode(self):
        """Enter step sequencer mode"""
        if self.selected_track >= 0 and self.selected_clip >= 0:
            clip = self.tracks[self.selected_track][self.selected_clip]
            if clip.type != ClipType.STEP:
                clip.type = ClipType.STEP
                clip.step_sequence = StepSequence(
                    steps=[StepParameters() for _ in range(64)],
                    length=16,
                    swing=self.swing,
                )
            self.edit_mode = EditMode.STEP
            self.step_edit_param = "note"
            self.step_edit_page = 0

    def _adjust_step_param(self, amount: float):
        """Adjust current step parameter value"""
        if self.step_edit_param == "note":
            self.step_param_values["note"] = max(
                0, min(127, self.step_param_values["note"] + amount)
            )
        elif self.step_edit_param == "velocity":
            self.step_param_values["velocity"] = max(
                1, min(127, self.step_param_values["velocity"] + amount)
            )
        elif self.step_edit_param == "gate":
            self.step_param_values["gate"] = max(
                0.1, min(1.0, self.step_param_values["gate"] + amount * 0.01)
            )
        elif self.step_edit_param == "probability":
            self.step_param_values["probability"] = max(
                0.0, min(1.0, self.step_param_values["probability"] + amount * 0.01)
            )

    def update_transport_leds(self):
        """Update transport button LEDs"""
        # Play button
        self.fire.set_button_led(
            self.fire.BUTTON_PLAY,
            (
                self.fire.LED_HIGH_GREEN
                if self.play_state == PlayState.PLAYING
                else self.fire.LED_OFF
            ),
        )

        # Record button
        self.fire.set_button_led(
            self.fire.BUTTON_REC,
            (
                self.fire.LED_HIGH_RED
                if self.play_state == PlayState.RECORDING
                else self.fire.LED_OFF
            ),
        )

        # Stop button
        self.fire.set_button_led(
            self.fire.BUTTON_STOP,
            (
                self.fire.LED_HIGH_RED
                if self.play_state == PlayState.STOPPED
                else self.fire.LED_OFF
            ),
        )

        # Solo buttons
        for i in range(4):
            self.fire.set_button_led(
                getattr(self.fire, f"BUTTON_SOLO_{i + 1}"),
                self.fire.LED_HIGH_GREEN if self.track_solos[i] else self.fire.LED_OFF,
            )

    def stop_all_notes(self):
        """Send note-off messages for all MIDI notes"""
        for note in range(128):
            self.midi_out.send_message([0x80, note, 0])


if __name__ == "__main__":
    groovebox = Groovebox()
    groovebox.run()
