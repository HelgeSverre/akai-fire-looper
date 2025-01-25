import math
import random
import time
from dataclasses import dataclass
from typing import List

from akai_fire import AkaiFire


@dataclass
class Droplet:
    x: float
    y: float
    age: float
    intensity: float
    impact: float


class DropletAnimationStandard:
    def __init__(self):
        self.fire = AkaiFire()
        self.droplets: List[Droplet] = []
        self.running = True

        # Set up pad press listener
        self.fire.add_global_listener(self.on_pad_pressed)

    def on_pad_pressed(self, pad_index):
        """Handle pad press events"""
        x = pad_index % 16
        y = pad_index // 16
        # Create stronger ripple for user interactions
        self.droplets.append(Droplet(x=x, y=y, age=0, intensity=1.0, impact=2.0))

    def create_random_droplet(self):
        """Create ambient background ripples"""
        x = random.uniform(0, 15)
        y = random.uniform(0, 3)
        return Droplet(x=x, y=y, age=0, intensity=1.0, impact=0.5)

    def run(self):
        try:
            print("Starting droplet animation using standard library...")
            print("Tap pads to create ripples!")

            # Clear everything initially
            self.fire.clear_all_pads()

            frame = 0
            while self.running:
                # Add random ambient droplets
                if random.random() < 0.02:
                    self.droplets.append(self.create_random_droplet())

                # Update all droplets
                active_droplets = []
                pad_intensities = [[0.0] for _ in range(64)]

                for drop in self.droplets:
                    drop.age += 0.1
                    drop.intensity = math.exp(-drop.age * 0.4)

                    if drop.intensity > 0.05:
                        active_droplets.append(drop)

                        # Calculate effect on all pads
                        for row in range(4):
                            for col in range(16):
                                pad_index = row * 16 + col
                                distance = math.sqrt(
                                    (col - drop.x) ** 2 + (row - drop.y) ** 2
                                )

                                # Ripple wave effect
                                ripple = (
                                    math.sin(distance * 2 - drop.age * 4) * 0.5 + 0.5
                                )
                                effect = (
                                    drop.intensity
                                    * drop.impact
                                    * ripple
                                    * math.exp(-distance * 0.5)
                                )

                                pad_intensities[pad_index][0] += effect

                self.droplets = active_droplets

                # Update pad colors individually
                for i in range(64):
                    intensity = min(127, max(0, int(pad_intensities[i][0] * 127)))
                    # Blue with hint of cyan
                    self.fire.set_pad_color(i, 0, int(intensity * 0.2), intensity)

                time.sleep(0.03)
                frame += 1

        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        self.fire.clear_all_pads()
        self.fire.clear_all_button_leds()
        self.fire.close()


if __name__ == "__main__":
    animation = DropletAnimationStandard()
    animation.run()
