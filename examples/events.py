from enum import Enum
import time
from akai_fire import AkaiFire
from canvas import Canvas, FireRenderer


class DemoMode(Enum):
    PAD_COLORS = "pad_colors"
    MONITOR = "monitor"
    NOTES = "notes"


class FireDemo:
    def __init__(self):
        self.fire = AkaiFire()
        self.canvas = Canvas()
        self.renderer = FireRenderer(self.fire)

        self.mode = DemoMode.PAD_COLORS
        self.current_velocity = 64
        self.current_color = 0

        # Color palette for demo
        self.colors = [
            (127, 0, 0),  # Red
            (0, 127, 0),  # Green
            (0, 0, 127),  # Blue
            (127, 127, 0),  # Yellow
            (127, 0, 127),  # Purple
            (0, 127, 127),  # Cyan
        ]

        self.setup_handlers()
        self.draw_screen()

    def setup_handlers(self):
        # Mode switching
        @self.fire.on_button(self.fire.BUTTON_STEP)
        def handle_pad_mode():
            self.mode = DemoMode.PAD_COLORS
            self.fire.set_button_led(self.fire.BUTTON_STEP, self.fire.LED_HIGH_GREEN)
            self.fire.set_button_led(self.fire.BUTTON_NOTE, self.fire.LED_OFF)
            self.fire.set_button_led(self.fire.BUTTON_DRUM, self.fire.LED_OFF)
            self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_monitor_mode():
            self.mode = DemoMode.MONITOR
            self.fire.set_button_led(self.fire.BUTTON_STEP, self.fire.LED_OFF)
            self.fire.set_button_led(self.fire.BUTTON_NOTE, self.fire.LED_HIGH_GREEN)
            self.fire.set_button_led(self.fire.BUTTON_DRUM, self.fire.LED_OFF)
            self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_DRUM)
        def handle_notes_mode():
            self.mode = DemoMode.NOTES
            self.fire.set_button_led(self.fire.BUTTON_STEP, self.fire.LED_OFF)
            self.fire.set_button_led(self.fire.BUTTON_NOTE, self.fire.LED_OFF)
            self.fire.set_button_led(self.fire.BUTTON_DRUM, self.fire.LED_HIGH_GREEN)
            self.draw_screen()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play():
            self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
            self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_OFF)

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop():
            self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_OFF)
            self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_HIGH_RED)

        # Color selection with rotary
        @self.fire.on_rotary_turn(RotaryId.VOLUME)
        def handle_color_select(direction, velocity):
            if direction == "clockwise":
                self.current_color = (self.current_color + 1) % len(self.colors)
            else:
                self.current_color = (self.current_color - 1) % len(self.colors)
            self.draw_screen()

        # Velocity control
        @self.fire.on_rotary_turn(RotaryId.PAN)
        def handle_velocity(direction, velocity):
            if direction == "clockwise":
                self.current_velocity = min(127, self.current_velocity + velocity)
            else:
                self.current_velocity = max(1, self.current_velocity - velocity)
            self.draw_screen()

        # Pad handlers
        @self.fire.on_pad()
        def handle_pad(pad_index):
            if self.mode == DemoMode.PAD_COLORS:
                # Set pad to current color
                r, g, b = self.colors[self.current_color]
                self.fire.set_pad_color(pad_index, r, g, b)
            elif self.mode == DemoMode.NOTES:
                # Light up pad while pressed
                self.fire.set_pad_color(
                    pad_index, self.current_velocity, self.current_velocity // 2, 0
                )

        # Clear controls
        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_clear():
            if self.mode == DemoMode.PAD_COLORS:
                self.fire.clear_all_pads()
            elif self.mode == DemoMode.MONITOR:
                self.canvas.clear()
                self.draw_screen()

    def draw_screen(self):
        """Update the OLED display"""
        self.canvas.clear()

        # Draw header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text(f"Mode: {self.mode.value}", 2, 2, color=1)

        # Draw mode-specific info
        if self.mode == DemoMode.PAD_COLORS:
            color_name = ["Red", "Green", "Blue", "Yellow", "Purple", "Cyan"][
                self.current_color
            ]
            self.canvas.draw_text(f"Color: {color_name}", 2, 15)
            r, g, b = self.colors[self.current_color]
            self.canvas.draw_text(f"RGB: {r},{g},{b}", 2, 27)
        elif self.mode == DemoMode.MONITOR:
            self.canvas.draw_text("MIDI Monitor Mode", 2, 15)
            self.canvas.draw_text("Press pads/buttons", 2, 27)
            self.canvas.draw_text("to see MIDI data", 2, 39)
        elif self.mode == DemoMode.NOTES:
            self.canvas.draw_text(f"Velocity: {self.current_velocity}", 2, 15)
            self.canvas.draw_text("Press pads to play", 2, 27)

        self.renderer.render_canvas(self.canvas)

    def run(self):
        """Main loop"""
        try:
            self.fire.start_listening()

            # Initial setup
            self.fire.set_button_led(self.fire.BUTTON_STEP, self.fire.LED_HIGH_GREEN)
            self.draw_screen()

            print("Demo running! Press Ctrl+C to exit")
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
