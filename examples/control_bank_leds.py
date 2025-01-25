"""
AKAI Fire Example: Control Bank LED Management

This script demonstrates various ways to manage the control bank LEDs on the AKAI Fire controller.
Control bank LEDs are the circular LEDs used to indicate different modes on the controller.

Features:
- Examples of using predefined constants for common LED combinations.
- Examples of using bitwise operations (bit-or `|`) to dynamically set LED states.
- Demonstrates raw hexadecimal values for advanced users.

Usage:
    python control_bank_leds_example.py

The script will:
1. Demonstrate predefined constants for common states.
2. Show how to manually combine bitfields for custom states.
3. Use raw hexadecimal values for demonstration purposes.
"""

import time

from akai_fire import AkaiFire


def main():
    """
    Main function to demonstrate control bank LED management.
    """
    # Initialize the AKAI Fire controller
    fire = AkaiFire()

    # === Predefined Constants ===
    print("=== Using Predefined Constants ===")
    fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_ALL_ON)
    print("Control Bank LED state -> ALL ON")
    time.sleep(2)

    fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_ALL_OFF)
    print("Control Bank LED state -> ALL OFF")
    time.sleep(2)

    fire.set_control_bank_leds(AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER)
    print("Control Bank LED state -> CHANNEL and MIXER")
    time.sleep(2)

    # === Using Bitfields (Dynamic Combination) ===
    print("\n=== Using Bitfields ===")
    # Combine fields dynamically using bitwise OR (|)
    custom_state = (
        AkaiFire.FIELD_BASE
        | AkaiFire.FIELD_CHANNEL
        | AkaiFire.FIELD_USER1
        | AkaiFire.FIELD_USER2
    )
    fire.set_control_bank_leds(custom_state)
    print("Control Bank LED state -> CHANNEL, USER1, and USER2 (bitwise OR)")
    time.sleep(2)

    # Another dynamic combination
    fire.set_control_bank_leds(
        AkaiFire.FIELD_BASE | AkaiFire.FIELD_MIXER | AkaiFire.FIELD_USER1
    )
    print("Control Bank LED state -> MIXER and USER1 (bitwise OR)")
    time.sleep(2)

    # === Using Raw Values ===
    print("\n=== Using Raw Hexadecimal Values ===")
    # Set a custom state using raw hexadecimal values
    fire.set_control_bank_leds(0x1F)  # All LEDs ON
    print("Control Bank LED state -> ALL ON (raw hex: 0x1F)")
    time.sleep(2)

    fire.set_control_bank_leds(0x10)  # All LEDs OFF
    print("Control Bank LED state -> ALL OFF (raw hex: 0x10)")
    time.sleep(2)

    fire.set_control_bank_leds(0x13)  # CHANNEL and MIXER
    print("Control Bank LED state -> CHANNEL and MIXER (raw hex: 0x13)")
    time.sleep(2)

    # === Clean Up ===
    print("\nClearing all control bank LEDs...")
    fire.clear_control_bank_leds()
    fire.close()


if __name__ == "__main__":
    print("Starting Control Bank LED Demo...")
    main()
