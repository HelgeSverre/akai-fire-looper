import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from enum import Enum
import rtmidi
from akai_fire import AkaiFire
from canvas import Canvas, FireRenderer


class ScreenMode(Enum):
    MAIN = "main"
    MIDI_SELECT_INPUT = "midi_select_input"
    MIDI_SELECT_OUTPUT = "midi_select_output"
    MIDI_MONITOR = "midi_monitor"


class LoopState(Enum):
    EMPTY = "empty"
    ARMED = "armed"
    RECORDING = "recording"
    PLAYING = "playing"
    STOPPED = "stopped"


@dataclass
class Loop:
    midi_messages: List[Tuple[float, List[int]]]
    state: LoopState = LoopState.EMPTY
    start_time: Optional[float] = None
    length: float = 4.0  # Length in bars
    quantize: bool = True


class Track:
    def __init__(self, index: int):
        self.index = index
        self.loops: Dict[int, Loop] = {i: Loop(midi_messages=[]) for i in range(16)}
        self.is_muted = False
        self.is_soloed = False


# noinspection PyUnusedLocal
class MidiLooper:
    def __init__(self, bpm: float = 120.0):
        print("Initializing MIDI Looper...")
        self.bpm = bpm
        self._update_timing_params()

        # Initialize hardware
        self.fire = AkaiFire()
        self.canvas = Canvas()
        self.fire_renderer = FireRenderer(self.fire)

        # MIDI setup
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()

        self.midi_inputs = self.midi_in.get_ports()
        self.midi_outputs = self.midi_out.get_ports()

        self.selected_midi_input = 0
        self.selected_midi_input_channel = 0

        self.selected_midi_output = 0
        self.selected_midi_output_channel = 0

        self.midi_input_select_index = 0
        self.midi_output_select_index = 0

        self.midi_monitor_messages = []
        self.max_monitor_messages = 20

        # Tracks (4 tracks, 16 loops each)
        self.tracks = [Track(i) for i in range(4)]
        self.selected_track = 0
        self.active_clip = None  # (track, loop) of currently selected clip

        self.screen_mode = ScreenMode.MAIN

        # Global state
        self.global_start_time: Optional[float] = None
        self.is_playing = False
        self.is_recording = False
        self.record_armed_loop: Optional[Tuple[int, int]] = None  # (track, loop)
        self.current_bar = 0
        self.current_step = 0

        # Setup hardware and UI
        self._setup_midi()
        self._setup_controls()
        self._init_display()
        print("Initialization complete")

    def _setup_midi(self):
        """Setup MIDI connections."""
        print("Available MIDI inputs:", self.midi_inputs)
        print("Available MIDI outputs:", self.midi_out.get_ports())

        if self.midi_inputs:
            try:
                self.midi_in.open_port(self.selected_midi_input)
                print(f"Opened MIDI input: {self.midi_inputs[self.selected_midi_input]}")
            except Exception as e:
                print(f"Error opening MIDI input: {e}")
                raise

        # Try to find a MIDI output port
        try:
            output_ports = self.midi_out.get_ports()
            if output_ports:
                self.midi_out.open_port(0)  # Open first available output
                print(f"Opened MIDI output: {output_ports[0]}")
            else:
                print("No MIDI output ports available")
        except Exception as e:
            print(f"Error opening MIDI output: {e}")
            raise

    def _update_timing_params(self):
        """Update timing parameters based on BPM."""
        self.beats_per_bar = 4
        self.steps_per_beat = 4
        self.total_steps = self.beats_per_bar * self.steps_per_beat
        self.beat_duration = 60.0 / self.bpm
        self.bar_duration = self.beat_duration * self.beats_per_bar
        self.step_duration = self.beat_duration / self.steps_per_beat

    def _setup_controls(self):
        """Set up all hardware controls."""
        # Pad matrix (64 pads total)
        self.fire.add_listener(range(64), self._handle_pad)

        # Transport controls
        self.fire.add_button_listener(self.fire.BUTTON_PLAY, self._handle_play)
        self.fire.add_button_listener(self.fire.BUTTON_STOP, self._handle_stop)
        self.fire.add_button_listener(self.fire.BUTTON_REC, self._handle_rec)

        # Track controls
        for i in range(4):
            self.fire.add_button_listener(getattr(self.fire, f'BUTTON_SOLO_{i + 1}'),
                                          lambda btn, evt, track=i: self._handle_solo(track, evt))

        # Navigation
        self.fire.add_button_listener(self.fire.BUTTON_PATTERN, self._handle_pattern)
        self.fire.add_button_listener(self.fire.BUTTON_BROWSER, self._handle_browser)

        # Parameter controls
        self.fire.add_rotary_listener(self.fire.ROTARY_VOLUME, self._handle_bpm)
        self.fire.add_rotary_listener(self.fire.ROTARY_PAN, self._handle_loop_length)
        self.fire.add_rotary_listener(self.fire.ROTARY_SELECT, self._handle_rotary_select)

        # Mode buttons
        self.fire.add_button_listener(self.fire.BUTTON_STEP, self._handle_step_mode)
        self.fire.add_button_listener(self.fire.BUTTON_NOTE, self._handle_note_mode)
        self.fire.add_button_listener(self.fire.BUTTON_SELECT, self._handle_rotary_select_press)
        self.fire.add_button_listener(self.fire.BUTTON_BANK, self._handle_bank)

        # Add grid left/right button handlers
        self.fire.add_button_listener(self.fire.BUTTON_GRID_LEFT, self._handle_grid_left)
        self.fire.add_button_listener(self.fire.BUTTON_GRID_RIGHT, self._handle_grid_right)

    def _init_display(self):
        """Initialize the display state."""
        self.fire.clear_all_pads()
        self.fire.clear_all_button_leds()
        self.fire.clear_all_track_leds()
        self._update_display()

    def _handle_play(self, button_id: int, event: str):
        """Handle play button press."""
        if event == "press":
            if not self.is_playing:
                self._start_playback(time.time())
            else:
                self._stop_playback()

    def _handle_stop(self, button_id: int, event: str):
        """Handle stop button press."""
        if event == "press":
            self._stop_playback()
            self.current_bar = 0
            self.current_step = 0
            self._update_display()

    def _handle_rec(self, button_id: int, event: str):
        """Handle record button press."""
        if event == "press":
            if self.is_recording:
                if self.record_armed_loop:
                    self._stop_recording(*self.record_armed_loop)
            else:
                self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_HIGH_RED)

    def _handle_solo(self, track: int, event: str):
        """Handle track solo button press."""
        if event == "press":
            self.tracks[track].is_soloed = not self.tracks[track].is_soloed
            self._update_display()

    def _handle_pattern(self, button_id: int, event: str):
        """Handle pattern button press."""
        pass  # To be implemented

    def _handle_grid_left(self, button_id: int, event: str):
        """Handle grid left button for channel selection."""
        if event == "press":
            if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                self.selected_midi_input_channel = (self.selected_midi_input_channel - 1) % 16
            elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                self.selected_midi_output_channel = (self.selected_midi_output_channel - 1) % 16
            self._update_display()

    def _handle_grid_right(self, button_id: int, event: str):
        """Handle grid right button for channel selection."""
        if event == "press":
            if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                self.selected_midi_input_channel = (self.selected_midi_input_channel + 1) % 16
            elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                self.selected_midi_output_channel = (self.selected_midi_output_channel + 1) % 16
            self._update_display()

    def _change_midi_output(self, new_index: int):
        """Change the active MIDI output."""
        if new_index != self.selected_midi_output:
            try:
                # Close existing port
                if self.midi_out.is_port_open():
                    self.midi_out.close_port()

                # Open new port
                self.midi_out.open_port(new_index)
                self.selected_midi_output = new_index
                print(f"Switched to MIDI output: {self.midi_outputs[new_index]}")
            except Exception as e:
                print(f"Error changing MIDI output: {e}")

    def _change_midi_input(self, new_index: int):
        print(f"Changing MIDI input to: {self.midi_inputs[new_index]}")

        """Change the active MIDI input."""
        if new_index != self.selected_midi_input:
            try:
                # Close existing port
                if self.midi_in.is_port_open():
                    self.midi_in.close_port()

                # Open new port
                self.midi_in.open_port(new_index)
                self.selected_midi_input = new_index
                print(f"Switched to MIDI input: {self.midi_inputs[new_index]}")
            except Exception as e:
                print(f"Error changing MIDI input: {e}")

    def _handle_browser(self, button_id: int, event: str):
        """Cycle through main -> input select -> output select screens."""
        if event == "press":
            # Cycle through modes
            if self.screen_mode == ScreenMode.MAIN:
                self.screen_mode = ScreenMode.MIDI_SELECT_INPUT
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_HIGH_GREEN)
            elif self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                self.screen_mode = ScreenMode.MIDI_SELECT_OUTPUT
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_HIGH_RED)
            else:  # MIDI_OUTPUT_SELECT or any other mode
                self.screen_mode = ScreenMode.MAIN
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_OFF)

        self._update_display()

    def _handle_rotary_select_press(self, button_id: int, event: str):
        """Handle select button press to confirm MIDI port selection."""
        if event == "press":
            if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                self._change_midi_input(self.midi_input_select_index)
                # Switch back to main screen after selection
                self.screen_mode = ScreenMode.MAIN
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_OFF)
            elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                self._change_midi_output(self.midi_output_select_index)
                # Switch back to main screen after selection
                self.screen_mode = ScreenMode.MAIN
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_OFF)
            self._update_display()

    def _handle_rotary_select(self, encoder_id: int, direction: str, velocity: int):
        """Handle MIDI port selection scrolling."""
        if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
            if direction == "clockwise":
                self.midi_input_select_index = min(len(self.midi_inputs) - 1, self.midi_input_select_index + 1)
            else:
                self.midi_input_select_index = max(0, self.midi_input_select_index - 1)
            self._update_display()
        elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
            if direction == "clockwise":
                self.midi_output_select_index = min(len(self.midi_outputs) - 1, self.midi_output_select_index + 1)
            else:
                self.midi_output_select_index = max(0, self.midi_output_select_index - 1)
            self._update_display()

    def _handle_bank(self, button_id: int, event: str):
        """Toggle MIDI monitor view."""
        if event == "press":
            if self.screen_mode == ScreenMode.MIDI_MONITOR:
                self.screen_mode = ScreenMode.MAIN
                self.fire.set_button_led(self.fire.BUTTON_BANK, self.fire.LED_OFF)
            else:
                self.screen_mode = ScreenMode.MIDI_MONITOR
                self.fire.set_button_led(self.fire.BUTTON_BANK, self.fire.LED_HIGH_GREEN)
            self._update_display()

    def _decode_midi_for_display(self, message):
        """Convert MIDI message to readable format."""
        if not message:
            return "Empty message"

        status = message[0] & 0xF0
        channel = message[0] & 0x0F

        # TODO: Program change, sysex, etc.

        if status == 0x90 and message[2] > 0:  # Note On
            return f"Note {message[1]} On  vel:{message[2]}"
        elif status == 0x80 or (status == 0x90 and message[2] == 0):  # Note Off
            return f"Note {message[1]} Off"
        elif status == 0xB0:  # CC
            return f"CC {message[1]}  val:{message[2]}"
        elif status == 0xE0:  # Pitch Bend
            value = (message[2] << 7) + message[1]
            return f"Pitch {value}"

        else:
            return f"MIDI: {' '.join(hex(b)[2:].zfill(2) for b in message)}"

    def _handle_step_mode(self, button_id: int, event: str):
        """Handle step mode button press."""
        pass  # To be implemented

    def _handle_note_mode(self, button_id: int, event: str):
        """Handle note mode button press."""
        pass  # To be implemented

    def _handle_bpm(self, encoder_id: int, direction: str, velocity: int):
        """Handle BPM changes from volume encoder."""
        if direction == "counterclockwise":
            diff = -1.0 * velocity
        else:
            diff = 1.0 * velocity

        self.bpm = max(30.0, min(300.0, self.bpm + diff))
        self._update_timing_params()
        self._update_display()

    def _handle_loop_length(self, encoder_id: int, direction: str, velocity: int):
        """Handle loop length changes from pan encoder."""
        if self.record_armed_loop:
            track, loop = self.record_armed_loop
            loop_obj = self.tracks[track].loops[loop]

            if direction == "counterclockwise":
                diff = -1.0 * velocity
            else:
                diff = 1.0 * velocity

            loop_obj.length = max(1.0, min(16.0, loop_obj.length + diff))
            self._update_display()

    def _handle_pad(self, pad_index: int):
        """Handle pad press for loop triggering/recording."""
        track = pad_index // 16
        loop = pad_index % 16
        self.active_clip = (track, loop)

        current_time = time.time()

        if self.is_recording and self.record_armed_loop == (track, loop):
            self._stop_recording(track, loop)
        else:
            loop_obj = self.tracks[track].loops[loop]

            if loop_obj.state == LoopState.EMPTY:
                # Arm empty loop for recording
                self.record_armed_loop = (track, loop)
                loop_obj.state = LoopState.ARMED
                if not self.is_playing:
                    self._start_playback(current_time)
            else:
                # Toggle existing loop
                if loop_obj.state == LoopState.PLAYING:
                    loop_obj.state = LoopState.STOPPED
                else:
                    loop_obj.state = LoopState.PLAYING
                    if not self.is_playing:
                        self._start_playback(current_time)

        self._update_display()

    def _start_playback(self, start_time: float):
        """Start global playback."""
        self.is_playing = True
        self.global_start_time = start_time
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
        self._update_display()

    def _stop_playback(self):
        """Stop global playback."""
        self.is_playing = False
        self.global_start_time = None
        self._all_notes_off()
        self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_OFF)
        self._update_display()

    def _stop_recording(self, track: int, loop: int):
        """Stop recording the current loop."""
        if not self.is_recording:
            return

        loop_obj = self.tracks[track].loops[loop]

        if not loop_obj.midi_messages:
            # No MIDI recorded, reset to empty
            loop_obj.state = LoopState.EMPTY
        else:
            loop_obj.state = LoopState.PLAYING

            # Quantize recorded MIDI if enabled
            if loop_obj.quantize:
                quantized_messages = []
                for timestamp, message in loop_obj.midi_messages:
                    # Quantize to nearest step
                    step = round(timestamp / self.step_duration)
                    quantized_time = step * self.step_duration
                    if quantized_time < loop_obj.length * self.bar_duration:
                        quantized_messages.append((quantized_time, message))
                loop_obj.midi_messages = sorted(quantized_messages)

        self.is_recording = False
        self.record_armed_loop = None
        self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
        self._update_display()

    def _all_notes_off(self):
        """Send note off messages for all notes on all channels."""
        for channel in range(16):
            for note in range(128):
                self.midi_out.send_message([0x80 | channel, note, 0])

    def _process_midi(self):
        """Process MIDI input/output and timing."""
        current_time = time.time()

        if self.is_playing:
            elapsed = current_time - self.global_start_time
            new_step = int((elapsed % self.bar_duration) / self.step_duration)
            new_bar = int(elapsed / self.bar_duration)

            # Handle step change
            if new_step != self.current_step:
                self.current_step = new_step
                if new_step == 0:
                    self.current_bar = new_bar
                    self._handle_bar_start()
                self._update_display()

            # Process recording
            if self.is_recording:
                message = self.midi_in.get_message()
                if message:
                    midi_data, delta = message
                    # Only record if message is on the selected input channel
                    if (midi_data[0] & 0x0F) == self.selected_midi_input_channel:
                        track, loop = self.record_armed_loop
                        loop_obj = self.tracks[track].loops[loop]
                        timestamp = elapsed % (loop_obj.length * self.bar_duration)
                        loop_obj.midi_messages.append((timestamp, midi_data))

            # Process playback
            self._process_loop_playback(current_time)

        # Always process incoming MIDI even when not recording
        # This allows monitoring the input
        while message := self.midi_in.get_message():
            midi_data, delta = message

            # Add to monitor if in monitor mode
            if self.screen_mode == ScreenMode.MIDI_MONITOR:
                decoded = self._decode_midi_for_display(midi_data)
                self.midi_monitor_messages.insert(0, decoded)
                if len(self.midi_monitor_messages) > self.max_monitor_messages:
                    self.midi_monitor_messages.pop()
                self._update_display()

            # Only process if message is on the selected input channel
            if (midi_data[0] & 0x0F) == self.selected_midi_input_channel:
                if self.is_recording and self.record_armed_loop:
                    track, loop = self.record_armed_loop
                    loop_obj = self.tracks[track].loops[loop]
                    timestamp = current_time - self.global_start_time
                    timestamp = timestamp % (loop_obj.length * self.bar_duration)
                    loop_obj.midi_messages.append((timestamp, midi_data))
                else:
                    # Redirect to selected output channel
                    status = midi_data[0] & 0xF0
                    new_message = [status | self.selected_midi_output_channel] + list(midi_data[1:])
                    self.midi_out.send_message(new_message)

    def _process_loop_playback(self, current_time: float):
        """Handle playback of all active loops."""
        if not self.is_playing:
            return

        elapsed = current_time - self.global_start_time

        for track in self.tracks:
            if track.is_muted or (any(t.is_soloed for t in self.tracks) and not track.is_soloed):
                continue

            for loop in track.loops.values():
                if loop.state == LoopState.PLAYING:
                    loop_position = elapsed % (loop.length * self.bar_duration)

                    # Find messages to play in this frame
                    messages_to_play = [
                        msg for time, msg in loop.midi_messages
                        if abs(time - loop_position) < 0.001  # 1ms window
                    ]

                    for message in messages_to_play:
                        # Redirect to selected output channel
                        status = message[0] & 0xF0
                        new_message = [status | self.selected_midi_output_channel] + list(message[1:])
                        self.midi_out.send_message(new_message)

    def _handle_bar_start(self):
        """Handle actions that occur at the start of each bar."""
        # Start recording if armed
        if self.record_armed_loop and not self.is_recording:
            track, loop = self.record_armed_loop
            loop_obj = self.tracks[track].loops[loop]
            if loop_obj.state == LoopState.ARMED:
                loop_obj.state = LoopState.RECORDING
                self.is_recording = True
                self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_HIGH_RED)

    def _update_display(self):
        """Update the display and LEDs."""
        self.canvas.clear()

        if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
            self._draw_midi_input_select_screen()
        elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
            self._draw_midi_output_select_screen()
        elif self.screen_mode == ScreenMode.MIDI_MONITOR:
            self._draw_midi_monitor_screen()
        else:
            self._draw_main_screen()

        self.fire_renderer.render_canvas(self.canvas)

    def _draw_midi_monitor_screen(self):
        """Draw the MIDI monitor screen."""
        # Header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("MIDI Monitor", 2, 2, color=1)

        # Show MIDI messages
        y = 15
        for i, message in enumerate(self.midi_monitor_messages[:4]):  # Show last 4 messages
            self.canvas.draw_text(message[:21], 2, y)  # Truncate to fit screen
            y += 12

        if not self.midi_monitor_messages:
            self.canvas.draw_text("Waiting for MIDI...", 2, y)

    def _draw_midi_input_select_screen(self):
        """Draw the MIDI input selection screen with channel."""
        # Header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("MIDI In (1/2)", 2, 2, color=1)

        # Show channel
        channel_text = f"Channel: {self.selected_midi_input_channel + 1}"
        self.canvas.draw_text(channel_text, 80, 2, color=1)

        # Show current and adjacent inputs with channel prefix
        y = 15
        for i in range(max(0, self.midi_input_select_index - 1),
                       min(len(self.midi_inputs), self.midi_input_select_index + 3)):
            prefix = ">" if i == self.midi_input_select_index else " "
            port_name = self.midi_inputs[i][:16]  # Truncate port name to leave room for channel
            if i == self.selected_midi_input:
                text = f"{prefix} ch{self.selected_midi_input_channel + 1} - {port_name}"
                self.canvas.fill_rect(0, y, self.canvas.WIDTH, 10, color=0)
                self.canvas.draw_text(text, 2, y, color=1)
            else:
                text = f"{prefix} {port_name}"
                self.canvas.draw_text(text, 2, y)
            y += 12

    def _draw_midi_output_select_screen(self):
        """Draw the MIDI output selection screen with channel."""
        # Header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("MIDI Out (2/2)", 2, 2, color=1)

        # Show channel
        channel_text = f"Ch: {self.selected_midi_output_channel + 1}"
        self.canvas.draw_text(channel_text, 80, 2, color=1)

        # Show current and adjacent outputs with channel prefix
        y = 15
        for i in range(max(0, self.midi_output_select_index - 1),
                       min(len(self.midi_outputs), self.midi_output_select_index + 3)):
            prefix = ">" if i == self.midi_output_select_index else " "
            port_name = self.midi_outputs[i][:16]  # Truncate port name to leave room for channel
            if i == self.selected_midi_output:
                text = f"{prefix} ch{self.selected_midi_output_channel + 1} - {port_name}"
                self.canvas.fill_rect(0, y, self.canvas.WIDTH, 10, color=0)
                self.canvas.draw_text(text, 2, y, color=1)
            else:
                text = f"{prefix} {port_name}"
                self.canvas.draw_text(text, 2, y)
            y += 12

    def _draw_main_screen(self):
        """Draw the main looper screen."""
        # Header with BPM and transport
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(f"BPM: {self.bpm:.1f}", 2, 2, color=1)

        # Draw transport status
        status = "REC" if self.is_recording else "PLAY" if self.is_playing else "STOP"
        self.canvas.draw_text(f"Bar: {self.current_bar + 1}  {status}", 64, 2, color=1)

        # Current state info
        y = 15
        if self.record_armed_loop:
            track, loop = self.record_armed_loop
            loop_obj = self.tracks[track].loops[loop]
            state_text = f"Track {track + 1} Loop {loop + 1}: {loop_obj.state.value.upper()}"
            length_text = f"Length: {loop_obj.length} bars"
            self.canvas.draw_text(state_text, 2, y)
            self.canvas.draw_text(length_text, 2, y + 12)
        elif self.active_clip:
            track, loop = self.active_clip
            loop_obj = self.tracks[track].loops[loop]
            state_text = f"Track {track + 1} Loop {loop + 1}: {loop_obj.state.value.upper()}"
            if loop_obj.state != LoopState.EMPTY:
                length_text = f"Length: {loop_obj.length} bars"
                self.canvas.draw_text(state_text, 2, y)
                self.canvas.draw_text(length_text, 2, y + 12)

        # Input info
        input_text = f"Input: {self.midi_inputs[self.selected_midi_input][:20]}"
        self.canvas.draw_text(input_text, 2, 50)

        # Update pad colors (existing code)
        colors = []
        for track_idx, track in enumerate(self.tracks):
            for loop_idx, loop_obj in track.loops.items():
                pad_idx = track_idx * 16 + loop_idx

                if loop_obj.state == LoopState.EMPTY:
                    color = (10, 10, 10)  # Dim white
                elif loop_obj.state == LoopState.ARMED:
                    color = (64, 0, 0)  # Medium red
                elif loop_obj.state == LoopState.RECORDING:
                    color = (127, 0, 0)  # Bright red
                elif loop_obj.state == LoopState.PLAYING:
                    color = (0, 127, 0)  # Bright green
                else:  # STOPPED
                    color = (0, 0, 127)  # Blue

                colors.append((pad_idx, *color))

        self.fire.set_multiple_pad_colors(colors)

        # Update track status LEDs
        for i, track in enumerate(self.tracks):
            if track.is_soloed:
                self.fire.set_track_led(i + 1, self.fire.RECTANGLE_LED_HIGH_GREEN)
            elif track.is_muted:
                self.fire.set_track_led(i + 1, self.fire.RECTANGLE_LED_HIGH_RED)
            else:
                self.fire.set_track_led(i + 1, self.fire.RECTANGLE_LED_OFF)

        # Display step indicators on bottom row
        if self.is_playing:
            step_colors = []
            for step in range(16):
                pad_idx = 48 + step  # Use bottom row for step display
                if step == self.current_step:
                    color = (127, 127, 0)  # Bright yellow for current step
                elif step % 4 == 0:
                    color = (64, 64, 64)  # Medium gray for beat markers
                else:
                    color = (20, 20, 20)  # Dim gray for other steps
                step_colors.append((pad_idx, *color))
            self.fire.set_multiple_pad_colors(step_colors)

        # Render canvas to OLED display
        self.fire_renderer.render_canvas(self.canvas)

    def _cleanup(self):
        """Clean up all resources."""
        print("Cleaning up...")
        try:
            # Stop all playback and recording
            self._stop_playback()
            if self.is_recording:
                if self.record_armed_loop:
                    self._stop_recording(*self.record_armed_loop)

            # Turn off all notes
            self._all_notes_off()

            # Clear all visual feedback
            self.fire.clear_all_pads()
            self.fire.clear_all_button_leds()
            self.fire.clear_all_track_leds()
            self.canvas.clear()
            self.fire_renderer.render_canvas(self.canvas)

            # Close MIDI ports
            if self.midi_in.is_port_open():
                self.midi_in.close_port()
            if self.midi_out.is_port_open():
                self.midi_out.close_port()

            # Close Fire controller
            self.fire.close()

        except Exception as e:
            print(f"Error during cleanup: {e}")

        print("Cleanup complete")

    def run(self):
        """Main loop."""
        print("Starting MIDI Looper...")
        try:
            while True:
                self._process_midi()
                time.sleep(0.001)  # 1ms loop interval
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self._cleanup()


if __name__ == "__main__":
    looper = MidiLooper(bpm=120)
    looper.run()
