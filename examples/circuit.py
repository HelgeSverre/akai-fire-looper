import random
import threading
import time
from enum import Enum, auto
from typing import Dict, List

# noinspection PyPackageRequirements
import rtmidi

from akai_fire import AkaiFire
from mock_gui import MockAkaiFire


class PlayState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    RECORDING = auto()


class ClipType(Enum):
    EMPTY = auto()
    RECORDED = auto()
    STEP = auto()


class ViewMode(Enum):
    NOTE = auto()  # For note input and pattern editing
    EXPANDED_NOTE = auto()  # Extended view without pattern display
    VELOCITY = auto()  # For editing velocity values
    GATE = auto()  # For editing gate/note length
    PATTERN = auto()  # For pattern selection
    PROJECTS = auto()  # For project selection
    SCALES = auto()  # For scale selection
    MIXER = auto()  # For levels and mute control
    FX = auto()  # For FX settings
    SIDE_CHAIN = auto()  # For side chain settings
    TEMPO = auto()  # For tempo and swing settings
    PATTERN_SETTINGS = auto()  # For pattern length and direction
    PROBABILITY = auto()  # For step probability settings
    MICRO_STEP = auto()  # For micro timing adjustments


class Step:
    def __init__(self):
        self.active = False
        self.notes: List[int] = []  # MIDI note numbers
        self.velocity = 100
        self.gate = 0.5  # 0.0 to 1.0 relative to step duration
        self.probability = 1.0  # 0-1.0
        self.micro_step = 0  # 0-5 ticks
        self.tied = False  # For continuous notes


class Pattern:
    def __init__(self, length=16):
        self.steps = [Step() for _ in range(32)]  # Support up to 32 steps
        self.length = length
        self.start_point = 0
        self.end_point = length - 1
        self.sync_rate = 16  # Default sync rate (1/16 notes)
        self.play_order = 0  # 0=forward, 1=backward, 2=ping-pong, 3=random
        self.swing = 0.5  # 0.5 = no swing


class Track:
    def __init__(self, channel=0, name="Track"):
        self.channel = channel
        self.name = name
        self.patterns = [Pattern() for _ in range(8)]  # 8 patterns per track
        self.current_pattern = 0
        self.chain = []  # Chain of pattern indices
        self.mute = False
        self.solo = False
        self.level = 100
        self.pan = 64  # 0-127, 64 = center
        self.reverb_send = 0
        self.delay_send = 0
        self.patch_index = 0  # Current patch or sample
        self.active_notes: Dict[int, float] = {}  # note: start_time


# noinspection PyUnusedLocal,PyMethodMayBeStatic,PyAssignmentToLoopOrWithParameter
class CircuitTracks:
    def __init__(self):
        # Core state
        self.view_mode = ViewMode.NOTE
        self.play_state = PlayState.STOPPED
        self.current_step = 0
        self.selected_step = 0
        self.tempo = 120.0
        self.swing = 0.5
        self.current_track_index = 0
        self.click_level = 64
        self.shift_pressed = False
        self.alt_pressed = False
        self.view_lock = False
        self.step_page = 0  # 0 for steps 1-16, 1 for steps 17-32
        self.fixed_velocity = False
        self.quantize_record = True
        self.record_armed = False
        self.last_step_time = 0
        self.selected_note = 0
        self.sequencer_thread = None

        # Color schemes
        self.track_colors = {
            0: (127, 0, 127),  # Synth 1 - Purple
            1: (0, 127, 50),  # Synth 2 - Light Green
            2: (0, 50, 127),  # MIDI 1 - Blue
            3: (127, 0, 50),  # MIDI 2 - Pink
            4: (127, 50, 0),  # Drum 1 - Orange
            5: (127, 127, 0),  # Drum 2 - Yellow
            6: (80, 0, 127),  # Drum 3 - Purple
            7: (0, 127, 127),  # Drum 4 - Aqua
        }

        # Tracks
        self.tracks = [
            Track(channel=0, name="Synth 1"),
            Track(channel=1, name="Synth 2"),
            Track(channel=2, name="MIDI 1"),
            Track(channel=3, name="MIDI 2"),
            Track(channel=9, name="Drum 1"),
            Track(channel=9, name="Drum 2"),
            Track(channel=9, name="Drum 3"),
            Track(channel=9, name="Drum 4"),
        ]

        # Scale settings
        self.scales = {
            0: [0, 2, 3, 5, 7, 8, 10],  # Natural Minor
            1: [0, 2, 4, 5, 7, 9, 11],  # Major
            2: [0, 2, 3, 5, 7, 9, 10],  # Dorian
            3: [0, 1, 3, 5, 7, 8, 10],  # Phrygian
            4: [0, 2, 4, 5, 7, 9, 10],  # Mixolydian
            5: [0, 2, 3, 5, 7, 9, 11],  # Melodic Minor
            6: [0, 2, 3, 5, 7, 8, 11],  # Harmonic Minor
            7: [0, 2, 3, 5, 7, 9, 10],  # Bebop Dorian
            8: [0, 3, 5, 6, 7, 10],  # Blues
            9: [0, 3, 5, 7, 10],  # Minor Pentatonic
            10: [0, 2, 3, 6, 7, 8, 11],  # Hungarian Minor
            11: [0, 2, 3, 6, 7, 9, 10],  # Ukrainian Dorian
            12: [0, 1, 4, 6, 7, 9],  # Marva
            13: [0, 1, 3, 6, 7, 8, 11],  # Todi
            14: [0, 2, 4, 6, 8, 10],  # Whole Tone
            15: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],  # Chromatic
        }
        self.current_scale = 1  # Default to major
        self.root_note = 60  # Middle C

        # Projects and scenes
        self.current_project = 0
        self.projects = []
        self.scenes = [
            [] for _ in range(16)
        ]  # 16 scenes that can store pattern references
        self.current_scene = 0

        # FX
        self.reverb_preset = 2  # Default to Large Room
        self.delay_preset = 7  # Default to 16th note ping pong
        self.master_filter_freq = 127  # Off position
        self.master_filter_res = 0

        # Setup MIDI
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.setup_midi()

        # Hardware interface
        try:
            self.fire = AkaiFire()
            self.canvas = self.fire.get_canvas()
            self.setup_handlers()
            print("Akai Fire connected successfully")
        except Exception as e:
            print(f"Could not connect to Akai Fire: {e}")
            # Use a mock implementation for development/testing
            self.fire = MockAkaiFire()
            self.canvas = self.fire.get_canvas()
            self.setup_handlers()
            print("Using mock Akai Fire interface")

        # Initial view update
        self.update_grid()
        self.update_leds()

    def setup_midi(self):
        """Setup MIDI input and output ports."""
        # Find MIDI ports
        available_in_ports = self.midi_in.get_ports()
        available_out_ports = self.midi_out.get_ports()

        if available_in_ports:
            self.midi_in.open_port(0)
            self.midi_in.set_callback(self.handle_midi_input)
            print(f"MIDI input connected to: {available_in_ports[0]}")
        else:
            self.midi_in.open_virtual_port("Circuit Tracks In")
            print("Opened virtual MIDI input port")

        if available_out_ports:
            self.midi_out.open_port(0)
            print(f"MIDI output connected to: {available_out_ports[0]}")
        else:
            self.midi_out.open_virtual_port("Circuit Tracks Out")
            print("Opened virtual MIDI output port")

    def handle_midi_input(self, msg, timestamp):
        """Process incoming MIDI messages."""
        if not msg:
            return

        message, delta_time = msg

        # Parse MIDI message
        if len(message) >= 3:
            status = message[0] & 0xF0
            channel = message[0] & 0x0F
            data1 = message[1]
            data2 = message[2] if len(message) > 2 else 0

            # Handle note on/off
            if status == 0x90 and data2 > 0:  # Note On
                self.handle_note_on(channel, data1, data2)
            elif status == 0x80 or (status == 0x90 and data2 == 0):  # Note Off
                self.handle_note_off(channel, data1)
            # Handle CC messages for parameter control
            elif status == 0xB0:  # Control Change
                self.handle_cc(channel, data1, data2)

        # Pass through MIDI to output
        self.midi_out.send_message(message)

    def handle_note_on(self, channel, note, velocity):
        """Process incoming MIDI note on messages."""
        # Record notes if in record mode
        if self.play_state == PlayState.RECORDING:
            track = self.tracks[self.current_track_index]
            if track.channel == channel:
                # Store note start time for recording
                current_time = time.time()
                track.active_notes[note] = current_time

                # If quantize is on, we'll quantize when note off is received
                if not self.quantize_record:
                    # Calculate which step and micro-step this corresponds to
                    beat_position = self.get_beat_position(current_time)
                    step_idx, micro_step = self.get_step_and_microstep(beat_position)

                    # Add note to step with micro-timing
                    pattern = track.patterns[track.current_pattern]
                    if 0 <= step_idx < pattern.length:
                        step = pattern.steps[step_idx]
                        step.active = True
                        step.notes.append(note)
                        step.velocity = velocity
                        step.micro_step = micro_step

    def handle_note_off(self, channel, note):
        """Process incoming MIDI note off messages."""
        # Record note length if in record mode
        if self.play_state == PlayState.RECORDING:
            track = self.tracks[self.current_track_index]
            if track.channel == channel and note in track.active_notes:
                start_time = track.active_notes[note]
                current_time = time.time()

                # If quantize record is on, add the note to the nearest step
                if self.quantize_record:
                    beat_position = self.get_beat_position(start_time)
                    step_idx = (
                        int(beat_position * 4)
                        % track.patterns[track.current_pattern].length
                    )

                    # Calculate note length in steps
                    duration = current_time - start_time
                    beats_duration = duration / (60 / self.tempo)
                    gate_value = min(
                        1.0, beats_duration * 4
                    )  # Convert to gate (0-1 per step)

                    # Add note to step
                    pattern = track.patterns[track.current_pattern]
                    if 0 <= step_idx < pattern.length:
                        step = pattern.steps[step_idx]
                        step.active = True
                        if note not in step.notes:
                            step.notes.append(note)

                        # Use the velocity from the stored active_notes MidiMessage
                        # This assumes active_notes stores MidiMessage objects with velocity
                        # or we need to keep track of note velocity when handling note_on
                        stored_velocity = getattr(
                            track.active_notes[note], "velocity", 100
                        )
                        step.velocity = stored_velocity
                        step.gate = gate_value

                # Remove from active notes
                del track.active_notes[note]

    def handle_cc(self, channel, cc_num, value):
        """Process incoming MIDI CC messages."""
        # Handle specific CC messages based on Circuit Tracks MIDI implementation
        pass

    def get_beat_position(self, timestamp):
        """Convert timestamp to musical beat position."""
        seconds_per_beat = 60.0 / self.tempo
        elapsed_time = timestamp - self.last_step_time
        return elapsed_time / seconds_per_beat

    def get_step_and_microstep(self, beat_position):
        """Convert beat position to step and micro-step indices."""
        # Each beat is 4 steps (16th notes)
        step_position = beat_position * 4

        # Calculate step and micro-step (6 micro-steps per step)
        step_idx = int(step_position)
        micro_step = int((step_position - step_idx) * 6)

        return step_idx, micro_step

    def setup_handlers(self):
        """Set up button and control handlers for the Akai Fire."""

        # Transport controls
        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.play_state == PlayState.STOPPED:
                    self.play()
                else:
                    self.stop()

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.stop()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_record(event):
            if event == "press":
                self.toggle_record()

        # Shift and Alt modifiers
        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def handle_shift(event):
            self.shift_pressed = event == "press"
            if event == "press":
                self.update_grid()  # Update to show shift-specific functions

        @self.fire.on_button(self.fire.BUTTON_ALT)
        def handle_alt(event):
            self.alt_pressed = event == "press"
            if event == "press":
                self.update_grid()  # Update to show alt-specific functions

        # Track selection buttons
        @self.fire.on_button(self.fire.BUTTON_STEP)
        def handle_synth1(event):
            if event == "press":
                self.select_track(0)  # Synth 1

        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_synth2(event):
            if event == "press":
                self.select_track(1)  # Synth 2

        @self.fire.on_button(self.fire.BUTTON_DRUM)
        def handle_midi1(event):
            if event == "press":
                self.select_track(2)  # MIDI 1

        @self.fire.on_button(self.fire.BUTTON_PERFORM)
        def handle_midi2(event):
            if event == "press":
                self.select_track(3)  # MIDI 2

        @self.fire.on_button(self.fire.BUTTON_SOLO_1)
        def handle_drum1(event):
            if event == "press":
                self.select_track(4)  # Drum 1

        @self.fire.on_button(self.fire.BUTTON_SOLO_2)
        def handle_drum2(event):
            if event == "press":
                self.select_track(5)  # Drum 2

        @self.fire.on_button(self.fire.BUTTON_SOLO_3)
        def handle_drum3(event):
            if event == "press":
                self.select_track(6)  # Drum 3

        @self.fire.on_button(self.fire.BUTTON_SOLO_4)
        def handle_drum4(event):
            if event == "press":
                self.select_track(7)  # Drum 4

        # View buttons
        @self.fire.on_button(self.fire.BUTTON_PATTERN)
        def handle_pattern_view(event):
            if event == "press":
                self.set_view_mode(ViewMode.PATTERN)

        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_mixer_view(event):
            if event == "press":
                self.set_view_mode(ViewMode.MIXER)

        # Main grid pad press
        @self.fire.on_pad()
        def handle_pad(pad_idx, velocity):
            # Handle pad press based on current view mode
            if self.view_mode == ViewMode.NOTE:
                self.handle_note_view_pad(pad_idx, velocity)
            elif self.view_mode == ViewMode.EXPANDED_NOTE:
                self.handle_expanded_note_view_pad(pad_idx, velocity)
            elif self.view_mode == ViewMode.PATTERN:
                self.handle_pattern_view_pad(pad_idx)
            elif self.view_mode == ViewMode.VELOCITY:
                self.handle_velocity_view_pad(pad_idx)
            elif self.view_mode == ViewMode.GATE:
                self.handle_gate_view_pad(pad_idx)
            elif self.view_mode == ViewMode.PATTERN_SETTINGS:
                self.handle_pattern_settings_view_pad(pad_idx)
            elif self.view_mode == ViewMode.PROBABILITY:
                self.handle_probability_view_pad(pad_idx)
            elif self.view_mode == ViewMode.MICRO_STEP:
                self.handle_micro_step_view_pad(pad_idx)
            elif self.view_mode == ViewMode.SCALES:
                self.handle_scales_view_pad(pad_idx)
            elif self.view_mode == ViewMode.PROJECTS:
                self.handle_projects_view_pad(pad_idx)
            elif self.view_mode == ViewMode.MIXER:
                self.handle_mixer_view_pad(pad_idx)
            elif self.view_mode == ViewMode.FX:
                self.handle_fx_view_pad(pad_idx)
            elif self.view_mode == ViewMode.SIDE_CHAIN:
                self.handle_side_chain_view_pad(pad_idx)

        # Macro knobs
        for i in range(8):
            rotary = getattr(
                self.fire,
                f"ROTARY_{['VOLUME', 'PAN', 'FILTER', 'RESONANCE', 'SELECT'][i % 5]}",
            )

            @self.fire.on_rotary_turn(rotary)
            def handle_macro(direction, value, macro_idx=i):
                self.handle_macro_control(macro_idx, direction, value)

    def handle_note_view_pad(self, pad_idx, velocity):
        """Handle pad press in Note View."""
        # In Note View, the grid is split:
        # - Upper 2 rows (0-31): Pattern steps
        # - Lower 2 rows (32-63): Keyboard/pads

        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Step selection/editing
            step_idx = col + (self.step_page * 16)
            if self.shift_pressed:
                self.clear_step(step_idx)
            else:
                self.select_step(step_idx)
        else:
            # Note input
            if self.current_track_index < 4:  # Synth or MIDI tracks
                note = self.note_for_pad(pad_idx - 32)
                self.play_note(note, velocity)

                # If recording is active, add note to the current step
                if self.play_state == PlayState.RECORDING:
                    self.add_note_to_step(note, velocity)
            else:  # Drum tracks
                # For drum tracks, the lower rows are sample selection
                sample_idx = col + ((row - 2) * 16)
                self.select_drum_sample(sample_idx)
                self.play_drum(sample_idx, velocity)

                # If recording, add drum hit to the current step
                if self.play_state == PlayState.RECORDING:
                    self.add_drum_to_step(sample_idx, velocity)

    def handle_expanded_note_view_pad(self, pad_idx, velocity):
        """Handle pad press in Expanded Note View (4 rows of keyboard/pads)."""
        # In Expanded Note View, all 4 rows are keyboard/pads
        if self.current_track_index < 4:  # Synth or MIDI tracks
            note = self.note_for_pad(pad_idx)
            self.play_note(note, velocity)

            # If recording is active, add note to the current step
            if self.play_state == PlayState.RECORDING:
                self.add_note_to_step(note, velocity)
        else:  # Drum tracks
            # For expanded drum view, we show all 4 drum tracks at once
            drum_track = pad_idx // 16
            sample_idx = pad_idx % 16
            self.play_drum_for_track(drum_track + 4, sample_idx, velocity)

            # If recording, add drum hit to the current step
            if self.play_state == PlayState.RECORDING:
                self.add_drum_to_step_for_track(drum_track + 4, sample_idx, velocity)

    def handle_pattern_view_pad(self, pad_idx):
        """Handle pad press in Pattern View."""
        # In Pattern View, we see all 8 patterns (4 per page) for each track
        row = pad_idx // 16
        col = pad_idx % 16

        # Calculate pattern index (0-7)
        pattern_idx = col + (row * 4)

        # Select or chain patterns
        if self.shift_pressed:
            # Chain patterns
            self.chain_pattern(pattern_idx)
        else:
            # Select pattern
            self.select_pattern(pattern_idx)

    def handle_velocity_view_pad(self, pad_idx):
        """Handle pad press in Velocity View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Select step
            step_idx = col + (self.step_page * 16)
            self.select_step(step_idx)
        else:
            # Lower 2 rows: Set velocity
            velocity_value = col + 1 + ((row - 2) * 16)
            self.set_step_velocity(velocity_value * 8)

    def handle_gate_view_pad(self, pad_idx):
        """Handle pad press in Gate View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Select step
            step_idx = col + (self.step_page * 16)
            self.select_step(step_idx)
        else:
            # Lower 2 rows: Set gate length
            gate_value = (col + 1 + ((row - 2) * 16)) / 16
            self.set_step_gate(gate_value)

    def handle_pattern_settings_view_pad(self, pad_idx):
        """Handle pad press in Pattern Settings View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row == 0:
            # First row: Set pattern start/end point
            if self.shift_pressed:
                # Set start point
                self.set_pattern_start_point(col)
            else:
                # Set end point
                self.set_pattern_end_point(col)
        elif row == 2:
            # Third row: Pattern sync rate
            if col < 8:
                sync_rates = [
                    4,
                    8,
                    8,
                    16,
                    16,
                    32,
                    32,
                ]  # Quarter, 8th, 8th triplet, etc.
                self.set_pattern_sync_rate(sync_rates[col])
        elif row == 3:
            # Fourth row: Play order
            if col > 27:
                play_order = col - 28
                self.set_pattern_play_order(play_order)

    def handle_probability_view_pad(self, pad_idx):
        """Handle pad press in Probability View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Select step
            step_idx = col + (self.step_page * 16)
            self.select_step(step_idx)
        else:
            # Lower 2 rows: Set probability
            prob_value = (col + 1) / 8
            if prob_value > 1.0:
                prob_value = 1.0
            self.set_step_probability(prob_value)

    def handle_micro_step_view_pad(self, pad_idx):
        """Handle pad press in Micro Step View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Select step
            step_idx = col + (self.step_page * 16)
            self.select_step(step_idx)
        elif row == 2:
            # Third row: Micro step timing (0-5)
            if col < 6:
                self.set_step_micro_step(col)
        elif row == 3:
            # Fourth row: Select which note in the step (when multiple)
            track = self.tracks[self.current_track_index]
            pattern = track.patterns[track.current_pattern]
            step = pattern.steps[self.selected_step]

            if col < len(step.notes):
                # Select specific note for editing
                self.selected_note = col

    def handle_scales_view_pad(self, pad_idx):
        """Handle pad press in Scales View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Root note selection
            if row == 0:
                # Black keys (sharps/flats)
                black_keys = [1, 3, 6, 8, 10]  # C#, D#, F#, G#, A#
                if col < len(black_keys):
                    self.set_root_note(black_keys[col])
            else:
                # White keys
                white_keys = [0, 2, 4, 5, 7, 9, 11]  # C, D, E, F, G, A, B
                if col < len(white_keys):
                    self.set_root_note(white_keys[col])
        else:
            # Lower 2 rows: Scale selection
            scale_idx = (row - 2) * 16 + col
            if scale_idx < len(self.scales):
                self.set_scale(scale_idx)

    def handle_projects_view_pad(self, pad_idx):
        """Handle pad press in Projects View."""
        # Projects are arranged in 4 rows of 16 (64 total)
        project_idx = pad_idx

        if self.shift_pressed:
            # Save project
            self.save_project(project_idx)
        else:
            # Load project
            self.load_project(project_idx)

    def handle_mixer_view_pad(self, pad_idx):
        """Handle pad press in Mixer View."""
        row = pad_idx // 16

        if row < 2:
            # Upper 2 rows: Mute toggles for 8 tracks
            track_idx = (row * 8) + (pad_idx % 8)
            if track_idx < 8:
                self.toggle_track_mute(track_idx)
        else:
            # Lower 2 rows: Scene selection or recording
            scene_idx = (row - 2) * 16 + (pad_idx % 16)
            if scene_idx < 16:
                if self.shift_pressed:
                    # Record current patterns to this scene
                    self.save_scene(scene_idx)
                else:
                    # Trigger this scene
                    self.trigger_scene(scene_idx)

    def handle_fx_view_pad(self, pad_idx):
        """Handle pad press in FX View."""
        row = pad_idx // 16
        col = pad_idx % 16

        if row < 2:
            # Upper 2 rows: Delay presets
            delay_preset = row * 16 + col
            if delay_preset < 16:
                self.select_delay_preset(delay_preset)
        elif row == 2:
            # Third row: Reverb presets
            if col < 8:
                self.select_reverb_preset(col)

    def handle_side_chain_view_pad(self, pad_idx):
        """Handle pad press in Side Chain View."""
        row = pad_idx // 16
        col = pad_idx % 16

        # Side chain setup - rows 0 and 1 are synth side chain settings
        if row == 0:
            # First row: Synth 1 side chain presets
            if col < 8:
                self.set_side_chain_preset(0, col)
        elif row == 1:
            # Second row: Synth 2 side chain presets
            if col < 8:
                self.set_side_chain_preset(1, col)
        elif row == 3:
            # Fourth row: Side chain source selection
            if col < 4:
                self.set_side_chain_source(col)  # 0-3 for Drums 1-4

    def handle_macro_control(self, macro_idx, direction, value):
        """Handle macro knob movement."""
        # The behavior depends on the current view
        if self.view_mode in [ViewMode.NOTE, ViewMode.EXPANDED_NOTE]:
            # In Note View, macros control synth parameters
            self.adjust_synth_parameter(macro_idx, direction, value)

            # Record automation if in recording mode
            if self.play_state == PlayState.RECORDING:
                self.record_automation(macro_idx, value)

        elif self.view_mode == ViewMode.MIXER:
            if macro_idx < 8:
                # Control track levels
                if self.shift_pressed:
                    # Control track panning
                    self.adjust_track_pan(macro_idx, direction, value)
                else:
                    # Control track volume
                    self.adjust_track_level(macro_idx, direction, value)

        elif self.view_mode == ViewMode.FX:
            if macro_idx < 8:
                # Control FX send levels
                if self.shift_pressed:
                    # Control delay send
                    self.adjust_track_delay(macro_idx, direction, value)
                else:
                    # Control reverb send
                    self.adjust_track_reverb(macro_idx, direction, value)

        elif self.view_mode == ViewMode.TEMPO:
            if macro_idx == 0:
                # Tempo control
                self.adjust_tempo(direction, value)
            elif macro_idx == 1:
                # Swing control
                self.adjust_swing(direction, value)
            elif macro_idx == 4:
                # Click track volume
                self.adjust_click_level(direction, value)

    def play(self):
        """Start playback."""
        self.play_state = PlayState.PLAYING
        self.last_step_time = time.time()
        self.current_step = 0

        # Start the sequencer thread if not already running
        if (
            not hasattr(self, "sequencer_thread")
            or not self.sequencer_thread.is_alive()
        ):
            self.sequencer_thread = threading.Thread(target=self.sequencer_loop)
            self.sequencer_thread.daemon = True
            self.sequencer_thread.start()

        # Update transport button LEDs
        self.update_leds()

    def stop(self):
        """Stop playback."""
        self.play_state = PlayState.STOPPED

        # Stop all notes
        self.all_notes_off()

        # Update transport button LEDs
        self.update_leds()

    def toggle_record(self):
        """Toggle record mode."""
        if self.play_state == PlayState.RECORDING:
            self.play_state = PlayState.PLAYING
        else:
            self.play_state = PlayState.RECORDING
            if not self.is_playing():
                self.play()

        # Update transport button LEDs
        self.update_leds()

    def is_playing(self):
        """Check if the sequencer is currently playing."""
        return self.play_state in [PlayState.PLAYING, PlayState.RECORDING]

    def sequencer_loop(self):
        """Main sequencer loop - runs in a separate thread."""
        while True:
            if self.is_playing():
                current_time = time.time()
                step_duration = (
                    60.0 / self.tempo / 4
                )  # Duration of a 16th note in seconds

                # Add swing to even-numbered steps
                if (
                    self.current_step % 2 == 1
                ):  # 0-indexed, so 1, 3, 5... are even steps
                    # Swing range is 20-80 where 50 is no swing
                    # Convert to seconds of delay (-30% to +30%)
                    swing_offset = (self.swing - 0.5) * step_duration
                    step_duration += swing_offset

                # Check if it's time for the next step
                if current_time - self.last_step_time >= step_duration:
                    self.process_step()
                    self.last_step_time = current_time

                    # Increment step counter
                    self.current_step += 1

                    # Check for pattern boundaries on each track
                    for track_idx, track in enumerate(self.tracks):
                        pattern = track.patterns[track.current_pattern]
                        # If we've reached the end of the pattern
                        if self.current_step > pattern.end_point:
                            # Reset step counter for this track
                            if track_idx == 0:  # Use Synth 1 as the master track
                                self.current_step = pattern.start_point

                            # Check if we need to move to the next pattern in a chain
                            if track.chain:
                                current_chain_idx = track.chain.index(
                                    track.current_pattern
                                )
                                next_chain_idx = (current_chain_idx + 1) % len(
                                    track.chain
                                )
                                track.current_pattern = track.chain[next_chain_idx]

                    # Update the grid to show current step
                    self.update_grid()

            # Small sleep to prevent CPU hogging
            time.sleep(0.001)

    def process_step(self):
        """Process the current sequencer step."""
        # Process each track
        for track_idx, track in enumerate(self.tracks):
            # Skip muted tracks (unless solo is active)
            if track.mute and not any(t.solo for t in self.tracks):
                continue

            # Skip tracks that aren't soloed if any track is soloed
            if any(t.solo for t in self.tracks) and not track.solo:
                continue

            pattern = track.patterns[track.current_pattern]

            # Check if current step is within pattern bounds
            if pattern.start_point <= self.current_step <= pattern.end_point:
                # Get effective step based on play order
                effective_step = self.get_effective_step(self.current_step, pattern)

                # Process the step
                step = pattern.steps[effective_step]

                # Only process if step is active
                if step.active:
                    # Apply probability
                    if step.probability >= random.random():
                        # For synth and MIDI tracks
                        if track_idx < 4:
                            for note in step.notes:
                                # Calculate note duration based on gate
                                note_duration = step.gate * 60.0 / self.tempo / 4

                                # Send note on
                                self.send_midi_note_on(
                                    track.channel, note, step.velocity
                                )

                                # Schedule note off
                                self.schedule_note_off(
                                    track.channel, note, note_duration
                                )
                        # For drum tracks
                        else:
                            for note in step.notes:
                                # Send drum hit (Note on channel 9)
                                self.send_midi_note_on(9, note, step.velocity)

                                # Schedule note off
                                self.schedule_note_off(
                                    9, note, 0.1
                                )  # Short duration for drums

                    # Process automation for this step
                    self.process_step_automation(track_idx, effective_step)

    def get_effective_step(self, current_step, pattern):
        """Get the effective step based on pattern play order."""
        rel_step = (current_step - pattern.start_point) % (
            pattern.end_point - pattern.start_point + 1
        )

        # Apply play order
        if pattern.play_order == 0:
            # Forward
            return pattern.start_point + rel_step
        elif pattern.play_order == 1:
            # Reverse
            return pattern.end_point - rel_step
        elif pattern.play_order == 2:
            # Ping-pong
            cycle_length = (pattern.end_point - pattern.start_point) * 2
            cycle_pos = rel_step % cycle_length

            if cycle_pos < (pattern.end_point - pattern.start_point):
                return pattern.start_point + cycle_pos
            else:
                return pattern.end_point - (
                    cycle_pos - (pattern.end_point - pattern.start_point)
                )
        elif pattern.play_order == 3:
            # Random
            return random.randint(pattern.start_point, pattern.end_point)

    def send_midi_note_on(self, channel, note, velocity):
        """Send MIDI note on message."""
        self.midi_out.send_message([0x90 + channel, note, velocity])

    def send_midi_note_off(self, channel, note):
        """Send MIDI note off message."""
        self.midi_out.send_message([0x80 + channel, note, 0])

    def schedule_note_off(self, channel, note, duration):
        """Schedule a note off message after the specified duration."""

        def note_off_callback():
            time.sleep(duration)
            self.send_midi_note_off(channel, note)

        # Start a thread for the scheduled note off
        note_off_thread = threading.Thread(target=note_off_callback)
        note_off_thread.daemon = True
        note_off_thread.start()

    def select_drum_sample(self, sample_idx):
        """Select a drum sample for the current drum track."""
        if self.current_track_index >= 4:  # Only for drum tracks
            track = self.tracks[self.current_track_index]
            track.patch_index = sample_idx
            self.update_grid()

    def play_drum_for_track(self, track_idx, sample_idx, velocity):
        """Play a drum sample for a specific track."""
        if 4 <= track_idx < 8:  # Drum tracks are 4-7
            # Calculate the actual MIDI note number for this drum sample
            # Typically drum samples start at MIDI note 36 (C1)
            note = sample_idx + 36
            # Send MIDI note on message on channel 9 (10 in 1-based numbering)
            self.send_midi_note_on(9, note, velocity)
            # Schedule note off
            self.schedule_note_off(9, note, 0.1)

    def add_drum_to_step_for_track(self, track_idx, sample_idx, velocity):
        """Add a drum hit to a step for a specific track."""
        if 4 <= track_idx < 8:  # Drum tracks are 4-7
            track = self.tracks[track_idx]
            pattern = track.patterns[track.current_pattern]

            # Calculate MIDI note for the drum sample
            note = sample_idx + 36

            if self.quantize_record:
                # Use current sequencer step
                step_idx = self.current_step
            else:
                # TODO: Calculate exact timing using micro steps
                step_idx = self.current_step

            if 0 <= step_idx < pattern.length:
                step = pattern.steps[step_idx]
                step.active = True

                if note not in step.notes:
                    step.notes.append(note)
                step.velocity = velocity

    def adjust_click_level(self, direction, value):
        """Adjust the volume of the metronome click."""
        # Implementation depends on how click/metronome is handled
        # This is a simple implementation that could be expanded
        if direction == "clockwise":
            self.click_level = (
                min(127, self.click_level + value)
                if hasattr(self, "click_level")
                else value
            )
        else:
            self.click_level = (
                max(0, self.click_level - value) if hasattr(self, "click_level") else 0
            )

        # Update display
        self.canvas.clear()
        self.canvas.draw_text("Click Level", 5, 10)
        self.canvas.draw_text(f"Level: {self.click_level}", 5, 25)
        self.fire.render_to_display()

    def draw_side_chain_view(self):
        """Draw the Side Chain View grid."""
        colors = []

        # First two rows: Synth side chain presets
        for i in range(32):
            row = i // 16
            col = i % 16

            if col < 8:
                # Only first 8 columns used for side chain presets
                preset_idx = col

                if row == 0:
                    # First row: Synth 1 side chain
                    track = self.tracks[0]  # Synth 1
                    # Get the actual side chain preset (or use a default value if not set)
                    side_chain_preset = getattr(track, "side_chain_preset", None)

                    if side_chain_preset == preset_idx:
                        color = (127, 80, 0)  # Bright orange for selected preset
                    elif preset_idx == 0:
                        color = (127, 0, 0)  # Red for "Off" position
                    else:
                        color = (50, 30, 0)  # Dim orange for other presets
                elif row == 1:
                    # Second row: Synth 2 side chain
                    track = self.tracks[1]  # Synth 2
                    side_chain_preset = getattr(track, "side_chain_preset", None)

                    if side_chain_preset == preset_idx:
                        color = (127, 80, 0)  # Bright orange for selected preset
                    elif preset_idx == 0:
                        color = (127, 0, 0)  # Red for "Off" position
                    else:
                        color = (50, 30, 0)  # Dim orange for other presets
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Fourth row: Side chain source
        for i in range(48, 64):
            col = i - 48

            if col < 4:
                # First 4 columns: select drum source (Drums 1-4)
                drum_idx = col

                # Check if this is the selected source for either synth
                synth1_source = getattr(self.tracks[0], "side_chain_source", None)
                synth2_source = getattr(self.tracks[1], "side_chain_source", None)

                if synth1_source == drum_idx or synth2_source == drum_idx:
                    color = (127, 0, 0)  # Bright red for selected source
                else:
                    color = (50, 0, 0)  # Dim red for other sources
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Third row: not used
        for i in range(32, 48):
            colors.append((i, 0, 0, 0))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Side Chain View", 5, 10)
        self.canvas.draw_text("Top row: Synth 1 SC presets", 5, 25)
        self.canvas.draw_text("2nd row: Synth 2 SC presets", 5, 40)
        self.canvas.draw_text("Bottom row: SC source (Drums 1-4)", 5, 55)

        self.fire.render_to_display()

    def all_notes_off(self):
        """Send note off for all notes on all channels."""
        for channel in range(16):
            for note in range(128):
                self.send_midi_note_off(channel, note)

    def process_step_automation(self, track_idx, step_idx):
        """Process automation data for the current step."""
        # This would handle automation of parameters that were recorded
        # In Circuit Tracks, automation is per-step and affects the macros
        pass

    def select_track(self, track_idx):
        """Select a track for editing."""
        if 0 <= track_idx < len(self.tracks):
            self.current_track_index = track_idx

            # Update view to show the selected track
            self.update_grid()
            self.update_leds()

    def select_step(self, step_idx):
        """Select a step for editing."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= step_idx < len(pattern.steps):
            self.selected_step = step_idx

            # Update view to show selected step
            self.update_grid()

    def clear_step(self, step_idx):
        """Clear data from a step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= step_idx < len(pattern.steps):
            # Reset step data
            pattern.steps[step_idx] = Step()

            # Update view
            self.update_grid()

    def select_pattern(self, pattern_idx):
        """Select a pattern for the current track."""
        if 0 <= pattern_idx < 8:
            track = self.tracks[self.current_track_index]
            track.current_pattern = pattern_idx

            # Clear any active pattern chain
            track.chain = []

            # Update view
            self.update_grid()

    def chain_pattern(self, pattern_idx):
        """Add a pattern to the chain for the current track."""
        if 0 <= pattern_idx < 8:
            track = self.tracks[self.current_track_index]

            # If this is the first pattern in the chain
            if not track.chain:
                track.chain = [track.current_pattern, pattern_idx]
            else:
                # Add to existing chain if not already in it
                if pattern_idx not in track.chain:
                    # Find smallest and largest pattern indices
                    min_idx = min(track.chain + [pattern_idx])
                    max_idx = max(track.chain + [pattern_idx])

                    # Create contiguous chain from min to max
                    track.chain = list(range(min_idx, max_idx + 1))

            # Update view
            self.update_grid()

    def set_pattern_start_point(self, step_idx):
        """Set the start point for the current pattern."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        # Validate step is before end point
        if step_idx < pattern.end_point:
            pattern.start_point = step_idx

            # Update view
            self.update_grid()

    def set_pattern_end_point(self, step_idx):
        """Set the end point for the current pattern."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        # Validate step is after start point
        if step_idx > pattern.start_point:
            pattern.end_point = step_idx

            # Update view
            self.update_grid()

    def set_pattern_sync_rate(self, rate):
        """Set the sync rate for the current pattern."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]
        pattern.sync_rate = rate

        # Update view
        self.update_grid()

    def set_pattern_play_order(self, order):
        """Set the play order for the current pattern."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]
        pattern.play_order = order

        # Update view
        self.update_grid()

    def set_step_velocity(self, velocity):
        """Set the velocity for the currently selected step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= self.selected_step < len(pattern.steps):
            pattern.steps[self.selected_step].velocity = velocity

            # Update view
            self.update_grid()

    def set_step_gate(self, gate):
        """Set the gate value for the currently selected step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= self.selected_step < len(pattern.steps):
            pattern.steps[self.selected_step].gate = gate

            # Update view
            self.update_grid()

    def set_step_probability(self, probability):
        """Set the probability for the currently selected step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= self.selected_step < len(pattern.steps):
            pattern.steps[self.selected_step].probability = probability

            # Update view
            self.update_grid()

    def set_step_micro_step(self, micro_step):
        """Set the micro step timing for the currently selected step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if 0 <= self.selected_step < len(pattern.steps):
            pattern.steps[self.selected_step].micro_step = micro_step

            # Update view
            self.update_grid()

    def note_for_pad(self, pad_idx):
        """Calculate which MIDI note a pad should trigger based on current scale."""
        # For synth tracks, calculate based on scale and root note
        if self.current_track_index < 4:  # Synth or MIDI tracks
            row = pad_idx // 16
            col = pad_idx % 16

            # Calculate octave offset (lower rows = lower octaves)
            octave_offset = -row

            if self.current_scale == 15:  # Chromatic scale
                # Special layout for chromatic scale
                note_in_octave = col
                return self.root_note + octave_offset * 12 + note_in_octave
            else:
                # Use scale-based mapping
                scale = self.scales[self.current_scale]
                note_in_scale = col % len(scale)
                octave_in_col = col // len(scale)

                return (
                    self.root_note
                    + (octave_offset + octave_in_col) * 12
                    + scale[note_in_scale]
                )
        else:
            # For drum tracks, simply return the pad index + offset
            return pad_idx + 36  # Start at MIDI note 36 (C1)

    def play_note(self, note, velocity):
        """Play a MIDI note on the current track."""
        channel = self.tracks[self.current_track_index].channel
        self.send_midi_note_on(channel, note, velocity)

        # Schedule a note off
        self.schedule_note_off(channel, note, 0.1)

    def play_drum(self, sample_idx, velocity):
        """Play a drum sample."""
        # Drum samples are mapped to MIDI notes starting at 36 (C1)
        note = sample_idx + 36
        self.send_midi_note_on(9, note, velocity)  # Channel 9 (10 in 1-based systems)

        # Schedule a note off
        self.schedule_note_off(9, note, 0.1)

    def add_note_to_step(self, note, velocity):
        """Add a note to the current step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if self.quantize_record:
            # Use current sequencer step
            step_idx = self.current_step
        else:
            # TODO: Calculate exact timing using micro steps
            step_idx = self.current_step

        if 0 <= step_idx < len(pattern.steps):
            step = pattern.steps[step_idx]
            step.active = True
            if note not in step.notes:
                step.notes.append(note)
            step.velocity = velocity

    def add_drum_to_step(self, sample_idx, velocity):
        """Add a drum hit to the current step."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        if self.quantize_record:
            # Use current sequencer step
            step_idx = self.current_step
        else:
            # TODO: Calculate exact timing using micro steps
            step_idx = self.current_step

        if 0 <= step_idx < len(pattern.steps):
            step = pattern.steps[step_idx]
            step.active = True

            # For drums, we store the sample index as the note
            note = sample_idx + 36  # MIDI note offset
            if note not in step.notes:
                step.notes.append(note)
            step.velocity = velocity

    def set_root_note(self, root):
        """Set the root note for scales."""
        self.root_note = 60 + root  # 60 = Middle C
        self.update_grid()

    def set_scale(self, scale_idx):
        """Set the current scale."""
        if 0 <= scale_idx < len(self.scales):
            self.current_scale = scale_idx
            self.update_grid()

    def toggle_track_mute(self, track_idx):
        """Toggle mute for a track."""
        if 0 <= track_idx < len(self.tracks):
            self.tracks[track_idx].mute = not self.tracks[track_idx].mute

            # If track is muted, send note offs for all active notes
            if self.tracks[track_idx].mute:
                channel = self.tracks[track_idx].channel
                for note in range(128):
                    self.send_midi_note_off(channel, note)

            self.update_grid()
            self.update_leds()

    def adjust_track_level(self, track_idx, direction, value):
        """Adjust the volume level for a track."""
        if 0 <= track_idx < len(self.tracks):
            if direction == "clockwise":
                self.tracks[track_idx].level = min(
                    127, self.tracks[track_idx].level + value
                )
            else:
                self.tracks[track_idx].level = max(
                    0, self.tracks[track_idx].level - value
                )

            # Send MIDI CC for volume
            self.send_midi_cc(
                self.tracks[track_idx].channel, 7, self.tracks[track_idx].level
            )

    def adjust_track_pan(self, track_idx, direction, value):
        """Adjust the pan position for a track."""
        if 0 <= track_idx < len(self.tracks):
            if direction == "clockwise":
                self.tracks[track_idx].pan = min(
                    127, self.tracks[track_idx].pan + value
                )
            else:
                self.tracks[track_idx].pan = max(0, self.tracks[track_idx].pan - value)

            # Send MIDI CC for pan
            self.send_midi_cc(
                self.tracks[track_idx].channel, 10, self.tracks[track_idx].pan
            )

    def adjust_track_reverb(self, track_idx, direction, value):
        """Adjust the reverb send for a track."""
        if 0 <= track_idx < len(self.tracks):
            if direction == "clockwise":
                self.tracks[track_idx].reverb_send = min(
                    127, self.tracks[track_idx].reverb_send + value
                )
            else:
                self.tracks[track_idx].reverb_send = max(
                    0, self.tracks[track_idx].reverb_send - value
                )

            # Update visual feedback
            self.update_grid()

    def adjust_track_delay(self, track_idx, direction, value):
        """Adjust the delay send for a track."""
        if 0 <= track_idx < len(self.tracks):
            if direction == "clockwise":
                self.tracks[track_idx].delay_send = min(
                    127, self.tracks[track_idx].delay_send + value
                )
            else:
                self.tracks[track_idx].delay_send = max(
                    0, self.tracks[track_idx].delay_send - value
                )

            # Update visual feedback
            self.update_grid()

    def adjust_tempo(self, direction, value):
        """Adjust the tempo."""
        if direction == "clockwise":
            self.tempo = min(240, self.tempo + value)
        else:
            self.tempo = max(40, self.tempo - value)

        # Update display
        self.draw_tempo_display()

    def adjust_swing(self, direction, value):
        """Adjust the swing amount."""
        if direction == "clockwise":
            self.swing = min(0.75, self.swing + (value * 0.01))
        else:
            self.swing = max(0.25, self.swing - (value * 0.01))

        # Update display
        self.draw_tempo_display()

    def adjust_synth_parameter(self, macro_idx, direction, value):
        """Adjust synth parameters using macro knobs."""
        if self.current_track_index < 2:  # Synth tracks only
            track = self.tracks[self.current_track_index]

            # Map macro index to CC numbers
            cc_map = [
                1,  # Oscillator
                2,  # Oscillator Mod
                3,  # Amp Envelope
                4,  # Filter Envelope
                5,  # Filter Frequency
                6,  # Resonance
                7,  # Modulation
                8,  # FX
            ]

            # Calculate new value
            current_value = 64  # Default middle position
            if direction == "clockwise":
                new_value = min(127, current_value + value)
            else:
                new_value = max(0, current_value - value)

            # Send MIDI CC
            if macro_idx < len(cc_map):
                self.send_midi_cc(track.channel, cc_map[macro_idx], new_value)

    def send_midi_cc(self, channel, cc_num, value):
        """Send MIDI Control Change message."""
        self.midi_out.send_message([0xB0 + channel, cc_num, value])

    def record_automation(self, macro_idx, value):
        """Record automation data for the current step."""
        # In Circuit Tracks, automation is recorded per step
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        step_idx = self.current_step
        if 0 <= step_idx < len(pattern.steps):
            # Store automation data (would be implemented with a proper automation data structure)
            pass

    def save_scene(self, scene_idx):
        """Save current pattern selections to a scene."""
        if 0 <= scene_idx < len(self.scenes):
            # Store current pattern for each track
            self.scenes[scene_idx] = [track.current_pattern for track in self.tracks]

            # Update display
            self.update_grid()

    def trigger_scene(self, scene_idx):
        """Trigger a scene, switching all tracks to the stored patterns."""
        if 0 <= scene_idx < len(self.scenes) and self.scenes[scene_idx]:
            # Set each track to the stored pattern
            for track_idx, pattern_idx in enumerate(self.scenes[scene_idx]):
                if track_idx < len(self.tracks):
                    self.tracks[track_idx].current_pattern = pattern_idx

            # If not playing, start playback
            if not self.is_playing():
                self.play()

            # Update display
            self.update_grid()

    def select_delay_preset(self, preset_idx):
        """Select a delay preset."""
        if 0 <= preset_idx < 16:
            self.delay_preset = preset_idx

            # Update display
            self.update_grid()

    def select_reverb_preset(self, preset_idx):
        """Select a reverb preset."""
        if 0 <= preset_idx < 8:
            self.reverb_preset = preset_idx

            # Update display
            self.update_grid()

    def set_side_chain_preset(self, synth_idx, preset_idx):
        """Set side chain preset for a synth track."""
        # Implementation would depend on how side chain is structured
        pass

    def set_side_chain_source(self, drum_idx):
        """Set which drum track triggers the side chain."""
        # Implementation would depend on how side chain is structured
        pass

    def save_project(self, project_idx):
        """Save current state to a project slot."""
        # This would save all patterns, scenes, and settings
        pass

    def load_project(self, project_idx):
        """Load a project from memory."""
        # This would load all patterns, scenes, and settings
        pass

    def draw_tempo_display(self):
        """Draw tempo and swing values on the display."""
        self.canvas.clear()

        # Display tempo
        self.canvas.draw_text(f"Tempo: {self.tempo:.1f} BPM", 5, 10)

        # Display swing
        swing_percent = int((self.swing - 0.5) * 100 * 2)
        self.canvas.draw_text(f"Swing: {swing_percent}%", 5, 25)

        # Render to display
        self.fire.render_to_display()

    def set_view_mode(self, mode):
        """Switch to a different view mode."""
        self.view_mode = mode

        # Update display for the new mode
        self.update_grid()
        self.update_leds()

    def update_grid(self):
        """Update the pad grid based on current view mode."""
        # Clear all pads
        self.fire.reset_pads()

        # Update based on view mode
        if self.view_mode == ViewMode.NOTE:
            self.draw_note_view()
        elif self.view_mode == ViewMode.EXPANDED_NOTE:
            self.draw_expanded_note_view()
        elif self.view_mode == ViewMode.VELOCITY:
            self.draw_velocity_view()
        elif self.view_mode == ViewMode.GATE:
            self.draw_gate_view()
        elif self.view_mode == ViewMode.PATTERN:
            self.draw_pattern_view()
        elif self.view_mode == ViewMode.PROJECTS:
            self.draw_projects_view()
        elif self.view_mode == ViewMode.SCALES:
            self.draw_scales_view()
        elif self.view_mode == ViewMode.MIXER:
            self.draw_mixer_view()
        elif self.view_mode == ViewMode.FX:
            self.draw_fx_view()
        elif self.view_mode == ViewMode.SIDE_CHAIN:
            self.draw_side_chain_view()
        elif self.view_mode == ViewMode.PATTERN_SETTINGS:
            self.draw_pattern_settings_view()
        elif self.view_mode == ViewMode.PROBABILITY:
            self.draw_probability_view()
        elif self.view_mode == ViewMode.MICRO_STEP:
            self.draw_micro_step_view()

    def update_leds(self):
        """Update all LEDs on the Akai Fire."""
        # Update transport controls
        self.fire.set_button_led(
            self.fire.BUTTON_PLAY,
            (
                self.fire.LED_HIGH_GREEN
                if self.play_state == PlayState.PLAYING
                else self.fire.LED_OFF
            ),
        )

        self.fire.set_button_led(
            self.fire.BUTTON_REC,
            (
                self.fire.LED_HIGH_RED
                if self.play_state == PlayState.RECORDING
                else self.fire.LED_OFF
            ),
        )

        # Update view mode buttons
        view_buttons = {
            ViewMode.NOTE: self.fire.BUTTON_NOTE,
            ViewMode.PATTERN: self.fire.BUTTON_PATTERN,
            ViewMode.MIXER: self.fire.BUTTON_BROWSER,
        }

        for view, button in view_buttons.items():
            self.fire.set_button_led(
                button,
                (
                    self.fire.LED_HIGH_GREEN
                    if self.view_mode == view
                    else self.fire.LED_DULL_GREEN
                ),
            )

        # Update track selection buttons
        track_buttons = [
            self.fire.BUTTON_STEP,  # Synth 1
            self.fire.BUTTON_NOTE,  # Synth 2
            self.fire.BUTTON_DRUM,  # MIDI 1
            self.fire.BUTTON_PERFORM,  # MIDI 2
            self.fire.BUTTON_SOLO_1,  # Drum 1
            self.fire.BUTTON_SOLO_2,  # Drum 2
            self.fire.BUTTON_SOLO_3,  # Drum 3
            self.fire.BUTTON_SOLO_4,  # Drum 4
        ]

        for idx, button in enumerate(track_buttons):
            if idx < len(self.tracks):
                color = (
                    self.fire.LED_HIGH_GREEN
                    if self.current_track_index == idx
                    else self.fire.LED_DULL_GREEN
                )

                # If track is muted, use red
                if self.tracks[idx].mute:
                    color = (
                        self.fire.LED_HIGH_RED
                        if self.current_track_index == idx
                        else self.fire.LED_DULL_RED
                    )

                # If track is soloed, use yellow
                if self.tracks[idx].solo:
                    color = (
                        self.fire.LED_HIGH_YELLOW
                        if self.current_track_index == idx
                        else self.fire.LED_DULL_YELLOW
                    )

                self.fire.set_button_led(button, color)

                # If track is muted, use red
                if self.tracks[idx].mute:
                    color = (
                        self.fire.LED_HIGH_RED
                        if self.current_track_index == idx
                        else self.fire.LED_DULL_RED
                    )

                # If track is soloed, use yellow
                if self.tracks[idx].solo:
                    color = (
                        self.fire.LED_HIGH_YELLOW
                        if self.current_track_index == idx
                        else self.fire.LED_DULL_YELLOW
                    )

                self.fire.set_button_led(button, color)

    def draw_note_view(self):
        """Draw the Note View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]
        track_color = self.track_colors[self.current_track_index]

        colors = []

        # Upper 2 rows: Pattern steps
        for i in range(32):
            row = i // 16
            col = i % 16
            step_idx = col + (self.step_page * 16)

            if step_idx < pattern.length:
                # Step color based on state
                if step_idx == self.current_step and self.is_playing():
                    # Current playing step: white
                    color = (127, 127, 127)
                elif step_idx == self.selected_step:
                    # Selected step: yellow
                    color = (127, 127, 0)
                elif pattern.steps[step_idx].active:
                    # Active step: track color
                    color = track_color
                else:
                    # Inactive step: dim blue
                    color = (0, 0, 40)
            else:
                # Steps beyond pattern length: off
                color = (0, 0, 0)

            colors.append((i, *color))

        # Lower 2 rows: Notes or drum pads
        if self.current_track_index < 4:  # Synth or MIDI tracks
            # Draw keyboard layout
            for i in range(32, 64):
                note = self.note_for_pad(i - 32)

                # Determine if this is a root note
                is_root = (note % 12) == (self.root_note % 12)

                # Determine if this is a note in the scale
                note_in_scale = (note % 12) in [
                    (self.root_note + interval) % 12
                    for interval in self.scales[self.current_scale]
                ]

                if is_root:
                    # Root notes: brighter
                    color = tuple(min(127, c + 40) for c in track_color)
                elif note_in_scale:
                    # Notes in scale: normal color
                    color = track_color
                else:
                    # Notes not in scale: dim
                    color = tuple(c // 3 for c in track_color)

                colors.append((i, *color))
        else:  # Drum tracks
            # Draw drum pads
            for i in range(32, 64):
                sample_idx = (i - 32) + (self.step_page * 16)

                # Highlight the current selected sample
                if sample_idx == track.patch_index:
                    color = (127, 127, 127)  # White for selected sample
                else:
                    color = track_color

                colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.draw_note_view_display()

    def draw_expanded_note_view(self):
        """Draw the Expanded Note View grid (4 rows of keyboard/pads)."""
        track = self.tracks[self.current_track_index]
        track_color = self.track_colors[self.current_track_index]

        colors = []

        # All 4 rows are keyboard/pads
        if self.current_track_index < 4:  # Synth or MIDI tracks
            # Draw expanded keyboard layout
            for i in range(64):
                note = self.note_for_pad(i)

                # Determine if this is a root note
                is_root = (note % 12) == (self.root_note % 12)

                # Determine if this is a note in the scale
                note_in_scale = (note % 12) in [
                    (self.root_note + interval) % 12
                    for interval in self.scales[self.current_scale]
                ]

                if is_root:
                    # Root notes: brighter
                    color = tuple(min(127, c + 40) for c in track_color)
                elif note_in_scale:
                    # Notes in scale: normal color
                    color = track_color
                else:
                    # Notes not in scale: dim
                    color = tuple(c // 3 for c in track_color)

                colors.append((i, *color))
        else:  # Drum tracks
            # Draw expanded drum view (all 4 drum tracks)
            for i in range(64):
                row = i // 16
                col = i % 16

                # Each row represents a different drum track
                drum_track_idx = row + 4  # Drum tracks start at index 4

                if drum_track_idx < 8:
                    drum_track = self.tracks[drum_track_idx]
                    drum_color = self.track_colors[drum_track_idx]

                    # Highlight the current selected sample for each drum track
                    if col == drum_track.patch_index:
                        color = (127, 127, 127)  # White for selected sample
                    else:
                        color = drum_color
                else:
                    color = (0, 0, 0)  # Off

                colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Expanded Note View", 5, 10)
        if self.current_track_index < 4:
            self.canvas.draw_text(f"Track: {track.name}", 5, 25)
            scale_name = list(self.scales.keys())[self.current_scale]
            self.canvas.draw_text(f"Scale: {scale_name}", 5, 40)
        else:
            self.canvas.draw_text("Drum tracks: 1-4", 5, 25)
        self.fire.render_to_display()

    def draw_velocity_view(self):
        """Draw the Velocity View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        colors = []

        # Upper 2 rows: Pattern steps
        for i in range(32):
            row = i // 16
            col = i % 16
            step_idx = col + (self.step_page * 16)

            if step_idx < pattern.length:
                # Step color based on state
                if step_idx == self.current_step and self.is_playing():
                    # Current playing step: white
                    color = (127, 127, 127)
                elif step_idx == self.selected_step:
                    # Selected step: yellow
                    color = (127, 127, 0)
                elif pattern.steps[step_idx].active:
                    # Active step: blue
                    color = (0, 0, 127)
                else:
                    # Inactive step: dim blue
                    color = (0, 0, 40)
            else:
                # Steps beyond pattern length: off
                color = (0, 0, 0)

            colors.append((i, *color))

        # Lower 2 rows: Velocity values
        for i in range(32, 64):
            idx = i - 32

            # If selected step is active, show its velocity
            if (
                0 <= self.selected_step < pattern.length
                and pattern.steps[self.selected_step].active
            ):
                vel = pattern.steps[self.selected_step].velocity

                # Check if this pad should be lit based on velocity
                if idx < vel // 8:
                    # Velocity scale from green (low) to red (high)
                    green = max(0, 127 - (idx * 8))
                    red = min(127, idx * 8)
                    color = (red, green, 0)
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Velocity View", 5, 10)

        if (
            0 <= self.selected_step < pattern.length
            and pattern.steps[self.selected_step].active
        ):
            vel = pattern.steps[self.selected_step].velocity
            self.canvas.draw_text(f"Step: {self.selected_step + 1}", 5, 25)
            self.canvas.draw_text(f"Velocity: {vel}", 5, 40)
        else:
            self.canvas.draw_text("No step selected", 5, 25)

        self.fire.render_to_display()

    def draw_gate_view(self):
        """Draw the Gate View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        colors = []

        # Upper 2 rows: Pattern steps
        for i in range(32):
            row = i // 16
            col = i % 16
            step_idx = col + (self.step_page * 16)

            if step_idx < pattern.length:
                # Step color based on state
                if step_idx == self.current_step and self.is_playing():
                    # Current playing step: white
                    color = (127, 127, 127)
                elif step_idx == self.selected_step:
                    # Selected step: yellow
                    color = (127, 127, 0)
                elif pattern.steps[step_idx].active:
                    # Active step: blue
                    color = (0, 0, 127)
                else:
                    # Inactive step: dim blue
                    color = (0, 0, 40)
            else:
                # Steps beyond pattern length: off
                color = (0, 0, 0)

            colors.append((i, *color))

        # Lower 2 rows: Gate values
        for i in range(32, 64):
            idx = i - 32

            # If selected step is active, show its gate
            if (
                0 <= self.selected_step < pattern.length
                and pattern.steps[self.selected_step].active
            ):
                gate = pattern.steps[self.selected_step].gate

                # Check if this pad should be lit based on gate
                if idx < int(gate * 16):
                    # Gate scale - cyan
                    color = (0, 127, 127)
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Gate View", 5, 10)

        if (
            0 <= self.selected_step < pattern.length
            and pattern.steps[self.selected_step].active
        ):
            gate = pattern.steps[self.selected_step].gate
            self.canvas.draw_text(f"Step: {self.selected_step + 1}", 5, 25)
            self.canvas.draw_text(f"Gate: {gate:.2f}", 5, 40)
        else:
            self.canvas.draw_text("No step selected", 5, 25)

        self.fire.render_to_display()

    def draw_pattern_view(self):
        """Draw the Pattern View grid."""
        track = self.tracks[self.current_track_index]
        track_color = self.track_colors[self.current_track_index]

        colors = []

        # Show 8 patterns (4 per page) for the current track
        page = 0  # TODO: Add support for Page 2 (patterns 5-8)

        for i in range(64):
            row = i // 16
            col = i % 16

            # Only use first 4 columns and all rows
            if col < 4:
                pattern_idx = col + (row * 4)

                if pattern_idx < 8:
                    # Determine pattern color
                    if pattern_idx == track.current_pattern:
                        # Current pattern: bright
                        color = track_color
                    elif pattern_idx in track.chain:
                        # Chained pattern: medium brightness
                        color = tuple(c // 2 for c in track_color)
                    else:
                        # Inactive pattern: dim
                        color = tuple(c // 4 for c in track_color)
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Pattern View", 5, 10)
        self.canvas.draw_text(f"Track: {track.name}", 5, 25)

        if track.chain:
            chain_str = " > ".join(str(p + 1) for p in track.chain)
            self.canvas.draw_text(f"Chain: {chain_str}", 5, 40)
        else:
            self.canvas.draw_text(f"Pattern: {track.current_pattern + 1}", 5, 40)

        self.fire.render_to_display()

    def draw_pattern_settings_view(self):
        """Draw the Pattern Settings View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        colors = []

        # First row: Pattern steps for start/end points
        for i in range(16):
            if i < pattern.length:
                if i == pattern.start_point:
                    color = (0, 127, 0)  # Green for start point
                elif i == pattern.end_point:
                    color = (127, 0, 0)  # Red for end point
                elif pattern.start_point < i < pattern.end_point:
                    color = (0, 0, 127)  # Blue for active steps
                else:
                    color = (30, 30, 30)  # Dim for inactive steps
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Second row: Currently unused
        for i in range(16, 32):
            colors.append((i, 0, 0, 0))

        # Third row: Sync rates
        sync_rates = [4, 8, 8, 16, 16, 32, 32, 32]  # Different sync rates
        for i in range(32, 48):
            idx = i - 32

            if idx < len(sync_rates):
                if sync_rates[idx] == pattern.sync_rate:
                    color = (127, 127, 0)  # Yellow for selected rate
                else:
                    color = (40, 40, 0)  # Dim yellow for other rates
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Fourth row: Play order
        play_orders = ["Forward", "Reverse", "Ping-pong", "Random"]
        for i in range(48, 64):
            idx = i - 48

            if 28 <= idx < 32:
                order_idx = idx - 28

                if order_idx == pattern.play_order:
                    color = (0, 127, 127)  # Cyan for selected order
                else:
                    color = (0, 40, 40)  # Dim cyan for other orders
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Pattern Settings", 5, 10)
        self.canvas.draw_text(
            f"Length: {pattern.end_point - pattern.start_point + 1}", 5, 25
        )

        play_orders = ["Forward", "Reverse", "Ping-pong", "Random"]
        self.canvas.draw_text(f"Play: {play_orders[pattern.play_order]}", 5, 40)
        self.canvas.draw_text(f"Sync: 1/{pattern.sync_rate}", 5, 55)

        self.fire.render_to_display()

    def draw_probability_view(self):
        """Draw the Probability View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        colors = []

        # Upper 2 rows: Pattern steps
        for i in range(32):
            row = i // 16
            col = i % 16
            step_idx = col + (self.step_page * 16)

            if step_idx < pattern.length:
                # Step color based on state
                if step_idx == self.current_step and self.is_playing():
                    # Current playing step: white
                    color = (127, 127, 127)
                elif step_idx == self.selected_step:
                    # Selected step: yellow
                    color = (127, 127, 0)
                elif pattern.steps[step_idx].active:
                    # Active step: blue
                    color = (0, 0, 127)
                else:
                    # Inactive step: dim blue
                    color = (0, 0, 40)
            else:
                # Steps beyond pattern length: off
                color = (0, 0, 0)

            colors.append((i, *color))

        # Lower 2 rows: Probability values
        for i in range(32, 64):
            idx = i - 32

            # If selected step is active, show its probability
            if (
                0 <= self.selected_step < pattern.length
                and pattern.steps[self.selected_step].active
            ):
                prob = pattern.steps[self.selected_step].probability

                # Check if this pad should be lit based on probability
                if idx < int(prob * 16):
                    # Probability scale - green
                    color = (0, 127, 0)
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Probability View", 5, 10)

        if (
            0 <= self.selected_step < pattern.length
            and pattern.steps[self.selected_step].active
        ):
            prob = pattern.steps[self.selected_step].probability
            self.canvas.draw_text(f"Step: {self.selected_step + 1}", 5, 25)
            self.canvas.draw_text(f"Probability: {int(prob * 100)}%", 5, 40)
        else:
            self.canvas.draw_text("No step selected", 5, 25)

        self.fire.render_to_display()

    def draw_micro_step_view(self):
        """Draw the Micro Step View grid."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        colors = []

        # Upper 2 rows: Pattern steps
        for i in range(32):
            row = i // 16
            col = i % 16
            step_idx = col + (self.step_page * 16)

            if step_idx < pattern.length:
                # Step color based on state
                if step_idx == self.current_step and self.is_playing():
                    # Current playing step: white
                    color = (127, 127, 127)
                elif step_idx == self.selected_step:
                    # Selected step: yellow
                    color = (127, 127, 0)
                elif pattern.steps[step_idx].active:
                    # Active step: blue
                    color = (0, 0, 127)
                else:
                    # Inactive step: dim blue
                    color = (0, 0, 40)
            else:
                # Steps beyond pattern length: off
                color = (0, 0, 0)

            colors.append((i, *color))

        # Third row: Micro step timing (0-5)
        for i in range(32, 48):
            idx = i - 32

            # If selected step is active, show its micro step
            if (
                0 <= self.selected_step < pattern.length
                and pattern.steps[self.selected_step].active
            ):
                micro_step = pattern.steps[self.selected_step].micro_step

                # Only first 6 pads are used (micro steps 0-5)
                if idx < 6:
                    if idx == micro_step:
                        # Selected micro step: bright
                        color = (127, 0, 127)  # Purple
                    else:
                        # Other micro steps: dim
                        color = (40, 0, 40)
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Fourth row: Note selection (when multiple notes on a step)
        for i in range(48, 64):
            idx = i - 48

            # If selected step is active, show notes
            if (
                0 <= self.selected_step < pattern.length
                and pattern.steps[self.selected_step].active
            ):
                # Show a pad for each note
                if idx < len(pattern.steps[self.selected_step].notes):
                    # Pad for each note
                    color = (127, 127, 0)  # Yellow
                else:
                    color = (0, 0, 0)  # Off
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Micro Step View", 5, 10)

        if (
            0 <= self.selected_step < pattern.length
            and pattern.steps[self.selected_step].active
        ):
            micro = pattern.steps[self.selected_step].micro_step
            self.canvas.draw_text(f"Step: {self.selected_step + 1}", 5, 25)
            self.canvas.draw_text(f"Micro step: {micro}", 5, 40)
        else:
            self.canvas.draw_text("No step selected", 5, 25)

        self.fire.render_to_display()

    def draw_scales_view(self):
        """Draw the Scales View grid."""
        colors = []

        # Upper 2 rows: Root note selection
        for i in range(32):
            row = i // 16
            col = i % 16

            if row == 0:
                # Black keys (sharps/flats)
                black_keys = [1, 3, 6, 8, 10]  # C#, D#, F#, G#, A#
                if col < len(black_keys):
                    # Check if this is the current root note
                    if (self.root_note % 12) == black_keys[col]:
                        color = (127, 127, 127)  # White for selected
                    else:
                        color = (50, 50, 50)  # Gray for black keys
                else:
                    color = (0, 0, 0)  # Off
            else:
                # White keys
                white_keys = [0, 2, 4, 5, 7, 9, 11]  # C, D, E, F, G, A, B
                if col < len(white_keys):
                    # Check if this is the current root note
                    if (self.root_note % 12) == white_keys[col]:
                        color = (127, 127, 127)  # White for selected
                    else:
                        color = (100, 100, 100)  # Bright gray for white keys
                else:
                    color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Lower 2 rows: Scale selection
        scale_count = len(self.scales)
        for i in range(32, 64):
            idx = i - 32

            if idx < scale_count:
                if idx == self.current_scale:
                    # Selected scale: bright
                    color = (0, 127, 127)  # Cyan
                else:
                    # Other scales: dim
                    color = (0, 50, 50)
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Scales View", 5, 10)

        # Get root note name
        root_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        root_name = root_names[self.root_note % 12]

        # Get scale name
        scale_names = [
            "Natural Minor",
            "Major",
            "Dorian",
            "Phrygian",
            "Mixolydian",
            "Melodic Minor",
            "Harmonic Minor",
            "Bebop Dorian",
            "Blues",
            "Minor Pentatonic",
            "Hungarian Minor",
            "Ukrainian Dorian",
            "Marva",
            "Todi",
            "Whole Tone",
            "Chromatic",
        ]
        scale_name = scale_names[self.current_scale]

        self.canvas.draw_text(f"Root: {root_name}", 5, 25)
        self.canvas.draw_text(f"Scale: {scale_name}", 5, 40)

        self.fire.render_to_display()

    def draw_projects_view(self):
        """Draw the Projects View grid."""
        colors = []

        # All 64 pads represent projects
        for i in range(64):
            if i == self.current_project:
                # Current project: white
                color = (127, 127, 127)
            elif i < len(self.projects) and self.projects[i]:
                # Saved project: blue
                color = (0, 0, 127)
            else:
                # Empty project: dim blue
                color = (0, 0, 40)

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Projects View", 5, 10)
        self.canvas.draw_text(f"Current project: {self.current_project + 1}", 5, 25)
        self.canvas.draw_text("Press pad to load", 5, 40)
        self.canvas.draw_text("Shift+pad to save", 5, 55)

        self.fire.render_to_display()

    def draw_mixer_view(self):
        """Draw the Mixer View grid."""
        colors = []

        # Upper 2 rows: Mute buttons for tracks
        for i in range(32):
            row = i // 16
            col = i % 16

            # Only first 8 columns are used (one per track)
            if col < 8:
                track_idx = col
                track = self.tracks[track_idx]

                if track.mute:
                    # Muted track: red
                    color = (127, 0, 0)
                elif track.solo:
                    # Soloed track: yellow
                    color = (127, 127, 0)
                else:
                    # Active track: green
                    color = (0, 127, 0)
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

        # Lower 2 rows: Scenes
        for i in range(32, 64):
            scene_idx = i - 32

            if scene_idx == self.current_scene:
                # Current scene: white
                color = (127, 127, 127)
            elif scene_idx < len(self.scenes) and self.scenes[scene_idx]:
                # Saved scene: bright blue
                color = (0, 127, 127)
            else:
                # Empty scene: dim blue
                color = (0, 40, 40)

            colors.append((i, *color))

        # Send colors to the grid
        self.fire.set_multiple_pad_colors(colors)

        # Update OLED display
        self.canvas.clear()
        self.canvas.draw_text("Mixer View", 5, 10)
        self.canvas.draw_text("Use Macros to adjust levels", 5, 25)
        self.canvas.draw_text("Shift+Macros for pan", 5, 40)

        self.fire.render_to_display()

    def draw_fx_view(self):
        """Draw the FX View grid."""
        colors = []

        # Upper 2 rows: Delay presets (16)
        for i in range(32):
            idx = i

            if idx < 16:
                if idx == self.delay_preset:
                    # Selected delay preset: bright
                    color = (127, 80, 0)  # Orange
                else:
                    # Other delay presets: dim
                    color = (50, 30, 0)
            else:
                color = (0, 0, 0)  # Off

            colors.append((i, *color))

            # Third row: Reverb presets (8)
            for i in range(32, 48):
                idx = i - 32

                if idx < 8:
                    if idx == self.reverb_preset:
                        # Selected reverb preset: bright
                        color = (127, 127, 80)  # Light yellow
                    else:
                        # Other reverb presets: dim
                        color = (50, 50, 30)
                else:
                    color = (0, 0, 0)  # Off

                colors.append((i, *color))

            # Fourth row: not used
            for i in range(48, 64):
                colors.append((i, 0, 0, 0))

            # Send colors to the grid
            self.fire.set_multiple_pad_colors(colors)

            # Update OLED display
            self.canvas.clear()
            self.canvas.draw_text("FX View", 5, 10)
            self.canvas.draw_text("Use Macros to adjust sends", 5, 25)

            # Display delay preset name
            delay_names = [
                "Slapback Fast",
                "Slapback Slow",
                "32nd Triplets",
                "32nd",
                "16th Triplets",
                "16th",
                "16th Ping Pong",
                "16th Ping Pong Swung",
                "8th Triplets",
                "8th Dotted",
                "8th",
                "8th Ping Pong",
                "8th Ping Pong Swung",
                "4th Triplets",
                "4th Dotted",
                "4th Triplets Wide",
            ]
            if 0 <= self.delay_preset < len(delay_names):
                self.canvas.draw_text(f"Delay: {delay_names[self.delay_preset]}", 5, 40)

            # Display reverb preset name
            reverb_names = [
                "Chamber",
                "Small Room",
                "Large Room",
                "Small Hall",
                "Large Hall",
                "Great Hall",
                "Hall - Long",
                "Hall - Large Long",
            ]
            if 0 <= self.reverb_preset < len(reverb_names):
                self.canvas.draw_text(
                    f"Reverb: {reverb_names[self.reverb_preset]}", 5, 55
                )

            self.fire.render_to_display()

        def draw_side_chain_view(self):
            """Draw the Side Chain View grid."""
            colors = []

            # First two rows: Synth side chain presets
            for i in range(32):
                row = i // 16
                col = i % 16

                if col < 8:
                    # Only first 8 columns used for side chain presets
                    preset_idx = col

                    if row == 0:
                        # First row: Synth 1 side chain
                        # Show currently selected preset
                        # This is placeholder logic - actual implementation would reference
                        # track-specific side chain settings
                        color = (127, 80, 0) if preset_idx == 0 else (50, 30, 0)
                    elif row == 1:
                        # Second row: Synth 2 side chain
                        color = (127, 80, 0) if preset_idx == 0 else (50, 30, 0)
                    else:
                        color = (0, 0, 0)  # Off
                else:
                    color = (0, 0, 0)  # Off

                colors.append((i, *color))

            # Fourth row: Side chain source
            for i in range(48, 64):
                col = i - 48

                if col < 4:
                    # First 4 columns: select drum source (Drums 1-4)
                    drum_idx = col

                    # This is placeholder logic - actual implementation would reference
                    # track-specific side chain settings
                    color = (127, 0, 0) if drum_idx == 0 else (50, 0, 0)
                else:
                    color = (0, 0, 0)  # Off

                colors.append((i, *color))

            # Third row: not used
            for i in range(32, 48):
                colors.append((i, 0, 0, 0))

            # Send colors to the grid
            self.fire.set_multiple_pad_colors(colors)

            # Update OLED display
            self.canvas.clear()
            self.canvas.draw_text("Side Chain View", 5, 10)
            self.canvas.draw_text("Top row: Synth 1 SC presets", 5, 25)
            self.canvas.draw_text("2nd row: Synth 2 SC presets", 5, 40)
            self.canvas.draw_text("Bottom row: SC source (Drums 1-4)", 5, 55)

            self.fire.render_to_display()

    def draw_note_view_display(self):
        """Update OLED display for Note View."""
        track = self.tracks[self.current_track_index]
        pattern = track.patterns[track.current_pattern]

        self.canvas.clear()

        # Show track name and pattern info
        self.canvas.draw_text(f"{track.name}", 5, 10)
        self.canvas.draw_text(
            f"Pattern {track.current_pattern + 1} ({pattern.length} steps)", 5, 25
        )

        # Show current scale for synth tracks
        if self.current_track_index < 4:  # Synth or MIDI tracks
            scale_names = [
                "Natural Minor",
                "Major",
                "Dorian",
                "Phrygian",
                "Mixolydian",
                "Melodic Minor",
                "Harmonic Minor",
                "Bebop Dorian",
                "Blues",
                "Minor Pentatonic",
                "Hungarian Minor",
                "Ukrainian Dorian",
                "Marva",
                "Todi",
                "Whole Tone",
                "Chromatic",
            ]

            root_names = [
                "C",
                "C#",
                "D",
                "D#",
                "E",
                "F",
                "F#",
                "G",
                "G#",
                "A",
                "A#",
                "B",
            ]
            root_name = root_names[self.root_note % 12]

            scale_name = scale_names[self.current_scale]
            self.canvas.draw_text(f"{root_name} {scale_name}", 5, 40)

        # Show tempo
        self.canvas.draw_text(f"Tempo: {self.tempo:.1f}", 5, 55)

        self.fire.render_to_display()

    def run(self):
        """Start the groovebox."""
        try:
            self.update_grid()
            self.update_leds()
            self.fire.start_gui()

            print("Circuit Tracks running...")
            print("Press Ctrl+C to exit")

            # Main loop - just keep the program running
            # The sequencer runs in its own thread
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            # Clean up
            self.all_notes_off()
            self.fire.clear_all()
            self.fire.close()

            # Close MIDI connections
            self.midi_in.close_port()
            self.midi_out.close_port()
            print("Circuit Tracks shut down.")


if __name__ == "__main__":
    circuit_tracks = CircuitTracks()
    circuit_tracks.run()
