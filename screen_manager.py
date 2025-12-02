"""
Simple screen abstraction for AKAI Fire OLED display.
Provides consistent GUI elements and screen management.
"""

from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class MenuItem:
    """A menu item with label and optional value."""

    label: str
    value: Any = None
    action: Optional[Callable] = None


class Screen:
    """Base class for screens."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.width = canvas.WIDTH
        self.height = canvas.HEIGHT

    def clear(self):
        """Clear the screen."""
        self.canvas.clear()

    def render(self):
        """Render the screen. Override in subclasses."""
        pass


class TextScreen(Screen):
    """Simple text display screen."""

    def __init__(self, canvas, title: str = "", lines: List[str] = None):
        super().__init__(canvas)
        self.title = title
        self.lines = lines or []

    def set_title(self, title: str):
        """Set the title."""
        self.title = title

    def set_lines(self, lines: List[str]):
        """Set the text lines."""
        self.lines = lines

    def add_line(self, line: str):
        """Add a line of text."""
        self.lines.append(line)

    def render(self):
        """Render the text screen."""
        self.clear()

        y = 2

        # Title
        if self.title:
            self.canvas.fill_rect(0, 0, self.width, 10, color=0)
            self.canvas.draw_text(self.title, 2, 1, color=1)
            y = 12

        # Lines
        line_height = 9
        for i, line in enumerate(self.lines):
            if y + line_height > self.height:
                break
            self.canvas.draw_text(line, 2, y + i * line_height)


class MenuScreen(Screen):
    """Menu screen with selectable items."""

    def __init__(self, canvas, title: str = "", items: List[MenuItem] = None):
        super().__init__(canvas)
        self.title = title
        self.items = items or []
        self.selected_index = 0
        self.visible_items = 5  # Number of items visible at once

    def add_item(
        self, label: str, value: Any = None, action: Optional[Callable] = None
    ):
        """Add a menu item."""
        self.items.append(MenuItem(label, value, action))

    def select_next(self):
        """Select next item."""
        if self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)

    def select_previous(self):
        """Select previous item."""
        if self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)

    def get_selected(self) -> Optional[MenuItem]:
        """Get the selected item."""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def activate_selected(self):
        """Activate the selected item's action."""
        item = self.get_selected()
        if item and item.action:
            item.action()

    def render(self):
        """Render the menu screen."""
        self.clear()

        # Title
        if self.title:
            self.canvas.fill_rect(0, 0, self.width, 10, color=0)
            self.canvas.draw_text(self.title, 2, 1, color=1)
            y_offset = 12
        else:
            y_offset = 2

        # Calculate visible range
        if len(self.items) <= self.visible_items:
            start_idx = 0
            end_idx = len(self.items)
        else:
            # Scroll to keep selected item visible
            if self.selected_index < self.visible_items // 2:
                start_idx = 0
            elif self.selected_index >= len(self.items) - self.visible_items // 2:
                start_idx = len(self.items) - self.visible_items
            else:
                start_idx = self.selected_index - self.visible_items // 2
            end_idx = start_idx + self.visible_items

        # Draw items
        line_height = 10
        for i, idx in enumerate(range(start_idx, min(end_idx, len(self.items)))):
            y = y_offset + i * line_height

            # Highlight selected
            if idx == self.selected_index:
                self.canvas.fill_rect(0, y - 1, self.width, line_height, color=0)
                self.canvas.draw_text(f"> {self.items[idx].label}", 2, y, color=1)
            else:
                self.canvas.draw_text(f"  {self.items[idx].label}", 2, y)

        # Scroll indicators
        if start_idx > 0:
            self.canvas.draw_text("^", self.width - 8, y_offset - 2)
        if end_idx < len(self.items):
            self.canvas.draw_text("v", self.width - 8, self.height - 8)


class ProgressScreen(Screen):
    """Progress bar screen."""

    def __init__(
        self, canvas, title: str = "", min_val: float = 0, max_val: float = 100
    ):
        super().__init__(canvas)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = min_val
        self.show_percentage = True
        self.additional_text = ""

    def set_progress(self, value: float):
        """Set the progress value."""
        self.current_val = max(self.min_val, min(self.max_val, value))

    def set_additional_text(self, text: str):
        """Set additional text to display."""
        self.additional_text = text

    def render(self):
        """Render the progress screen."""
        self.clear()

        # Title
        y = 2
        if self.title:
            self.canvas.draw_text(self.title, 2, y)
            y += 12

        # Progress bar
        bar_width = self.width - 20
        bar_height = 10
        bar_x = 10
        bar_y = y + 5

        # Border
        self.canvas.draw_rect(bar_x, bar_y, bar_width, bar_height)

        # Fill
        if self.max_val > self.min_val:
            progress = (self.current_val - self.min_val) / (self.max_val - self.min_val)
            fill_width = int(bar_width * progress)
            if fill_width > 2:
                self.canvas.fill_rect(
                    bar_x + 1, bar_y + 1, fill_width - 2, bar_height - 2
                )

        # Percentage
        if self.show_percentage:
            percentage = int(progress * 100) if self.max_val > self.min_val else 0
            percent_text = f"{percentage}%"
            text_x = bar_x + bar_width // 2 - len(percent_text) * 3
            self.canvas.draw_text(percent_text, text_x, bar_y + bar_height + 3)

        # Additional text
        if self.additional_text:
            self.canvas.draw_text(self.additional_text, 2, bar_y + bar_height + 15)


class GridScreen(Screen):
    """Grid display screen for pad visualization."""

    def __init__(self, canvas, title: str = "", rows: int = 4, cols: int = 16):
        super().__init__(canvas)
        self.title = title
        self.rows = rows
        self.cols = cols
        self.grid_data = [[False for _ in range(cols)] for _ in range(rows)]

    def set_cell(self, row: int, col: int, active: bool):
        """Set a cell's state."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid_data[row][col] = active

    def toggle_cell(self, row: int, col: int):
        """Toggle a cell's state."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid_data[row][col] = not self.grid_data[row][col]

    def clear_grid(self):
        """Clear all cells."""
        self.grid_data = [[False for _ in range(self.cols)] for _ in range(self.rows)]

    def render(self):
        """Render the grid screen."""
        self.clear()

        # Title
        y_offset = 2
        if self.title:
            self.canvas.draw_text(self.title, 2, y_offset)
            y_offset += 10

        # Calculate cell size
        available_width = self.width - 4
        available_height = self.height - y_offset - 2
        cell_width = available_width // self.cols
        cell_height = available_height // self.rows

        # Draw grid
        for row in range(self.rows):
            for col in range(self.cols):
                x = 2 + col * cell_width
                y = y_offset + row * cell_height

                if self.grid_data[row][col]:
                    self.canvas.fill_rect(x, y, cell_width - 1, cell_height - 1)
                else:
                    self.canvas.draw_rect(x, y, cell_width - 1, cell_height - 1)


class ValueScreen(Screen):
    """Screen for displaying a labeled value with optional units."""

    def __init__(self, canvas, label: str = "", value: Any = "", unit: str = ""):
        super().__init__(canvas)
        self.label = label
        self.value = value
        self.unit = unit
        self.large_font = False  # TODO: Implement larger font support

    def set_value(self, value: Any, unit: str = None):
        """Set the value and optionally the unit."""
        self.value = value
        if unit is not None:
            self.unit = unit

    def render(self):
        """Render the value screen."""
        self.clear()

        # Draw border
        self.canvas.draw_rect(0, 0, self.width - 1, self.height - 1)

        # Label at top
        if self.label:
            self.canvas.draw_text(self.label, 4, 4)

        # Value in center
        value_str = f"{self.value}"
        if self.unit:
            value_str += f" {self.unit}"

        # Center the value
        text_width = len(value_str) * 6  # Approximate
        x = (self.width - text_width) // 2
        y = self.height // 2 - 4

        self.canvas.draw_text(value_str, x, y)


class ScreenManager:
    """Manages multiple screens and transitions."""

    def __init__(self, fire_instance):
        self.fire = fire_instance
        self.canvas = fire_instance.get_canvas()
        self.screens: Dict[str, Screen] = {}
        self.current_screen_name: Optional[str] = None
        self.current_screen: Optional[Screen] = None

    def add_screen(self, name: str, screen: Screen):
        """Add a screen."""
        self.screens[name] = screen

    def show_screen(self, name: str):
        """Show a specific screen."""
        if name in self.screens:
            self.current_screen_name = name
            self.current_screen = self.screens[name]
            self.render()

    def render(self):
        """Render the current screen."""
        if self.current_screen:
            self.current_screen.render()
            self.fire.render_to_display()

    def get_current_screen(self) -> Optional[Screen]:
        """Get the current screen."""
        return self.current_screen

    # Convenience methods for common screens

    def show_text(self, title: str, lines: List[str]):
        """Show a text screen."""
        screen = TextScreen(self.canvas, title, lines)
        self.add_screen("_text", screen)
        self.show_screen("_text")

    def show_message(self, message: str, duration: float = 2.0):
        """Show a temporary message."""
        lines = message.split("\n")
        self.show_text("", lines)
        if duration > 0:
            time.sleep(duration)

    def show_error(self, error: str):
        """Show an error message."""
        self.show_text("ERROR", [error])

    def show_progress(self, title: str, value: float, max_value: float = 100):
        """Show a progress bar."""
        if "_progress" not in self.screens:
            screen = ProgressScreen(self.canvas, title, 0, max_value)
            self.add_screen("_progress", screen)
        else:
            screen = self.screens["_progress"]
            screen.title = title
            screen.max_val = max_value
        screen.set_progress(value)
        self.show_screen("_progress")
