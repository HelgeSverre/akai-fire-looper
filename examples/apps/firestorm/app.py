"""Declarative input and two views of one particle world."""

from akai_fire.constants import (
    BUTTON_BROWSER,
    BUTTON_PLAY,
    BUTTON_REC,
    BUTTON_SELECT,
    BUTTON_STOP,
    ROTARY_FILTER,
    ROTARY_PAN,
    ROTARY_RESONANCE,
    ROTARY_SELECT,
    ROTARY_VOLUME,
)
from akai_fire_framework import AkaiFireApp, GridMixin, ScreenMixin, on

from .model import HEIGHT, SCENES, WIDTH, World


class FirestormApp(AkaiFireApp, GridMixin, ScreenMixin):
    APP_NAME = "Firestorm"

    def __init__(self, fire, *, sound=None, seed=None):
        self.sound = sound
        self.seed = seed
        super().__init__(fire)

    def on_init(self):
        self.world = World(self.seed)
        self.help = False
        self.notice = "TAP TO PLAY"
        self.notice_left = 4.0

    def on_start(self):
        self.fire.clear_all()
        for row, column in ((1, 3), (2, 8), (1, 13)):
            self.world.burst(row, column, manual=False)
        self._draw()

    def notify(self, text):
        self.notice, self.notice_left = text, 2.0

    @on.pad()
    def launch(self, event):
        row, column = self.pad_position(event.pad)
        if event.shift:
            self.world.attract(row, column)
            self.notify("SHIFT: attractors")
        else:
            self.world.burst(row, column)
            self.help = False
            if self.sound is not None:
                self.sound.play(row, column)

    @on.encoder(ROTARY_VOLUME)
    def energy(self, event):
        self.world.energy = max(0, min(100, self.world.energy + event.delta))
        self.notify(f"Energy {self.world.energy}")

    @on.encoder(ROTARY_PAN)
    def gravity(self, event):
        self.world.gravity = max(0, min(100, self.world.gravity + event.delta))
        self.notify(f"Gravity {self.world.gravity}")

    @on.encoder(ROTARY_FILTER)
    def trails(self, event):
        self.world.trails = max(0, min(100, self.world.trails + event.delta))
        self.notify(f"Trails {self.world.trails}")

    @on.encoder(ROTARY_RESONANCE)
    def color(self, event):
        self.world.color = (self.world.color + event.delta * 3) % 360
        self.notify(f"Color {self.world.color}")

    @on.encoder(ROTARY_SELECT)
    def scene(self, event):
        self.world.change_scene(event.delta)
        self.help = False
        self.notify("TAP TO PLAY")

    @on.button(BUTTON_SELECT)
    def next_scene(self, event):
        self.world.change_scene(1)
        self.help = False
        self.notify("TAP TO PLAY")

    @on.button(BUTTON_PLAY)
    def pause(self, event):
        self.world.paused = not self.world.paused
        if self.world.paused and self.sound is not None:
            self.sound.stop()
        self.notify("Paused" if self.world.paused else "Playing")

    @on.button(BUTTON_STOP)
    def clear(self, event):
        self.world.clear()
        self.world.paused = False
        if self.sound is not None:
            self.sound.stop()
        self.notify("Cleared: tap a pad")

    @on.button(BUTTON_REC)
    def autoplay(self, event):
        self.world.auto = not self.world.auto
        self.notify("Auto on" if self.world.auto else "Auto off")

    @on.button(BUTTON_BROWSER)
    def instructions(self, event):
        self.help = not self.help

    def on_update(self, dt):
        self.notice_left = max(0, self.notice_left - dt)
        self.world.update(dt)
        self._draw()

    def _draw(self):
        self.fire.set_multiple_pad_colors(self.world.pad_colors())
        self.fire.set_button_led(BUTTON_PLAY, 1 if self.world.paused else 3)
        self.fire.set_button_led(BUTTON_REC, 4 if self.world.auto else 0)
        self.fire.set_button_led(BUTTON_BROWSER, 2 if self.help else 0)
        self.canvas.clear()
        if self.help:
            self.canvas.draw_page(
                "FIRESTORM",
                ["VOL Energy PAN Grav", "FILTER Trail RES Hue", "SHIFT pad: attract"],
            )
            return
        status = "PAUSE" if self.world.paused else "AUTO" if self.world.auto else "LIVE"
        self.draw_header(SCENES[self.world.scene], status)
        # The 128×32 field occupies OLED rows 18–49; each pad owns an 8×8 tile.
        # A fixed ordered threshold gives trails texture without temporal flicker.
        threshold = ((0, 2), (3, 1))
        for i, value in enumerate(self.world.light):
            x, y = i % WIDTH, i // WIDTH
            if value > 0.12 + threshold[y % 2][x % 2] * 0.18:
                self.canvas.set_pixel(x, y + 18, 0)
        for x, y in self.world.attractors:
            self.canvas.draw_rect(x - 2, y + 16, 5, 5)
        footer = self.notice if self.notice_left else "PAD burst  SELECT scene"
        self.canvas.draw_text_fitted(footer, 4, HEIGHT + 19, width=120)

    def on_stop(self):
        if self.sound is not None:
            self.sound.stop()
