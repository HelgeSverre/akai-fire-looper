import time
from enum import Enum

from akai_fire import AkaiFire


class PlayState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    RECORDING = "recording"


class RhythmDemo:
    def __init__(self):
        self.fire = AkaiFire()
        self.canvas = self.fire.get_canvas()

        # Sequencer state
        self.play_state = PlayState.STOPPED
        self.current_step = 0
        self.tempo = 120
        self.max_steps = 64
        self.current_page = 0  # 0 to 3 for 64 steps
        self.bank_leds = {
            0: self.fire.CONTROL_BANK_CHANNEL,  # Steps 1-16
            1: self.fire.CONTROL_BANK_MIXER,  # Steps 17-32
            2: self.fire.CONTROL_BANK_USER1,  # Steps 33-48
            3: self.fire.CONTROL_BANK_USER2,  # Steps 49-64
        }
        self.pattern_length = 8  # Current pattern length
        self.loop_mode = False  # Whether we're in loop mode
        self.loop_start = 0  # Start of loop region when in loop mode
        self.loop_length = 16  # New property for loop length

        # Track states (4 rows)
        self.tracks = [
            [False] * 64,  # Track 1 steps
            [False] * 64,  # Track 2 steps
            [False] * 64,  # Track 3 steps
            [False] * 64,  # Track 4 steps
        ]

        # Visual settings
        self.intensity = 64  # Default LED intensity
        self.color_schemes = [
            (127, 0, 0),  # Red
            (0, 127, 0),  # Green
            (0, 0, 127),  # Blue
            (127, 127, 0),  # Yellow
        ]

        self.setup_handlers()
        self.update_display()
        self.update_pads()

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
                    self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
                else:
                    self.play_state = PlayState.RECORDING
                    self.fire.set_button_led(
                        self.fire.BUTTON_REC, self.fire.LED_HIGH_RED
                    )
                self.update_display()

        # Tempo control with rotary
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_tempo(direction, velocity):
            if direction == "clockwise":
                self.tempo = min(300, self.tempo + velocity)
            else:
                self.tempo = max(60, self.tempo - velocity)
            self.update_display()

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

        # Pattern length control with select knob
        @self.fire.on_rotary_turn(self.fire.ROTARY_SELECT)
        def handle_pattern_length(direction, velocity):
            if self.loop_mode:
                # In loop mode, move the loop region
                if direction == "clockwise":
                    self.loop_start = min(
                        self.max_steps - self.loop_length, self.loop_start + 1
                    )
                else:
                    self.loop_start = max(0, self.loop_start - 1)
            else:
                # Normal mode, adjust pattern length
                if direction == "clockwise":
                    self.pattern_length = min(self.max_steps, self.pattern_length + 1)
                else:
                    self.pattern_length = max(1, self.pattern_length - 1)
            self.update_pads()
            self.update_display()

        # Pad input handler
        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            (col, row) = AkaiFire.pad_position(pad_index)
            absolute_col = col + (self.current_page * 16)
            self.tracks[row][absolute_col] = not self.tracks[row][absolute_col]
            self.update_pads()

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

        # Update loop mode handler
        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def handle_loop_mode(event):
            if event == "press":
                self.loop_mode = not self.loop_mode
                if self.loop_mode:
                    self.loop_start = 0
                    self.loop_length = self.pattern_length

                # Reset loop length to full pattern
                self.fire.set_button_led(
                    self.fire.BUTTON_BROWSER,
                    self.fire.LED_HIGH_GREEN if self.loop_mode else self.fire.LED_OFF,
                )
                # Light up grid buttons in loop mode
                grid_led = (
                    self.fire.LED_DULL_GREEN if self.loop_mode else self.fire.LED_OFF
                )
                self.fire.set_button_led(self.fire.BUTTON_GRID_LEFT, grid_led)
                self.fire.set_button_led(self.fire.BUTTON_GRID_RIGHT, grid_led)
                self.update_pads()
                self.update_display()

    @staticmethod
    def blend_colors(base_color, tint_color, tint_amount):
        """Blend two colors with a given amount"""
        r1, g1, b1 = base_color
        r2, g2, b2 = tint_color
        r = int(r1 * (1 - tint_amount) + r2 * tint_amount)
        g = int(g1 * (1 - tint_amount) + g2 * tint_amount)
        b = int(b1 * (1 - tint_amount) + b2 * tint_amount)
        return (r, g, b)

    def update_pads(self):
        """Update all pad colors based on current state"""
        loop_tint = (0, 0, 32)  # Slight blue tint for loop region
        edge_intensity = 5  # Dim light for pattern edge

        for row in range(4):
            for col in range(16):
                absolute_col = col + (self.current_page * 16)
                pad_index = row * 16 + col
                base_color = (0, 0, 0)  # Default off state

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

    def update_display(self):
        """Update OLED display"""
        self.canvas.clear()

        # Draw header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(f"BPM: {self.tempo}", 2, 2, color=1)

        # Draw playhead position
        beat = (self.current_step // 4) + 1
        tick = (self.current_step % 4) + 1
        self.canvas.draw_text(f"Beat {beat}.{tick}", 70, 2, color=1)

        # Draw play state and pattern info
        self.canvas.draw_text(f"State: {self.play_state.value}", 2, 15)

        # Draw pattern length and loop info
        if self.loop_mode:
            self.canvas.draw_text(
                f"Loop: {self.loop_start + 1} to {self.loop_start + self.loop_length}",
                2,
                28,
            )
        else:
            self.canvas.draw_text(f"Length: {self.pattern_length} steps", 2, 28)

        # Draw active steps count
        active_steps = sum(sum(1 for step in track if step) for track in self.tracks)
        self.canvas.draw_text(f"Active: {active_steps}", 2, 41)

        self.fire.render_to_display()

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

                        self.update_pads()
                        self.update_display()
                        last_step_time = current_time

                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.clear_all()
            self.fire.close()


if __name__ == "__main__":
    demo = RhythmDemo()
    demo.run()
