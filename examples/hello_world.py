import time

from akai_fire import AkaiFire

if __name__ == "__main__":
    # Initialize the AKAI Fire controller
    fire = AkaiFire()

    # Clear any existing pad colors
    fire.clear_all_pads()

    try:
        while True:
            for r in range(4):  # Red intensity (0-3)
                for g in range(4):  # Green intensity (0-3)
                    for b in range(4):  # Blue intensity (0-3)
                        for pad in range(64):  # Loop through all 64 pads
                            fire.set_pad_color(pad, r, g, b)

                        # Brief delay before the next color
                        time.sleep(0.1)
    except KeyboardInterrupt:
        # Reset pads when exiting
        fire.clear_all_pads()
        fire.close()