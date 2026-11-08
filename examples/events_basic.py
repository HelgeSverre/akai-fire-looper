"""Log pad/button/encoder input and light each pressed pad."""

from akai_fire import get_akai_fire
from examples._runtime import wait


def main():
    with get_akai_fire() as fire:

        @fire.on_pad()
        def on_pad(pad, velocity):
            row, column = divmod(pad, 16)
            print(f"Pad {pad}: row {row}, column {column}, velocity {velocity}")
            fire.set_pad_color(pad, 0, min(127, velocity), 0)

        @fire.on_button()
        def on_button(button, event):
            print(f"Button {button:#04x}: {event}")

        @fire.on_rotary_turn()
        def on_encoder(encoder, direction, velocity):
            print(f"Encoder {encoder:#04x}: {direction}, {velocity}")

        print("Press pads/buttons or turn encoders. Ctrl+C or close window to exit.")
        try:
            while True:
                wait(fire, 0.01)
        except KeyboardInterrupt:
            pass
        finally:
            fire.clear_all()


if __name__ == "__main__":
    main()
