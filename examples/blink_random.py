"""
AKAI Fire Example: Dynamic Wave Pads and Reversing Button LED Cycling

This script demonstrates how to use the AKAI Fire MIDI controller to create an advanced
lighting effect. Pads feature a dynamic wave-like animation with pulsating brightness, while
buttons cycle through their LED states in alternating directions.

Key Features:
- Dynamic wave-like animation with pulsating brightness for pads.
- Buttons cycle through LED states, reversing direction periodically.
- Faster and visually engaging effects.
- Clears the pads and resets button states on exit.
"""

import time

from akai_fire import AkaiFire


def main():
    """
    Main function for running the enhanced lighting animation.

    Features dynamic wave-like animations on the pads and reversing button LED cycling.
    """
    # Initialize the AKAI Fire controller
    fire = AkaiFire()

    # LED states for BUTTON_* LEDs
    button_led_states = [
        fire.LED_OFF,
        fire.LED_DULL_RED,
        fire.LED_HIGH_RED,
        fire.LED_DULL_GREEN,
        fire.LED_HIGH_GREEN,
    ]

    # List of button IDs to cycle through
    buttons = [
        fire.BUTTON_STEP,
        fire.BUTTON_NOTE,
        fire.BUTTON_DRUM,
        fire.BUTTON_PERFORM,
        fire.BUTTON_PLAY,
        fire.BUTTON_STOP,
        fire.BUTTON_REC,
    ]

    # Animation parameters
    frame = 0  # Frame counter
    button_cycle_reverse = False  # Toggle for reversing button cycling
    wave_speed = 2  # Speed of the wave effect
    brightness_pulse_period = 60  # Frames for one full brightness pulse

    try:
        while True:
            # Wave effect on pads
            for pad_index in range(64):
                # Create a traveling wave effect with pulsating brightness
                distance = (pad_index + frame * wave_speed) % 64
                intensity = abs(distance - 32) / 32  # Normalize distance for wave
                brightness = int(
                    (
                        1
                        + abs(
                            (frame % brightness_pulse_period)
                            - brightness_pulse_period / 2
                        )
                        / (brightness_pulse_period / 2)
                    )
                    * 3
                )

                # RGB values modulated by wave intensity and brightness
                red = int((1 - intensity) * brightness) % 4
                green = int((0.5 + intensity / 2) * brightness) % 4
                blue = int(intensity * brightness) % 4

                fire.set_pad_color(pad_index, red, green, blue)

            # Reverse button cycling direction every 10 seconds
            if frame % (10 * int(1 / 0.1)) == 0:  # 10 seconds
                button_cycle_reverse = not button_cycle_reverse

            # Cycle button LEDs
            for i, button in enumerate(buttons):
                offset = -i if button_cycle_reverse else i
                state = button_led_states[
                    (frame // 4 + offset) % len(button_led_states)
                ]
                fire.set_button_led(button, state)

            # Brief delay for smoother animation
            time.sleep(0.1)
            frame += 1

    except KeyboardInterrupt:
        print("Animation interrupted by user.")
    finally:
        print("Resetting pads and buttons, and closing connection...")
        fire.clear_all_pads()
        fire.clear_all_button_leds()
        fire.close()


if __name__ == "__main__":
    main()
