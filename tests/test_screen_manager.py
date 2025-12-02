import unittest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screen_manager import (
    ScreenManager,
    TextScreen,
    MenuScreen,
    ProgressScreen,
    GridScreen,
    ValueScreen,
)


class MockAkaiFire:
    """Mock AkaiFire for testing"""

    def __init__(self):
        self.canvas = MagicMock()
        self.canvas.clear = Mock()
        self.canvas.draw_text = Mock()
        self.canvas.draw_rect = Mock()
        self.canvas.fill_rect = Mock()
        self.canvas.draw_line = Mock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.render_to_display = Mock()

    def get_canvas(self):
        return self.canvas


class TestScreenManager(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.manager = ScreenManager(self.fire)

    def test_initialization(self):
        """Test screen manager initialization"""
        self.assertEqual(self.manager.fire, self.fire)
        self.assertIsNone(self.manager.current_screen)
        self.assertEqual(len(self.manager.screens), 0)

    def test_add_screen(self):
        """Test adding screens"""
        screen = TextScreen(self.fire.canvas, "Test")
        self.manager.add_screen("test", screen)

        self.assertIn("test", self.manager.screens)
        self.assertEqual(self.manager.screens["test"], screen)

    def test_switch_screen(self):
        """Test switching between screens"""
        screen1 = TextScreen(self.fire.canvas, "Screen 1")
        screen2 = TextScreen(self.fire.canvas, "Screen 2")

        self.manager.add_screen("s1", screen1)
        self.manager.add_screen("s2", screen2)

        self.manager.show_screen("s1")
        self.assertEqual(self.manager.current_screen_name, "s1")

        self.manager.show_screen("s2")
        self.assertEqual(self.manager.current_screen_name, "s2")

    def test_update_current_screen(self):
        """Test updating current screen"""
        screen = TextScreen(self.fire.canvas, "Test")
        self.manager.add_screen("test", screen)
        self.manager.show_screen("test")

        # ScreenManager doesn't have update(), it has render()
        self.manager.render()
        self.fire.canvas.clear.assert_called()
        self.fire.render_to_display.assert_called()

    def test_get_screen(self):
        """Test getting screens"""
        screen = TextScreen(self.fire.canvas, "Test")
        self.manager.add_screen("test", screen)

        # ScreenManager doesn't have get_screen method, access directly
        self.assertIn("test", self.manager.screens)
        self.assertEqual(self.manager.screens["test"], screen)

        # Non-existent screen
        self.assertNotIn("nonexistent", self.manager.screens)


class TestTextScreen(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.screen = TextScreen(
            self.canvas, title="Hello World", lines=["Line 1", "Line 2"]
        )

    def test_initialization(self):
        """Test text screen initialization"""
        self.assertEqual(self.screen.title, "Hello World")
        self.assertEqual(self.screen.lines, ["Line 1", "Line 2"])

    def test_render(self):
        """Test text screen rendering"""
        self.screen.render()

        # Should have cleared and drawn text
        self.canvas.clear.assert_called()
        self.canvas.draw_text.assert_called()

    def test_set_text(self):
        """Test updating text"""
        self.screen.set_title("New Title")
        self.assertEqual(self.screen.title, "New Title")

        self.screen.set_lines(["New Line"])
        self.assertEqual(self.screen.lines, ["New Line"])


class TestMenuScreen(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.items = ["Option 1", "Option 2", "Option 3"]
        self.screen = MenuScreen(self.canvas, title="Menu", items=[])
        # Add items after creation
        for item in self.items:
            self.screen.add_item(item)

    def test_initialization(self):
        """Test menu screen initialization"""
        self.assertEqual(len(self.screen.items), 3)
        self.assertEqual(self.screen.items[0].label, "Option 1")
        self.assertEqual(self.screen.items[1].label, "Option 2")
        self.assertEqual(self.screen.items[2].label, "Option 3")
        self.assertEqual(self.screen.selected_index, 0)

    def test_navigation(self):
        """Test menu navigation"""
        # Move down
        self.screen.select_next()
        self.assertEqual(self.screen.selected_index, 1)

        self.screen.select_next()
        self.assertEqual(self.screen.selected_index, 2)

        # Wrap around
        self.screen.select_next()
        self.assertEqual(self.screen.selected_index, 0)

        # Move up
        self.screen.select_previous()
        self.assertEqual(self.screen.selected_index, 2)

    def test_render(self):
        """Test menu rendering"""
        self.screen.render()

        # Should have cleared and drawn menu
        self.canvas.clear.assert_called()
        # Should have drawn text for items
        self.assertGreater(self.canvas.draw_text.call_count, 0)

    def test_get_selected(self):
        """Test getting selected item"""
        selected = self.screen.get_selected()
        self.assertEqual(selected.label, "Option 1")

        self.screen.select_next()
        selected = self.screen.get_selected()
        self.assertEqual(selected.label, "Option 2")


class TestProgressScreen(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.screen = ProgressScreen(self.canvas, "Loading")
        self.screen.set_progress(50)  # 50 out of default 100

    def test_initialization(self):
        """Test progress screen initialization"""
        self.assertEqual(self.screen.title, "Loading")
        self.assertEqual(self.screen.current_val, 50)

    def test_set_progress(self):
        """Test setting progress"""
        self.screen.set_progress(75)
        self.assertEqual(self.screen.current_val, 75)

        # Clamp to valid range
        self.screen.set_progress(150)
        self.assertEqual(self.screen.current_val, 100)

        self.screen.set_progress(-50)
        self.assertEqual(self.screen.current_val, 0)

    def test_render(self):
        """Test progress bar rendering"""
        self.screen.render()

        # Should have cleared and drawn progress
        self.canvas.clear.assert_called()
        # Should draw text and shapes
        self.assertGreater(self.canvas.draw_text.call_count, 0)


class TestGridScreen(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.screen = GridScreen(self.canvas, title="Grid", rows=4, cols=16)

    def test_initialization(self):
        """Test grid screen initialization"""
        self.assertEqual(self.screen.rows, 4)
        self.assertEqual(self.screen.cols, 16)
        self.assertEqual(len(self.screen.grid_data), 4)
        self.assertEqual(len(self.screen.grid_data[0]), 16)

    def test_set_cell(self):
        """Test setting grid cells"""
        self.screen.set_cell(1, 2, True)
        self.assertEqual(self.screen.grid_data[1][2], True)

    def test_render(self):
        """Test grid rendering"""
        # Set some cells
        self.screen.set_cell(0, 0, True)
        self.screen.set_cell(1, 1, True)

        self.screen.render()

        # Should have cleared and drawn grid
        self.canvas.clear.assert_called()


class TestValueScreen(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.canvas.WIDTH = 128
        self.canvas.HEIGHT = 64
        self.screen = ValueScreen(self.canvas, label="Volume", value=75, unit="%")

    def test_initialization(self):
        """Test value screen initialization"""
        self.assertEqual(self.screen.label, "Volume")
        self.assertEqual(self.screen.value, 75)
        self.assertEqual(self.screen.unit, "%")

    def test_set_value(self):
        """Test setting values"""
        self.screen.set_value(100)
        self.assertEqual(self.screen.value, 100)

        # Set value with new unit
        self.screen.set_value(50, "dB")
        self.assertEqual(self.screen.value, 50)
        self.assertEqual(self.screen.unit, "dB")

    def test_render(self):
        """Test value display rendering"""
        self.screen.render()

        # Should have cleared and drawn border
        self.canvas.clear.assert_called()
        self.canvas.draw_rect.assert_called()
        # Should draw label and value
        self.assertGreaterEqual(self.canvas.draw_text.call_count, 2)


class TestScreenTransitions(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.manager = ScreenManager(self.fire)

        # Add multiple screens
        menu = MenuScreen(self.fire.canvas, title="Main Menu")
        menu.add_item("Play")
        menu.add_item("Settings")
        menu.add_item("Exit")
        self.manager.add_screen("menu", menu)
        self.manager.add_screen("loading", ProgressScreen(self.fire.canvas, "Loading"))
        self.manager.add_screen(
            "grid", GridScreen(self.fire.canvas, title="Grid", rows=4, cols=16)
        )

    def test_screen_lifecycle(self):
        """Test screen switching lifecycle"""
        # Start with menu
        self.manager.show_screen("menu")

        # Switch to loading
        self.manager.show_screen("loading")

        # Update progress
        loading = self.manager.screens["loading"]
        loading.set_progress(50)
        self.manager.render()

        # Switch to grid
        self.manager.show_screen("grid")
        grid = self.manager.screens["grid"]
        grid.set_cell(0, 0, True)
        self.manager.render()

        # All transitions should work without errors
        self.assertEqual(self.manager.current_screen_name, "grid")


if __name__ == "__main__":
    unittest.main()
