import time

from akai_fire import AkaiFire


def main():
    fire = AkaiFire()

    for label, state in [
        # fmt: off
        ("CONTROL_BANK_ALL_OFF", AkaiFire.CONTROL_BANK_ALL_OFF),
        ("CONTROL_BANK_ALL_ON", AkaiFire.CONTROL_BANK_ALL_ON),
        ("CONTROL_BANK_CHANNEL", AkaiFire.CONTROL_BANK_CHANNEL),
        ("CONTROL_BANK_CHANNEL_AND_MIXER", AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER),
        ("CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1", AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1),
        ("CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2", AkaiFire.CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2),
        ("CONTROL_BANK_CHANNEL_AND_USER1", AkaiFire.CONTROL_BANK_CHANNEL_AND_USER1),
        ("CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2", AkaiFire.CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2),
        ("CONTROL_BANK_CHANNEL_AND_USER2", AkaiFire.CONTROL_BANK_CHANNEL_AND_USER2),
        ("CONTROL_BANK_MIXER", AkaiFire.CONTROL_BANK_MIXER),
        ("CONTROL_BANK_MIXER_AND_USER1_AND_USER2", AkaiFire.CONTROL_BANK_MIXER_AND_USER1_AND_USER2),
        ("CONTROL_BANK_MIXER_AND_USER2", AkaiFire.CONTROL_BANK_MIXER_AND_USER2),
        ("CONTROL_BANK_USER1", AkaiFire.CONTROL_BANK_USER1),
        ("CONTROL_BANK_USER1_AND_USER2", AkaiFire.CONTROL_BANK_USER1_AND_USER2),
        ("CONTROL_BANK_USER2", AkaiFire.CONTROL_BANK_USER2),
        # fmt: on
    ]:
        fire.set_control_bank_leds(state)
        print(f"Control Bank LED state -> '{label}' : {hex(state)} (hex)")
        time.sleep(0.1)

    time.sleep(1)
    fire.clear_control_bank_leds()
    fire.close()


if __name__ == "__main__":
    print("Clearing all pads and buttons...")
    main()
