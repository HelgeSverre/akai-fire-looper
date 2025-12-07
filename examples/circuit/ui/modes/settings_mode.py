"""
Settings Mode implementation for global configuration.
Handles MIDI channels, BPM, Swing, Quantization, and JSON persistence.
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import sys

# Add parent directories to path
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)

from ui.screen_manager import Mode
from core.timing import QuantizationMode


@dataclass
class TrackSettings:
    """Settings for a single track."""

    midi_channel: int = 1
    midi_port: str = ""
    scale: str = "MAJOR"
    root_note: int = 60


@dataclass
class GlobalSettings:
    """Global sequencer settings."""

    bpm: float = 120.0
    swing: float = 0.0  # 0.0-0.75
    quantization: str = "1/16"
    track_settings: List[Dict] = field(
        default_factory=lambda: [
            {
                "midi_channel": 10,
                "midi_port": "",
                "scale": "MAJOR",
                "root_note": 60,
            },  # Drums
            {
                "midi_channel": 1,
                "midi_port": "",
                "scale": "MAJOR",
                "root_note": 60,
            },  # Bass
            {
                "midi_channel": 2,
                "midi_port": "",
                "scale": "MAJOR",
                "root_note": 60,
            },  # Lead
            {
                "midi_channel": 3,
                "midi_port": "",
                "scale": "MAJOR",
                "root_note": 60,
            },  # Pad
        ]
    )


class SettingsCategory(Enum):
    """Settings menu categories."""

    GLOBAL = "Global"
    TRACK_1 = "Track 1"
    TRACK_2 = "Track 2"
    TRACK_3 = "Track 3"
    TRACK_4 = "Track 4"
    FILE = "File"


class SettingsMode:
    """
    Handles Settings Mode functionality - global and track configuration.
    Manages BPM, swing, quantization, MIDI channels, and persistence.
    """

    # Settings file path
    DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.circuit_sequencer_settings.json")

    def __init__(self, sequencer, mode_manager):
        self.sequencer = sequencer
        self.mode_manager = mode_manager

        # Menu state
        self.current_category = SettingsCategory.GLOBAL
        self.selected_item = 0
        self.editing_value = False

        # Track being edited (0-3)
        self.editing_track = 0

        # Menu structure
        self.menu_items = self._build_menu()

        # Settings path
        self.settings_path = self.DEFAULT_SETTINGS_PATH

        # Register mode callbacks
        self.mode_manager.register_mode_callback(
            Mode.SETTINGS, "on_enter", self._on_enter
        )
        self.mode_manager.register_mode_callback(
            Mode.SETTINGS, "on_exit", self._on_exit
        )

        # Register this instance as the Settings Mode handler
        self.mode_manager.register_mode_handler(Mode.SETTINGS, self)

    def _build_menu(self) -> List[Dict[str, Any]]:
        """Build the settings menu structure."""
        return [
            # Global settings
            {
                "name": "BPM",
                "type": "value",
                "category": SettingsCategory.GLOBAL,
                "get": lambda: self.sequencer.get_bpm(),
                "set": lambda v: self.sequencer.set_bpm(v),
                "min": 30,
                "max": 300,
                "step": 1,
            },
            {
                "name": "Swing",
                "type": "value",
                "category": SettingsCategory.GLOBAL,
                "get": lambda: int(self.sequencer.get_swing() * 100),
                "set": lambda v: self.sequencer.set_swing(v / 100.0),
                "min": 0,
                "max": 75,
                "step": 5,
                "suffix": "%",
            },
            {
                "name": "Quantization",
                "type": "options",
                "category": SettingsCategory.GLOBAL,
                "options": ["Off", "1/4", "1/8", "1/16", "1/32"],
                "get": lambda: self._get_quantization_index(),
                "set": lambda v: self._set_quantization_index(v),
            },
            # Track 1 settings
            {
                "name": "T1 MIDI Ch",
                "type": "value",
                "category": SettingsCategory.TRACK_1,
                "get": lambda: self.sequencer.tracks[0].midi_channel,
                "set": lambda v: self._set_track_midi_channel(0, v),
                "min": 1,
                "max": 16,
                "step": 1,
            },
            {
                "name": "T1 Scale",
                "type": "options",
                "category": SettingsCategory.TRACK_1,
                "options": ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"],
                "get": lambda: self._get_track_scale_index(0),
                "set": lambda v: self._set_track_scale_index(0, v),
            },
            # Track 2 settings
            {
                "name": "T2 MIDI Ch",
                "type": "value",
                "category": SettingsCategory.TRACK_2,
                "get": lambda: self.sequencer.tracks[1].midi_channel,
                "set": lambda v: self._set_track_midi_channel(1, v),
                "min": 1,
                "max": 16,
                "step": 1,
            },
            {
                "name": "T2 Scale",
                "type": "options",
                "category": SettingsCategory.TRACK_2,
                "options": ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"],
                "get": lambda: self._get_track_scale_index(1),
                "set": lambda v: self._set_track_scale_index(1, v),
            },
            # Track 3 settings
            {
                "name": "T3 MIDI Ch",
                "type": "value",
                "category": SettingsCategory.TRACK_3,
                "get": lambda: self.sequencer.tracks[2].midi_channel,
                "set": lambda v: self._set_track_midi_channel(2, v),
                "min": 1,
                "max": 16,
                "step": 1,
            },
            {
                "name": "T3 Scale",
                "type": "options",
                "category": SettingsCategory.TRACK_3,
                "options": ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"],
                "get": lambda: self._get_track_scale_index(2),
                "set": lambda v: self._set_track_scale_index(2, v),
            },
            # Track 4 settings
            {
                "name": "T4 MIDI Ch",
                "type": "value",
                "category": SettingsCategory.TRACK_4,
                "get": lambda: self.sequencer.tracks[3].midi_channel,
                "set": lambda v: self._set_track_midi_channel(3, v),
                "min": 1,
                "max": 16,
                "step": 1,
            },
            {
                "name": "T4 Scale",
                "type": "options",
                "category": SettingsCategory.TRACK_4,
                "options": ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"],
                "get": lambda: self._get_track_scale_index(3),
                "set": lambda v: self._set_track_scale_index(3, v),
            },
            # File operations
            {
                "name": "Save Settings",
                "type": "action",
                "category": SettingsCategory.FILE,
                "action": self.save_settings,
            },
            {
                "name": "Load Settings",
                "type": "action",
                "category": SettingsCategory.FILE,
                "action": self.load_settings,
            },
        ]

    def _on_enter(self, previous_mode: Mode):
        """Called when entering Settings Mode."""
        print("Entered Settings Mode")
        self.selected_item = 0
        self.editing_value = False
        self._update_mode_state()

    def _on_exit(self):
        """Called when exiting Settings Mode."""
        print("Exited Settings Mode")
        self.editing_value = False

    def _update_mode_state(self):
        """Update mode manager state with current Settings Mode settings."""
        # Build display items for screen
        display_items = []
        for item in self.menu_items:
            if item["type"] == "value":
                value = item["get"]()
                suffix = item.get("suffix", "")
                display_items.append(f"{item['name']}: {value}{suffix}")
            elif item["type"] == "options":
                idx = item["get"]()
                options = item["options"]
                current = options[idx] if 0 <= idx < len(options) else "?"
                display_items.append(f"{item['name']}: {current}")
            else:
                display_items.append(item["name"])

        self.mode_manager.set_mode_state(
            Mode.SETTINGS, "selected_item", self.selected_item
        )
        self.mode_manager.set_mode_state(
            Mode.SETTINGS, "editing_value", self.editing_value
        )
        self.mode_manager.set_mode_state(Mode.SETTINGS, "menu_items", display_items)
        self.mode_manager.set_mode_state(
            Mode.SETTINGS, "selected_index", self.selected_item
        )

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """Handle pad press in Settings Mode."""
        grid = self.mode_manager.grid
        row, col = grid.pad_position(pad_index)

        if row == grid.STEP_ROW:
            # Row 0: Category selection (first 6 pads)
            categories = list(SettingsCategory)
            if col < len(categories):
                self.current_category = categories[col]
                # Move to first item in this category
                for i, item in enumerate(self.menu_items):
                    if item["category"] == self.current_category:
                        self.selected_item = i
                        break
                self._update_mode_state()
                print(f"Category: {self.current_category.value}")
                return True

        elif row == grid.TRACK_PATTERN_ROW:
            # Row 1: Menu item selection (first 12 pads)
            if col < len(self.menu_items):
                self.selected_item = col
                self._update_mode_state()
                item = self.menu_items[self.selected_item]
                print(f"Selected: {item['name']}")
                return True

        elif row == grid.INPUT_ROW_1:
            # Row 2: Quick value presets or action trigger
            item = self.menu_items[self.selected_item]
            if item["type"] == "action":
                # Execute action
                item["action"]()
                return True
            elif item["type"] == "options":
                # Quick option selection
                options = item["options"]
                if col < len(options):
                    item["set"](col)
                    self._update_mode_state()
                    print(f"{item['name']}: {options[col]}")
                    return True

        elif row == grid.INPUT_ROW_2:
            # Row 3: Value adjustment (mapped across 16 pads)
            item = self.menu_items[self.selected_item]
            if item["type"] == "value":
                # Map pad to value range
                min_val = item["min"]
                max_val = item["max"]
                value = min_val + (col * (max_val - min_val)) // 15
                item["set"](value)
                self._update_mode_state()
                suffix = item.get("suffix", "")
                print(f"{item['name']}: {value}{suffix}")
                return True

        return False

    def handle_encoder_turn(self, encoder: str, direction: str, velocity: int):
        """Handle encoder turns in Settings Mode."""
        try:
            if encoder == "volume":
                # Navigate menu items
                if direction == "clockwise":
                    self.selected_item = (self.selected_item + 1) % len(self.menu_items)
                else:
                    self.selected_item = (self.selected_item - 1) % len(self.menu_items)
                self._update_mode_state()
                item = self.menu_items[self.selected_item]
                print(f"Selected: {item['name']}")

            elif encoder in ["filter", "pan"]:
                # Adjust current value
                item = self.menu_items[self.selected_item]
                delta = velocity if direction == "clockwise" else -velocity

                if item["type"] == "value":
                    current = item["get"]()
                    step = item.get("step", 1)
                    new_value = max(
                        item["min"], min(item["max"], current + delta * step)
                    )
                    item["set"](new_value)
                    self._update_mode_state()
                    suffix = item.get("suffix", "")
                    print(f"{item['name']}: {new_value}{suffix}")

                elif item["type"] == "options":
                    current_idx = item["get"]()
                    options = item["options"]
                    if direction == "clockwise":
                        new_idx = (current_idx + 1) % len(options)
                    else:
                        new_idx = (current_idx - 1) % len(options)
                    item["set"](new_idx)
                    self._update_mode_state()
                    print(f"{item['name']}: {options[new_idx]}")

        except Exception as e:
            print(
                f"Error in Settings mode encoder handling ({encoder}, {direction}): {e}"
            )

    def handle_button_press(self, button: str):
        """Handle button presses in Settings Mode."""
        if button == "grid_left":
            # Previous item
            self.selected_item = (self.selected_item - 1) % len(self.menu_items)
            self._update_mode_state()
        elif button == "grid_right":
            # Next item
            self.selected_item = (self.selected_item + 1) % len(self.menu_items)
            self._update_mode_state()
        elif button == "select":
            # Execute action if current item is an action
            item = self.menu_items[self.selected_item]
            if item["type"] == "action":
                item["action"]()

    def get_display_info(self) -> Dict[str, Any]:
        """Get information for display updates."""
        item = self.menu_items[self.selected_item] if self.menu_items else None

        if item:
            if item["type"] == "value":
                current_value = item["get"]()
                suffix = item.get("suffix", "")
                value_str = f"{current_value}{suffix}"
            elif item["type"] == "options":
                idx = item["get"]()
                value_str = (
                    item["options"][idx] if 0 <= idx < len(item["options"]) else "?"
                )
            else:
                value_str = ""
        else:
            value_str = ""

        return {
            "selected_item": self.selected_item,
            "item_name": item["name"] if item else "",
            "item_value": value_str,
            "editing_value": self.editing_value,
            "category": self.current_category.value,
        }

    # Quantization helpers
    def _get_quantization_index(self) -> int:
        """Get current quantization as menu index."""
        q = self.sequencer.timing.quantization
        mapping = {
            QuantizationMode.OFF: 0,
            QuantizationMode.QUARTER: 1,
            QuantizationMode.EIGHTH: 2,
            QuantizationMode.SIXTEENTH: 3,
            QuantizationMode.THIRTY_SECOND: 4,
        }
        return mapping.get(q, 3)

    def _set_quantization_index(self, idx: int):
        """Set quantization from menu index."""
        mapping = [
            QuantizationMode.OFF,
            QuantizationMode.QUARTER,
            QuantizationMode.EIGHTH,
            QuantizationMode.SIXTEENTH,
            QuantizationMode.THIRTY_SECOND,
        ]
        if 0 <= idx < len(mapping):
            self.sequencer.set_quantization(mapping[idx])

    # Track helpers
    def _set_track_midi_channel(self, track_idx: int, channel: int):
        """Set MIDI channel for a track."""
        if 0 <= track_idx < len(self.sequencer.tracks):
            self.sequencer.tracks[track_idx].midi_channel = channel

    def _get_track_scale_index(self, track_idx: int) -> int:
        """Get scale index for a track."""
        if 0 <= track_idx < len(self.sequencer.tracks):
            scale = self.sequencer.tracks[track_idx].scale
            scales = ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"]
            return scales.index(scale) if scale in scales else 0
        return 0

    def _set_track_scale_index(self, track_idx: int, scale_idx: int):
        """Set scale for a track by index."""
        scales = ["MAJOR", "MINOR", "DORIAN", "MIXOLYDIAN", "CHROMATIC"]
        if 0 <= track_idx < len(self.sequencer.tracks) and 0 <= scale_idx < len(scales):
            self.sequencer.tracks[track_idx].scale = scales[scale_idx]

    # JSON Persistence
    def save_settings(self, path: Optional[str] = None):
        """Save current settings to JSON file."""
        if path is None:
            path = self.settings_path

        settings = {
            "bpm": self.sequencer.get_bpm(),
            "swing": self.sequencer.get_swing(),
            "quantization": self.sequencer.timing.quantization.value,
            "tracks": [],
        }

        for track in self.sequencer.tracks:
            settings["tracks"].append(
                {
                    "name": track.name,
                    "midi_channel": track.midi_channel,
                    "midi_port": track.midi_port,
                    "scale": track.scale,
                    "root_note": track.root_note,
                    "level": track.level,
                    "pan": track.pan,
                }
            )

        try:
            with open(path, "w") as f:
                json.dump(settings, f, indent=2)
            print(f"Settings saved to {path}")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self, path: Optional[str] = None):
        """Load settings from JSON file."""
        if path is None:
            path = self.settings_path

        if not os.path.exists(path):
            print(f"Settings file not found: {path}")
            return

        try:
            with open(path, "r") as f:
                settings = json.load(f)

            # Apply global settings
            if "bpm" in settings:
                self.sequencer.set_bpm(settings["bpm"])
            if "swing" in settings:
                self.sequencer.set_swing(settings["swing"])
            if "quantization" in settings:
                q_str = settings["quantization"]
                for q in QuantizationMode:
                    if q.value == q_str:
                        self.sequencer.set_quantization(q)
                        break

            # Apply track settings
            for i, track_data in enumerate(settings.get("tracks", [])):
                if i < len(self.sequencer.tracks):
                    track = self.sequencer.tracks[i]
                    if "name" in track_data:
                        track.name = track_data["name"]
                    if "midi_channel" in track_data:
                        track.midi_channel = track_data["midi_channel"]
                    if "midi_port" in track_data:
                        track.midi_port = track_data["midi_port"]
                    if "scale" in track_data:
                        track.scale = track_data["scale"]
                    if "root_note" in track_data:
                        track.root_note = track_data["root_note"]
                    if "level" in track_data:
                        track.level = track_data["level"]
                    if "pan" in track_data:
                        track.pan = track_data["pan"]

            self._update_mode_state()
            print(f"Settings loaded from {path}")

        except Exception as e:
            print(f"Error loading settings: {e}")
