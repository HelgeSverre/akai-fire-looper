"""
AKAI Fire Example: Batch vs Individual Pad Updates Performance Comparison

This example demonstrates the performance difference between updating pads
individually versus using batch updates with set_multiple_pad_colors().

Results show that batch updates are significantly more efficient for
animations or when updating many pads at once.
"""

import time
import random
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


def measure_individual_updates(fire, num_updates=10):
    """Measure time for individual pad updates."""
    colors = [(random.randint(0, 127), random.randint(0, 127), random.randint(0, 127)) 
              for _ in range(64)]
    
    start_time = time.time()
    
    for _ in range(num_updates):
        # Update each pad individually
        for i in range(64):
            r, g, b = colors[i]
            fire.set_pad_color(i, r, g, b)
    
    end_time = time.time()
    return end_time - start_time


def measure_batch_updates(fire, num_updates=10):
    """Measure time for batch pad updates."""
    colors = [(i, random.randint(0, 127), random.randint(0, 127), random.randint(0, 127)) 
              for i in range(64)]
    
    start_time = time.time()
    
    for _ in range(num_updates):
        # Update all pads in one batch
        fire.set_multiple_pad_colors(colors)
    
    end_time = time.time()
    return end_time - start_time


def animate_wave_individual(fire, frames=60):
    """Animate a wave pattern using individual updates."""
    print("\nAnimating wave with individual updates...")
    start_time = time.time()
    
    for frame in range(frames):
        for i in range(64):
            intensity = int((math.sin(i * 0.2 + frame * 0.1) + 1) * 63.5)
            fire.set_pad_color(i, intensity, 0, 127 - intensity)
        time.sleep(0.016)  # Target 60 FPS
        
        # Handle mock GUI events
        if hasattr(fire, "process_events"):
            if not fire.process_events():
                break
    
    return time.time() - start_time


def animate_wave_batch(fire, frames=60):
    """Animate a wave pattern using batch updates."""
    print("\nAnimating wave with batch updates...")
    start_time = time.time()
    
    for frame in range(frames):
        pad_colors = []
        for i in range(64):
            intensity = int((math.sin(i * 0.2 + frame * 0.1) + 1) * 63.5)
            pad_colors.append((i, intensity, 0, 127 - intensity))
        
        fire.set_multiple_pad_colors(pad_colors)
        time.sleep(0.016)  # Target 60 FPS
        
        # Handle mock GUI events
        if hasattr(fire, "process_events"):
            if not fire.process_events():
                break
    
    return time.time() - start_time


def main():
    import math  # Import here to use in animation functions
    
    # Initialize controller
    fire = get_akai_fire()
    fire.clear_all_pads()
    
    print("=== Batch vs Individual Performance Test ===\n")
    
    # Test 1: Static updates
    print("Test 1: Updating all 64 pads 10 times")
    print("-" * 40)
    
    individual_time = measure_individual_updates(fire, 10)
    print(f"Individual updates: {individual_time:.3f}s")
    print(f"  Per update: {individual_time/10:.3f}s")
    print(f"  Updates/sec: {10/individual_time:.1f}")
    
    time.sleep(0.5)
    
    batch_time = measure_batch_updates(fire, 10)
    print(f"\nBatch updates: {batch_time:.3f}s")
    print(f"  Per update: {batch_time/10:.3f}s")
    print(f"  Updates/sec: {10/batch_time:.1f}")
    
    speedup = individual_time / batch_time
    print(f"\n✨ Batch is {speedup:.1f}x faster!")
    
    time.sleep(1)
    
    # Test 2: Animation performance
    print("\n\nTest 2: 60-frame wave animation")
    print("-" * 40)
    
    individual_anim_time = animate_wave_individual(fire, 60)
    print(f"Individual animation: {individual_anim_time:.3f}s")
    print(f"  Average FPS: {60/individual_anim_time:.1f}")
    
    time.sleep(0.5)
    
    batch_anim_time = animate_wave_batch(fire, 60)
    print(f"Batch animation: {batch_anim_time:.3f}s")
    print(f"  Average FPS: {60/batch_anim_time:.1f}")
    
    anim_speedup = individual_anim_time / batch_anim_time
    print(f"\n✨ Batch animation is {anim_speedup:.1f}x faster!")
    
    # Recommendations
    print("\n\nRecommendations:")
    print("-" * 40)
    print("✓ Use set_multiple_pad_colors() when:")
    print("  - Updating many pads at once (>5-10 pads)")
    print("  - Creating animations")
    print("  - Clearing the pad grid")
    print("  - Loading preset patterns")
    print("\n✓ Use set_pad_color() when:")
    print("  - Updating just 1-2 pads")
    print("  - Responding to individual pad presses")
    print("  - Making small incremental changes")
    
    # Demo: Show the difference visually
    print("\n\nPress any key to see visual comparison...")
    input()
    
    print("\nShowing choppy animation (individual updates)...")
    for frame in range(30):
        for i in range(64):
            brightness = int((frame / 30) * 127)
            fire.set_pad_color(i, brightness, 0, 0)
        time.sleep(0.033)
        if hasattr(fire, "process_events"):
            if not fire.process_events():
                break
    
    fire.clear_all_pads()
    time.sleep(0.5)
    
    print("Showing smooth animation (batch updates)...")
    for frame in range(30):
        pad_colors = []
        brightness = int((frame / 30) * 127)
        for i in range(64):
            pad_colors.append((i, 0, brightness, 0))
        fire.set_multiple_pad_colors(pad_colors)
        time.sleep(0.033)
        if hasattr(fire, "process_events"):
            if not fire.process_events():
                break
    
    print("\nTest complete!")
    fire.clear_all_pads()
    fire.close()


if __name__ == "__main__":
    main()