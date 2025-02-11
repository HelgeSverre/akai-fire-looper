from screen.text_renderer import TextStyle
from screen.ui_components import StatusBar, IconButton, TabBar


class ScreenTemplates:
    def __init__(self, display):
        """Initialize with a display implementing DisplayInterface"""
        self.display = display

    def show_main_screen(self, bpm=120.0, current_bar=1, playing=True):
        """Main looper screen with BPM, transport, and clip status"""
        self.display.clear()

        # Status bar at top
        status = StatusBar(self.display)
        status.items = [f"BPM:{bpm:.1f}", f"BAR:{current_bar:02d}"]
        status.draw(0)

        # Transport control
        transport = IconButton(
            self.display, 54, 20, ">" if playing else "[]", width=20, height=20
        )
        transport.draw(selected=playing)

        # Clip timeline
        self.display.draw_rect(10, 35, 108, 20, 1)
        self.display.draw_text("1  2  3  4", 12, 40)

        self.display.update()
        self.display.render("main.bmp")

    def show_recording_screen(
        self, clip_num=1, time="0:00", level=0.6, peak=0.8, progress=0.4
    ):
        """Recording screen with level meter and progress bar"""
        self.display.clear()

        # Top status
        rec_button = IconButton(self.display, 2, 2, "REC", width=30, height=10)
        rec_button.draw(selected=True)

        self.display.draw_text(f"CLIP {clip_num}", 40, 2)
        self.display.draw_text(time, 90, 2)

        # Level meter
        self.display.draw_level_meter(10, 20, 108, 8, level, peak=peak)

        # Recording progress bar
        self.display.draw_progress_bar(10, 35, 108, 10, progress)

        self.display.update()
        self.display.render("recording.bmp")

    def show_clip_info_screen(
        self, clip_num=1, length=4, quantize="1/16", mode="Loop", midi_ch="All"
    ):
        """Clip information and settings screen"""
        self.display.clear()

        # Header with tabs
        tab_bar = TabBar(self.display, 0)
        tab_bar.set_tabs(["INFO", "MIDI", "FX"])
        tab_bar.draw()

        # Clip header
        self.display.draw_text(f"CLIP {clip_num}", 2, 15, TextStyle(invert=True))

        # Settings
        settings = [
            f"Length: {length} bars",
            f"Quantize: {quantize}",
            f"Mode: {mode}",
            f"MIDI Ch: {midi_ch}",
        ]

        y = 25
        for setting in settings:
            self.display.draw_text(setting, 5, y)
            y += 10

        self.display.update()
        self.display.render("clip_info.bmp")

    def show_mixer_screen(self, tracks=4, track_levels=None):
        """Mixer view with multiple tracks"""
        self.display.clear()

        # Header
        status = StatusBar(self.display)
        status.items = ["MIXER"]
        status.draw(0)

        # Use provided track levels or generate defaults
        if track_levels is None:
            track_levels = [0.3 + (i * 0.2) for i in range(tracks)]

        # Track meters
        width = 10
        gap = 8
        x = 10
        for i in range(tracks):
            # Track number
            self.display.draw_text(str(i + 1), x, 12)

            # Level meter (vertical)
            level = track_levels[i]
            height = 35
            segments = 8
            segment_height = height // segments
            for seg in range(segments):
                y = 20 + (seg * (segment_height + 1))
                if level >= (seg / segments):
                    self.display.fill_rect(x, y, width, segment_height, 1)
                else:
                    self.display.draw_rect(x, y, width, segment_height, 1)

            x += width + gap

        self.display.update()
        self.display.render("mixer.bmp")
