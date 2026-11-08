"""
Base application class for AKAI Fire applications.

Provides the minimal foundation for any AKAI Fire app:
- Hardware initialization (auto-detects mock vs real)
- Main loop with configurable FPS
- Lifecycle hooks (on_init, on_start, on_update, on_stop)
- Event hooks (on_pad_press, on_button_press, on_encoder_turn)
- Context manager support
"""

import math
import time
from functools import partial

from akai_fire import get_akai_fire
from akai_fire_framework._subscriptions import _EventSubscriptions


class AkaiFireApp:
    """
    Base application class for AKAI Fire apps.

    Subclass this to create your own app. Override the lifecycle hooks
    and event handlers as needed.

    Example:
        class MyApp(AkaiFireApp):
            APP_NAME = "My App"

            def on_init(self):
                self.counter = 0

            def on_pad_press(self, pad, velocity):
                self.counter += 1
                self.fire.set_pad_color(pad, 0, 127, 0)
                self.canvas.clear()
                self.canvas.draw_text(f"Count: {self.counter}", 30, 30)

        if __name__ == "__main__":
            with MyApp() as app:
                app.run()
    """

    # Class-level configuration (override in subclass)
    STARTUP_SECONDS: float = 0.0
    FPS: int = 30
    APP_NAME: str = "AKAI Fire App"
    VERSION: str = "1.0"

    def __init__(self, fire=None):
        """
        Initialize the application.

        Args:
            fire: Optional AkaiFire instance. If None, uses get_akai_fire()
                  which auto-detects hardware or falls back to mock.
        """
        self.fire = fire if fire is not None else get_akai_fire()
        self._owns_fire = fire is None  # Track if we need to close it

        self.running = False
        self._last_update_time = 0.0
        self._shutdown = False
        self._event_subscriptions = _EventSubscriptions()

        # User state must exist before decorators start MIDI polling.
        try:
            self.canvas = self.fire.get_canvas()
            self.on_init()
            self._setup_event_handlers()
        except Exception:
            try:
                self._event_subscriptions.close()
            finally:
                if self._owns_fire:
                    self.fire.close()
            raise

    def _setup_event_handlers(self):
        """Wire up hardware events to instance methods as one owned batch."""
        self._event_subscriptions.bind_all(
            [
                (
                    self.fire.on_pad(),
                    self.fire.remove_global_listener,
                    lambda pad, velocity: (
                        self.on_pad_press(pad, velocity) if velocity > 0 else None
                    ),
                ),
                (
                    self.fire.on_button(),
                    partial(self.fire.remove_button_listener, "global"),
                    lambda button, event: self.on_button_press(button, event),
                ),
                (
                    self.fire.on_rotary_turn(),
                    partial(self.fire.remove_rotary_listener, "global"),
                    lambda encoder, direction, velocity: self.on_encoder_turn(
                        encoder, direction, velocity
                    ),
                ),
            ]
        )

    # =========================================================================
    # Lifecycle Hooks (override in subclass)
    # =========================================================================

    def on_init(self):
        """Called once during __init__, after hardware is connected."""
        pass

    def on_start(self):
        """Called once when run() begins, before the main loop."""
        pass

    def on_update(self, dt: float):
        """
        Called each frame at the configured FPS.

        Args:
            dt: Time elapsed since last update in seconds.
        """
        pass

    def on_stop(self):
        """Called once during shutdown, before hardware is released."""
        pass

    # =========================================================================
    # Event Hooks (override in subclass)
    # =========================================================================

    def on_pad_press(self, pad: int, velocity: int):
        """
        Called when any pad is pressed.

        Args:
            pad: Pad index (0-63)
            velocity: Press velocity (0-127)
        """
        pass

    def on_button_press(self, button_id: int, event: str):
        """
        Called when any button is pressed or released.

        Args:
            button_id: Button constant (e.g., fire.BUTTON_PLAY)
            event: "press" or "release"
        """
        pass

    def on_encoder_turn(self, encoder_id: int, direction: str, velocity: int):
        """
        Called when any encoder is turned.

        Args:
            encoder_id: Encoder constant (e.g., fire.ROTARY_VOLUME)
            direction: "clockwise" or "counterclockwise"
            velocity: Turn speed (1-127)
        """
        pass

    # =========================================================================
    # Main Loop
    # =========================================================================

    def run(self, *, duration: float | None = None):
        """
        Main application loop.

        Runs until quit(), window close, or the optional duration in seconds.
        Duration is useful for bounded smoke runs; it excludes the startup banner.
        """
        if self.FPS <= 0:
            raise ValueError("FPS must be positive")
        if duration is not None and (duration < 0 or not math.isfinite(duration)):
            raise ValueError("duration must be finite and non-negative")
        if self._shutdown:
            raise RuntimeError("Application has shut down")
        if self.running:
            raise RuntimeError("Application is already running")
        self.running = True
        try:
            self._show_startup_screen()
            # The banner must not erase the application's initial display.
            self.on_start()
            self.fire.start_listening()
            self._last_update_time = time.monotonic()
            deadline = None if duration is None else self._last_update_time + duration
            while self.running:
                current_time = time.monotonic()
                if deadline is not None and current_time >= deadline:
                    break
                dt = current_time - self._last_update_time

                # Update at configured FPS
                if dt >= 1.0 / self.FPS:
                    self.on_update(dt)
                    self.fire.render_to_display()
                    self._last_update_time = current_time

                # Process mock events if in mock mode
                if hasattr(self.fire, "process_events"):
                    if not self.fire.process_events():
                        break

                # Short sleep to prevent CPU spinning
                time.sleep(0.001)

        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _show_startup_screen(self):
        """Display startup screen briefly."""
        if self.STARTUP_SECONDS <= 0:
            return
        self.canvas.clear()
        self.canvas.draw_text(self.APP_NAME, 20, 20)
        self.canvas.draw_text(f"v{self.VERSION}", 45, 40)
        self.fire.render_to_display()
        time.sleep(self.STARTUP_SECONDS)
        self.canvas.clear()

    def shutdown(self):
        """Clean shutdown of the application."""
        if self._shutdown:
            return
        self._shutdown = True
        self.running = False
        try:
            try:
                self._event_subscriptions.close()
            finally:
                try:
                    self.on_stop()
                finally:
                    # Instrument cleanup can fail after unplugging. The controller
                    # still needs its own cleanup, including when it was borrowed.
                    try:
                        self.fire.clear_all()
                        self.canvas.clear()
                        self.canvas.draw_text("GOODBYE", 35, 25)
                        self.fire.render_to_display()
                    except Exception as e:
                        print(f"Error during shutdown: {e}")
        finally:
            if self._owns_fire:
                self.fire.close()

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
        return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def quit(self):
        """Request the application to stop."""
        self.running = False
