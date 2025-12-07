"""
Mode manager for handling different UI modes and their transitions.
Coordinates between screen display and pad grid updates.
"""

from enum import Enum
from typing import Dict, Any, Optional, Callable
from ui.screen_manager import Mode, ScreenManager
from ui.grid_manager import GridManager


class ModeManager:
    """
    Manages UI mode switching and coordinates screen and grid updates.
    Handles the Circuit Tracks-inspired mode system.
    """

    def __init__(self, screen_manager: ScreenManager, grid_manager: GridManager):
        self.screen = screen_manager
        self.grid = grid_manager
        self.current_mode = Mode.NOTE

        # Mode-specific state
        self.mode_state = {
            Mode.NOTE: {},
            Mode.MIXER: {},
            Mode.PATTERN: {},
            Mode.STEP_EDIT: {},
            Mode.SETTINGS: {},
        }

        # Mode transition callbacks
        self.mode_callbacks = {}

        # Mode handler registry (will be populated by mode instances)
        self.mode_handlers = {}

    def set_mode(self, new_mode: Mode):
        """Switch to a different mode."""
        if new_mode != self.current_mode:
            # Call exit callback for current mode
            if self.current_mode in self.mode_callbacks:
                exit_callback = self.mode_callbacks[self.current_mode].get("on_exit")
                if exit_callback:
                    exit_callback()

            # Switch modes
            old_mode = self.current_mode
            self.current_mode = new_mode

            # Update screen and grid
            self.screen.set_mode(new_mode)
            self.grid.set_mode(new_mode)

            # Call enter callback for new mode
            if new_mode in self.mode_callbacks:
                enter_callback = self.mode_callbacks[new_mode].get("on_enter")
                if enter_callback:
                    enter_callback(old_mode)

            print(f"Mode switched: {old_mode.value} → {new_mode.value}")

    def get_current_mode(self) -> Mode:
        """Get the current mode."""
        return self.current_mode

    def cycle_mode(self):
        """Cycle through modes (Circuit Tracks style: Note → Mixer → Pattern → Settings → Note)."""
        mode_cycle = [Mode.NOTE, Mode.MIXER, Mode.PATTERN, Mode.SETTINGS]

        try:
            current_index = mode_cycle.index(self.current_mode)
            next_index = (current_index + 1) % len(mode_cycle)
            self.set_mode(mode_cycle[next_index])
        except ValueError:
            # If current mode not in cycle, default to NOTE
            self.set_mode(Mode.NOTE)

    def update_display(self, sequencer_status: Dict[str, Any], **kwargs):
        """Update both screen and grid displays."""
        # Add mode-specific state to kwargs
        mode_kwargs = kwargs.copy()
        mode_kwargs.update(self.mode_state[self.current_mode])

        # Add menu data for SETTINGS mode
        if self.current_mode == Mode.SETTINGS:
            if not hasattr(self, "settings_menu"):
                self.__init_menu_system()

            menu = self.settings_menu
            # Convert menu items to display format
            menu_items = []
            for item in menu["items"]:
                if item["type"] == "value":
                    menu_items.append(f"{item['name']}: {item['value']}")
                elif item["type"] == "options":
                    current_option = item["options"][item["current"]]
                    menu_items.append(f"{item['name']}: {current_option}")
                else:
                    menu_items.append(item["name"])

            mode_kwargs.update(
                {
                    "menu_items": menu_items,
                    "selected_index": menu["selected_index"],
                    "menu_title": menu["title"],
                }
            )

        # Update screen and grid
        self.screen.update_display(sequencer_status, **mode_kwargs)
        self.grid.update_grid(sequencer_status, **mode_kwargs)

    def set_mode_state(self, mode: Mode, key: str, value: Any):
        """Set mode-specific state."""
        if mode not in self.mode_state:
            self.mode_state[mode] = {}
        self.mode_state[mode][key] = value

    def get_mode_state(self, mode: Mode, key: str, default: Any = None) -> Any:
        """Get mode-specific state."""
        return self.mode_state.get(mode, {}).get(key, default)

    def register_mode_callback(
        self, mode: Mode, callback_type: str, callback: Callable
    ):
        """Register a callback for mode transitions."""
        if mode not in self.mode_callbacks:
            self.mode_callbacks[mode] = {}
        self.mode_callbacks[mode][callback_type] = callback

    def register_mode_handler(self, mode: Mode, handler):
        """Register a mode handler instance."""
        self.mode_handlers[mode] = handler

    def handle_pad_press(self, pad_index: int, velocity: int) -> bool:
        """
        Handle pad press events based on current mode.
        Returns True if the event was handled.
        """
        # First try to delegate to registered mode handler
        if self.current_mode in self.mode_handlers:
            handler = self.mode_handlers[self.current_mode]
            if hasattr(handler, "handle_pad_press"):
                return handler.handle_pad_press(pad_index, velocity)

        # Fallback to internal mode-specific handling
        if self.current_mode == Mode.NOTE:
            return self._handle_note_mode_pad(pad_index, velocity)
        elif self.current_mode == Mode.MIXER:
            return self._handle_mixer_mode_pad(pad_index, velocity)
        elif self.current_mode == Mode.PATTERN:
            return self._handle_pattern_mode_pad(pad_index, velocity)
        elif self.current_mode == Mode.STEP_EDIT:
            return self._handle_step_edit_mode_pad(pad_index, velocity)
        elif self.current_mode == Mode.SETTINGS:
            return self._handle_settings_mode_pad(pad_index, velocity)

        return False

    def _handle_note_mode_pad(self, pad_index: int, velocity: int) -> bool:
        """Handle pad presses in Note Mode."""
        row, col = self.grid.pad_position(pad_index)

        if row == self.grid.STEP_ROW:
            # Row 1: Step sequencer - not directly interactive in Note Mode
            return False
        elif row == self.grid.TRACK_PATTERN_ROW:
            if col < 4:
                # Track selection (columns 0-3)
                self.set_mode_state(Mode.NOTE, "selected_track", col)
                return True
            elif col < 12:
                # Pattern selection (columns 4-11)
                pattern_num = col - 4
                self.set_mode_state(Mode.NOTE, "selected_pattern", pattern_num)
                return True
        elif row in [self.grid.INPUT_ROW_1, self.grid.INPUT_ROW_2]:
            # Rows 3-4: Scale keyboard
            keyboard_index = col if row == self.grid.INPUT_ROW_1 else col + 16
            self.set_mode_state(Mode.NOTE, "last_note_played", keyboard_index)
            self.set_mode_state(Mode.NOTE, "note_velocity", velocity)
            return True

        return False

    def _handle_mixer_mode_pad(self, pad_index: int, velocity: int) -> bool:
        """Handle pad presses in Mixer Mode."""
        row, col = self.grid.pad_position(pad_index)

        if row == self.grid.TRACK_PATTERN_ROW:
            if col < 4:
                # Track mute/solo (columns 0-3)
                self.set_mode_state(
                    Mode.MIXER, "track_action", {"track": col, "action": "toggle"}
                )
                return True
            elif col < 12:
                # Scene triggers (columns 4-11)
                scene_num = col - 4
                self.set_mode_state(Mode.MIXER, "launch_scene", scene_num)
                return True
        elif row in [self.grid.INPUT_ROW_1, self.grid.INPUT_ROW_2]:
            # CC controls
            cc_index = col if row == self.grid.INPUT_ROW_1 else col + 16
            cc_value = (velocity * 127) // 127  # Convert pad velocity to CC value
            self.set_mode_state(
                Mode.MIXER, "cc_change", {"cc": cc_index + 1, "value": cc_value}
            )
            return True

        return False

    def _handle_pattern_mode_pad(self, pad_index: int, velocity: int) -> bool:
        """Handle pad presses in Pattern Mode."""
        row, col = self.grid.pad_position(pad_index)

        # Pattern selection across the grid
        if row < 4 and col < 8:
            track_idx = row
            pattern_idx = col
            self.set_mode_state(
                Mode.PATTERN,
                "pattern_select",
                {"track": track_idx, "pattern": pattern_idx},
            )
            return True

        return False

    def _handle_step_edit_mode_pad(self, pad_index: int, velocity: int) -> bool:
        """Handle pad presses in Step Edit Mode."""
        row, col = self.grid.pad_position(pad_index)

        if row == self.grid.STEP_ROW:
            # Step selection
            self.set_mode_state(Mode.STEP_EDIT, "selected_step", col)
            return True
        elif row == self.grid.TRACK_PATTERN_ROW and col < 4:
            # Parameter selection
            parameters = ["velocity", "gate", "probability", "micro"]
            if col < len(parameters):
                self.set_mode_state(Mode.STEP_EDIT, "edit_parameter", parameters[col])
                return True
        elif row in [self.grid.INPUT_ROW_1, self.grid.INPUT_ROW_2]:
            # Value adjustment
            value_index = col if row == self.grid.INPUT_ROW_1 else col + 16
            # Map to 0-127 range
            value = (value_index * 127) // 31
            self.set_mode_state(Mode.STEP_EDIT, "parameter_value", value)
            return True

        return False

    def _handle_settings_mode_pad(self, pad_index: int, velocity: int) -> bool:
        """Handle pad presses in Settings Mode."""
        # Settings mode typically uses encoder/button navigation
        # Pads might be used for confirmation or selection
        return False

    def get_current_note_input(self) -> Optional[Dict[str, Any]]:
        """Get current note input info for Note Mode."""
        if self.current_mode == Mode.NOTE:
            return {
                "keyboard_index": self.get_mode_state(Mode.NOTE, "last_note_played"),
                "velocity": self.get_mode_state(Mode.NOTE, "note_velocity", 85),
                "selected_track": self.get_mode_state(Mode.NOTE, "selected_track", 0),
                "selected_pattern": self.get_mode_state(
                    Mode.NOTE, "selected_pattern", 0
                ),
            }
        return None

    def get_mixer_actions(self) -> Optional[Dict[str, Any]]:
        """Get pending mixer actions."""
        if self.current_mode == Mode.MIXER:
            actions = {}

            track_action = self.get_mode_state(Mode.MIXER, "track_action")
            if track_action:
                actions["track_action"] = track_action
                self.set_mode_state(
                    Mode.MIXER, "track_action", None
                )  # Clear after reading

            scene_launch = self.get_mode_state(Mode.MIXER, "launch_scene")
            if scene_launch is not None:
                actions["launch_scene"] = scene_launch
                self.set_mode_state(Mode.MIXER, "launch_scene", None)

            cc_change = self.get_mode_state(Mode.MIXER, "cc_change")
            if cc_change:
                actions["cc_change"] = cc_change
                self.set_mode_state(Mode.MIXER, "cc_change", None)

            return actions if actions else None
        return None

    def get_pattern_actions(self) -> Optional[Dict[str, Any]]:
        """Get pending pattern actions."""
        if self.current_mode == Mode.PATTERN:
            pattern_select = self.get_mode_state(Mode.PATTERN, "pattern_select")
            if pattern_select:
                self.set_mode_state(Mode.PATTERN, "pattern_select", None)
                return {"pattern_select": pattern_select}
        return None

    def get_step_edit_actions(self) -> Optional[Dict[str, Any]]:
        """Get pending step edit actions."""
        if self.current_mode == Mode.STEP_EDIT:
            actions = {}

            selected_step = self.get_mode_state(Mode.STEP_EDIT, "selected_step")
            if selected_step is not None:
                actions["selected_step"] = selected_step

            edit_parameter = self.get_mode_state(Mode.STEP_EDIT, "edit_parameter")
            if edit_parameter:
                actions["edit_parameter"] = edit_parameter

            parameter_value = self.get_mode_state(Mode.STEP_EDIT, "parameter_value")
            if parameter_value is not None:
                actions["parameter_value"] = parameter_value
                self.set_mode_state(
                    Mode.STEP_EDIT, "parameter_value", None
                )  # Clear after reading

            return actions if actions else None
        return None

    # Menu Navigation System
    def __init_menu_system(self):
        """Initialize the settings menu system."""
        # Settings menu system
        self.settings_menu = self._create_settings_menu()
        self.menu_selected_index = 0

    def _create_settings_menu(self):
        """Create the settings menu structure."""
        return {
            "title": "Settings Menu",
            "items": [
                {
                    "name": "MIDI Channels",
                    "type": "submenu",
                    "options": ["Auto", "Manual"],
                },
                {"name": "BPM", "type": "value", "value": 120, "min": 30, "max": 300},
                {"name": "Swing", "type": "value", "value": 0, "min": 0, "max": 75},
                {
                    "name": "Quantization",
                    "type": "options",
                    "options": ["Off", "1/4", "1/8", "1/16", "1/32"],
                    "current": 3,
                },
                {
                    "name": "Scale",
                    "type": "options",
                    "options": ["Major", "Minor", "Dorian", "Mixolydian"],
                    "current": 0,
                },
                {
                    "name": "Root Note",
                    "type": "options",
                    "options": [
                        "C",
                        "C#",
                        "D",
                        "D#",
                        "E",
                        "F",
                        "F#",
                        "G",
                        "G#",
                        "A",
                        "A#",
                        "B",
                    ],
                    "current": 0,
                },
                {"name": "Save Settings", "type": "action"},
                {"name": "Load Settings", "type": "action"},
            ],
            "selected_index": 0,
        }

    def next_menu_item(self):
        """Navigate to next menu item."""
        if not hasattr(self, "settings_menu"):
            self.__init_menu_system()
        menu = self.settings_menu
        menu["selected_index"] = (menu["selected_index"] + 1) % len(menu["items"])
        print(f"Settings menu: {menu['items'][menu['selected_index']]['name']}")

    def prev_menu_item(self):
        """Navigate to previous menu item."""
        if not hasattr(self, "settings_menu"):
            self.__init_menu_system()
        menu = self.settings_menu
        menu["selected_index"] = (menu["selected_index"] - 1) % len(menu["items"])
        print(f"Settings menu: {menu['items'][menu['selected_index']]['name']}")

    def get_current_menu_item(self):
        """Get currently selected menu item."""
        if not hasattr(self, "settings_menu"):
            self.__init_menu_system()
        menu = self.settings_menu
        return menu["items"][menu["selected_index"]]

    def adjust_menu_value(self, direction: int):
        """Adjust the current menu item's value."""
        item = self.get_current_menu_item()
        if item["type"] == "value":
            # Numeric value adjustment
            current = item["value"]
            step = 1 if item["name"] == "BPM" else 1
            new_value = current + (direction * step)
            item["value"] = max(item["min"], min(item["max"], new_value))
            print(f"{item['name']}: {item['value']}")
        elif item["type"] == "options":
            # Option selection
            options = item["options"]
            current_idx = item["current"]
            new_idx = (current_idx + direction) % len(options)
            item["current"] = new_idx
            print(f"{item['name']}: {options[new_idx]}")

    def activate_menu_item(self):
        """Activate/execute current menu item."""
        item = self.get_current_menu_item()
        if item["type"] == "action":
            print(f"Executing: {item['name']}")
            # Implement action logic here
        else:
            print(f"Selected: {item['name']}")
