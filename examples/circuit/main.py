"""
Main application entry point for the Circuit Tracks-inspired MIDI sequencer.
Phase 1 MVP implementation with core 4-track functionality.
"""

import os
import sys
import time
import signal
import threading
from typing import Optional

# Add project root to path to import akai_fire
current_dir = os.path.dirname(os.path.abspath(__file__))
# circuit dir -> examples dir -> project root
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

try:
    from akai_fire import get_akai_fire
except ImportError as e:
    print(f"Error importing akai_fire: {e}")
    print(
        "Make sure you're running from the correct directory and have the AKAI Fire connected."
    )
    sys.exit(1)

# Import our sequencer components
sys.path.insert(0, current_dir)
from core.sequencer import Sequencer, TransportState
from ui.screen_manager import ScreenManager, Mode
from ui.grid_manager import GridManager
from ui.mode_manager import ModeManager
from ui.modes.note_mode import NoteMode
from ui.modes.mixer_mode import MixerMode
from ui.modes.pattern_mode import PatternMode
from ui.modes.step_edit_mode import StepEditMode


class CircuitSequencer:
    """
    Main application class for the Circuit Tracks-inspired MIDI sequencer.
    Coordinates all components and handles the main application loop.
    """

    def __init__(self, fire=None):
        """
        Initialize the Circuit Sequencer.

        Args:
            fire: Optional AkaiFire instance. If None, uses get_akai_fire().
        """
        print("Initializing Circuit Sequencer...")

        # Initialize hardware
        try:
            self.fire = fire if fire is not None else get_akai_fire()
            self.canvas = self.fire.get_canvas()
            self._owns_fire = fire is None  # Track if we need to close it
            print("AKAI Fire connected successfully")
        except Exception as e:
            print(f"Failed to connect to AKAI Fire: {e}")
            sys.exit(1)

        # Initialize core sequencer
        self.sequencer = Sequencer()

        # Initialize UI components
        self.screen_manager = ScreenManager(self.canvas)
        self.grid_manager = GridManager(self.fire)
        self.mode_manager = ModeManager(self.screen_manager, self.grid_manager)

        # Initialize mode handlers
        self.note_mode = NoteMode(self.sequencer, self.mode_manager)
        self.mixer_mode = MixerMode(self.sequencer, self.mode_manager)
        self.pattern_mode = PatternMode(self.sequencer, self.mode_manager)
        self.step_edit_mode = StepEditMode(self.sequencer, self.mode_manager)

        # Application state
        self.running = False
        self.last_update_time = 0.0
        
        # Thread-safe state for UI updates
        self._current_step = 0
        self._step_lock = threading.Lock()

        # Set up MIDI ports
        self._setup_midi()

        # Set up hardware event handlers
        self._setup_hardware_handlers()

        # Set up sequencer callbacks
        self._setup_sequencer_callbacks()

        print("Circuit Sequencer initialized successfully!")

    def _setup_midi(self):
        """Set up MIDI input/output ports."""
        input_ports, output_ports = self.sequencer.midi.refresh_ports()

        print("\nAvailable MIDI ports:")
        print("Input ports:", input_ports)
        print("Output ports:", output_ports)

        # Try to connect to default ports
        default_output = "FL STUDIO FIRE"  # Common AKAI Fire MIDI port

        if default_output in output_ports:
            self.sequencer.midi.set_output_port(default_output)
        elif output_ports:
            # Use first available output port
            self.sequencer.midi.set_output_port(output_ports[0])
            print(f"Using output port: {output_ports[0]}")
        else:
            print("Warning: No MIDI output ports available")

    def _setup_hardware_handlers(self):
        """Set up AKAI Fire hardware event handlers."""

        # Transport buttons
        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                if self.sequencer.transport_state == TransportState.STOPPED:
                    self.sequencer.play()
                else:
                    self.sequencer.stop()

        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_record(event):
            if event == "press":
                if self.sequencer.transport_state == TransportState.RECORDING:
                    self.sequencer.stop()
                else:
                    self.sequencer.record()

        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.sequencer.stop()

        # Mode switching - Circuit Tracks style button mapping
        @self.fire.on_button(self.fire.BUTTON_NOTE)
        def handle_note_button(event):
            if event == "press":
                self.mode_manager.set_mode(Mode.NOTE)
                
        @self.fire.on_button(self.fire.BUTTON_STEP)
        def handle_step_button(event):
            if event == "press":
                self.mode_manager.set_mode(Mode.STEP_EDIT)
                
        @self.fire.on_button(self.fire.BUTTON_DRUM)
        def handle_drum_button(event):
            if event == "press":
                self.mode_manager.set_mode(Mode.MIXER)
                
        @self.fire.on_button(self.fire.BUTTON_PERFORM)
        def handle_perform_button(event):
            if event == "press":
                self.mode_manager.set_mode(Mode.PATTERN)
                
        # Browser button for settings/menu access
        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                # Toggle settings mode or menu
                if self.mode_manager.get_current_mode() == Mode.SETTINGS:
                    self.mode_manager.set_mode(Mode.NOTE)  # Return to default
                else:
                    self.mode_manager.set_mode(Mode.SETTINGS)

        # Grid navigation
        @self.fire.on_button(self.fire.BUTTON_GRID_LEFT)
        def handle_grid_left(event):
            if event == "press":
                if self.mode_manager.get_current_mode() == Mode.NOTE:
                    self.note_mode.handle_button_press("grid_left")

        @self.fire.on_button(self.fire.BUTTON_GRID_RIGHT)
        def handle_grid_right(event):
            if event == "press":
                if self.mode_manager.get_current_mode() == Mode.NOTE:
                    self.note_mode.handle_button_press("grid_right")

        # SOLO buttons for track selection (Circuit Tracks style)
        @self.fire.on_button(self.fire.BUTTON_SOLO_1)
        def handle_solo_1(event):
            if event == "press":
                self.sequencer.set_current_track(0)
                self._update_track_leds()
                self._refresh_mode_display()

        @self.fire.on_button(self.fire.BUTTON_SOLO_2)
        def handle_solo_2(event):
            if event == "press":
                self.sequencer.set_current_track(1)
                self._update_track_leds()
                self._refresh_mode_display()

        @self.fire.on_button(self.fire.BUTTON_SOLO_3)
        def handle_solo_3(event):
            if event == "press":
                self.sequencer.set_current_track(2)
                self._update_track_leds()
                self._refresh_mode_display()

        @self.fire.on_button(self.fire.BUTTON_SOLO_4)
        def handle_solo_4(event):
            if event == "press":
                self.sequencer.set_current_track(3)
                self._update_track_leds()
                self._refresh_mode_display()

        # Rotary encoders
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_volume_encoder(direction, velocity):
            if self.mode_manager.get_current_mode() == Mode.NOTE:
                self.note_mode.handle_encoder_turn("volume", direction, velocity)

        @self.fire.on_rotary_turn(self.fire.ROTARY_FILTER)
        def handle_filter_encoder(direction, velocity):
            if self.mode_manager.get_current_mode() == Mode.NOTE:
                self.note_mode.handle_encoder_turn("filter", direction, velocity)

        @self.fire.on_rotary_turn(self.fire.ROTARY_PAN)
        def handle_pan_encoder(direction, velocity):
            if self.mode_manager.get_current_mode() == Mode.NOTE:
                self.note_mode.handle_encoder_turn("pan", direction, velocity)
                
        # Menu navigation with SELECT encoder  
        @self.fire.on_rotary_turn(self.fire.ROTARY_SELECT)
        def handle_select_encoder(direction, velocity):
            if self.mode_manager.get_current_mode() == Mode.SETTINGS:
                # Navigate through settings menu
                if direction == "clockwise":
                    self.mode_manager.next_menu_item()
                else:
                    self.mode_manager.prev_menu_item()

        # Menu item selection with SELECT button
        @self.fire.on_button(self.fire.BUTTON_SELECT)
        def handle_select_button(event):
            if event == "press" and self.mode_manager.get_current_mode() == Mode.SETTINGS:
                # Adjust current menu item value or activate action
                current_item = self.mode_manager.get_current_menu_item()
                if current_item["type"] in ["value", "options"]:
                    # For value and options types, cycle/increment the value
                    self.mode_manager.adjust_menu_value(1)
                elif current_item["type"] == "action":
                    # For action types, activate the action
                    self.mode_manager.activate_menu_item()

        # Pad events
        @self.fire.on_pad()
        def handle_pad_press(pad, velocity):
            self.mode_manager.handle_pad_press(pad, velocity)

        # Note: pad release is handled differently in the current API
        # For now we'll handle it in the pad press handler

    def _setup_sequencer_callbacks(self):
        """Set up sequencer event callbacks."""

        # Step callback - only store step info (UI updates happen in main thread)
        def on_step(step):
            with self._step_lock:
                self._current_step = step

        self.sequencer.add_step_callback(on_step)

        # Transport state callback - UI updates will be handled by main thread
        def on_transport_change(state):
            print(f"Transport: {state.value}")
            # Note: Transport LED updates will be handled in main loop to avoid threading issues

        self.sequencer.add_transport_callback(on_transport_change)

    def _update_transport_leds(self):
        """Update transport button LEDs based on sequencer state."""
        state = self.sequencer.transport_state

        # Clear all transport LEDs
        self.fire.set_button_led(self.fire.BUTTON_PLAY, 0)
        self.fire.set_button_led(self.fire.BUTTON_REC, 0)
        self.fire.set_button_led(self.fire.BUTTON_STOP, 0)

        # Set LEDs based on state
        if state == TransportState.PLAYING:
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 2)  # Bright green
        elif state == TransportState.RECORDING:
            self.fire.set_button_led(self.fire.BUTTON_REC, 2)  # Bright red
            self.fire.set_button_led(self.fire.BUTTON_PLAY, 1)  # Dim green
        else:  # STOPPED
            self.fire.set_button_led(self.fire.BUTTON_STOP, 1)  # Dim red

    def _update_track_leds(self):
        """Update track LEDs to show selected track."""
        current_track = self.sequencer.current_track
        for i in range(4):
            if i == current_track:
                self.fire.set_track_led(i + 1, 2)  # Bright for selected
            else:
                self.fire.set_track_led(i + 1, 1)  # Dim for others

    def _refresh_mode_display(self):
        """Refresh the current mode's display after track change."""
        # Update the current mode handler with new track context
        current_mode = self.mode_manager.get_current_mode()
        if current_mode == Mode.NOTE:
            self.note_mode.on_track_changed()
        elif current_mode == Mode.MIXER:
            self.mixer_mode.on_track_changed()
        elif current_mode == Mode.STEP_EDIT:
            self.step_edit_mode.on_track_changed()

    def _update_display(self, current_step=None):
        """Update screen and grid displays."""
        # Get sequencer status
        status = self.sequencer.get_status()

        # Add mode-specific information
        display_kwargs = {}

        if self.mode_manager.get_current_mode() == Mode.NOTE:
            display_kwargs.update(self.note_mode.get_display_info())

        # Add current step information for grid highlighting
        if current_step is not None:
            display_kwargs['current_step'] = current_step

        # Update displays
        self.mode_manager.update_display(status, **display_kwargs)

        # Render to hardware
        self.fire.render_to_display()

    def _show_startup_screen(self):
        """Show startup screen."""
        self.screen_manager.draw_startup_screen("1.0-MVP")
        self.fire.render_to_display()
        time.sleep(2)

    def run(self):
        """Main application loop."""
        print("\nStarting Circuit Sequencer...")
        self.running = True

        # Show startup screen
        self._show_startup_screen()

        # Start listening for hardware events
        self.fire.start_listening()

        # Initialize track LEDs (show track 1 as selected)
        self._update_track_leds()

        # Initial display update
        self._update_display()

        print("Circuit Sequencer is running!")
        print("Controls:")
        print("  PLAY: Start/Stop playback")
        print("  REC: Start/Stop recording")
        print("  STOP: Panic stop")
        print("  NOTE: Switch to Note Mode (scale keyboard)")
        print("  STEP: Switch to Step Edit Mode (parameter editing)")
        print("  DRUM: Switch to Mixer Mode (track control)")
        print("  PERFORM: Switch to Pattern Mode (pattern chains)")
        print("  BROWSER: Access Settings Menu")
        print("  SELECT Encoder: Navigate settings menu")
        print("  GRID LEFT/RIGHT: Octave down/up (Note Mode)")
        print("  Volume Encoder: BPM")
        print("  Filter Encoder: Swing")
        print("  Pan Encoder: Quantization")
        print("  Pads: Track selection, pattern selection, note input")
        print("\nPress Ctrl+C to quit")

        try:
            # Main loop
            while self.running:
                current_time = time.time()

                # Update display at 30 FPS
                if current_time - self.last_update_time > 0.033:  # ~30 FPS
                    # Update transport LEDs (needs to be in main thread)
                    self._update_transport_leds()
                    
                    # Get current step (thread-safe) and update display with step info
                    with self._step_lock:
                        current_step = self._current_step
                    self._update_display(current_step)
                    
                    self.last_update_time = current_time

                # Process mock events if in mock mode
                if hasattr(self.fire, "process_events"):
                    if not self.fire.process_events():
                        break

                # Short sleep to prevent excessive CPU usage
                time.sleep(0.001)  # 1ms

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.shutdown()

    def shutdown(self):
        """Clean shutdown of the application."""
        print("Shutting down Circuit Sequencer...")
        self.running = False

        try:
            # Stop sequencer
            self.sequencer.cleanup()

            # Clear all pads and display
            self.fire.clear_all()

            # Show shutdown message
            self.canvas.clear()
            self.canvas.draw_text("GOODBYE", 32, 25)
            self.fire.render_to_display()

            # Close Fire controller only if we own it
            if self._owns_fire:
                self.fire.close()

            print("Shutdown complete")

        except Exception as e:
            print(f"Error during shutdown: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
        return False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\nReceived interrupt signal...")
    # The main loop will catch KeyboardInterrupt and shutdown gracefully


def main():
    """Main entry point."""
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Create and run the sequencer
        app = CircuitSequencer()
        app.run()

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
