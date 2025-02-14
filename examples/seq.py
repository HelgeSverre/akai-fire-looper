import time
from enum import Enum

import rtmidi

from akai_fire import AkaiFire


class PlayState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    RECORDING = "recording"


class ScreenMode(Enum):
    MAIN = "main"
    NOTES = "notes"
    MIDI_MONITOR = "midi_monitor"
    MIDI_SELECT_INPUT = "midi_select_input"
    MIDI_SELECT_OUTPUT = "midi_select_output"
    QUANTIZATION = "quantization_settings"


class MenuOption:
    def __init__(self, name, options, current_index=0):
        self.name = name
        self.options = options
        self.current_index = current_index

    def next_option(self):
        self.current_index = (self.current_index + 1) % len(self.options)

    def prev_option(self):
        self.current_index = (self.current_index - 1) % len(self.options)

    def get_current_option(self):
        return self.options[self.current_index]


class RhythmDemo:
    def __init__(self):

        self.fire = AkaiFire()
        self.canvas = self.fire.get_canvas()

        # Sequencer state
        self.play_state = PlayState.STOPPED
        self.current_step = 0
        self.tempo = 120
        self.max_steps = 64
        self.current_page = 0
        self.bank_leds = {
            0: self.fire.CONTROL_BANK_CHANNEL,
            1: self.fire.CONTROL_BANK_MIXER,
            2: self.fire.CONTROL_BANK_USER1,
            3: self.fire.CONTROL_BANK_USER2,
        }
        self.pattern_length = 16
        self.loop_mode = False
        self.loop_start = 0
        self.loop_length = 16

        # Track states
        self.tracks = [[False] * 64 for _ in range(4)]

        # Visual settings
        self.intensity = 64
        self.color_schemes = [
            (127, 0, 0),
            (0, 127, 0),
            (0, 0, 127),
            (127, 127, 0),
        ]

        # MIDI setup
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.midi_inputs = self.midi_in.get_ports()
        self.midi_outputs = self.midi_out.get_ports()

        self.midi_input_option = MenuOption("MIDI In", self.midi_inputs)
        self.midi_output_option = MenuOption("MIDI Out", self.midi_outputs)

        self.selected_midi_input = 0
        self.selected_midi_output = 0

        self.midi_monitor_messages = []
        self.max_monitor_messages = 20

        # Quantization settings
        self.quantization_option = MenuOption(
            "Quantization", ["Off", "1/4", "1/8", "1/16", "1/32"]
        )

        self.screen_mode = ScreenMode.MAIN
        self.last_note = None

        # MIDI Recording State
        self.recorded_notes = []  # Store (step, note, velocity, duration)
        self.is_recording_midi = False

        # Setup MIDI Input callback
        self.midi_in.set_callback(self.handle_midi_input)

        self.setup_handlers()
        self.update_display()
        self.update_pads()

    def handle_midi_input(self, message_data, _):
        message, _ = message_data
        status = message[0] & 0xF0
        note = message[1]
        velocity = message[2] if len(message) > 2 else 0

        if status == 0x90 and velocity > 0:  # Note On
            if self.is_recording_midi and self.play_state == PlayState.RECORDING:
                step = self.current_step % self.max_steps
                self.recorded_notes.append(
                    {"step": step, "note": note, "velocity": velocity, "duration": 0}
                )
                self.update_pads()

        elif status == 0x80 or (status == 0x90 and velocity == 0):  # Note Off
            for recorded_note in self.recorded_notes:
                if recorded_note["note"] == note and recorded_note["duration"] == 0:
                    recorded_note["duration"] = (
                        self.current_step - recorded_note["step"]
                    )

        # For MIDI Monitor Display
        if len(self.midi_monitor_messages) >= self.max_monitor_messages:
            self.midi_monitor_messages.pop(0)
        self.midi_monitor_messages.append(f"Note: {note}, Vel: {velocity}")

        self.update_display()

    def update_pads(self):
        """Update all pad colors based on current state"""
        loop_tint = (0, 0, 32)
        edge_intensity = 5

        for row in range(4):
            for col in range(16):
                absolute_col = col + (self.current_page * 16)
                pad_index = row * 16 + col
                base_color = (0, 0, 0)

                in_pattern = absolute_col < self.pattern_length
                is_pattern_edge = absolute_col == (self.pattern_length - 1)
                in_loop_region = self.loop_mode and self.loop_start <= absolute_col < (
                    self.loop_start + self.loop_length
                )
                is_loop_edge = self.loop_mode and absolute_col == (
                    self.loop_start + self.loop_length - 1
                )

                if absolute_col == self.current_step:
                    if self.tracks[row][absolute_col]:
                        base_color = self.color_schemes[row]
                    else:
                        # Inactive step at playhead
                        base_color = (
                            self.intensity // 2,
                            self.intensity // 2,
                            self.intensity // 2,
                        )
                elif self.tracks[row][absolute_col]:
                    r, g, b = self.color_schemes[row]
                    base_color = (
                        min(127, r * self.intensity // 127),
                        min(127, g * self.intensity // 127),
                        min(127, b * self.intensity // 127),
                    )
                elif is_pattern_edge or is_loop_edge:
                    base_color = (edge_intensity, edge_intensity, edge_intensity)

                # Apply recorded notes
                for recorded_note in self.recorded_notes:
                    if recorded_note["step"] == absolute_col:
                        intensity = min(127, recorded_note["velocity"])
                        base_color = (intensity, intensity, intensity)

                # Apply loop region tint if applicable
                final_color = (
                    self.blend_colors(base_color, loop_tint, 0.3)
                    if in_loop_region
                    else base_color
                )

                # Set final pad color
                if in_pattern or is_pattern_edge:
                    self.fire.set_pad_color(pad_index, *final_color)
                else:
                    self.fire.set_pad_color(pad_index, 0, 0, 0)

    @staticmethod
    def blend_colors(base_color, tint_color, tint_amount):
        """Blend two colors with a given amount"""
        r1, g1, b1 = base_color
        r2, g2, b2 = tint_color
        r = int(r1 * (1 - tint_amount) + r2 * tint_amount)
        g = int(g1 * (1 - tint_amount) + g2 * tint_amount)
        b = int(b1 * (1 - tint_amount) + b2 * tint_amount)
        return r, g, b

    def setup_handlers(self):
        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.play_state = PlayState.STOPPED
                self.current_page = 0
                self.current_step = 0
                self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_OFF)
                self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_OFF)
                self.update_pads()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.play_state == PlayState.STOPPED:
                    self.play_state = PlayState.PLAYING
                    self.fire.set_button_led(
                        self.fire.BUTTON_PLAY, self.fire.LED_DULL_YELLOW
                    )
                    self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_OFF)
                else:
                    self.play_state = PlayState.STOPPED
                    self.current_step = 0
                    self.current_page = 0
                    self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_OFF)
                    self.fire.set_button_led(
                        self.fire.BUTTON_STOP, self.fire.LED_HIGH_RED
                    )
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                if self.play_state == PlayState.RECORDING:
                    self.play_state = PlayState.STOPPED
                    self.is_recording_midi = False
                    self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
                else:
                    self.play_state = PlayState.RECORDING
                    self.is_recording_midi = True
                    self.recorded_notes.clear()  # Clear previous recording
                    self.fire.set_button_led(
                        self.fire.BUTTON_REC, self.fire.LED_HIGH_RED
                    )
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def clear_recording(event):
            if event == "press":
                self.recorded_notes.clear()
                self.update_pads()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                if self.screen_mode == ScreenMode.MAIN:
                    self.screen_mode = ScreenMode.MIDI_SELECT_INPUT
                elif self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                    self.screen_mode = ScreenMode.MIDI_SELECT_OUTPUT
                elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                    self.screen_mode = ScreenMode.QUANTIZATION
                elif self.screen_mode == ScreenMode.QUANTIZATION:
                    self.screen_mode = ScreenMode.MIDI_MONITOR
                elif self.screen_mode == ScreenMode.MIDI_MONITOR:
                    self.screen_mode = ScreenMode.MAIN
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_PATTERN)
        def handle_loop(event):
            if event == "press":
                self.loop_mode = not self.loop_mode
                if self.loop_mode:
                    self.loop_start = self.current_step
                    self.loop_length = 8
                    self.loop_mode = True
                else:
                    self.loop_mode = False

                self.update_pads()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_note_mode(event):
            if event == "press":
                print("Switching to notes mode")
                self.screen_mode = (
                    ScreenMode.NOTES
                    if self.screen_mode != ScreenMode.NOTES
                    else ScreenMode.MAIN
                )
                self.update_display()

        # Move playhead
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_bpm(direction, velocity):
            if direction == "clockwise":
                self.tempo = min(240, self.tempo + 1)
            else:
                self.tempo = max(1, self.tempo - 1)
            self.update_display()
            self.update_pads()

        # Move playhead
        @self.fire.on_rotary_turn(self.fire.ROTARY_FILTER)
        def handle_needle(direction, velocity):
            if direction == "clockwise":
                self.current_step = min(self.max_steps, self.current_step + 1)
            else:
                self.current_step = max(0, self.current_step - 1)
            self.update_display()
            self.update_pads()

        # Intensity control with pan
        @self.fire.on_rotary_turn(self.fire.ROTARY_PAN)
        def handle_intensity(direction, velocity):
            if direction == "clockwise":
                self.intensity = min(127, self.intensity + velocity)
            else:
                self.intensity = max(1, self.intensity - velocity)
            self.update_pads()

        @self.fire.on_rotary_turn(self.fire.ROTARY_SELECT)
        def handle_midi_selection(direction, velocity):
            if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                if direction == "clockwise":
                    self.midi_input_option.next_option()
                else:
                    self.midi_input_option.prev_option()
            elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                if direction == "clockwise":
                    self.midi_output_option.next_option()
                else:
                    self.midi_output_option.prev_option()
            elif self.screen_mode == ScreenMode.QUANTIZATION:
                if direction == "clockwise":
                    self.quantization_option.next_option()
                else:
                    self.quantization_option.prev_option()
            elif self.screen_mode == ScreenMode.MAIN:
                if direction == "clockwise":
                    self.pattern_length = min(64, self.pattern_length + 1)
                else:
                    self.pattern_length = max(1, self.pattern_length - 1)
            self.update_pads()
            self.update_display()

        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def confirm_selection(event):
            if event == "press":
                if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
                    self._change_midi_input(self.midi_input_option.current_index)
                    # TODO: SHOW success
                elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
                    self._change_midi_output(self.midi_output_option.current_index)
                    # TODO: SHOW success
                elif self.screen_mode == ScreenMode.QUANTIZATION:
                    self.screen_mode = ScreenMode.MAIN
                self.update_display()

        # Pad input handler
        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            if self.screen_mode is not ScreenMode.NOTES:
                (col, row) = AkaiFire.pad_position(pad_index)
                absolute_col = col + (self.current_page * 16)
                self.tracks[row][absolute_col] = not self.tracks[row][absolute_col]
                self.update_pads()

        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            if self.screen_mode == ScreenMode.NOTES:
                note = 36 + pad_index  # Mapping pad to MIDI note
                print(f"Note on: {note} - {velocity}")
                self.midi_out.send_message([0x90, note, velocity])  # Note on
                self.last_note = note
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def handle_note_off(event):
            if self.screen_mode == ScreenMode.NOTES and self.last_note:
                print(f"Note off: {self.last_note} - {event}")
                self.midi_out.send_message([0x80, self.last_note, 0])  # Note off
                self.last_note = None
                self.update_display()

        # Grid left/right buttons control loop length
        @self.fire.on_button(self.fire.BUTTON_GRID_LEFT)
        def handle_grid_left(event):
            if event == "press":
                if self.loop_mode:
                    # Existing loop length control
                    self.loop_length = max(1, self.loop_length - 1)
                else:
                    # Page control
                    self.current_page = max(0, self.current_page - 1)
                    self.fire.set_control_bank_leds(self.bank_leds[self.current_page])
            self.update_pads()
            self.update_display()

        @self.fire.on_button(self.fire.BUTTON_GRID_RIGHT)
        def handle_grid_right(event):
            if event == "press":
                if self.loop_mode:
                    self.loop_length = min(self.pattern_length, self.loop_length + 1)
                else:
                    self.current_page = min(3, self.current_page + 1)
                    self.fire.set_control_bank_leds(self.bank_leds[self.current_page])
                self.update_pads()
                self.update_display()

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

    def update_display(self):
        self.canvas.clear()
        if self.screen_mode == ScreenMode.MIDI_SELECT_INPUT:
            self._draw_menu_screen("MIDI Input", self.midi_input_option)
        elif self.screen_mode == ScreenMode.MIDI_SELECT_OUTPUT:
            self._draw_menu_screen("MIDI Output", self.midi_output_option)
        elif self.screen_mode == ScreenMode.QUANTIZATION:
            self._draw_menu_screen("Quantize", self.quantization_option)
        elif self.screen_mode == ScreenMode.MIDI_MONITOR:
            self._draw_midi_monitor_screen()
        elif self.screen_mode == ScreenMode.NOTES:
            self._draw_notes_display()
        else:
            self._draw_main_display()

        self.fire.render_to_display()

    def _draw_notes_display(self):
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("Notes Mode", 2, 2, color=1)
        if self.last_note:
            self.canvas.draw_text(
                f"Last Note: {self.last_note}",
                2,
                15,
            )

        else:
            self.canvas.draw_text(
                "Press a pad to play",
                2,
                15,
            )

    def _draw_midi_monitor_screen(self):
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("MIDI Monitor", 2, 1, color=1)

        y = 15
        for i, message in enumerate(self.midi_monitor_messages[-4:]):
            self.canvas.draw_text(message[:21], 2, y)
            y += 12

        if not self.midi_monitor_messages:
            self.canvas.draw_text("Waiting for MIDI...", 2, y)

    def _draw_main_display(self):
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(f"BPM: {self.tempo}", 2, 1, color=1)
        beat = (self.current_step // 4) + 1
        tick = (self.current_step % 4) + 1
        self.canvas.draw_text(f"Beat {beat}.{tick}", 70, 2, color=1)
        self.canvas.draw_text(f"State: {self.play_state.value}", 2, 15)
        if self.loop_mode:
            self.canvas.draw_text(
                f"Loop: {self.loop_start + 1} to {self.loop_start + self.loop_length}",
                2,
                28,
            )
        else:
            self.canvas.draw_text(f"Length: {self.pattern_length} steps", 2, 28)
        active_steps = sum(sum(1 for step in track if step) for track in self.tracks)
        self.canvas.draw_text(f"Active: {active_steps}", 2, 41)

    def _draw_menu_screen(self, title, menu_option):
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(title, 2, 1, color=1)

        y = 15
        visible_options = 4  # Number of options to display at once
        start_index = max(0, menu_option.current_index - visible_options // 2)
        end_index = min(len(menu_option.options), start_index + visible_options)

        if end_index - start_index < visible_options:
            start_index = max(0, end_index - visible_options)

        for i in range(start_index, end_index):
            option = menu_option.options[i]
            prefix = "> " if i == menu_option.current_index else "    "
            self.canvas.draw_text(f"{prefix}{option}", 2, y, color=0)
            y += 12

    def run(self):
        """Main loop"""
        try:
            self.fire.start_listening()
            last_step_time = time.time()

            while True:
                if self.play_state != PlayState.STOPPED:
                    current_time = time.time()
                    step_duration = 60.0 / (self.tempo * 4)

                    if current_time - last_step_time >= step_duration:
                        if self.loop_mode:
                            # In loop mode, stay within loop region
                            self.current_step += 1
                            if self.current_step >= (
                                self.loop_start + self.loop_length
                            ):
                                self.current_step = self.loop_start
                        else:
                            self.current_step = (
                                self.current_step + 1
                            ) % self.pattern_length

                        self.current_page = self.current_step // 16
                        self.fire.set_control_bank_leds(
                            self.bank_leds[self.current_page]
                        )

                        self.playback_recorded_notes()
                        self.update_pads()
                        self.update_display()
                        last_step_time = current_time

                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.clear_all()
            self.fire.close()

    def playback_recorded_notes(self):
        for recorded_note in self.recorded_notes:
            if recorded_note["step"] == self.current_step:
                self.midi_out.send_message(
                    [0x90, recorded_note["note"], recorded_note["velocity"]]
                )
            if (
                recorded_note["duration"] > 0
                and (recorded_note["step"] + recorded_note["duration"])
                % self.pattern_length
                == self.current_step
            ):
                self.midi_out.send_message([0x80, recorded_note["note"], 0])


if __name__ == "__main__":
    demo = RhythmDemo()
    demo.run()
