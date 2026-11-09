"""The tutorial app: one model, queued input, pads and a monochrome preview."""

from enum import Enum, auto
from pathlib import Path

from akai_fire.constants import (
    BUTTON_BROWSER,
    BUTTON_GRID_LEFT,
    BUTTON_GRID_RIGHT,
    BUTTON_NOTE,
    BUTTON_REC,
    BUTTON_SELECT,
    BUTTON_STOP,
    ROTARY_FILTER,
    ROTARY_PAN,
    ROTARY_RESONANCE,
    ROTARY_SELECT,
    ROTARY_VOLUME,
)
from akai_fire_framework import AkaiFireApp, EncoderMenu, MenuItem, ScreenMixin, on

from .model import BLACK, Picture


class View(Enum):
    DRAW = auto()
    SETTINGS = auto()


class PixelEditorApp(AkaiFireApp, ScreenMixin):
    APP_NAME = "Pixel Editor"

    def __init__(self, fire, *, path: Path = Path("pixel-art.json")):
        self.path = Path(path).expanduser()
        super().__init__(fire)

    def on_init(self):
        self.picture = Picture()
        self.view = View.DRAW
        self.unsaved = False
        self.notice = ""
        self.notice_left = 0.0
        self._dirty = True
        self.menu = EncoderMenu(
            [
                MenuItem("Color", adjust=self._adjust_color),
                MenuItem("Brightness", adjust=self._adjust_brightness),
                MenuItem("Save", activate=self._save),
                MenuItem("Load", activate=self._load),
                MenuItem("Back", activate=self._toggle_view),
                MenuItem("Quit", activate=self.quit),
            ]
        )

    @on.pad()
    def paint(self, event):
        if self.view == View.DRAW:
            self.picture.paint(event.pad, erase=event.shift)
            self.unsaved = True
            self._dirty = True

    @on.encoder((ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER))
    def mix_color(self, event):
        channel = (ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER).index(event.encoder)
        before = self.picture.brush_color
        self.picture.adjust_channel(channel, event.delta)
        self.unsaved |= self.picture.brush_color != before
        self._notify(self._rgb_label())

    @on.encoder(ROTARY_RESONANCE)
    def dim_picture(self, event):
        self._adjust_brightness(event.delta)
        self._notify(f"Brightness {self.picture.brightness}%")

    @on.encoder(ROTARY_SELECT)
    def turn_select(self, event):
        if self.view == View.SETTINGS:
            self.menu.turn(event.delta)
        else:
            self._adjust_color(event.delta)
        self._dirty = True

    @on.button(BUTTON_NOTE)
    def show_picture(self, event):
        self.menu.finish_editing()
        self.view = View.DRAW
        self._dirty = True

    @on.button(BUTTON_SELECT)
    def press_select(self, event):
        if self.view == View.SETTINGS:
            self.menu.press()
        else:
            self._toggle_view()
        self._dirty = True

    @on.button((BUTTON_GRID_LEFT, BUTTON_GRID_RIGHT))
    def navigate(self, event):
        delta = 1 if event.button == BUTTON_GRID_RIGHT else -1
        if self.view == View.SETTINGS:
            self.menu.move(delta, keep_editing=True)
        else:
            self._adjust_color(delta)
        self._dirty = True

    @on.button(BUTTON_STOP, shift=True)
    def clear_picture(self, event):
        self.picture.clear()
        self.unsaved = True
        self._notify("Picture cleared")

    def on_start(self):
        self.fire.clear_all()
        self._draw()

    def on_update(self, dt):
        if self.notice_left > 0:
            self.notice_left = max(0, self.notice_left - dt)
            if not self.notice_left:
                self.notice = ""
                self._dirty = True
        if self._dirty:
            self._draw()

    @on.button(BUTTON_BROWSER)
    def _toggle_view(self, event=None):
        self.menu.finish_editing()
        self.view = View.SETTINGS if self.view == View.DRAW else View.DRAW
        self._dirty = True

    def _adjust_color(self, delta):
        before = (self.picture.brush, self.picture.custom_color)
        self.picture.select_color(delta)
        self.unsaved |= (self.picture.brush, self.picture.custom_color) != before
        self.notice = ""
        self.notice_left = 0.0
        self._dirty = True

    def _adjust_brightness(self, delta):
        before = self.picture.brightness
        self.picture.brightness = max(10, min(100, before + 5 * delta))
        self.unsaved |= self.picture.brightness != before
        self._dirty = True

    def _rgb_label(self):
        red, green, blue = self.picture.brush_color
        return f"R{red} G{green} B{blue}"

    def _notify(self, message):
        self.notice = message
        self.notice_left = 2.0
        self._dirty = True

    @on.button(BUTTON_REC)
    def _save(self, event=None):
        try:
            self.picture.save(self.path)
        except OSError as exc:
            self._notify("Save failed")
            print(f"Cannot save {self.path}: {exc}")
        else:
            self.unsaved = False
            self._notify("Saved picture")

    def _load(self):
        try:
            picture = Picture.load(self.path)
        except (OSError, ValueError) as exc:
            self._notify("Load failed")
            print(f"Cannot load {self.path}: {exc}")
        else:
            # Replace the live model only after the entire file has validated.
            self.picture = picture
            self.unsaved = False
            self._notify("Loaded picture")

    def _draw(self):
        # One pad batch per changed frame, rather than a clear/repaint burst.
        sent = self.fire.set_multiple_pad_colors(self.picture.pad_colors())
        self._dirty = not sent
        self.fire.set_button_led(
            self.fire.BUTTON_NOTE,
            self.fire.DUAL_LED_BRIGHT_PRIMARY if self.view == View.DRAW else 0,
        )
        self.fire.set_button_led(
            self.fire.BUTTON_BROWSER, 2 if self.view == View.SETTINGS else 0
        )
        self.canvas.clear()
        if self.view == View.SETTINGS:
            self._draw_settings()
        else:
            count = sum(color != BLACK for color in self.picture.pixels)
            self.draw_header("PIXELS", f"{count}/64" + ("*" if self.unsaved else ""))
            for pad, color in enumerate(self.picture.pixels):
                row, column = divmod(pad, 16)
                x, y = 8 + column * 7, 20 + row * 7
                if color != BLACK:
                    self.canvas.fill_rect(x, y, 5, 5)
                else:
                    self.canvas.fill_rect(x + 2, y + 2, 1, 1)
            footer = self.notice or (
                f"{self._rgb_label()} {self.picture.brightness}%"
                if self.picture.custom_color is not None
                else f"{self.picture.brush_name} {self.picture.brightness}%"
            )
            self.canvas.draw_text_fitted(footer, 4, 51)

    def _draw_settings(self):
        values = [
            self.picture.brush_name,
            f"{self.picture.brightness}%",
            "",
            "",
            "",
            "",
        ]
        if self.menu.editing:
            index = self.menu.selected_index
            self.canvas.draw_page(
                f"Edit {self.menu.items[index].label}",
                [values[index], "SELECT: done", self.notice or "GRID: next value"],
            )
        else:
            labels = [
                f"{item.label} {value}".rstrip()
                for item, value in zip(self.menu.items, values)
            ]
            self.draw_menu(self.notice or "Settings", labels, self.menu.selected_index)
