from akai_fire import AkaiFire
import math
import time


def main():
    fire = AkaiFire()
    canvas = fire.get_canvas()

    try:
        frame = 0
        while True:
            canvas.clear()

            # Calculate time-based variables
            t = frame * 0.1
            wave_offset = math.sin(t * 0.5) * 10
            frequency = 2 + math.sin(t * 0.2) * 1

            # Draw multiple interference waves
            for x in range(128):
                # Main sine wave
                y1 = math.sin((x + wave_offset) * frequency * 0.05) * 20
                # Secondary wave
                y2 = math.cos((x - wave_offset) * frequency * 0.03) * 15
                # Combine waves with time-based amplitude
                y = 32 + y1 + y2

                # Draw vertical "energy" lines with varying heights
                height = abs(y2) + 5
                canvas.draw_vertical_line(x, int(y - height / 2), int(height), 0)

            # Add floating particles
            for i in range(8):
                particle_x = (t * 20 + i * 16) % 128
                particle_y = 32 + math.sin((t + i) * 2) * 20
                canvas.fill_circle(int(particle_x), int(particle_y), 2, 0)

            # Add interference pattern in background
            for y in range(0, 64, 4):
                for x in range(0, 128, 4):
                    if math.sin(x * 0.1 + y * 0.1 + t) > 0.7:
                        canvas.set_pixel(x, y)

            # Send to display
            fire.render_to_display()

            time.sleep(0.03)
            frame += 1

    except KeyboardInterrupt:
        fire.clear_display()
        fire.close()


if __name__ == "__main__":
    main()
