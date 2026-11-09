"""
AkaiFireApp Framework - Modular application framework for AKAI Fire applications.

This framework provides composable building blocks for creating AKAI Fire apps:
- AkaiFireApp: Base application class with lifecycle and event hooks
- EncoderMenu / MenuItem: Encoder navigation and press-to-edit state
- ModeHandler: Abstract base for mode implementations
- ModeManagerMixin: Add modal behavior to apps
- ScreenMixin: OLED screen utilities
- GridMixin: 4x16 pad grid utilities
- TransportMixin: Transport state management (play/stop/record)

Basic usage:
    from akai_fire_framework import AkaiFireApp, on

    class MyApp(AkaiFireApp):
        APP_NAME = "My App"

        @on.pad()
        def paint(self, event):
            self.fire.set_pad_color(event.pad, 0, 127, 0)

    if __name__ == "__main__":
        with MyApp() as app:
            app.run()

With mixins:
    from akai_fire_framework import (
        AkaiFireApp, ModeManagerMixin, ScreenMixin, GridMixin
    )

    class MyModalApp(AkaiFireApp, ModeManagerMixin, ScreenMixin, GridMixin):
        # Full-featured app with modes, screen helpers, and grid utilities
        pass
"""

from .app import AkaiFireApp
from .events import ButtonEvent, EncoderEvent, PadEvent, on
from .grid import GridMixin
from .menu import EncoderMenu, MenuItem
from .mode import ModeHandler, ModeManagerMixin
from .screen import ScreenMixin
from .transport import TransportMixin, TransportState

__all__ = [
    "AkaiFireApp",
    "ButtonEvent",
    "EncoderEvent",
    "EncoderMenu",
    "GridMixin",
    "MenuItem",
    "ModeHandler",
    "ModeManagerMixin",
    "PadEvent",
    "ScreenMixin",
    "TransportMixin",
    "TransportState",
    "on",
]

__version__ = "0.1.0"
