import time

from akai_fire import AkaiFire

"""
Clears the screen, all pads and the button LEDs on the AKAI Fire.
"""


def main():
    fire = AkaiFire()

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
    fire.close()


if __name__ == "__main__":
    print("Clearing all pads and buttons...")
    main()
