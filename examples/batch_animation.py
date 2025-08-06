"""
AKAI Fire Example: Batch Pad Animation

This example demonstrates efficient batch pad updates using set_multiple_pad_colors().
It creates smooth animations by updating all 64 pads in a single call.
"""

import time
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


def rainbow_wave(fire, frame):
    """Create a rainbow wave pattern across all pads."""
    pad_colors = []
    
    for i in range(64):
        row = i // 16
        col = i % 16
        
        # Create wave effect
        angle = (frame * 2 + (col + row * 16) * (360 / 64)) % 360
        
        # Convert HSV to RGB (simplified)
        h = angle / 60
        x = int(127 * (1 - abs(h % 2 - 1)))
        
        if h < 1:
            rgb = (127, x, 0)
        elif h < 2:
            rgb = (x, 127, 0)
        elif h < 3:
            rgb = (0, 127, x)
        elif h < 4:
            rgb = (0, x, 127)
        elif h < 5:
            rgb = (x, 0, 127)
        else:
            rgb = (127, 0, x)
            
        pad_colors.append((i, *rgb))
    
    # Update all pads at once
    fire.set_multiple_pad_colors(pad_colors)


def circular_pulse(fire, frame):
    """Create expanding circular pulses from the center."""
    pad_colors = []
    center_x, center_y = 7.5, 1.5
    radius = (math.sin(frame * 0.1) + 1) * 4
    
    for i in range(64):
        row = i // 16
        col = i % 16
        
        distance = math.sqrt((col - center_x) ** 2 + (row - center_y) ** 2)
        intensity = max(0, min(127, int(127 * (1 - abs(distance - radius) / 2))))
        
        # Blue-cyan gradient
        pad_colors.append((i, 0, intensity // 2, intensity))
    
    fire.set_multiple_pad_colors(pad_colors)


def matrix_rain(fire, frame):
    """Create a matrix-style rain effect."""
    pad_colors = []
    
    for i in range(64):
        row = i // 16
        col = i % 16
        
        # Different drop speeds for each column
        drop_pos = (col * 7 + frame * 2) % 80
        
        if drop_pos < 64:
            # Calculate intensity based on position
            intensity = max(0, min(127, int(127 * (1 - abs(row * 16 - drop_pos) / 16))))
            pad_colors.append((i, 0, intensity, 0))
        else:
            pad_colors.append((i, 0, 0, 0))
    
    fire.set_multiple_pad_colors(pad_colors)


def main():
    # Initialize controller
    fire = get_akai_fire()
    
    # Clear everything first
    fire.clear_all_pads()
    
    animations = [rainbow_wave, circular_pulse, matrix_rain]
    current_animation = 0
    frame = 0
    
    print("Batch Animation Demo")
    print("Press Ctrl+C to exit")
    print("\nAnimations cycle automatically every 10 seconds")
    
    try:
        while True:
            # Switch animation every 300 frames (~10 seconds at 30fps)
            if frame % 300 == 0 and frame > 0:
                current_animation = (current_animation + 1) % len(animations)
                print(f"Switching to: {animations[current_animation].__name__}")
            
            # Run current animation
            animations[current_animation](fire, frame)
            
            # ~30 FPS
            time.sleep(0.033)
            frame += 1
            
            # Handle mock GUI events if using mock
            if hasattr(fire, "process_events"):
                if not fire.process_events():
                    break
                    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        fire.clear_all_pads()
        fire.close()


if __name__ == "__main__":
    main()