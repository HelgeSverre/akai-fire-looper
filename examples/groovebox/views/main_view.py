from examples.groovebox.app import MainApp
from examples.groovebox.core.view import View


class MainView(View):
    def __init__(self, app: "MainApp"):
        super().__init__(app)
        self.selected_track = -1
        self.selected_clip = -1

    def activate(self):
        super().activate()
        self.update_display()
        self.update_pads()

    def deactivate(self):
        super().deactivate()

    def update_display(self):
        screen = self.app.screen
        screen.clear()

        # Draw header
        screen.draw_header(f"BPM: {self.app.settings.tempo:.1f}")

        # Draw track info
        if self.selected_track >= 0:
            screen.draw_param("Track", self.selected_track + 1, 20)
            screen.draw_param("Clip", self.selected_clip + 1, 32)

        # Draw transport info
        screen.draw_param("Bar", f"{self.app.current_bar + 1}", 44)

        self.app.hardware.render_display()

    def update_pads(self):
        colors = []
        for track in range(4):
            for clip in range(16):
                pad_idx = track * 16 + clip
                color = self._get_clip_color(track, clip)
                colors.append((pad_idx, *color))

        self.app.hardware.set_pad_colors(colors)

    def _get_clip_color(self, track: int, clip: int) -> tuple[int, int, int]:
        # Implementation
        return (20, 20, 20)  # Default dim color

    def handle_pad(self, pad: int, velocity: int):
        track = pad // 16
        clip = pad % 16

        if self.app.shift_held:
            self._handle_shift_pad(track, clip)
        elif self.app.alt_held:
            self._handle_alt_pad(track, clip)
        else:
            self._handle_normal_pad(track, clip)

        self.update_display()
        self.update_pads()
