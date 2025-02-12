from akai_fire import AkaiFire
import time


def main():
    fire = AkaiFire()

    # # Global button listener
    # @fire.on_button()
    # def on_any_button(button_id, event):
    #     print(f"Button {button_id} {event}")
    #
    # # Specific button listener
    # @fire.on_button(fire.BUTTON_DRUM)
    # def on_drum_button(event):
    #     print(f"Button DRUM {event}")
    #
    # # Global rotary listener
    # @fire.on_rotary_touch(fire.ROTARY_VOLUME)
    # def on_volume_touch(event, velocity):
    #     print(f"Rotary VOLUME {event} with velocity {velocity}")
    #
    # # Global rotary listener
    # @fire.on_rotary_turn(fire.ROTARY_VOLUME)
    # def on_volume_rotate(event, direction, velocity):
    #     print(
    #         f"Rotary TURN event: {event}, direction: {direction}, velocity: {velocity}"
    #     )

    # # Global rotary listener
    # @fire.on_rotary_turn()
    # def on_any_rotary(rotary_id, direction):
    #     print(f"Rotary {rotary_id} turned {direction}")
    #
    # # Specific rotary listener
    # @fire.on_rotary_turn(fire.ROTARY_PAN)
    # def on_pan_turn(direction):
    #     print(f"Rotary PAN turned {direction}")
    #
    # # Global pad listener
    # @fire.on_pad()
    # def on_any_pad(pad_number):
    #     print(f"Pad {pad_number} pressed")

    # Multiple handlers for the same button
    @fire.on_button(fire.BUTTON_PLAY)
    def handle_play_led(event):
        if event == "press":
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
        else:
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_OFF)

    @fire.on_button(fire.BUTTON_PLAY)
    def handle_play_logic(event):
        if event == "press":
            print("Starting playback...")
        else:
            print("Playback stopped or paused.")

    @fire.on_button(fire.BUTTON_SOLO_3)
    def go_solo(event):
        print("SOLO: ", event)

    # Multiple global handlers
    @fire.on_pad()
    def log_pads(pad_index, velocity):
        print(
            f"Pad {pad_index} hit with velocity {velocity} - col: "
            + str(AkaiFire.get_pad_column(pad_index))
            + " row: "
            + str(AkaiFire.get_pad_row(pad_index))
        )

    @fire.on_pad()
    def light_pads(pad_index, velocity):
        if velocity > 40:
            fire.set_pad_color(pad_index, 3, 0, 0)
        else:
            fire.set_pad_color(pad_index, 0, 0, 0)

    @fire.on_rotary_turn(fire.ROTARY_VOLUME)
    def handle_volume_display(direction, velocity, **kwargs):
        print(f"Volume display updated to {velocity} - {direction}")

    print("Listening for events... Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Exiting...")
        fire.clear_all()


if __name__ == "__main__":
    main()
