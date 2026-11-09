#!/usr/bin/env python3
"""
Modal app example using AkaiFireApp framework with mixins.

Demonstrates:
- Multiple modes (Main, Settings)
- Mode switching via buttons
- Screen helpers
- Grid utilities
- Transport controls

Usage:
    uv run python -m examples.apps.modal_demo
"""

from enum import Enum, auto

from akai_fire.device import AkaiFireDevice
from akai_fire_framework import (
    AkaiFireApp,
    GridMixin,
    ModeHandler,
    ModeManagerMixin,
    ScreenMixin,
    TransportMixin,
    on,
)


class Mode(Enum):
    """App modes."""

    MAIN = auto()
    SETTINGS = auto()


class MainMode(ModeHandler):
    """Main mode - pad colors and playback."""

    def __init__(self, app):
        self.app = app

    def handle_pad_press(self, pad, velocity):
        row, col = self.app.pad_position(pad)

        if row == self.app.ROW_STEP:
            # Toggle step color
            color = self.app.color_by_name("green" if velocity > 64 else "blue")
            self.app.set_pad(pad, color)
        elif row == self.app.ROW_TRACK:
            # Select track
            if col < 4:
                self.app.selected_track = col
                self.app.show_track_selection(col)

        return True

    def handle_encoder_turn(self, encoder, direction, velocity):
        if encoder == "volume":
            delta = velocity if direction == "clockwise" else -velocity
            self.app.bpm = max(30, min(300, self.app.bpm + delta))

    def handle_button_press(self, button):
        return False

    def get_display_info(self):
        return {
            "mode": "MAIN",
            "bpm": self.app.bpm,
            "track": self.app.selected_track + 1,
        }

    def on_enter(self, previous_mode):
        print("Entered MAIN mode")
        self.app.fill_row(self.app.ROW_STEP, self.app.COLORS["off"])
        self.app.show_track_selection(self.app.selected_track)


class SettingsMode(ModeHandler):
    """Settings mode - configuration menu."""

    MENU_ITEMS = ["BPM", "Swing", "Scale", "Root Note", "Back"]

    def __init__(self, app):
        self.app = app
        self.selected_item = 0

    def handle_pad_press(self, pad, velocity):
        return False

    def handle_encoder_turn(self, encoder, direction, velocity):
        if encoder == "select":
            if direction == "clockwise":
                self.selected_item = (self.selected_item + 1) % len(self.MENU_ITEMS)
            else:
                self.selected_item = (self.selected_item - 1) % len(self.MENU_ITEMS)

    def handle_button_press(self, button):
        return False

    def get_display_info(self):
        return {
            "mode": "SETTINGS",
            "selected": self.selected_item,
            "items": self.MENU_ITEMS,
        }

    def on_enter(self, previous_mode):
        print("Entered SETTINGS mode")
        self.app.clear_grid()


class ModalDemoApp(
    AkaiFireApp, ModeManagerMixin, ScreenMixin, GridMixin, TransportMixin
):
    """Demo app with modes, screen, grid, and transport."""

    APP_NAME = "Modal Demo"
    VERSION = "1.0"

    # Button to mode mapping
    MODE_BUTTONS = {
        Mode.MAIN: AkaiFireDevice.BUTTON_NOTE,
        Mode.SETTINGS: AkaiFireDevice.BUTTON_BROWSER,
    }

    def on_init(self):
        """Initialize app state and modes."""
        # App state
        self.bpm = 120
        self.selected_track = 0

        # Initialize mixins
        self.init_mode_manager(Mode, Mode.MAIN)
        self.init_transport()

        # Register modes
        self.register_mode(Mode.MAIN, MainMode(self))
        self.register_mode(Mode.SETTINGS, SettingsMode(self))

        # Start in main mode
        self.set_mode(Mode.MAIN)

    @on.button(AkaiFireDevice.BUTTON_PLAY)
    def play_button(self, event):
        self.toggle_play()

    @on.button(AkaiFireDevice.BUTTON_STOP)
    def stop_button(self, event):
        self.stop()

    @on.button(AkaiFireDevice.BUTTON_REC)
    def record_button(self, event):
        self.toggle_record()

    @on.button((AkaiFireDevice.BUTTON_NOTE, AkaiFireDevice.BUTTON_BROWSER))
    def choose_mode(self, event):
        self.set_mode(
            Mode.MAIN if event.button == self.fire.BUTTON_NOTE else Mode.SETTINGS
        )

    @on.pad()
    def route_pad(self, event):
        self.dispatch_pad_press(event.pad, event.velocity)

    @on.encoder()
    def route_encoder(self, event):
        self.dispatch_encoder_turn(
            event.encoder,
            "clockwise" if event.delta > 0 else "counterclockwise",
            abs(event.delta),
        )

    def on_update(self, dt):
        """Update display based on current mode."""
        self.canvas.clear()

        info = self.current_handler.get_display_info()

        if self.current_mode == Mode.MAIN:
            # Main mode display
            status = f"{info['bpm']} BPM"
            if self.is_recording:
                status = "REC"
            elif self.is_playing:
                status = "PLAYING"

            self.draw_header("MAIN MODE", status)
            self.draw_content_lines(
                [
                    f"Track: {info['track']}",
                    f"BPM: {info['bpm']}",
                    "BROWSER: settings",
                ]
            )

        elif self.current_mode == Mode.SETTINGS:
            # Settings menu
            self.draw_menu("SETTINGS", info["items"], info["selected"])

        # Update transport LEDs
        self.update_transport_leds()


if __name__ == "__main__":
    print("Starting Modal Demo...")
    print("Controls:")
    print("  NOTE button: Switch to Main mode")
    print("  BROWSER button: Switch to Settings mode")
    print("  PLAY/STOP/REC: Transport controls")
    print("  VOLUME encoder: Adjust BPM (Main mode)")
    print("  SELECT encoder: Navigate menu (Settings mode)")
    print("  Pads: Color/track selection (Main mode)")
    print()

    with ModalDemoApp() as app:
        app.run()
