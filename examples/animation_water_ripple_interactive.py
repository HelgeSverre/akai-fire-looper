"""
AKAI Fire Example: Interactive Water Ripple Animation

This example creates an interactive water ripple effect on the pad grid.
- Tap pads to create ripples (velocity-sensitive)
- Use encoders to control animation parameters
- Based on the experimental batching_water.py

Controls:
- VOLUME: Wave frequency (ripple density)
- PAN: Color hue
- FILTER: Ripple radius/spread
- RESONANCE: Decay speed
"""

import time
import math
import threading
from dataclasses import dataclass
from typing import List
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire
from animation_utils import hsv_to_rgb_127, SmoothedValue, pad_index_to_xy


@dataclass
class Droplet:
    """A water droplet with position and properties."""
    x: float
    y: float
    age: float
    intensity: float
    impact: float


class WaterRippleAnimation:
    def __init__(self):
        # Initialize controller
        self.fire = get_akai_fire()
        self.fire.clear_all_pads()
        
        # Animation parameters with smoothing
        self.wave_frequency = SmoothedValue(1.0)  # 0.5 to 8.0
        self.color_hue = SmoothedValue(0.66)  # 0.0 to 1.0 (blue by default)
        self.radius_multiplier = SmoothedValue(1.0)  # 0.5 to 6.0
        self.age_decay = SmoothedValue(0.05)  # 0.05 to 2.0
        
        # Droplet management
        self.droplets: List[Droplet] = []
        self.droplets_lock = threading.Lock()
        
        # Setup event handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup pad and encoder handlers."""
        
        # Pad handler for creating ripples
        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            x, y = pad_index_to_xy(pad_index)
            
            # Scale velocity to impact
            if velocity == 127:
                impact = 2.01
            else:
                # Linear mapping from [32, 127] to [0.25, 2.0]
                impact = 0.25 + (velocity - 32) / 95 * 1.75
                
            with self.droplets_lock:
                self.droplets.append(Droplet(x=x, y=y, age=0, intensity=1.0, impact=impact))
            
            print(f"Ripple at ({x}, {y}) with impact {impact:.2f}")
        
        # Encoder handlers
        @self.fire.on_rotary_turn(self.fire.ROTARY_VOLUME)
        def handle_frequency(direction, velocity):
            # Exponential scaling for wave frequency
            change = (velocity / 63) * 0.3
            if direction == "counterclockwise":
                change = -change
                
            current = math.log2(self.wave_frequency.current)
            new_freq = math.pow(2, current + change)
            new_freq = max(0.5, min(8.0, new_freq))
            self.wave_frequency.set_target(new_freq)
            print(f"Wave frequency: {new_freq:.2f}Hz")
            
        @self.fire.on_rotary_turn(self.fire.ROTARY_PAN)
        def handle_color(direction, velocity):
            change = (velocity / 63) * 0.3 * 5.0
            if direction == "counterclockwise":
                change = -change
                
            new_hue = self.color_hue.current + change
            # Wrap hue around
            if new_hue >= 1.0:
                new_hue -= 1.0
            elif new_hue < 0.0:
                new_hue += 1.0
                
            self.color_hue.set_target(new_hue)
            
            # Color name approximation
            hue_names = [
                (0.0, "Red"), (0.08, "Orange"), (0.17, "Yellow"),
                (0.33, "Green"), (0.5, "Cyan"), (0.67, "Blue"),
                (0.83, "Purple"), (0.92, "Pink")
            ]
            closest = min(hue_names, key=lambda x: abs(x[0] - new_hue))
            print(f"Color: {closest[1]} (Hue: {new_hue:.3f})")
            
        @self.fire.on_rotary_turn(self.fire.ROTARY_FILTER)
        def handle_radius(direction, velocity):
            change = (velocity / 63) * 0.3 * 4
            if direction == "counterclockwise":
                change = -change
                
            new_radius = self.radius_multiplier.current + change
            new_radius = max(0.5, min(6.0, new_radius))
            self.radius_multiplier.set_target(new_radius)
            
            if new_radius < 1.0:
                desc = "Very tight ripples"
            elif new_radius < 2.0:
                desc = "Compact ripples"
            elif new_radius < 4.0:
                desc = "Medium spread"
            else:
                desc = "Wide ripples"
            print(f"Ripple spacing: {new_radius:.2f} - {desc}")
            
        @self.fire.on_rotary_turn(self.fire.ROTARY_RESONANCE)
        def handle_decay(direction, velocity):
            change = (velocity / 63) * 0.3
            if direction == "counterclockwise":
                change = -change
                
            new_decay = self.age_decay.current * math.exp(change)
            new_decay = max(0.05, min(2.0, new_decay))
            self.age_decay.set_target(new_decay)
            
            if new_decay < 0.2:
                desc = "Very long trails"
            elif new_decay < 0.5:
                desc = "Long-lasting ripples"
            elif new_decay < 1.0:
                desc = "Medium decay"
            else:
                desc = "Quick fadeout"
            print(f"Decay speed: {new_decay:.2f} - {desc}")
            
        # Clear button
        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_clear(event):
            if event == "press":
                with self.droplets_lock:
                    self.droplets.clear()
                self.fire.clear_all_pads()
                print("Cleared all ripples")
                
    def update_frame(self):
        """Update and render one animation frame."""
        # Update smoothed values
        current_freq = self.wave_frequency.update()
        current_hue = self.color_hue.update()
        current_radius = self.radius_multiplier.update()
        current_decay = self.age_decay.update()
        
        # Initialize intensity accumulator
        pad_intensities = [0.0 for _ in range(64)]
        
        # Update droplets
        with self.droplets_lock:
            active_droplets = []
            
            for drop in self.droplets:
                # Age the droplet
                drop.age += 0.1
                drop.intensity = math.exp(-drop.age * current_decay)
                
                # Keep if still visible
                if drop.intensity > 0.05:
                    active_droplets.append(drop)
                    
                    # Calculate effect on each pad
                    for i in range(64):
                        x, y = pad_index_to_xy(i)
                        distance = math.sqrt((x - drop.x) ** 2 + (y - drop.y) ** 2)
                        
                        # Ripple wave calculation
                        ripple = math.sin(distance * current_freq - drop.age * 4) * 0.5 + 0.5
                        effect = drop.intensity * drop.impact * ripple * math.exp(-distance * 0.5)
                        
                        pad_intensities[i] += effect
                        
            self.droplets = active_droplets
            
        # Convert intensities to colors and prepare batch update
        pad_colors = []
        for i in range(64):
            intensity = min(1.0, max(0.0, pad_intensities[i]))
            r, g, b = hsv_to_rgb_127(current_hue, 1.0, intensity)
            pad_colors.append((i, r, g, b))
            
        # Update all pads at once
        self.fire.set_multiple_pad_colors(pad_colors)
        
    def run(self):
        """Main animation loop."""
        try:
            self.fire.start_listening()
            
            print("\n=== Water Ripple Animation ===")
            print("\nControls:")
            print("- Tap pads to create ripples (velocity-sensitive)")
            print("- VOLUME: Wave frequency")
            print("- PAN: Color selection")
            print("- FILTER: Ripple spacing")
            print("- RESONANCE: Decay speed")
            print("- BROWSER: Clear all ripples")
            print("\nPress Ctrl+C to exit")
            
            while True:
                self.update_frame()
                time.sleep(0.033)  # ~30 FPS
                
                # Handle mock GUI events if using mock
                if hasattr(self.fire, "process_events"):
                    if not self.fire.process_events():
                        break
                        
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.clear_all_pads()
            self.fire.close()


if __name__ == "__main__":
    animation = WaterRippleAnimation()
    animation.run()