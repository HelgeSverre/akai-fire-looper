import time
from enum import Enum
from akai_fire import AkaiFire


class DemoMode(Enum):
    PAINT = "paint"  # RGB painting with modifier keys
    PIANO = "piano"  # Piano mode with velocity
    STEPS = "steps"  # Step sequencer visualization
    MIXER = "mixer"  # Mixing board simulation


class FireDemo:
    def __init__(self):
        self.fire = AkaiFire()
        self.canvas = self.fire.get_canvas()

        self.mode = DemoMode.PAINT
        self.current_velocity = 64
        self.current_color = 0

        # State tracking
        self.active_steps = set()  # For step sequencer
        self.current_track = 0  # For mixer mode
        self.track_volumes = [64] * 4  # Mixer volumes
        self.track_colors = [
            (127, 0, 0),  # Track 1 - Red
            (0, 127, 0),  # Track 2 - Green
            (0, 0, 127),  # Track 3 - Blue
            (127, 127, 0),  # Track 4 - Yellow
        ]

        # Color palette for paint mode
        self.colors = [
            (127, 0, 0),  # Red
            (0, 127, 0),  # Green
            (0, 0, 127),  # Blue
            (127, 127, 0),  # Yellow
            (127, 0, 127),  # Purple
            (0, 127, 127),  # Cyan
            (127, 64, 0),  # Orange
            (64, 0, 127),  # Purple
        ]

        self.setup_handlers()
        self.draw_screen()

    def setup_handlers(self):
        # Mode switching with visual feedback
        @self.fire.on_button(self.fire.BUTTON_STEP)
        def handle_paint_mode(event):
            if event == "press":
                self.mode = DemoMode.PAINT
                self._update_mode_leds()
                self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_piano_mode(event):
            if event == "press":
                self.mode = DemoMode.PIANO
                self._update_mode_leds()
                self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_DRUM)
        def handle_steps_mode(event):
            if event == "press":
                self.mode = DemoMode.STEPS
                self._update_mode_leds()
                self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_PERFORM)
        def handle_mixer_mode(event):
            if event == "press":
                self.mode = DemoMode.MIXER
                self._update_mode_leds()
                self._update_mixer_display()
                self.draw_screen()

        # Paint mode: Color selection with modifier support
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_color_select(direction, velocity):
            if self.mode == DemoMode.PAINT:
                if direction == "clockwise":
                    self.current_color = (self.current_color + 1) % len(self.colors)
                else:
                    self.current_color = (self.current_color - 1) % len(self.colors)
                self.draw_screen()
            elif self.mode == DemoMode.MIXER:
                # In mixer mode, adjust current track volume
                if direction == "clockwise":
                    self.track_volumes[self.current_track] = min(
                        127, self.track_volumes[self.current_track] + velocity
                    )
                else:
                    self.track_volumes[self.current_track] = max(
                        0, self.track_volumes[self.current_track] - velocity
                    )
                self._update_mixer_display()

        @self.fire.on_solo()
        def handle_track_select(index, event):
            if self.mode == DemoMode.MIXER:
                if event == "press":
                    # Visual indicator that you pressed the track selection, but its not selected yet.
                    self.fire.set_track_led(index, self.fire.RECTANGLE_LED_DULL_RED)
                else:
                    # Released, so now we select the track for realz
                    self.current_track = index - 1
                    self._update_mixer_display()

        # Piano mode: Velocity control
        @self.fire.on_rotary_turn(self.fire.ROTARY_PAN)
        def handle_velocity(direction, velocity):
            if self.mode == DemoMode.PIANO:
                if direction == "clockwise":
                    self.current_velocity = min(127, self.current_velocity + velocity)
                else:
                    self.current_velocity = max(1, self.current_velocity - velocity)
                self.draw_screen()

        # Pad handlers with mode-specific behavior
        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            if self.mode == DemoMode.PAINT:
                r, g, b = self.colors[self.current_color]
                # Shift modifies brightness
                if self.fire.is_shift_pressed():
                    factor = 0.5
                    r, g, b = int(r * factor), int(g * factor), int(b * factor)
                # Alt adds white mix
                if self.fire.is_alt_pressed():
                    r, g, b = min(127, r + 64), min(127, g + 64), min(127, b + 64)
                self.fire.set_pad_color(pad_index, r, g, b)

            elif self.mode == DemoMode.PIANO:
                # Piano mode: velocity-sensitive with row colors
                row = pad_index // 16
                brightness = int((velocity / 127) * 127)
                if row == 0:
                    self.fire.set_pad_color(pad_index, brightness, 0, 0)
                elif row == 1:
                    self.fire.set_pad_color(pad_index, 0, brightness, 0)
                elif row == 2:
                    self.fire.set_pad_color(pad_index, 0, 0, brightness)
                else:
                    self.fire.set_pad_color(pad_index, brightness, brightness, 0)

            elif self.mode == DemoMode.STEPS:
                # Toggle step on/off with color based on row
                if pad_index in self.active_steps:
                    self.active_steps.remove(pad_index)
                    self.fire.set_pad_color(pad_index, 0, 0, 0)
                else:
                    self.active_steps.add(pad_index)
                    row = pad_index // 16
                    self.fire.set_pad_color(pad_index, *self.track_colors[row])

            elif self.mode == DemoMode.MIXER:
                # Select track in mixer mode
                row = pad_index // 16
                if row < 4:  # Only first 4 rows for tracks
                    self.current_track = row
                    self._update_mixer_display()

        # Clear functionality
        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_clear(event):
            if event == "press":
                self.active_steps.clear()
                self.fire.clear_all_pads()
                self.draw_screen()

    def _update_mode_leds(self):
        """Update mode selection button LEDs"""
        self.fire.set_button_led(
            self.fire.BUTTON_STEP,
            (
                self.fire.LED_HIGH_GREEN
                if self.mode == DemoMode.PAINT
                else self.fire.LED_OFF
            ),
        )
        self.fire.set_button_led(
            self.fire.BUTTON_NOTE,
            (
                self.fire.LED_HIGH_GREEN
                if self.mode == DemoMode.PIANO
                else self.fire.LED_OFF
            ),
        )
        self.fire.set_button_led(
            self.fire.BUTTON_DRUM,
            (
                self.fire.LED_HIGH_GREEN
                if self.mode == DemoMode.STEPS
                else self.fire.LED_OFF
            ),
        )
        self.fire.set_button_led(
            self.fire.BUTTON_PERFORM,
            (
                self.fire.LED_HIGH_GREEN
                if self.mode == DemoMode.MIXER
                else self.fire.LED_OFF
            ),
        )

    def _update_mixer_display(self):
        """Update mixer visualization"""
        # Update track LEDs
        for i in range(4):
            color = (
                self.fire.RECTANGLE_LED_HIGH_GREEN
                if i == self.current_track
                else self.fire.RECTANGLE_LED_DULL_GREEN
            )
            self.fire.set_track_led(i + 1, color)

        # Update pad visualization
        for i in range(4):
            volume = self.track_volumes[i]
            num_lit = int((volume / 127) * 16)  # Scale to 16 pads
            for j in range(16):
                pad_index = i * 16 + j
                if j < num_lit:
                    self.fire.set_pad_color(pad_index, *self.track_colors[i])
                else:
                    self.fire.set_pad_color(pad_index, 0, 0, 0)

        self.draw_screen()

    def draw_screen(self):
        """Update the OLED display"""
        self.canvas.clear()

        # Draw header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(f"Mode: {self.mode.value}", 2, 2, color=1)

        if self.mode == DemoMode.PAINT:
            # Show color info and modifier hints
            color_name = [
                "Red",
                "Green",
                "Blue",
                "Yellow",
                "Purple",
                "Cyan",
                "Orange",
                "Purple",
            ][self.current_color]
            r, g, b = self.colors[self.current_color]
            self.canvas.draw_text(f"Color: {color_name}", 2, 15)
            self.canvas.draw_text(f"RGB: {r},{g},{b}", 2, 27)
            self.canvas.draw_text("SHIFT: Dim   ALT: Lighten", 2, 39)

        elif self.mode == DemoMode.PIANO:
            self.canvas.draw_text(f"Velocity: {self.current_velocity}", 2, 15)
            self.canvas.draw_text("Rows = Different Tones", 2, 27)
            self.canvas.draw_text("Velocity = Brightness", 2, 39)

        elif self.mode == DemoMode.STEPS:
            self.canvas.draw_text(f"Active Steps: {len(self.active_steps)}", 2, 15)
            self.canvas.draw_text("Toggle steps per track", 2, 27)
            self.canvas.draw_text("Each row = different track", 2, 39)

        elif self.mode == DemoMode.MIXER:

            vol = self.track_volumes[self.current_track]
            self.canvas.draw_text(f"Track {self.current_track +1} Volume:", 2, 15)
            self.canvas.draw_text(f"{self.track_volumes[self.current_track]}", 2, 27)
            self.canvas.fill_rect(0, 40, self.canvas.WIDTH * (vol / 127), 4, color=1)

            self.canvas.draw_text("Select track & adjust vol", 2, 39)

        self.fire.render_to_display()

    def run(self):
        """Main loop"""
        try:
            self.fire.start_listening()
            self._update_mode_leds()
            self.draw_screen()

            print("Demo running! Press Ctrl+C to exit")
            print("Modes: STEP=Paint, NOTE=Piano, DRUM=Steps, PERFORM=Mixer")
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.clear_all()
            self.fire.close()


if __name__ == "__main__":
    demo = FireDemo()
    demo.run()
