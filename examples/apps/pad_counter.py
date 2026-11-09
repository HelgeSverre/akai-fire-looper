#!/usr/bin/env python3
"""
Minimal example using AkaiFireApp framework.

This demonstrates the simplest possible app using just the base class.
Press any pad to increment a counter and light up that pad.

Usage:
    uv run python -m examples.apps.pad_counter
"""

from akai_fire.constants import BUTTON_STOP
from akai_fire_framework import AkaiFireApp, on


class PadCounterApp(AkaiFireApp):
    """Minimal app - counts pad presses."""

    APP_NAME = "Pad Counter"
    VERSION = "1.0"

    def on_init(self):
        """Initialize counter."""
        self.count = 0
        self.last_pad = None

    def on_start(self):
        """Show initial screen."""
        self.canvas.clear()
        self.canvas.draw_text_fitted("Press any pad!", 15, 25)
        self.canvas.draw_text_fitted("Count: 0", 35, 45)

    @on.pad()
    def count_pad(self, event):
        """Increment the counter and light the selected pad on the frame thread."""
        pad = event.pad
        self.count += 1

        # Clear previous pad
        if self.last_pad is not None:
            self.fire.set_pad_color(self.last_pad, 0, 0, 0)

        # Light new pad green
        self.fire.set_pad_color(pad, 0, 127, 0)
        self.last_pad = pad

        # Update display
        self.canvas.clear()
        self.canvas.draw_text_fitted("Pad Counter", 25, 10)
        self.canvas.draw_text_fitted(f"Pad: {pad}", 40, 28)
        self.canvas.draw_text_fitted(f"Count: {self.count}", 35, 45)

    @on.button(BUTTON_STOP)
    def stop(self, event):
        self.quit()


if __name__ == "__main__":
    print("Starting Pad Counter...")
    print("Press any pad to count. Press STOP to quit.")

    with PadCounterApp() as app:
        app.run()
