#!/usr/bin/env python3
"""
MIDI Looper application using AkaiFireApp framework.

Features:
- 4 tracks x 16 clips grid
- Record/play/overdub per clip
- Visual feedback on pads
- Transport controls

Controls:
- Pads: Select/trigger clips
- REC: Arm selected clip for recording
- PLAY: Start/stop playback
- STOP: Stop all clips
- SOLO buttons: Select track
- Volume encoder: Adjust BPM

Usage:
    uv run python examples/apps/looper/looper_app.py
"""

import sys
import os
from enum import Enum, auto

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from akai_fire_framework import (
    AkaiFireApp,
    ModeHandler,
    ModeManagerMixin,
    ScreenMixin,
    GridMixin,
    TransportMixin,
    TransportState,
)

# Handle both direct execution and module import
try:
    from .clip import Clip, ClipState, ClipGrid
except ImportError:
    from clip import Clip, ClipState, ClipGrid


class Mode(Enum):
    """Looper modes."""
    MAIN = auto()
    SETTINGS = auto()


class MainMode(ModeHandler):
    """Main looper mode - clip triggering and recording."""

    def __init__(self, app: "LooperApp"):
        self.app = app

    def handle_pad_press(self, pad: int, velocity: int) -> bool:
        """Handle pad press - trigger or select clip."""
        track, slot = self.app.grid.pad_to_position(pad)
        clip = self.app.grid.get_clip(track, slot)

        if clip is None:
            return False

        # Select this clip
        self.app.grid.select(track, slot)

        if self.app.is_recording:
            # If recording, start recording into this clip
            clip.start_recording(self.app.bpm)
        elif clip.has_content:
            # Toggle playback
            clip.toggle_playback()
        else:
            # Empty clip - arm for recording
            clip.arm()

        # Update pad display
        self.app._update_pads()
        return True

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder - adjust BPM."""
        if encoder == "volume":
            delta = velocity if direction == "clockwise" else -velocity
            self.app.bpm = max(30, min(300, self.app.bpm + delta))

    def handle_button_press(self, button: str) -> bool:
        """Handle button press."""
        return False

    def get_display_info(self) -> dict:
        """Get info for display."""
        clip = self.app.grid.selected_clip
        return {
            "mode": "LOOPER",
            "bpm": self.app.bpm,
            "track": self.app.grid.selected_track + 1,
            "slot": self.app.grid.selected_slot + 1,
            "clip_state": clip.state.name,
            "events": len(clip.events),
        }

    def on_enter(self, previous_mode):
        """Called when entering this mode."""
        self.app._update_pads()


class SettingsMode(ModeHandler):
    """Settings mode - configuration."""

    MENU_ITEMS = [
        "BPM",
        "Loop Length",
        "Quantize",
        "MIDI Channel",
        "Clear All",
        "Back",
    ]

    def __init__(self, app: "LooperApp"):
        self.app = app
        self.selected_item = 0

    def handle_pad_press(self, pad: int, velocity: int) -> bool:
        return False

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        if encoder == "select":
            if direction == "clockwise":
                self.selected_item = (self.selected_item + 1) % len(self.MENU_ITEMS)
            else:
                self.selected_item = (self.selected_item - 1) % len(self.MENU_ITEMS)

    def handle_button_press(self, button: str) -> bool:
        return False

    def get_display_info(self) -> dict:
        return {
            "mode": "SETTINGS",
            "selected": self.selected_item,
            "items": self.MENU_ITEMS,
        }

    def on_enter(self, previous_mode):
        self.app.clear_grid()


class LooperApp(AkaiFireApp, ModeManagerMixin, ScreenMixin, GridMixin, TransportMixin):
    """MIDI Looper application."""

    APP_NAME = "MIDI Looper"
    VERSION = "1.0"
    FPS = 30

    # Track colors for visual feedback
    TRACK_COLORS = [
        (127, 0, 0),      # Track 1: Red
        (0, 127, 0),      # Track 2: Green
        (0, 0, 127),      # Track 3: Blue
        (127, 127, 0),    # Track 4: Yellow
    ]

    def on_init(self):
        """Initialize looper state."""
        # Core state
        self.bpm = 120
        self.loop_length = 4  # bars

        # Clip grid (4 tracks x 16 slots)
        self.grid = ClipGrid(tracks=4, slots=16)

        # Initialize mixins
        self.init_mode_manager(Mode, Mode.MAIN)
        self.init_transport()

        # Register modes
        self.register_mode(Mode.MAIN, MainMode(self))
        self.register_mode(Mode.SETTINGS, SettingsMode(self))

        # Set up transport buttons
        self.setup_transport_buttons()

        # Override record button for looper-specific behavior
        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                self._handle_record()

        # Set up mode buttons
        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_note(event):
            if event == "press":
                self.set_mode(Mode.MAIN)

        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                self.set_mode(Mode.SETTINGS)

        # SOLO buttons for track selection
        solo_buttons = [
            self.fire.BUTTON_SOLO_1,
            self.fire.BUTTON_SOLO_2,
            self.fire.BUTTON_SOLO_3,
            self.fire.BUTTON_SOLO_4,
        ]

        for idx, btn in enumerate(solo_buttons):
            @self.fire.on_button(btn)
            def handle_solo(event, track=idx):
                if event == "press":
                    self.grid.selected_track = track
                    self._update_track_leds()

        # Add transport callback for state changes
        self.add_transport_callback(self._on_transport_change)

        # Start in main mode
        self.set_mode(Mode.MAIN)

    def on_start(self):
        """Called when app starts."""
        self._update_pads()
        self._update_track_leds()

    def on_pad_press(self, pad: int, velocity: int):
        """Dispatch pad press to current mode."""
        self.dispatch_pad_press(pad, velocity)

    def on_encoder_turn(self, encoder_id: int, direction: str, velocity: int):
        """Dispatch encoder turn to current mode."""
        self.dispatch_encoder_turn(encoder_id, direction, velocity)

    def on_update(self, dt: float):
        """Main update loop."""
        # Update all clips and check for triggered events
        if self.is_playing:
            triggered = self.grid.update(self.bpm)
            for track, slot, events in triggered:
                # In a real implementation, send MIDI events
                for event in events:
                    # print(f"Trigger: T{track+1} S{slot+1} - Note {event.note}")
                    pass

        # Update display
        self._update_display()

        # Update pad colors for playing clips (animation)
        if self.is_playing:
            self._update_pads()

        # Update transport LEDs
        self.update_transport_leds()

    def _handle_record(self):
        """Handle record button press."""
        clip = self.grid.selected_clip

        if clip.is_recording:
            # Stop recording
            clip.stop_recording()
            self._update_pads()
        elif self.is_recording:
            # Global record - start recording into selected clip
            clip.start_recording(self.bpm)
            self._update_pads()
        else:
            # Arm for recording
            if clip.has_content:
                # Overdub mode
                clip.start_overdub(self.bpm)
            else:
                clip.arm()
            self._update_pads()

            # Toggle global record state
            self.toggle_record()

    def _on_transport_change(self, new_state: TransportState, old_state: TransportState):
        """Handle transport state changes."""
        if new_state == TransportState.STOPPED:
            # Stop all clips
            self.grid.stop_all()
            self._update_pads()

    def _update_pads(self):
        """Update all pad colors based on clip states."""
        for track in range(4):
            track_color = self.TRACK_COLORS[track]

            for slot in range(16):
                clip = self.grid.get_clip(track, slot)
                pad = self.grid.position_to_pad(track, slot)

                if clip.state == ClipState.EMPTY:
                    # Empty - dim track color
                    color = tuple(c // 8 for c in track_color)
                elif clip.state == ClipState.RECORDING:
                    # Recording - bright red
                    color = (127, 0, 0)
                elif clip.state == ClipState.PLAYING:
                    # Playing - bright green
                    color = (0, 127, 0)
                elif clip.state == ClipState.STOPPED:
                    # Stopped with content - medium brightness
                    color = tuple(c // 2 for c in track_color)
                elif clip.state == ClipState.ARMED:
                    # Armed - pulsing red (simplified to dim red)
                    color = (64, 0, 0)
                else:
                    color = (0, 0, 0)

                self.fire.set_pad_color(pad, *color)

    def _update_track_leds(self):
        """Update track LED indicators."""
        # Use SOLO LEDs to show selected track
        for i in range(4):
            btn = getattr(self.fire, f"BUTTON_SOLO_{i+1}")
            brightness = 2 if i == self.grid.selected_track else 0
            self.fire.set_button_led(btn, brightness)

    def _update_display(self):
        """Update OLED display."""
        self.canvas.clear()

        info = self.current_handler.get_display_info()

        if self.current_mode == Mode.MAIN:
            # Header
            status = f"{info['bpm']} BPM"
            if self.is_recording:
                status = "REC"
            elif self.is_playing:
                status = "PLAY"

            self.draw_header("LOOPER", status)

            # Content
            lines = [
                f"Track {info['track']} / Slot {info['slot']}",
                f"State: {info['clip_state']}",
                f"Events: {info['events']}",
            ]

            if info['clip_state'] == "EMPTY":
                lines.append("Press pad to arm")
            elif info['clip_state'] == "ARMED":
                lines.append("Press REC to record")

            self.draw_content_lines(lines)

        elif self.current_mode == Mode.SETTINGS:
            self.draw_menu("SETTINGS", info["items"], info["selected"])


if __name__ == "__main__":
    print("Starting MIDI Looper...")
    print()
    print("Controls:")
    print("  Pads: Select/trigger clips")
    print("  REC: Arm/start recording")
    print("  PLAY: Start/stop playback")
    print("  STOP: Stop all clips")
    print("  SOLO 1-4: Select track")
    print("  Volume encoder: Adjust BPM")
    print("  NOTE: Main mode")
    print("  BROWSER: Settings mode")
    print()

    with LooperApp() as app:
        app.run()
