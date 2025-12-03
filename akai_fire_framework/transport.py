"""
Transport state management for AKAI Fire applications.

Provides play/stop/record functionality with LED feedback.
"""

from enum import Enum
from typing import Callable, List, Optional


class TransportState(Enum):
    """Transport state enumeration."""

    STOPPED = "stopped"
    PLAYING = "playing"
    RECORDING = "recording"
    ARMED = "armed"  # Ready to record on next play


class TransportMixin:
    """
    Mixin for transport control (play/stop/record).

    Provides standard transport functionality with:
    - State management
    - LED feedback for transport buttons
    - Callback system for state changes

    Usage:
        class MyApp(AkaiFireApp, TransportMixin):
            def on_init(self):
                self.init_transport()

                # Optional: add callback
                self.add_transport_callback(self.on_transport_change)

            def on_button_press(self, button_id, event):
                if event != "press":
                    return

                if button_id == self.fire.BUTTON_PLAY:
                    self.toggle_play()
                elif button_id == self.fire.BUTTON_STOP:
                    self.stop()
                elif button_id == self.fire.BUTTON_REC:
                    self.toggle_record()

            def on_update(self, dt):
                self.update_transport_leds()

            def on_transport_change(self, new_state, old_state):
                print(f"Transport: {old_state} -> {new_state}")
    """

    def init_transport(self):
        """
        Initialize transport state.

        Call this in your on_init() method.
        """
        self._transport_state = TransportState.STOPPED
        self._transport_callbacks: List[Callable] = []

    @property
    def transport_state(self) -> TransportState:
        """Get current transport state."""
        return self._transport_state

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._transport_state in (TransportState.PLAYING, TransportState.RECORDING)

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._transport_state == TransportState.RECORDING

    @property
    def is_stopped(self) -> bool:
        """Check if currently stopped."""
        return self._transport_state == TransportState.STOPPED

    # =========================================================================
    # Transport Actions
    # =========================================================================

    def play(self):
        """Start playback."""
        if self._transport_state == TransportState.ARMED:
            self._set_transport(TransportState.RECORDING)
        else:
            self._set_transport(TransportState.PLAYING)

    def stop(self):
        """Stop playback/recording."""
        self._set_transport(TransportState.STOPPED)

    def record(self):
        """Start recording (implies playing)."""
        self._set_transport(TransportState.RECORDING)

    def arm(self):
        """Arm for recording (record on next play)."""
        self._set_transport(TransportState.ARMED)

    def toggle_play(self):
        """Toggle between playing and stopped."""
        if self.is_playing:
            self.stop()
        else:
            self.play()

    def toggle_record(self):
        """Toggle recording on/off."""
        if self.is_recording:
            self.play()  # Keep playing, just stop recording
        elif self.is_playing:
            self.record()
        else:
            # Not playing - arm for record
            self.arm()

    def panic(self):
        """Emergency stop - immediately halt everything."""
        self._set_transport(TransportState.STOPPED)
        # Subclass can override to send all-notes-off, etc.

    # =========================================================================
    # State Management
    # =========================================================================

    def _set_transport(self, state: TransportState):
        """
        Internal method to change transport state.

        Triggers callbacks and LED updates.
        """
        old_state = self._transport_state
        self._transport_state = state

        # Notify callbacks
        for callback in self._transport_callbacks:
            try:
                callback(state, old_state)
            except Exception as e:
                print(f"Transport callback error: {e}")

        # Notify mode handler if using ModeManagerMixin
        if hasattr(self, "dispatch_transport_change"):
            self.dispatch_transport_change(state.value)

    def add_transport_callback(
        self, callback: Callable[[TransportState, TransportState], None]
    ):
        """
        Add a callback for transport state changes.

        Args:
            callback: Function(new_state, old_state) to call on change
        """
        self._transport_callbacks.append(callback)

    def remove_transport_callback(
        self, callback: Callable[[TransportState, TransportState], None]
    ):
        """Remove a previously added callback."""
        if callback in self._transport_callbacks:
            self._transport_callbacks.remove(callback)

    # =========================================================================
    # LED Feedback
    # =========================================================================

    def update_transport_leds(self):
        """
        Update transport button LEDs based on current state.

        Call this in your on_update() method.
        """
        if not hasattr(self, "fire"):
            return

        # Clear all transport LEDs first
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 0)
        self.fire.set_button_led(self.fire.BUTTON_REC, 0)
        self.fire.set_button_led(self.fire.BUTTON_STOP, 0)

        # Set LEDs based on state
        if self._transport_state == TransportState.PLAYING:
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 2)  # Bright green

        elif self._transport_state == TransportState.RECORDING:
            self.fire.set_button_led(self.fire.BUTTON_REC, 2)   # Bright red
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)  # Dim green

        elif self._transport_state == TransportState.ARMED:
            self.fire.set_button_led(self.fire.BUTTON_REC, 1)   # Dim red (blinking ideally)

        else:  # STOPPED
            self.fire.set_button_led(self.fire.BUTTON_STOP, 1)  # Dim red

    def setup_transport_buttons(self):
        """
        Set up default transport button handlers.

        Call this in on_init() if you want standard behavior.
        """
        if not hasattr(self, "fire"):
            return

        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                self.toggle_play()

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.stop()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                self.toggle_record()
