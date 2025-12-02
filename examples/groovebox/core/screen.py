from typing import Any


class Screen:
    """Wrapper for OLED display operations"""

    def __init__(self, width: int = 128, height: int = 64):
        self.width = width
        self.height = height
        self.buffer = []  # Could use actual pixel buffer

    def clear(self):
        """Clear screen buffer"""
        self.buffer = []

    def draw_header(self, text: str):
        """Draw standard header with background"""
        # Implementation using Fire canvas primitives
        pass

    def draw_param(self, name: str, value: Any, y: int):
        """Draw parameter name: value pair"""
        # Implementation
        pass

    def draw_progress(self, value: float, y: int):
        """Draw progress bar"""
        # Implementation
        pass
