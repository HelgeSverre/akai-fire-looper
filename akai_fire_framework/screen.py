"""
Screen utilities for AKAI Fire OLED display.

Provides helper methods for common screen drawing patterns.
"""

from typing import List, Optional


class ScreenMixin:
    """
    Mixin for OLED screen management with standard layouts.

    Provides typography constants and helper methods for drawing
    consistent screens across your application.

    Usage:
        class MyApp(AkaiFireApp, ScreenMixin):
            def on_update(self, dt):
                self.canvas.clear()
                self.draw_header("MY APP", "120 BPM")
                self.draw_content_lines(["Line 1", "Line 2"])
    """

    # Typography constants (matching Canvas class)
    HEADER_HEIGHT = 16
    TEXT_MARGIN_Y = 3
    CONTENT_GAP = 2
    CONTENT_START = 18  # HEADER_HEIGHT + CONTENT_GAP
    LINE_HEIGHT = 12
    SCREEN_WIDTH = 128
    SCREEN_HEIGHT = 64

    def draw_header(self, title: str, status: str = ""):
        """
        Draw an inverted header bar with title and optional status.

        Args:
            title: Main title text (left-aligned)
            status: Optional status text (right-aligned)
        """
        # Inverted header background
        self.canvas.fill_rect(0, 0, self.SCREEN_WIDTH, self.HEADER_HEIGHT, 0)

        # Title (left-aligned, inverted color)
        self.canvas.draw_text(title, 4, self.TEXT_MARGIN_Y, color=1)

        # Status (right-aligned, inverted color)
        if status:
            # Approximate character width for positioning
            status_width = len(status) * 6
            self.canvas.draw_text(
                status, self.SCREEN_WIDTH - status_width - 4, self.TEXT_MARGIN_Y, color=1
            )

        # Bottom border line
        self.canvas.draw_line(0, self.HEADER_HEIGHT, self.SCREEN_WIDTH, self.HEADER_HEIGHT)

    def draw_content_lines(
        self, lines: List[str], start_y: Optional[int] = None, indent: int = 4
    ):
        """
        Draw multiple lines of content.

        Args:
            lines: List of text lines to draw
            start_y: Y position to start (defaults to CONTENT_START)
            indent: Left margin in pixels
        """
        y = start_y if start_y is not None else self.CONTENT_START

        for line in lines:
            if y + self.LINE_HEIGHT > self.SCREEN_HEIGHT:
                break
            self.canvas.draw_text(line, indent, y)
            y += self.LINE_HEIGHT

    def draw_startup_screen(self, version: Optional[str] = None):
        """
        Draw a standard startup screen with app name and version.

        Args:
            version: Version string (defaults to self.VERSION if available)
        """
        self.canvas.clear()

        # Center app name
        app_name = getattr(self, "APP_NAME", "AKAI Fire App")
        name_x = (self.SCREEN_WIDTH - len(app_name) * 6) // 2
        self.canvas.draw_text(app_name, max(0, name_x), 20)

        # Version below
        ver = version or getattr(self, "VERSION", "1.0")
        ver_text = f"v{ver}"
        ver_x = (self.SCREEN_WIDTH - len(ver_text) * 6) // 2
        self.canvas.draw_text(ver_text, max(0, ver_x), 36)

        # Border
        self.canvas.draw_rect(2, 2, self.SCREEN_WIDTH - 4, self.SCREEN_HEIGHT - 4)

    def draw_menu(
        self,
        title: str,
        items: List[str],
        selected_index: int,
        visible_items: int = 4,
    ):
        """
        Draw a scrollable menu.

        Args:
            title: Menu title
            items: List of menu item strings
            selected_index: Currently selected item index
            visible_items: Number of items visible at once
        """
        self.canvas.clear()
        self.draw_header(title)

        # Calculate scroll offset
        start_idx = max(0, selected_index - visible_items // 2)
        if start_idx + visible_items > len(items):
            start_idx = max(0, len(items) - visible_items)

        y = self.CONTENT_START

        for i in range(visible_items):
            idx = start_idx + i
            if idx >= len(items):
                break

            if idx == selected_index:
                # Highlight selected item
                self.canvas.fill_rect(0, y - 1, self.SCREEN_WIDTH, self.LINE_HEIGHT, 0)
                self.canvas.draw_text(f"> {items[idx]}", 4, y, color=1)
            else:
                self.canvas.draw_text(f"  {items[idx]}", 4, y)

            y += self.LINE_HEIGHT

        # Scroll indicators
        if start_idx > 0:
            self.canvas.draw_text("^", 120, self.CONTENT_START)
        if start_idx + visible_items < len(items):
            self.canvas.draw_text("v", 120, self.SCREEN_HEIGHT - 10)

    def draw_value_display(
        self,
        title: str,
        value: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        current_val: Optional[float] = None,
    ):
        """
        Draw a value with optional progress bar.

        Args:
            title: Title text
            value: Value to display (as string)
            min_val: Minimum value (for progress bar)
            max_val: Maximum value (for progress bar)
            current_val: Current numeric value (for progress bar)
        """
        self.canvas.clear()
        self.draw_header(title)

        # Large value display
        value_x = (self.SCREEN_WIDTH - len(value) * 8) // 2
        self.canvas.draw_text(value, max(4, value_x), 26)

        # Optional progress bar
        if min_val is not None and max_val is not None and current_val is not None:
            bar_y = 46
            bar_height = 8
            bar_margin = 8

            try:
                normalized = (current_val - min_val) / (max_val - min_val)
                normalized = max(0.0, min(1.0, normalized))
            except ZeroDivisionError:
                normalized = 0.0

            bar_width = int(normalized * (self.SCREEN_WIDTH - bar_margin * 2))

            # Bar outline
            self.canvas.draw_rect(
                bar_margin, bar_y, self.SCREEN_WIDTH - bar_margin * 2, bar_height
            )
            # Bar fill
            if bar_width > 0:
                self.canvas.fill_rect(bar_margin, bar_y, bar_width, bar_height)

    def draw_split_screen(
        self, title: str, left_content: List[str], right_content: List[str]
    ):
        """
        Draw a split-screen layout.

        Args:
            title: Header title
            left_content: Lines for left half
            right_content: Lines for right half
        """
        self.canvas.clear()
        self.draw_header(title)

        mid_x = self.SCREEN_WIDTH // 2

        # Divider line
        self.canvas.draw_line(
            mid_x, self.HEADER_HEIGHT, mid_x, self.SCREEN_HEIGHT
        )

        # Left content
        y = self.CONTENT_START
        for line in left_content[:4]:
            if y + self.LINE_HEIGHT > self.SCREEN_HEIGHT:
                break
            # Truncate to fit half screen
            self.canvas.draw_text(line[:10], 4, y)
            y += self.LINE_HEIGHT

        # Right content
        y = self.CONTENT_START
        for line in right_content[:4]:
            if y + self.LINE_HEIGHT > self.SCREEN_HEIGHT:
                break
            self.canvas.draw_text(line[:10], mid_x + 4, y)
            y += self.LINE_HEIGHT
