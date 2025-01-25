import time

from akai_fire import AkaiFire


def animate_track_pads(fire, track_number, color_type="red"):
    """Animate pads in a track with forward and reverse patterns."""
    # Calculate pad indices for this track (16 pads per track)
    start_pad = (track_number - 1) * 16
    end_pad = start_pad + 16

    # Set color values based on type
    if color_type == "red":
        dull_color = [(0, 20, 0, 0)]  # Dull red
        high_color = [(0, 60, 0, 0)]  # High red
    else:  # green
        dull_color = [(0, 0, 20, 0)]  # Dull green
        high_color = [(0, 0, 60, 0)]  # High green

    # Forward animation
    for pad in range(start_pad, end_pad):
        # Set pad to dull color
        fire.set_multiple_pad_colors([(pad, *dull_color[0][1:])])
        time.sleep(0.01)

        # Set pad to high color
        fire.set_multiple_pad_colors([(pad, *high_color[0][1:])])
        time.sleep(0.01)

        # Set back to dull before moving to next pad
        fire.set_multiple_pad_colors([(pad, *dull_color[0][1:])])

    # Reverse animation
    for pad in range(end_pad - 1, start_pad - 1, -1):
        # Set pad to dull color
        fire.set_multiple_pad_colors([(pad, *dull_color[0][1:])])
        time.sleep(0.01)

        # Turn off pad
        fire.set_multiple_pad_colors([(pad, 0, 0, 0)])
        time.sleep(0.01)


if __name__ == "__main__":

    fire = AkaiFire()

    try:
        print("Starting AKAI Fire demo sequence...")

        # Clear all pads and LEDs initially
        fire.clear_all_pads()
        fire.clear_all_button_leds()
        fire.clear_all_track_leds()

        # Animate each track's LED and pads
        for track_index in [1, 2, 3, 4]:

            if track_index == 1:
                button = AkaiFire.BUTTON_SOLO_1
            elif track_index == 2:
                button = AkaiFire.BUTTON_SOLO_2
            elif track_index == 3:
                button = AkaiFire.BUTTON_SOLO_3
            else:
                button = AkaiFire.BUTTON_SOLO_4

            if button:
                fire.set_button_led(AkaiFire.BUTTON_SOLO_1, AkaiFire.LED_DULL_GREEN)
                time.sleep(0.5)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_1, AkaiFire.LED_HIGH_GREEN)
                time.sleep(0.1)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_2, AkaiFire.LED_DULL_GREEN)
                time.sleep(0.5)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_2, AkaiFire.LED_HIGH_GREEN)
                time.sleep(0.1)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_3, AkaiFire.LED_DULL_GREEN)
                time.sleep(0.5)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_3, AkaiFire.LED_HIGH_GREEN)
                time.sleep(0.1)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_4, AkaiFire.LED_DULL_GREEN)
                time.sleep(0.5)
                fire.set_button_led(AkaiFire.BUTTON_SOLO_4, AkaiFire.LED_HIGH_GREEN)
                time.sleep(0.1)

            time.sleep(0.02)

            fire.set_track_led(track_index, AkaiFire.RECTANGLE_LED_DULL_RED)
            time.sleep(0.02)
            fire.set_track_led(track_index, AkaiFire.RECTANGLE_LED_HIGH_RED)
            time.sleep(0.02)
            fire.set_track_led(track_index, AkaiFire.RECTANGLE_LED_DULL_RED)
            time.sleep(0.02)

            # Animate pads with red
            # animate_track_pads(fire, track_index, "red")

            # Animate pads with green
            # animate_track_pads(fire, track_index, "green")

            time.sleep(1)

            fire.set_track_led(track_index, AkaiFire.RECTANGLE_LED_OFF)

        print("Demo sequence completed successfully.")

    except KeyboardInterrupt:
        print("Animation interrupted by user.")

    finally:
        # Clean up
        fire.clear_bitmap()
        fire.clear_all_pads()
        fire.clear_all_button_leds()
        fire.clear_all_track_leds()
        fire.close()
