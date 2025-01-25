import time

from akai_fire import AkaiFire


def create_color_batch(r, g, b):
    """Create a batch of pad colors for all 64 pads."""
    return [(pad, r, g, b) for pad in range(64)]


if __name__ == "__main__":
    fire = AkaiFire()
    fire.clear_all_pads()

    try:
        # We'll create smoother transitions by using more intensity levels
        intensity_levels = 32  # More granular than the original 4 levels

        while True:
            # Red fade up and down
            for i in range(intensity_levels * 2):
                intensity = min(
                    127, abs(intensity_levels - i) * (127 // intensity_levels)
                )
                fire.set_multiple_pad_colors(create_color_batch(intensity, 0, 0))
                time.sleep(0.02)

            # Green fade up and down
            for i in range(intensity_levels * 2):
                intensity = min(
                    127, abs(intensity_levels - i) * (127 // intensity_levels)
                )
                fire.set_multiple_pad_colors(create_color_batch(0, intensity, 0))
                time.sleep(0.02)

            # Blue fade up and down
            for i in range(intensity_levels * 2):
                intensity = min(
                    127, abs(intensity_levels - i) * (127 // intensity_levels)
                )
                fire.set_multiple_pad_colors(create_color_batch(0, 0, intensity))
                time.sleep(0.02)

            # Rainbow transition
            for i in range(intensity_levels * 3):
                position = i % (intensity_levels * 3)
                r = max(
                    0,
                    min(
                        127,
                        abs(intensity_levels - position) * (127 // intensity_levels),
                    ),
                )
                g = max(
                    0,
                    min(
                        127,
                        abs(intensity_levels - (position - intensity_levels))
                        * (127 // intensity_levels),
                    ),
                )
                b = max(
                    0,
                    min(
                        127,
                        abs(intensity_levels - (position - intensity_levels * 2))
                        * (127 // intensity_levels),
                    ),
                )
                fire.set_multiple_pad_colors(create_color_batch(r, g, b))
                time.sleep(0.02)

    except KeyboardInterrupt:
        fire.clear_all_pads()
        fire.close()
