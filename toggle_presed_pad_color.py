from akai_fire import AkaiFire

if __name__ == "__main__":
    fire = AkaiFire(port_name="FL STUDIO FIRE")

    fire.clear_pads()

    fire.set_pad_color(0, 0, 3, 0)
