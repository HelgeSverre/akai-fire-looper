"""Sweep all 64 pads through red, green and blue at four visible brightnesses.

Run with ``uv run python -m examples.pads_color_cycle``. Close the mock window
or press Ctrl+C to stop; pad LEDs are cleared on exit.
"""

from akai_fire import get_akai_fire
from examples._runtime import wait


def main():
    with get_akai_fire() as fire:
        fire.clear_all_pads()
        try:
            print(
                "Cycling pad colors at brightness 32, 64, 96 and 127. Ctrl+C to stop."
            )
            for _ in range(3):
                for channel, name in enumerate(("Red", "Green", "Blue")):
                    print(f"Cycling {name}")
                    # Pad RGB is 7-bit (0–127), unlike the small button LED enums.
                    for intensity in (32, 64, 96, 127):
                        rgb = [0, 0, 0]
                        rgb[channel] = intensity
                        for pad in range(64):
                            fire.set_pad_color(pad, *rgb)
                            wait(fire, 0.01)
                        wait(fire, 0.15)
        except KeyboardInterrupt:
            print("Animation stopped.")
        finally:
            fire.clear_all_pads()


if __name__ == "__main__":
    main()
