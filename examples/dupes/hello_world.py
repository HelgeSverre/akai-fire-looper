import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire

if __name__ == "__main__":
    # Initialize controller (auto-detects hardware or falls back to mock GUI)
    fire = get_akai_fire()

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
                        time.sleep(0.2)
                        # Handle mock GUI events if using mock
                        if hasattr(fire, "process_events"):
                            if not fire.process_events():
                                break
    except KeyboardInterrupt:
        # Reset pads when exiting
        fire.clear_all_pads()
        fire.close()
