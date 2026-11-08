"""Four-track MIDI sequencer with a framework-owned controller lifecycle."""

import os
import threading

from akai_fire_framework import AkaiFireApp

from .core.sequencer import Sequencer, TransportState
from .ui.grid_manager import GridManager
from .ui.mode_manager import ModeManager
from .ui.modes.mixer_mode import MixerMode
from .ui.modes.note_mode import NoteMode
from .ui.modes.pattern_mode import PatternMode
from .ui.modes.settings_mode import SettingsMode
from .ui.modes.step_edit_mode import StepEditMode
from .ui.screen_manager import Mode, ScreenManager


class CircuitSequencer(AkaiFireApp):
    APP_NAME = "Circuit Sequencer"

    def on_init(self):
        self.sequencer = Sequencer()
        try:
            self.screen_manager = ScreenManager(self.canvas)
            self.grid_manager = GridManager(self.fire)
            self.mode_manager = ModeManager(self.screen_manager, self.grid_manager)
            self.note_mode = NoteMode(self.sequencer, self.mode_manager)
            self.mixer_mode = MixerMode(self.sequencer, self.mode_manager)
            self.pattern_mode = PatternMode(self.sequencer, self.mode_manager)
            self.step_edit_mode = StepEditMode(self.sequencer, self.mode_manager)
            self.settings_mode = SettingsMode(self.sequencer, self.mode_manager)
            self._current_step = 0
            self._step_lock = threading.Lock()
            self._setup_midi()
            self._setup_sequencer_callbacks()
        except Exception:
            self.sequencer.cleanup()
            raise

    def _setup_midi(self):
        inputs, outputs = self.sequencer.midi.refresh_ports()
        print(f"MIDI inputs: {inputs}\nMIDI outputs: {outputs}")
        # The Fire's port carries controller LEDs and input, not instrument notes.
        # Explicit routing also prevents a demo from choosing the wrong synth.
        for variable, setter in (
            ("CIRCUIT_MIDI_OUTPUT", self.sequencer.midi.set_output_port),
            ("CIRCUIT_MIDI_INPUT", self.sequencer.midi.set_input_port),
        ):
            port = os.environ.get(variable)
            if port:
                if "fire" in port.lower():
                    raise ValueError(f"{variable} must be an instrument port")
                if not setter(port):
                    raise ValueError(f"Cannot open {variable}={port!r}")
        if not os.environ.get("CIRCUIT_MIDI_OUTPUT"):
            print(
                "Preview only: set CIRCUIT_MIDI_OUTPUT to an instrument port for sound."
            )

    def on_button_press(self, button_id, event):
        if event != "press":
            return
        fire = self.fire
        if button_id == fire.BUTTON_PLAY:
            if self.sequencer.transport_state == TransportState.STOPPED:
                self.sequencer.play()
            else:
                self.sequencer.stop()
        elif button_id == fire.BUTTON_REC:
            if self.sequencer.transport_state == TransportState.RECORDING:
                self.sequencer.stop()
            else:
                self.sequencer.record()
        elif button_id == fire.BUTTON_STOP:
            self.sequencer.stop()
        elif button_id == fire.BUTTON_BROWSER:
            self.mode_manager.set_mode(
                Mode.NOTE
                if self.mode_manager.current_mode == Mode.SETTINGS
                else Mode.SETTINGS
            )
        else:
            modes = {
                fire.BUTTON_NOTE: Mode.NOTE,
                fire.BUTTON_STEP: Mode.STEP_EDIT,
                fire.BUTTON_DRUM: Mode.MIXER,
                fire.BUTTON_PERFORM: Mode.PATTERN,
            }
            tracks = [
                fire.BUTTON_SOLO_1,
                fire.BUTTON_SOLO_2,
                fire.BUTTON_SOLO_3,
                fire.BUTTON_SOLO_4,
            ]
            buttons = {
                fire.BUTTON_GRID_LEFT: "grid_left",
                fire.BUTTON_GRID_RIGHT: "grid_right",
                fire.BUTTON_SELECT: "select",
            }
            if button_id in modes:
                self.mode_manager.set_mode(modes[button_id])
            elif button_id in tracks:
                self.note_mode._stop_all_notes()
                self.sequencer.set_current_track(tracks.index(button_id))
                self._update_track_leds()
                self._refresh_mode_display()
            elif button_id in buttons:
                self.mode_manager.mode_handlers[
                    self.mode_manager.current_mode
                ].handle_button_press(buttons[button_id])

    def on_encoder_turn(self, encoder_id, direction, velocity):
        encoders = {
            self.fire.ROTARY_VOLUME: "volume",
            self.fire.ROTARY_FILTER: "filter",
            self.fire.ROTARY_PAN: "pan",
            self.fire.ROTARY_SELECT: "volume",
        }
        if encoder_id in encoders:
            self.mode_manager.mode_handlers[
                self.mode_manager.current_mode
            ].handle_encoder_turn(encoders[encoder_id], direction, velocity)

    def on_pad_press(self, pad, velocity):
        self.mode_manager.handle_pad_press(pad, velocity)

    def on_start(self):
        self.note_mode.on_track_changed()
        self._update_track_leds()
        self._update_display()
        print(
            "Circuit: NOTE keyboard, STEP editor, DRUM mixer, PERFORM patterns, BROWSER settings."
        )
        print("PLAY/REC/STOP transport; Ctrl+C or close the mock window to quit.")

    def on_update(self, dt):
        self.note_mode.expire_previews()
        self._update_transport_leds()
        with self._step_lock:
            current_step = self._current_step
        self._update_display(current_step)

    def on_stop(self):
        self.sequencer.cleanup()

    def _setup_sequencer_callbacks(self):
        """Set up sequencer event callbacks."""

        # Step callback - only store step info (UI updates happen in main thread)
        def on_step(step):
            with self._step_lock:
                self._current_step = step

        self.sequencer.add_step_callback(on_step)

        # Transport state callback - UI updates will be handled by main thread
        def on_transport_change(state):
            print(f"Transport: {state.value}")
            # Note: Transport LED updates will be handled in main loop to avoid threading issues

        self.sequencer.add_transport_callback(on_transport_change)

    def _update_transport_leds(self):
        """Update transport button LEDs based on sequencer state."""
        state = self.sequencer.transport_state

        # Clear all transport LEDs
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 0)
        self.fire.set_button_led(self.fire.BUTTON_REC, 0)
        self.fire.set_button_led(self.fire.BUTTON_STOP, 0)

        # Set LEDs based on state
        if state == TransportState.PLAYING:
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 2)  # Bright green
        elif state == TransportState.RECORDING:
            self.fire.set_button_led(self.fire.BUTTON_REC, 2)  # Bright red
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)  # Dim green
        else:  # STOPPED
            self.fire.set_button_led(self.fire.BUTTON_STOP, 1)  # Dim red

    def _update_track_leds(self):
        """Update track LEDs to show selected track."""
        current_track = self.sequencer.current_track
        for i in range(4):
            if i == current_track:
                self.fire.set_track_led(i + 1, 2)  # Bright for selected
            else:
                self.fire.set_track_led(i + 1, 1)  # Dim for others

    def _refresh_mode_display(self):
        """Refresh the current mode's display after track change."""
        # Update the current mode handler with new track context
        current_mode = self.mode_manager.get_current_mode()
        if current_mode == Mode.NOTE:
            self.note_mode.on_track_changed()
        elif current_mode == Mode.MIXER:
            self.mixer_mode.on_track_changed()
        elif current_mode == Mode.STEP_EDIT:
            self.step_edit_mode.on_track_changed()

    def _update_display(self, current_step=None):
        """Update screen and grid displays."""
        # Get sequencer status
        status = self.sequencer.get_status()

        # Add mode-specific information
        display_kwargs = {}

        handler = self.mode_manager.mode_handlers.get(self.mode_manager.current_mode)
        if handler is not None:
            display_kwargs.update(handler.get_display_info())

        # Add current step information for grid highlighting
        if current_step is not None:
            display_kwargs["current_step"] = current_step

        # Update displays
        self.mode_manager.update_display(status, **display_kwargs)


def main():
    with CircuitSequencer() as app:
        app.run()


if __name__ == "__main__":
    main()
