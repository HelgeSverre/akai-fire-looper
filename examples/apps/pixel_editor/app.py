"""The tutorial app: one model, queued input, pads and a monochrome preview."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Literal

from akai_fire_framework import AkaiFireApp, EncoderMenu, MenuItem, ScreenMixin

from .model import BLACK, Picture


class View(Enum):
    DRAW = auto()
    SETTINGS = auto()


@dataclass(frozen=True)
class Input:
    kind: Literal["pad", "button", "encoder"]
    control: int
    delta: int = 0
    shifted: bool = False


class PixelEditorApp(AkaiFireApp, ScreenMixin):
    APP_NAME = "Pixel Editor"

    def __init__(self, fire, *, path: Path = Path("pixel-art.json")):
        self.path = Path(path).expanduser()
        super().__init__(fire)

    def on_init(self):
        self.picture = Picture()
        self.view = View.DRAW
        self.inputs: SimpleQueue[Input] = SimpleQueue()
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

    def on_pad_press(self, pad, velocity):
        self.inputs.put(Input("pad", pad, shifted=self.fire.is_shift_pressed()))

    def on_button_press(self, button_id, event):
        if event == "press":
            self.inputs.put(
                Input("button", button_id, shifted=self.fire.is_shift_pressed())
            )

    def on_encoder_turn(self, encoder_id, direction, velocity):
        delta = velocity if direction == "clockwise" else -velocity
        self.inputs.put(Input("encoder", encoder_id, delta=delta))

    def on_start(self):
        self.fire.clear_all()
        self._draw()

    def on_update(self, dt):
        if self.notice_left > 0:
            self.notice_left = max(0, self.notice_left - dt)
            if not self.notice_left:
                self.notice = ""
                self._dirty = True
        # Bound work per frame so an input burst cannot starve drawing.
        for _ in range(64):
            try:
                event = self.inputs.get_nowait()
            except Empty:
                break
            self._apply(event)
        if self._dirty:
            self._draw()

    def _apply(self, event: Input):
        fire = self.fire
        if event.kind == "pad" and self.view == View.DRAW:
            self.picture.paint(event.control, erase=event.shifted)
            self.unsaved = True
        elif event.kind == "encoder":
            channels = (fire.ROTARY_VOLUME, fire.ROTARY_PAN, fire.ROTARY_FILTER)
            if event.control in channels:
                before = self.picture.brush_color
                self.picture.adjust_channel(channels.index(event.control), event.delta)
                self.unsaved |= self.picture.brush_color != before
                self._notify(self._rgb_label())
            elif event.control == fire.ROTARY_RESONANCE:
                self._adjust_brightness(event.delta)
                self._notify(f"Brightness {self.picture.brightness}%")
            elif event.control == fire.ROTARY_SELECT:
                if self.view == View.SETTINGS:
                    self.menu.turn(event.delta)
                else:
                    self._adjust_color(event.delta)
        elif event.kind == "button":
            if event.control == fire.BUTTON_BROWSER:
                self._toggle_view()
            elif event.control == fire.BUTTON_NOTE:
                self.menu.finish_editing()
                self.view = View.DRAW
            elif event.control == fire.BUTTON_SELECT:
                if self.view == View.SETTINGS:
                    self.menu.press()
                else:
                    self._toggle_view()
            elif event.control in (fire.BUTTON_GRID_LEFT, fire.BUTTON_GRID_RIGHT):
                delta = 1 if event.control == fire.BUTTON_GRID_RIGHT else -1
                if self.view == View.SETTINGS:
                    self.menu.move(delta, keep_editing=True)
                else:
                    self._adjust_color(delta)
            elif event.control == fire.BUTTON_REC:
                self._save()
            elif event.control == fire.BUTTON_STOP and event.shifted:
                self.picture.clear()
                self.unsaved = True
                self._notify("Picture cleared")
        self._dirty = True

    def _toggle_view(self):
        self.menu.finish_editing()
        self.view = View.SETTINGS if self.view == View.DRAW else View.DRAW

    def _adjust_color(self, delta):
        before = (self.picture.brush, self.picture.custom_color)
        self.picture.select_color(delta)
        self.unsaved |= (self.picture.brush, self.picture.custom_color) != before
        self.notice = ""
        self.notice_left = 0.0

    def _adjust_brightness(self, delta):
        before = self.picture.brightness
        self.picture.brightness = max(10, min(100, before + 5 * delta))
        self.unsaved |= self.picture.brightness != before

    def _rgb_label(self):
        red, green, blue = self.picture.brush_color
        return f"R{red} G{green} B{blue}"

    def _notify(self, message):
        self.notice = message
        self.notice_left = 2.0

    def _save(self):
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
