"""
AKAI Fire Example: Bouncing Ball Animation

This script demonstrates how to use the AKAI Fire MIDI controller's canvas display
to render a simple animation. A ball moves around the display, bouncing off the edges
of the screen. The animation runs for a specified number of seconds or until the user interrupts it.

Key Features:
- Clears the screen before rendering each frame.
- Draws a filled circle (the ball) at updated positions.
- Adjusts the ball's position based on velocity and detects collisions with screen edges.
- Adjustable frame rate (FPS) for controlling animation speed.
"""

import time
from dataclasses import dataclass

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import (
    get_akai_fire,
    AkaiFire,
    Canvas,
    MIDIConnectionError,
    HardwareError,
)


@dataclass
class Ball:
    """Represents a ball with position, velocity, and appearance properties."""

    x: float
    y: float
    dx: float
    dy: float
    radius: int = 10

    def update_position(self) -> None:
        """Update ball position based on velocity."""
        self.x += self.dx
        self.y += self.dy

    def handle_boundary_collision(self, canvas: Canvas) -> None:
        """Handle collisions with screen boundaries."""
        if self.x - self.radius <= 0 or self.x + self.radius >= canvas.WIDTH:
            self.dx = -self.dx
        if self.y - self.radius <= 0 or self.y + self.radius >= canvas.HEIGHT:
            self.dy = -self.dy


@dataclass
class AnimationConfig:
    """Configuration parameters for the bouncing ball animation."""

    fps: int = 30
    duration: int = 10

    @property
    def total_frames(self) -> int:
        """Calculate total frames for the animation duration."""
        return int(self.duration * self.fps)

    @property
    def frame_delay(self) -> float:
        """Calculate delay between frames to achieve target FPS."""
        return 1.0 / self.fps


class BouncingBallSimulation:
    """Handles the physics and rendering of the bouncing ball animation."""

    def __init__(self, fire: AkaiFire, config: AnimationConfig) -> None:
        self.fire = fire
        self.canvas = fire.get_canvas()
        self.config = config
        self.ball = Ball(x=32.0, y=32.0, dx=4.0, dy=2.0, radius=10)

    def render_frame(self) -> None:
        """Render a single frame of the animation."""
        # Clear the display
        self.canvas.clear()

        # Draw the ball at the current position
        self.canvas.fill_circle(int(self.ball.x), int(self.ball.y), self.ball.radius)

        # Send the updated canvas to the device
        self.fire.render_to_display()

    def update_physics(self) -> None:
        """Update ball physics (position and collisions)."""
        self.ball.update_position()
        self.ball.handle_boundary_collision(self.canvas)

    def run_animation(self) -> None:
        """Run the complete bouncing ball animation."""
        print(f"Starting animation for {self.config.duration} seconds...")

        try:
            for frame in range(self.config.total_frames):
                self.render_frame()
                self.update_physics()
                time.sleep(self.config.frame_delay)

        except KeyboardInterrupt:
            print("Animation interrupted by user.")
        except (MIDIConnectionError, HardwareError) as e:
            print(f"Hardware error occurred: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise


def main(duration: int = 10) -> None:
    """
    Main function to run the bouncing ball animation on the AKAI Fire's display.

    Args:
        duration: Duration of the animation in seconds (default: 10 seconds).
    """
    config = AnimationConfig(duration=duration)

    with get_akai_fire() as fire:
        simulation = BouncingBallSimulation(fire, config)
        simulation.run_animation()


if __name__ == "__main__":
    # You can change the duration by passing a value to `main(duration=...)`
    main(duration=10)
