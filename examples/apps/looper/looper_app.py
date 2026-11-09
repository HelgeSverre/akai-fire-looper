#!/usr/bin/env python3
"""
Clip-state looper demo using AkaiFireApp; MIDI input/output is not wired.

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
    uv run python -m examples.apps.looper.looper_app
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
    TransportState,
    on,
)

from .clip import ClipGrid, ClipState


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
            self.app.arm()

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
        (127, 0, 0),  # Track 1: Red
        (0, 127, 0),  # Track 2: Green
        (0, 0, 127),  # Track 3: Blue
        (127, 127, 0),  # Track 4: Yellow
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

        # Add transport callback for state changes
        self.add_transport_callback(self._on_transport_change)

        # Start in main mode
        self.set_mode(Mode.MAIN)

    def on_start(self):
        """Called when app starts."""
        self._update_pads()
        self._update_track_leds()

    @on.button(AkaiFireDevice.BUTTON_PLAY)
    def play_button(self, event):
        self.toggle_play()

    @on.button(AkaiFireDevice.BUTTON_STOP)
    def stop_button(self, event):
        self.stop()

    @on.button(AkaiFireDevice.BUTTON_REC)
    def record_button(self, event):
        self._handle_record()

    @on.button((AkaiFireDevice.BUTTON_NOTE, AkaiFireDevice.BUTTON_BROWSER))
    def choose_mode(self, event):
        self.set_mode(
            Mode.MAIN if event.button == self.fire.BUTTON_NOTE else Mode.SETTINGS
        )

    @on.button(tuple(AkaiFireDevice.SOLO_BUTTONS.values()))
    def choose_track(self, event):
        self.grid.selected_track = self.fire.get_solo_index(event.button) - 1
        self._update_track_leds()

    def on_stop(self):
        self.grid.stop_all()

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

    def on_update(self, dt: float):
        """Main update loop."""
        # Update all clips and check for triggered events
        if self.is_playing:
            # This example demonstrates clip state and timing. It has no MIDI
            # instrument output; applications can send the returned events.
            self.grid.update(self.bpm)

        # Update display
        self._update_display()

        # Update pad colors for playing clips (animation)
        if self.is_playing:
            self._update_pads()

        # Update transport LEDs
        self.update_transport_leds()

    def _handle_record(self):
        clip = self.grid.selected_clip
        if clip.is_recording:
            clip.stop_recording()
            self.play()
        elif self.transport_state == TransportState.ARMED:
            self.stop()
        elif self.is_playing:
            self.record()
        else:
            clip.arm()
            self.arm()
        self._update_pads()

    def _on_transport_change(self, new_state, old_state):
        if new_state == TransportState.STOPPED:
            self.grid.stop_all()
        elif new_state == TransportState.RECORDING:
            # One transition owns both the transport and selected clip. REC is
            # registered once, so it cannot arm and cancel in the same press.
            clip = self.grid.selected_clip
            if not clip.is_recording:
                if clip.has_content:
                    clip.start_overdub(self.bpm)
                else:
                    clip.start_recording(self.bpm)
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
            btn = getattr(self.fire, f"BUTTON_SOLO_{i + 1}")
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
            ]

            if info["clip_state"] == "EMPTY":
                lines.append("Press pad to arm")
            elif info["clip_state"] == "ARMED":
                lines.append("PLAY:rec REC:cancel")
            else:
                lines.append(f"Events: {info['events']}")

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
