import time

from akai_fire import AkaiFire
from screen.display_interface import FireDisplay, DebugDisplay
from screen.screen_templates import ScreenTemplates


class MixerTest:
    def __init__(self):
        self.fire = AkaiFire()
        self.display = FireDisplay(self.fire)
        self.screens = ScreenTemplates(self.display)

        # Track levels (0.0 - 1.0)
        self.levels = [0.2, 0.5, 0.8, 0.3]

        # Map rotary encoders to tracks
        self.fire.add_rotary_listener(
            self.fire.ROTARY_VOLUME, lambda *args: self._handle_rotary(0, *args)
        )
        self.fire.add_rotary_listener(
            self.fire.ROTARY_PAN, lambda *args: self._handle_rotary(1, *args)
        )
        self.fire.add_rotary_listener(
            self.fire.ROTARY_FILTER, lambda *args: self._handle_rotary(2, *args)
        )
        self.fire.add_rotary_listener(
            self.fire.ROTARY_RESONANCE, lambda *args: self._handle_rotary(3, *args)
        )

    def _handle_rotary(
        self, track: int, encoder_id: int, direction: str, velocity: int
    ):
        """Handle rotary changes for track levels"""
        # Scale velocity to smaller changes (0.01 - 0.05 per tick)
        change = velocity * 0.01

        if direction == "counterclockwise":
            change = -change

        # Update level with clamping
        self.levels[track] = max(0.0, min(1.0, self.levels[track] + change))

        # Update display
        self.screens.show_mixer_screen(track_levels=self.levels)
        print(f"Track {track+1}: {self.levels[track]:.2f}")

    def run(self):
        try:
            # Show initial mixer state
            self.screens.show_mixer_screen(track_levels=self.levels)
            print("Turn rotary knobs to adjust levels. Press Ctrl+C to exit.")

            # Keep running until interrupted
            while True:
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.close()


if __name__ == "__main__":
    mixer = MixerTest()
    mixer.run()
