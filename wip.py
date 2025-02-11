from canvas import Canvas


class MidiMonitorScreen:
    """Displays real-time MIDI activity with note/CC and velocity info."""

    def __init__(self):
        self.canvas = Canvas()
        self.midi_events = []  # Store recent MIDI events

    def add_midi_event(self, event_type, number, velocity):
        """Add new MIDI event to display."""
        self.midi_events.append({"type": event_type, "num": number, "vel": velocity})
        if len(self.midi_events) > 4:
            self.midi_events.pop(0)
        self.render()

    def render(self):
        """Render the MIDI monitor screen."""
        self.canvas.clear()

        # Header
        self.canvas.fill_rect(0, 0, self.canvas.WIDTH, 12, color=0)
        self.canvas.draw_text("MIDI IN", 2, 2, color=1)

        # Display MIDI events with velocity bars
        y_offset = 14
        for event in self.midi_events:
            label = f"{event['type']}: {event['num']}"
            self.canvas.draw_text(label, 2, y_offset)

            # Velocity bar visualization
            bar_length = int((self.canvas.WIDTH - 50) * (event['vel'] / 127))
            self.canvas.fill_rect(60, y_offset, bar_length, 8, color=0)
            y_offset += 12

        # # Bottom full-bleed status bar
        # self.canvas.fill_rect(0, self.canvas.HEIGHT - 6, self.canvas.WIDTH, 6, color=0)


class SettingsScreen:
    """Settings screen to adjust BPM and quantization per track."""

    def __init__(self):
        self.canvas = Canvas()
        self.bpm = 120
        self.quantization = "1/16"
        self.selected_index = 0  # 0: BPM, 1: Quantization

    def scroll(self, direction):
        """Scroll between settings."""
        self.selected_index = (self.selected_index + direction) % 2
        self.render()

    def adjust_value(self, delta):
        """Adjust the selected setting."""
        if self.selected_index == 0:
            self.bpm = max(40, min(300, self.bpm + delta))
        else:
            options = ["1/4", "1/8", "1/16", "1/32"]
            idx = options.index(self.quantization)
            self.quantization = options[(idx + delta) % len(options)]
        self.render()

    def render(self):
        """Render the settings screen."""
        self.canvas.clear()
        self.canvas.draw_text("SETTINGS", 2, 2)

        # BPM setting
        bpm_text = f"BPM: [{self.bpm}]" if self.selected_index == 0 else f"BPM: {self.bpm}"
        self.canvas.draw_text(bpm_text, 2, 20)

        # Quantization setting
        quant_text = f"Quant: [{self.quantization}]" if self.selected_index == 1 else f"Quant: {self.quantization}"
        self.canvas.draw_text(quant_text, 2, 30)


class TrackSetupScreen:
    """Screen for routing MIDI out to ports, channels, and toggling clock send."""

    def __init__(self):
        self.canvas = Canvas()
        self.options = [("Port", 1), ("Channel", 10), ("Clock", "On")]
        self.selected_index = 0

    def scroll(self, direction):
        """Scroll between routing options."""
        self.selected_index = (self.selected_index + direction) % len(self.options)
        self.render()

    def adjust_value(self, delta):
        """Adjust the selected routing option."""
        label, value = self.options[self.selected_index]

        if label == "Port":
            value = max(1, min(4, value + delta))
        elif label == "Channel":
            value = max(1, min(16, value + delta))
        elif label == "Clock":
            value = "Off" if value == "On" else "On"

        self.options[self.selected_index] = (label, value)
        self.render()

    def render(self):
        """Render the track setup screen."""
        self.canvas.clear()
        self.canvas.draw_text("TRACK SETUP", 2, 2)

        y_pos = 20
        for idx, (label, value) in enumerate(self.options):
            display_text = f"{label}: [{value}]" if idx == self.selected_index else f"{label}: {value}"
            self.canvas.draw_text(display_text, 2, y_pos)
            y_pos += 10


if __name__ == "__main__":
    from wip import MidiMonitorScreen
    from canvas import FireRenderer, BMPRenderer
    from akai_fire import AkaiFire

    # Initialize Akai Fire and Renderer
    fire = AkaiFire()
    fire_renderer = FireRenderer(fire)
    bmp_renderer = BMPRenderer()

    # Initialize the MIDI Monitor Screen
    midi_screen = MidiMonitorScreen()

    # Simulate adding MIDI events
    midi_screen.add_midi_event("Note", 60, 90)
    midi_screen.add_midi_event("CC", 74, 127)
    midi_screen.add_midi_event("Note", 64, 45)
    midi_screen.add_midi_event("Note", 67, 80)
    midi_screen.add_midi_event("CC", 1, 100)

    # Render the screen on the Akai Fire OLED
    fire_renderer.render_canvas(midi_screen.canvas)

    # Optionally, save the screen as a BMP for debugging
    bmp_renderer.render_canvas(midi_screen.canvas, "midi_monitor_screen.bmp")
    # from wip import SettingsScreen
    # from canvas import FireRenderer, BMPRenderer
    # from akai_fire import AkaiFire
    #
    # # Initialize Akai Fire and Renderer
    # fire = AkaiFire()
    # fire_renderer = FireRenderer(fire)
    # bmp_renderer = BMPRenderer()
    #
    # # Initialize the Settings Screen
    # settings_screen = SettingsScreen()
    #
    # # Simulate scrolling and adjusting values
    # settings_screen.scroll(1)  # Move selection to Quantization
    # settings_screen.adjust_value(1)  # Change Quantization to next value
    # settings_screen.scroll(-1)  # Move back to BPM
    # settings_screen.adjust_value(5)  # Increase BPM by 5
    #
    # # Render the screen on the Akai Fire OLED
    # fire_renderer.render_canvas(settings_screen.canvas)
    #
    # # Optionally, save the screen as a BMP for debugging
    # bmp_renderer.render_canvas(settings_screen.canvas, "settings_screen.bmp")
    #
    # from wip import TrackSetupScreen
    # from canvas import FireRenderer, BMPRenderer
    # from akai_fire import AkaiFire
    #
    # # Initialize Akai Fire and Renderer
    # fire = AkaiFire()
    # fire_renderer = FireRenderer(fire)
    # bmp_renderer = BMPRenderer()
    #
    # # Initialize the Track Setup Screen
    # track_setup_screen = TrackSetupScreen()
    #
    # # Simulate scrolling and adjusting routing options
    # track_setup_screen.scroll(1)  # Move to Channel option
    # track_setup_screen.adjust_value(2)  # Increase Channel by 2
    # track_setup_screen.scroll(1)  # Move to Clock option
    # track_setup_screen.adjust_value(1)  # Toggle Clock On/Off
    #
    # # Render the screen on the Akai Fire OLED
    # fire_renderer.render_canvas(track_setup_screen.canvas)
    #
    # # Optionally, save the screen as a BMP for debugging
    # bmp_renderer.render_canvas(track_setup_screen.canvas, "track_setup_screen.bmp")
