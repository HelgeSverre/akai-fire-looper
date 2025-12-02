import os
import sys
import time
from dataclasses import dataclass
from typing import List

import rtmidi
from transitions import Machine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


@dataclass
class MenuOption:
    name: str
    options: List[str]
    current_index: int = 0

    def next_option(self):
        self.current_index = (self.current_index + 1) % len(self.options)

    def prev_option(self):
        self.current_index = (self.current_index - 1) % len(self.options)

    def get_current_option(self):
        return self.options[self.current_index]


@dataclass
class Menu:
    title: str
    options: List[MenuOption]
    selected_index: int = 0

    def next_option(self):
        self.selected_index = (self.selected_index + 1) % len(self.options)

    def prev_option(self):
        self.selected_index = (self.selected_index - 1) % len(self.options)

    def get_selected_option(self):
        return self.options[self.selected_index]


class SequencerApp:
    # Transport states - what the sequencer is doing
    transport_states = ["stopped", "playing", "recording"]
    transport_transitions = [
        {"trigger": "play", "source": "stopped", "dest": "playing"},
        {"trigger": "stop", "source": ["playing", "recording"], "dest": "stopped"},
        {"trigger": "record", "source": "stopped", "dest": "recording"},
    ]

    # UI states - what the user is looking at
    ui_states = ["main", "settings", "midi_menu", "quantization_menu"]
    ui_transitions = [
        {"trigger": "open_settings_menu", "source": "main", "dest": "settings"},
        {"trigger": "open_midi_menu", "source": "settings", "dest": "midi_menu"},
        {
            "trigger": "open_quantization_menu",
            "source": "settings",
            "dest": "quantization_menu",
        },
        {
            "trigger": "close_menu",
            "source": ["settings", "midi_menu", "quantization_menu"],
            "dest": "main",
        },
    ]

    def __init__(self):
        # Transport state machine - controls playback
        self.transport_machine = Machine(
            model=self,
            states=SequencerApp.transport_states,
            transitions=SequencerApp.transport_transitions,
            initial="stopped",
            model_attribute="transport_state",
        )

        # UI state machine - controls what's displayed
        self.ui_machine = Machine(
            model=self,
            states=SequencerApp.ui_states,
            transitions=SequencerApp.ui_transitions,
            initial="main",
            model_attribute="ui_state",
        )
        self.fire = get_akai_fire()
        self.canvas = self.fire.get_canvas()

        midi_in_ports = rtmidi.MidiIn().get_ports()
        midi_out_ports = rtmidi.MidiOut().get_ports()

        self.settings_menu = Menu(
            title="Settings Menu",
            options=[
                MenuOption(name="MIDI In", options=midi_in_ports),
                MenuOption(name="MIDI Out", options=midi_out_ports),
                MenuOption(name="Quantization", options=["Off", "1/4", "1/8", "1/16"]),
            ],
        )

        self.setup_handlers()
        self.update_button_leds()
        self.update_display()

    def setup_handlers(self):
        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.do_stop()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.transport_state == "stopped":
                    self.do_play()
                else:
                    self.do_stop()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                if self.transport_state == "recording":
                    self.do_stop()
                else:
                    self.do_record()

        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                if self.ui_state == "main":
                    self.do_open_settings_menu()
                else:
                    self.do_close_menu()

        @self.fire.on_rotary_turn(self.fire.ROTARY_SELECT)
        def navigate_menu(direction, velocity):
            if self.ui_state in ["settings", "midi_menu", "quantization_menu"]:
                if direction == "clockwise":
                    self.settings_menu.next_option()
                else:
                    self.settings_menu.prev_option()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def select_menu_option(event):
            if event == "press" and self.ui_state in [
                "settings",
                "midi_menu",
                "quantization_menu",
            ]:
                selected_option = self.settings_menu.get_selected_option()
                selected_option.next_option()
                self.update_display()

    def update_transport_leds(self):
        """Update transport button LEDs based on transport state"""
        # Clear all transport LEDs first
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 0)
        self.fire.set_button_led(self.fire.BUTTON_STOP, 0)
        self.fire.set_button_led(self.fire.BUTTON_REC, 0)

        # Set LEDs based on current transport state
        if self.transport_state == "playing":
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 2)  # High green
        elif self.transport_state == "recording":
            self.fire.set_button_led(self.fire.BUTTON_REC, 2)  # High red
            self.fire.set_button_led(
                self.fire.BUTTON_PLAY, 1
            )  # Dim green (playing while recording)
        else:  # stopped
            self.fire.set_button_led(self.fire.BUTTON_STOP, 1)  # Dim red

    def update_ui_leds(self):
        """Update UI button LEDs based on UI state"""
        # Browser button LED indicates menu state
        if self.ui_state == "main":
            self.fire.set_button_led(
                self.fire.BUTTON_BROWSER, 0
            )  # Off when in main view
        else:
            self.fire.set_button_led(
                self.fire.BUTTON_BROWSER, 2
            )  # High green when in menu

    def update_button_leds(self):
        """Update all button LEDs based on current states"""
        self.update_transport_leds()
        self.update_ui_leds()

    # Transport state machine callbacks
    def on_enter_playing(self):
        """Called when transport enters playing state"""
        self.update_transport_leds()
        self.update_display()

    def on_enter_recording(self):
        """Called when transport enters recording state"""
        self.update_transport_leds()
        self.update_display()

    def on_enter_stopped(self):
        """Called when transport enters stopped state"""
        self.update_transport_leds()
        self.update_display()

    # UI state machine callbacks
    def on_enter_main(self):
        """Called when UI enters main view"""
        self.update_ui_leds()
        self.update_display()

    def on_enter_settings(self):
        """Called when UI enters settings menu"""
        self.update_ui_leds()
        self.update_display()

    def on_enter_midi_menu(self):
        """Called when UI enters MIDI menu"""
        self.update_ui_leds()
        self.update_display()

    def on_enter_quantization_menu(self):
        """Called when UI enters quantization menu"""
        self.update_ui_leds()
        self.update_display()

    def update_display(self):
        self.canvas.clear()
        if self.ui_state in ["settings", "midi_menu", "quantization_menu"]:
            # Build menu items list
            items = []
            for option in self.settings_menu.options:
                items.append(f"{option.name}: {option.get_current_option()}")

            # Use built-in menu renderer
            self.canvas.draw_menu(
                self.settings_menu.title, items, self.settings_menu.selected_index
            )
        else:
            # Main transport display - shows current state of both machines
            ui_info = f"UI: {self.ui_state}"
            transport_info = f"Transport: {self.transport_state}"
            self.canvas.draw_page(
                "Music Sequencer",
                [
                    ui_info,
                    transport_info,
                    "",
                    "Press BROWSER for settings",
                    "Use transport buttons",
                ],
            )

        self.fire.render_to_display()

    def do_play(self):
        """Start playback"""
        try:
            # Call the transport state machine trigger
            self.play()
        except Exception as e:
            print(f"Cannot play from current state: {e}")

    def do_stop(self):
        """Stop playback"""
        try:
            # Call the transport state machine trigger
            self.stop()
        except Exception as e:
            print(f"Cannot stop from current state: {e}")

    def do_record(self):
        """Start recording"""
        try:
            # Call the transport state machine trigger
            self.record()
        except Exception as e:
            print(f"Cannot record from current state: {e}")

    def do_open_settings_menu(self):
        """Open settings menu"""
        try:
            # Call the UI state machine trigger
            self.open_settings_menu()
        except Exception as e:
            print(f"Cannot open settings menu: {e}")

    def do_close_menu(self):
        """Close current menu and return to main"""
        try:
            # Call the UI state machine trigger
            self.close_menu()
        except Exception as e:
            print(f"Cannot close menu: {e}")


if __name__ == "__main__":
    app = SequencerApp()
    app.fire.start_listening()

    try:
        while True:
            time.sleep(0.1)

            # Handle mock GUI events if using mock

            if hasattr(app.fire, "process_events"):
                if not app.fire.process_events():
                    break
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        app.fire.clear_all()
        app.fire.close()
