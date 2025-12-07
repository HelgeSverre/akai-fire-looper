#!/usr/bin/env python3
"""
E2E Visual Demo for Circuit Sequencer.
Opens the pygame mock GUI and runs automated demo sequences that you can watch.

Usage:
    uv run python examples/circuit/demo_e2e.py
    uv run python examples/circuit/demo_e2e.py --speed 0.5   # Slower
    uv run python examples/circuit/demo_e2e.py --speed 2.0   # Faster
    uv run python examples/circuit/demo_e2e.py --demo intro  # Specific demo only
"""
import argparse
import os
import sys
import time
from typing import Callable, List, Optional

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from mock_gui_pygame import MockAkaiFire
from main import CircuitSequencer
from ui.screen_manager import Mode


class DemoRunner:
    """
    Runs automated demo sequences on the Circuit Sequencer with pygame visualization.
    """

    def __init__(self, speed: float = 1.0):
        """
        Initialize the demo runner.

        Args:
            speed: Demo speed multiplier. 0.5 = half speed, 2.0 = double speed
        """
        self.speed = speed
        self.fire: Optional[MockAkaiFire] = None
        self.app: Optional[CircuitSequencer] = None
        self.running = True
        self.annotation = ""

        # Demo registry
        self.demos = {
            "intro": self.demo_intro,
            "modes": self.demo_mode_switching,
            "notes": self.demo_note_entry,
            "transport": self.demo_transport,
            "patterns": self.demo_pattern_workflow,
            "encoders": self.demo_encoders,
            "full": self.demo_full_workflow,
        }

    def setup(self):
        """Initialize the mock fire and sequencer."""
        print("Setting up demo environment...")
        self.fire = MockAkaiFire()
        self.app = CircuitSequencer(fire=self.fire)
        print("Demo environment ready!")

    def cleanup(self):
        """Clean up resources."""
        if self.app:
            self.app.shutdown()
        self.running = False

    def wait(self, seconds: float):
        """
        Wait while processing pygame events and updating display.

        Args:
            seconds: Time to wait (adjusted by speed multiplier)
        """
        adjusted_time = seconds / self.speed
        start = time.time()

        while self.running and (time.time() - start) < adjusted_time:
            # Process pygame events
            if not self.fire.process_events():
                self.running = False
                return

            # Update display
            self.app._update_transport_leds()
            self.app._update_display()

            time.sleep(0.016)  # ~60 FPS

    def annotate(self, text: str):
        """
        Show annotation on the OLED screen.

        Args:
            text: Text to display at top of screen
        """
        self.annotation = text
        print(f"[DEMO] {text}")

    def simulate_pad_press(
        self, pad: int, velocity: int = 100, hold_time: float = 0.15
    ):
        """
        Simulate pressing a pad with visual feedback.

        Args:
            pad: Pad index (0-63)
            velocity: Press velocity (0-127)
            hold_time: How long to "hold" the pad
        """
        # Save original color
        original_color = (
            self.fire.pad_colors[pad].copy()
            if hasattr(self.fire, "pad_colors")
            else (0, 0, 0)
        )

        # Flash white to show press
        self.fire.set_pad_color(pad, 127, 127, 127)
        self.wait(0.05)

        # Trigger the event handler
        self.app.mode_manager.handle_pad_press(pad, velocity)

        # Brief hold
        self.wait(hold_time)

    def simulate_button_press(self, button_id: int, hold_time: float = 0.2):
        """
        Simulate pressing a button.

        Args:
            button_id: Button constant (e.g., self.fire.BUTTON_PLAY)
            hold_time: How long to "hold" the button
        """
        # Flash button LED
        self.fire.set_button_led(button_id, 2)

        # Find and call the button handler
        if button_id in self.fire.button_listeners:
            for callback in self.fire.button_listeners[button_id]:
                callback("press")

        self.wait(hold_time)

        # "Release"
        if button_id in self.fire.button_listeners:
            for callback in self.fire.button_listeners[button_id]:
                callback("release")

    def simulate_encoder_turn(self, encoder_id: int, direction: str, steps: int = 5):
        """
        Simulate turning an encoder.

        Args:
            encoder_id: Encoder constant (e.g., self.fire.ROTARY_VOLUME)
            direction: "clockwise" or "counterclockwise"
            steps: Number of steps to turn
        """
        for _ in range(steps):
            if encoder_id in self.fire.rotary_listeners:
                for callback in self.fire.rotary_listeners[encoder_id]:
                    callback(direction, 1)
            self.wait(0.05)

    # ==========================================================================
    # Demo Sequences
    # ==========================================================================

    def demo_intro(self):
        """Intro sequence - wave pattern across pads."""
        self.annotate("Welcome to Circuit Sequencer!")
        self.wait(1.0)

        # Wave pattern across pads
        self.annotate("Pad animation...")
        for row in range(4):
            for col in range(16):
                pad = row * 16 + col
                # Rainbow colors
                r = int((col / 16) * 127)
                g = int((row / 4) * 127)
                b = 127 - r
                self.fire.set_pad_color(pad, r, g, b)
                self.wait(0.02)

        self.wait(0.5)

        # Flash all pads white
        self.annotate("Ready!")
        for i in range(64):
            self.fire.set_pad_color(i, 127, 127, 127)
        self.wait(0.3)

        # Clear pads
        self.fire.clear_all_pads()
        self.wait(0.5)

    def demo_mode_switching(self):
        """Demonstrate switching between modes."""
        self.annotate("Mode Switching Demo")
        self.wait(0.5)

        modes = [
            (self.fire.BUTTON_NOTE, "NOTE Mode - Keyboard"),
            (self.fire.BUTTON_DRUM, "MIXER Mode - Tracks"),
            (self.fire.BUTTON_PERFORM, "PATTERN Mode - Arrangement"),
            (self.fire.BUTTON_STEP, "STEP EDIT Mode - Parameters"),
            (self.fire.BUTTON_NOTE, "Back to NOTE Mode"),
        ]

        for button, desc in modes:
            self.annotate(desc)
            self.simulate_button_press(button)
            self.wait(1.0)

    def demo_note_entry(self):
        """Demonstrate entering notes."""
        self.annotate("Note Entry Demo")
        self.wait(0.5)

        # Make sure we're in NOTE mode
        self.simulate_button_press(self.fire.BUTTON_NOTE)
        self.wait(0.3)

        # Select Track 1 (pad 0 in row 1)
        self.annotate("Select Track 1")
        self.simulate_pad_press(16)  # Row 1, Col 0
        self.wait(0.3)

        # Add some notes using the keyboard area (rows 2-3, pads 32-63)
        self.annotate("Adding notes to pattern...")
        keyboard_pads = [32, 34, 36, 37, 39, 41, 43, 44]  # C major scale positions
        for pad in keyboard_pads:
            self.simulate_pad_press(pad)
            self.wait(0.2)

        self.wait(0.5)

        # Show the pattern on step row
        self.annotate("Notes added to steps!")
        self.wait(1.0)

    def demo_transport(self):
        """Demonstrate transport controls."""
        self.annotate("Transport Controls Demo")
        self.wait(0.5)

        # Press PLAY
        self.annotate("Starting playback...")
        self.simulate_button_press(self.fire.BUTTON_PLAY)
        self.wait(2.0)

        # Watch playback
        self.annotate("Sequencer playing...")
        self.wait(3.0)

        # Press STOP
        self.annotate("Stopping...")
        self.simulate_button_press(self.fire.BUTTON_STOP)
        self.wait(0.5)

        # Press REC
        self.annotate("Recording mode...")
        self.simulate_button_press(self.fire.BUTTON_REC)
        self.wait(1.0)

        # Add a note while recording
        self.annotate("Recording notes...")
        self.simulate_pad_press(35)
        self.wait(0.5)
        self.simulate_pad_press(37)
        self.wait(0.5)

        # Stop
        self.annotate("Stopping recording...")
        self.simulate_button_press(self.fire.BUTTON_STOP)
        self.wait(0.5)

    def demo_pattern_workflow(self):
        """Demonstrate pattern selection and chaining."""
        self.annotate("Pattern Workflow Demo")
        self.wait(0.5)

        # Switch to Pattern mode
        self.annotate("Entering Pattern Mode...")
        self.simulate_button_press(self.fire.BUTTON_PERFORM)
        self.wait(0.5)

        # Select different patterns
        pattern_pads = [0, 1, 2, 3]  # First 4 pattern slots
        for i, pad in enumerate(pattern_pads):
            self.annotate(f"Selecting Pattern {i + 1}")
            self.simulate_pad_press(pad)
            self.wait(0.5)

        # Back to NOTE mode
        self.annotate("Back to Note Mode...")
        self.simulate_button_press(self.fire.BUTTON_NOTE)
        self.wait(0.5)

    def demo_encoders(self):
        """Demonstrate encoder controls."""
        self.annotate("Encoder Demo")
        self.wait(0.5)

        # Make sure we're in NOTE mode
        self.simulate_button_press(self.fire.BUTTON_NOTE)
        self.wait(0.3)

        # Turn VOLUME encoder (BPM)
        self.annotate("Adjusting BPM...")
        self.simulate_encoder_turn(self.fire.ROTARY_VOLUME, "clockwise", 10)
        self.wait(0.5)
        self.simulate_encoder_turn(self.fire.ROTARY_VOLUME, "counterclockwise", 5)
        self.wait(0.5)

        # Turn FILTER encoder (Swing)
        self.annotate("Adjusting Swing...")
        self.simulate_encoder_turn(self.fire.ROTARY_FILTER, "clockwise", 8)
        self.wait(0.5)

        # Turn PAN encoder (Quantization)
        self.annotate("Adjusting Quantization...")
        self.simulate_encoder_turn(self.fire.ROTARY_PAN, "clockwise", 3)
        self.wait(0.5)

    def demo_full_workflow(self):
        """Full workflow demonstration combining everything."""
        self.annotate("Full Workflow Demo")
        self.wait(0.5)

        # Intro animation
        self.demo_intro()

        # Set BPM
        self.annotate("Setting tempo to 130 BPM...")
        self.simulate_button_press(self.fire.BUTTON_NOTE)
        self.simulate_encoder_turn(self.fire.ROTARY_VOLUME, "clockwise", 15)
        self.wait(0.5)

        # Add notes to pattern
        self.annotate("Creating a melody...")
        melody_pads = [32, 34, 36, 39, 41, 39, 36, 34]
        for pad in melody_pads:
            self.simulate_pad_press(pad)
            self.wait(0.15)

        # Play the sequence
        self.annotate("Playing sequence...")
        self.simulate_button_press(self.fire.BUTTON_PLAY)
        self.wait(4.0)

        # Switch modes while playing
        self.annotate("Checking mixer...")
        self.simulate_button_press(self.fire.BUTTON_DRUM)
        self.wait(1.5)

        self.annotate("Checking patterns...")
        self.simulate_button_press(self.fire.BUTTON_PERFORM)
        self.wait(1.5)

        # Stop
        self.annotate("Stopping...")
        self.simulate_button_press(self.fire.BUTTON_STOP)
        self.wait(0.5)

        # Final message
        self.annotate("Demo Complete!")
        self.wait(2.0)

    def run(self, demo_name: Optional[str] = None):
        """
        Run the demo.

        Args:
            demo_name: Specific demo to run, or None for all demos
        """
        try:
            self.setup()

            if demo_name:
                if demo_name in self.demos:
                    self.demos[demo_name]()
                else:
                    print(f"Unknown demo: {demo_name}")
                    print(f"Available demos: {', '.join(self.demos.keys())}")
                    return
            else:
                # Run all demos in sequence
                for name, demo_func in self.demos.items():
                    if not self.running:
                        break
                    print(f"\n=== Running {name} demo ===")
                    demo_func()
                    self.wait(1.0)

            print("\nDemo finished!")

        except KeyboardInterrupt:
            print("\nDemo interrupted.")
        finally:
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Circuit Sequencer E2E Visual Demo")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Demo speed multiplier (0.5 = slower, 2.0 = faster)",
    )
    parser.add_argument(
        "--demo",
        type=str,
        default=None,
        help="Run specific demo: intro, modes, notes, transport, patterns, encoders, full",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Circuit Sequencer E2E Visual Demo")
    print("=" * 60)
    print(f"Speed: {args.speed}x")
    if args.demo:
        print(f"Demo: {args.demo}")
    else:
        print("Running all demos...")
    print()
    print("Controls:")
    print("  - Close window or Ctrl+C to exit")
    print("  - Watch the automated interactions!")
    print("=" * 60)
    print()

    runner = DemoRunner(speed=args.speed)
    runner.run(demo_name=args.demo)


if __name__ == "__main__":
    main()
