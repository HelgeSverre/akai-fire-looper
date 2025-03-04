from enum import Enum, auto
from typing import Optional, Dict

from core.screen import Screen
from core.settings import AppSettings
from core.view import View
from examples.groovebox.views.main_view import MainView


# --- Core Types ---
class ViewID(Enum):
    MAIN = auto()
    PATTERN = auto()
    EUCLIDEAN = auto()
    SETTINGS = auto()
    MONITOR = auto()


# --- Main App ---
class MainApp:
    def __init__(self):
        # Core state
        self.settings = AppSettings()
        self.current_view: Optional[View] = None
        self.views: Dict[ViewID, View] = {}
        self.current_bar = 0
        self.current_step = 0

        # Hardware interface
        self.hardware = None  # AkaiFire instance
        self.screen = Screen()

        # Modifier state
        self.shift_held = False
        self.alt_held = False

        self._setup_views()
        self._setup_hardware()

    def _setup_views(self):
        """Initialize all views"""
        self.views[ViewID.MAIN] = MainView(self)
        # Add other views...

        self.set_view(ViewID.MAIN)

    def _setup_hardware(self):
        """Setup hardware and controls"""
        # Implementation
        pass

    def set_view(self, view_id: ViewID):
        """Switch to a different view"""
        if self.current_view:
            self.current_view.deactivate()

        self.current_view = self.views[view_id]
        self.current_view.activate()

    def run(self):
        """Main application loop"""
        try:
            while True:
                # Process MIDI
                # Process timing
                # Update display if needed
                pass
        finally:
            # Cleanup
            pass


if __name__ == "__main__":
    app = MainApp()
    app.run()
