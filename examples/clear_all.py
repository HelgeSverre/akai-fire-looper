import time

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire

"""
Clears the screen, all pads and the button LEDs on the AKAI Fire.
"""


def main():
    # Initialize controller with context manager
    with get_akai_fire() as fire:
        print("Clearing all pads...")
        time.sleep(0.1)
        fire.clear_all_pads()

        print("Clearing all button LEDs...")
        time.sleep(0.1)
        fire.clear_all_button_leds()

        print("Clearing all rectangle LEDs...")
        time.sleep(0.1)
        fire.clear_all_track_leds()

        print("Clearing all control bank LEDs...")
        time.sleep(0.1)
        fire.clear_control_bank_leds()

        print("Clearing screen...")
        time.sleep(0.1)
        fire.clear_display()

        print("Done.")
        time.sleep(0.1)


if __name__ == "__main__":
    print("Clearing all pads and buttons...")
    main()
