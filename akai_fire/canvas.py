"""Canvas abstraction for the AKAI Fire OLED (128x64 monochrome).

Kept in its own module so importing ``akai_fire`` (or
``akai_fire_testing``, which only needs ``akai_fire.device``) does not
pull in Pillow. PIL is only loaded when Canvas is actually used.
"""

from typing import Optional, Union

from PIL import Image, ImageDraw, ImageFont


class Canvas:
    WIDTH, HEIGHT = 128, 64

    # Typography constants for consistent spacing
    HEADER_HEIGHT = 16  # Standard header height
    TEXT_MARGIN_Y = 3  # Top margin for header text
    CONTENT_GAP = 2  # Gap between header and content
    CONTENT_START = HEADER_HEIGHT + CONTENT_GAP  # Y=18

    def __init__(self):
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 1)
        self.draw = ImageDraw.Draw(self.image)

    def clone(self):
        """Create a copy of the current canvas."""
        cloned_canvas = Canvas()
        cloned_canvas.image = self.image.copy()
        cloned_canvas.draw = ImageDraw.Draw(cloned_canvas.image)
        return cloned_canvas

    def clear(self, color: int = 1):
        """Clear the canvas."""
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), color)
        self.draw = ImageDraw.Draw(self.image)

    def get_pixel(self, x, y) -> Optional[int]:
        """Get a pixel from the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            return self.image.getpixel((x, y))
        return None

    def set_pixel(self, x, y, color: int = 0):
        """Set a pixel on the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.image.putpixel((x, y), color)

    def draw_rect(self, x, y, width, height, color: int = 0):
        """Draw rectangle outline."""
        if width <= 0 or height <= 0:
            return
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], outline=color)

    def fill_rect(self, x, y, width, height, color: int = 0):
        """Draw filled rectangle."""
        if width <= 0 or height <= 0:
            return
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], fill=color)

    def draw_text(self, text, x, y, font=None, color: int = 0):
        """Draw text."""
        if font is None:
            font = ImageFont.load_default()

        self.draw.text((x, y), text, fill=color, font=font)

    def draw_border(self, thickness: int = 1, color: int = 0):
        """Draw a border around the entire canvas."""
        for i in range(thickness):
            self.draw_rect(i, i, self.WIDTH - 2 * i, self.HEIGHT - 2 * i, color)

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a horizontal line using PIL's line method for efficiency."""
        if length > 0 and 0 <= y < self.HEIGHT:
            x_end = min(x + length - 1, self.WIDTH - 1)
            self.draw.line([(x, y), (x_end, y)], fill=color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a vertical line using PIL's line method for efficiency."""
        if length > 0 and 0 <= x < self.WIDTH:
            y_end = min(y + length - 1, self.HEIGHT - 1)
            self.draw.line([(x, y), (x, y_end)], fill=color)

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Draw a rectangle."""
        self.draw_horizontal_line(x, y, width, color)
        self.draw_horizontal_line(x, y + height - 1, width, color)
        self.draw_vertical_line(x, y, height, color)
        self.draw_vertical_line(x + width - 1, y, height, color)

    def fill_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Fill a rectangle."""
        for i in range(height):
            self.draw_horizontal_line(x, y + i, width, color)

    def draw_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Draw a circle using PIL's ellipse method."""
        bbox = [x0 - radius, y0 - radius, x0 + radius, y0 + radius]
        self.draw.ellipse(bbox, outline=color)

    def fill_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Fill a circle using PIL's ellipse method."""
        bbox = [x0 - radius, y0 - radius, x0 + radius, y0 + radius]
        self.draw.ellipse(bbox, fill=color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 0):
        """Draw a line using Bresenham's line algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_page(self, title: str, lines: list[str], header_inverted: bool = True):
        """
        Draw a basic page layout with header and content lines.

        Args:
            title: Title text for the header
            lines: List of text lines to display below header
            header_inverted: If True, header is black with white text
        """
        # Header with optional inversion
        if header_inverted:
            self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)
        else:
            self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=0)
            self.draw_horizontal_line(0, self.HEADER_HEIGHT, self.WIDTH, color=0)

        # Content lines with proper spacing
        y_offset = self.CONTENT_START  # Start below header
        line_height = 12  # Standard line height

        for i, line in enumerate(lines):
            if y_offset + line_height > self.HEIGHT:
                break  # Don't draw beyond screen bounds
            self.draw_text(line, 2, y_offset + (i * line_height))

    def draw_value_page(
        self,
        title: str,
        value: Union[int, float, str],
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        show_bar: bool = True,
    ):
        """
        Draw a page showing a value with optional bar visualization.

        Args:
            title: Title text for the header
            value: Current value to display
            min_val: Minimum value for bar scaling (if showing bar)
            max_val: Maximum value for bar scaling (if showing bar)
            show_bar: Whether to show a progress bar
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)

        # Large value display
        value_text = str(value)
        self.draw_text(value_text, 2, 20, color=0)

        # Optional bar visualization
        if show_bar and min_val is not None and max_val is not None:
            bar_y = 40
            bar_height = 8
            if max_val == min_val:
                # Degenerate range: full bar only when value meets it.
                normalized = 1.0 if float(value) >= float(max_val) else 0.0
            else:
                normalized = (float(value) - min_val) / (max_val - min_val)
            normalized = max(0.0, min(1.0, normalized))
            bar_width = int(normalized * (self.WIDTH - 4))

            # Bar outline
            self.draw_rect(2, bar_y, self.WIDTH - 4, bar_height)
            # Bar fill
            self.fill_rect(2, bar_y, bar_width, bar_height)

    def draw_menu(self, title: str, items: list[str], selected_index: int):
        """
        Draw a menu with selectable items.

        Args:
            title: Title text for the header
            items: List of menu items
            selected_index: Index of currently selected item
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)

        # Menu items
        y_offset = self.CONTENT_START
        line_height = 12

        visible_items = min(4, len(items))  # Show max 4 items at once
        start_idx = max(0, min(selected_index - 1, len(items) - visible_items))

        for i in range(visible_items):
            idx = start_idx + i
            if idx >= len(items):
                break

            # Highlight selected item
            if idx == selected_index:
                self.fill_rect(
                    0, y_offset + (i * line_height), self.WIDTH, line_height, color=0
                )
                self.draw_text(items[idx], 4, y_offset + (i * line_height), color=1)
            else:
                self.draw_text(items[idx], 4, y_offset + (i * line_height))

    def draw_grid_info(
        self, title: str, rows: int, cols: int, cell_info: list[tuple[int, int, str]]
    ):
        """
        Draw information about a grid layout (useful for pad layouts).

        Args:
            title: Title text for the header
            rows: Number of rows in grid
            cols: Number of columns in grid
            cell_info: List of (row, col, text) tuples showing cell contents
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Draw grid outline
        cell_width = (self.WIDTH - 4) // cols
        cell_height = (self.HEIGHT - 20) // rows

        for row in range(rows + 1):
            y = 16 + (row * cell_height)
            self.draw_horizontal_line(2, y, self.WIDTH - 4)

        for col in range(cols + 1):
            x = 2 + (col * cell_width)
            self.draw_vertical_line(x, 16, (rows * cell_height))

        # Draw cell contents
        for row, col, text in cell_info:
            x = 2 + (col * cell_width) + 2
            y = 16 + (row * cell_height) + 2
            self.draw_text(text, x, y)

    def draw_split_screen(
        self, title: str, left_content: list[str], right_content: list[str]
    ):
        """
        Draw a screen split into two columns.

        Args:
            title: Title text for the header
            left_content: List of text lines for left column
            right_content: List of text lines for right column
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Split line
        mid_x = self.WIDTH // 2
        self.draw_vertical_line(mid_x, 15, self.HEIGHT - 15)

        # Left content
        y_offset = 15
        line_height = 12
        for i, line in enumerate(left_content):
            if y_offset + (i * line_height) + line_height > self.HEIGHT:
                break
            self.draw_text(line, 2, y_offset + (i * line_height))

        # Right content
        for i, line in enumerate(right_content):
            if y_offset + (i * line_height) + line_height > self.HEIGHT:
                break
            self.draw_text(line, mid_x + 2, y_offset + (i * line_height))
