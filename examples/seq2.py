from transitions import Machine
from enum import Enum
from dataclasses import dataclass, field
from typing import List
import time
import rtmidi
from akai_fire import AkaiFire


class PlayState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    RECORDING = "recording"


class ScreenMode(Enum):
    MAIN = "main"
    SETTINGS = "settings"
    MENU = "menu"


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
    states = [
        "idle",
        "playing",
        "paused",
        "stopped",
        "recording",
        "main_menu",
        "settings_menu",
        "midi_menu",
        "quantization_menu",
    ]

    transitions = [
        {"trigger": "play", "source": ["idle", "paused", "stopped"], "dest": "playing"},
        {"trigger": "pause", "source": "playing", "dest": "paused"},
        {
            "trigger": "stop",
            "source": ["playing", "paused", "recording"],
            "dest": "stopped",
        },
        {"trigger": "record", "source": ["idle", "playing"], "dest": "recording"},
        {"trigger": "reset", "source": ["stopped", "recording"], "dest": "idle"},
        {"trigger": "open_main_menu", "source": "*", "dest": "main_menu"},
        {"trigger": "open_settings_menu", "source": "*", "dest": "settings_menu"},
        {"trigger": "open_midi_menu", "source": "*", "dest": "midi_menu"},
        {
            "trigger": "open_quantization_menu",
            "source": "*",
            "dest": "quantization_menu",
        },
        {
            "trigger": "close_menu",
            "source": ["main_menu", "settings_menu", "midi_menu", "quantization_menu"],
            "dest": "idle",
        },
    ]

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=SequencerApp.states,
            transitions=SequencerApp.transitions,
            initial="idle",
        )
        self.fire = AkaiFire()
        self.play_state = PlayState.STOPPED
        self.screen_mode = ScreenMode.MAIN

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
        self.update_display()

    def setup_handlers(self):
        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.stop()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.play_state == PlayState.STOPPED:
                    self.play()
                else:
                    self.stop()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                if self.play_state == PlayState.RECORDING:
                    self.stop()
                else:
                    self.record()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                if self.screen_mode == ScreenMode.MAIN:
                    self.open_settings_menu()
                    self.screen_mode = ScreenMode.SETTINGS
                else:
                    self.close_menu()
                    self.screen_mode = ScreenMode.MAIN
                self.update_display()

        @self.fire.on_rotary_turn(self.fire.ROTARY_SELECT)
        def navigate_menu(direction, velocity):
            if self.state in ["settings_menu", "midi_menu", "quantization_menu"]:
                if direction == "clockwise":
                    self.settings_menu.next_option()
                else:
                    self.settings_menu.prev_option()
                self.update_display()

        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def select_menu_option(event):
            if event == "press" and self.state in [
                "settings_menu",
                "midi_menu",
                "quantization_menu",
            ]:
                selected_option = self.settings_menu.get_selected_option()
                selected_option.next_option()
                self.update_display()

    def on_enter_playing(self):
        self.play_state = PlayState.PLAYING

    def on_enter_paused(self):
        self.play_state = PlayState.STOPPED

    def on_enter_recording(self):
        self.play_state = PlayState.RECORDING

    def on_enter_stopped(self):
        self.play_state = PlayState.STOPPED

    def on_enter_idle(self):
        self.play_state = PlayState.STOPPED

    def on_enter_main_menu(self):
        self.screen_mode = ScreenMode.MENU

    def on_enter_settings_menu(self):
        self.screen_mode = ScreenMode.SETTINGS

    def on_enter_midi_menu(self):
        self.screen_mode = ScreenMode.SETTINGS

    def on_enter_quantization_menu(self):
        self.screen_mode = ScreenMode.SETTINGS

    def update_display(self):
        if self.screen_mode == ScreenMode.SETTINGS:
            print(self.settings_menu.title)
            for idx, option in enumerate(self.settings_menu.options):
                prefix = "> " if idx == self.settings_menu.selected_index else "  "
                print(f"{prefix}{option.name}: {option.get_current_option()}")
        else:
            print(f"Current play state: {self.play_state.value}")

    def play(self):
        pass

    def stop(self):
        pass

    def record(self):
        pass

    def open_settings_menu(self):
        pass

    def close_menu(self):
        pass


if __name__ == "__main__":
    app = SequencerApp()
    app.fire.start_listening()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        app.fire.clear_all()
        app.fire.close()
