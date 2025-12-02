"""
AKAI Fire Example: Performance Optimizations Demo

This example demonstrates the performance improvements available in the library:
1. Fast path methods that skip validation
2. Cached common operations
3. Batch updates vs individual updates
4. Display optimization with caching
"""

import time
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire


def benchmark_operation(name, operation, iterations=100):
    """Benchmark an operation and return timing."""
    start = time.time()
    for _ in range(iterations):
        operation()
    end = time.time()
    total_time = end - start
    avg_time = total_time / iterations
    print(f"{name}: {total_time:.3f}s total, {avg_time*1000:.2f}ms avg")
    return total_time


def demo_fast_path(fire):
    """Demonstrate fast path methods."""
    print("\n=== Fast Path Methods ===")
    print("Setting pad colors with validation vs fast path...")

    # Regular method with validation
    def regular_update():
        for i in range(64):
            fire.set_pad_color(i, i * 2, 127 - i * 2, i)

    # Fast path (assuming we know values are valid)
    def fast_update():
        for i in range(64):
            fire.set_pad_color_fast(i, i * 2, 127 - i * 2, i)

    regular_time = benchmark_operation("Regular set_pad_color", regular_update, 10)
    fast_time = benchmark_operation("Fast set_pad_color_fast", fast_update, 10)

    speedup = regular_time / fast_time
    print(f"✨ Fast path is {speedup:.1f}x faster!")


def demo_cached_operations(fire):
    """Demonstrate cached operations."""
    print("\n=== Cached Operations ===")
    print("Clearing pads with cached vs uncached methods...")

    # Using cached clear
    def cached_clear():
        fire.clear_all_pads()

    # Using uncached method
    def uncached_clear():
        fire.reset_pads(0, 0, 0)

    # Using optimized set_all_pads
    def optimized_clear():
        fire.set_all_pads((0, 0, 0))

    cached_time = benchmark_operation("Cached clear_all_pads", cached_clear, 50)
    uncached_time = benchmark_operation("Uncached reset_pads", uncached_clear, 50)
    optimized_time = benchmark_operation("Optimized set_all_pads", optimized_clear, 50)

    print(f"✨ Cached method is {uncached_time/cached_time:.1f}x faster than uncached!")
    print(
        f"✨ Optimized method is {uncached_time/optimized_time:.1f}x faster than uncached!"
    )


def demo_display_caching(fire):
    """Demonstrate display caching benefits."""
    print("\n=== Display Caching ===")
    print("Rendering identical vs changing content...")

    canvas = fire.get_canvas()

    # Render same content multiple times
    def render_same():
        canvas.clear()
        canvas.draw_text("Static Text", 10, 20)
        fire.render_to_display(canvas)

    # Render changing content
    counter = [0]

    def render_changing():
        canvas.clear()
        canvas.draw_text(f"Counter: {counter[0]}", 10, 20)
        counter[0] += 1
        fire.render_to_display(canvas)

    # First render to establish cache
    render_same()

    same_time = benchmark_operation("Rendering same content", render_same, 50)
    changing_time = benchmark_operation(
        "Rendering changing content", render_changing, 50
    )

    print(
        f"✨ Display caching provides {changing_time/same_time:.1f}x speedup for static content!"
    )


def demo_batch_patterns(fire):
    """Demonstrate efficient pattern generation."""
    print("\n=== Batch Pattern Generation ===")
    print("Creating animated patterns...")

    frames = 60
    start = time.time()

    for frame in range(frames):
        # Create entire pattern in one batch
        pad_colors = []
        for i in range(64):
            # Create wave pattern
            intensity = int((math.sin(i * 0.2 + frame * 0.1) + 1) * 63.5)
            pad_colors.append((i, intensity, 0, 127 - intensity))

        fire.set_multiple_pad_colors(pad_colors)
        time.sleep(0.016)  # Target 60 FPS

        # Handle mock GUI events
        if hasattr(fire, "process_events"):
            if not fire.process_events():
                break

    end = time.time()
    actual_fps = frames / (end - start)
    print(f"Achieved {actual_fps:.1f} FPS with batch updates")


def main():
    # Initialize controller
    fire = get_akai_fire()
    fire.clear_all_pads()

    print("=== AKAI Fire Performance Demo ===")
    print("This demo showcases various performance optimizations")

    try:
        # Run demos
        demo_fast_path(fire)
        time.sleep(1)

        demo_cached_operations(fire)
        time.sleep(1)

        demo_display_caching(fire)
        time.sleep(1)

        demo_batch_patterns(fire)

        print("\n=== Performance Tips ===")
        print("1. Use set_pad_color_fast() when you know inputs are valid")
        print("2. Use set_all_pads() for common colors (cached)")
        print("3. Use set_multiple_pad_colors() for animations")
        print("4. Minimize display updates - content is cached")
        print("5. Track pad states to avoid redundant updates")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        fire.clear_all_pads()
        fire.close()


if __name__ == "__main__":
    main()
