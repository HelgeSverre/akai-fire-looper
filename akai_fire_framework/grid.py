"""
Grid utilities for AKAI Fire 4x16 pad grid.

Provides coordinate conversion, color management, and row assignments.
"""

from typing import Tuple, List, Optional


class GridMixin:
    """
    Mixin for 4x16 pad grid management.

    Provides utilities for working with the 64-pad grid including:
    - Coordinate conversion (index <-> row/col)
    - Standard row assignments
    - Color utilities with brightness levels
    - Batch pad updates

    Usage:
        class MyApp(AkaiFireApp, GridMixin):
            def on_pad_press(self, pad, velocity):
                row, col = self.pad_position(pad)
                if row == self.ROW_STEP:
                    self.toggle_step(col)
    """

    # Grid dimensions
    ROWS = 4
    COLS = 16
    TOTAL_PADS = 64

    # Standard row assignments (customize in subclass if needed)
    ROW_STEP = 0       # Step sequencer
    ROW_TRACK = 1      # Track/pattern selection
    ROW_INPUT_1 = 2    # Keyboard/input (upper)
    ROW_INPUT_2 = 3    # Keyboard/input (lower)

    # Default track colors (can be overridden)
    TRACK_COLORS = [
        (127, 0, 0),      # Track 1: Red
        (0, 127, 0),      # Track 2: Green
        (0, 0, 127),      # Track 3: Blue
        (127, 127, 0),    # Track 4: Yellow
    ]

    # Brightness levels
    BRIGHTNESS = {
        "off": 0,
        "dim": 25,
        "medium": 75,
        "bright": 127,
    }

    # Common colors
    COLORS = {
        "off": (0, 0, 0),
        "red": (127, 0, 0),
        "green": (0, 127, 0),
        "blue": (0, 0, 127),
        "yellow": (127, 127, 0),
        "cyan": (0, 127, 127),
        "magenta": (127, 0, 127),
        "white": (127, 127, 127),
        "orange": (127, 64, 0),
        "purple": (64, 0, 127),
    }

    # =========================================================================
    # Coordinate Conversion
    # =========================================================================

    def pad_index(self, row: int, col: int) -> int:
        """
        Convert (row, col) to pad index.

        Args:
            row: Row number (0-3)
            col: Column number (0-15)

        Returns:
            Pad index (0-63)
        """
        return row * self.COLS + col

    def pad_position(self, index: int) -> Tuple[int, int]:
        """
        Convert pad index to (row, col).

        Args:
            index: Pad index (0-63)

        Returns:
            Tuple of (row, col)
        """
        return (index // self.COLS, index % self.COLS)

    def is_valid_pad(self, index: int) -> bool:
        """Check if pad index is valid (0-63)."""
        return 0 <= index < self.TOTAL_PADS

    def is_valid_position(self, row: int, col: int) -> bool:
        """Check if row/col position is valid."""
        return 0 <= row < self.ROWS and 0 <= col < self.COLS

    # =========================================================================
    # Pad Color Control
    # =========================================================================

    def set_pad(
        self, index: int, color: Tuple[int, int, int], brightness: str = "bright"
    ):
        """
        Set a single pad color with brightness.

        Args:
            index: Pad index (0-63)
            color: RGB tuple (0-127 each)
            brightness: "off", "dim", "medium", or "bright"
        """
        if not self.is_valid_pad(index):
            return

        adjusted = self.apply_brightness(color, brightness)
        self.fire.set_pad_color(index, *adjusted)

    def set_pad_at(
        self,
        row: int,
        col: int,
        color: Tuple[int, int, int],
        brightness: str = "bright",
    ):
        """
        Set pad color by row/col position.

        Args:
            row: Row number (0-3)
            col: Column number (0-15)
            color: RGB tuple
            brightness: Brightness level
        """
        if self.is_valid_position(row, col):
            self.set_pad(self.pad_index(row, col), color, brightness)

    def set_row(
        self,
        row: int,
        colors: List[Tuple[int, int, int]],
        brightness: str = "bright",
    ):
        """
        Set an entire row of pads.

        Args:
            row: Row number (0-3)
            colors: List of RGB tuples (up to 16)
            brightness: Brightness level for all pads
        """
        for col, color in enumerate(colors[: self.COLS]):
            self.set_pad_at(row, col, color, brightness)

    def set_column(
        self,
        col: int,
        colors: List[Tuple[int, int, int]],
        brightness: str = "bright",
    ):
        """
        Set an entire column of pads.

        Args:
            col: Column number (0-15)
            colors: List of RGB tuples (up to 4)
            brightness: Brightness level for all pads
        """
        for row, color in enumerate(colors[: self.ROWS]):
            self.set_pad_at(row, col, color, brightness)

    def fill_row(
        self, row: int, color: Tuple[int, int, int], brightness: str = "bright"
    ):
        """Fill an entire row with one color."""
        for col in range(self.COLS):
            self.set_pad_at(row, col, color, brightness)

    def clear_row(self, row: int):
        """Clear an entire row (set to off)."""
        self.fill_row(row, self.COLORS["off"])

    def clear_grid(self):
        """Clear all pad colors."""
        self.fire.clear_all_pads()

    # =========================================================================
    # Color Utilities
    # =========================================================================

    def apply_brightness(
        self, color: Tuple[int, int, int], brightness: str = "bright"
    ) -> Tuple[int, int, int]:
        """
        Apply a brightness level to a color.

        Args:
            color: RGB tuple (0-127 each)
            brightness: "off", "dim", "medium", or "bright"

        Returns:
            Adjusted RGB tuple
        """
        level = self.BRIGHTNESS.get(brightness, 127)
        if level == 0:
            return (0, 0, 0)
        return tuple(c * level // 127 for c in color)

    def get_track_color(self, track: int, brightness: str = "bright") -> Tuple[int, int, int]:
        """
        Get the color for a track.

        Args:
            track: Track index (0-3)
            brightness: Brightness level

        Returns:
            RGB tuple
        """
        if 0 <= track < len(self.TRACK_COLORS):
            return self.apply_brightness(self.TRACK_COLORS[track], brightness)
        return self.COLORS["off"]

    def color_by_name(
        self, name: str, brightness: str = "bright"
    ) -> Tuple[int, int, int]:
        """
        Get a color by name with brightness.

        Args:
            name: Color name (e.g., "red", "green")
            brightness: Brightness level

        Returns:
            RGB tuple
        """
        color = self.COLORS.get(name, self.COLORS["off"])
        return self.apply_brightness(color, brightness)

    # =========================================================================
    # Common Patterns
    # =========================================================================

    def highlight_step(self, step: int, color: Tuple[int, int, int] = None):
        """
        Highlight a step in the step row (row 0).

        Args:
            step: Step index (0-15)
            color: Optional color (defaults to white)
        """
        if 0 <= step < self.COLS:
            color = color or self.COLORS["white"]
            self.set_pad_at(self.ROW_STEP, step, color)

    def show_track_selection(self, selected_track: int):
        """
        Update track row to show selected track.

        Args:
            selected_track: Currently selected track (0-3)
        """
        for track in range(4):
            brightness = "bright" if track == selected_track else "dim"
            self.set_pad_at(self.ROW_TRACK, track, self.TRACK_COLORS[track], brightness)
