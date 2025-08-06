import time

import rtmidi


def find_fire_ports():
    """Find the Akai Fire MIDI input and output ports."""
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    input_port = None
    output_port = None

    for i, port_name in enumerate(midi_in.get_ports()):
        if "FL STUDIO FIRE" in port_name:
            input_port = i
            print(f"Found Akai Fire MIDI INPUT port: {port_name}")

    for i, port_name in enumerate(midi_out.get_ports()):
        if "FL STUDIO FIRE" in port_name:
            output_port = i
            print(f"Found Akai Fire MIDI OUTPUT port: {port_name}")

    return midi_in, midi_out, input_port, output_port


def create_pad_sysex(pad_colors):
    """Create a SysEx message for multiple pad colors."""
    sysex_header = [0xF0, 0x47, 0x7F, 0x43, 0x65]

    # Length of payload (4 bytes per pad: index, R, G, B)
    length = len(pad_colors) * 4
    length_high = (length >> 7) & 0x7F
    length_low = length & 0x7F

    # Construct payload
    payload = []
    for index, red, green, blue in pad_colors:
        payload.extend(
            [
                index & 0x3F,
                red & 0x7F,
                green & 0x7F,
                blue & 0x7F,
            ]
        )

    return sysex_header + [length_high, length_low] + payload + [0xF7]


def main():
    midi_in, midi_out, in_port, out_port = find_fire_ports()

    if in_port is None or out_port is None:
        print("Error: Couldn't find Akai Fire ports!")
        return

    midi_out.open_port(out_port)

    try:
        print("Starting batch pad test...")

        # Prepare all 64 pads in a single batch
        # Format: (pad_index, red, green, blue)
        pad_colors = []

        # Create a rainbow pattern across all pads
        for i in range(64):
            row = i // 16  # 0-3
            col = i % 16  # 0-15

            # Create some interesting color patterns
            red = int(127 * ((16 - col) / 16))  # Fade red from right to left
            green = int(127 * (col / 16))  # Fade green from left to right
            blue = int(127 * (row / 3))  # Fade blue from top to bottom

            pad_colors.append((i, red, green, blue))

        # Send the entire batch in one SysEx message
        sysex_message = create_pad_sysex(pad_colors)
        print(f"Sending batch message of {len(pad_colors)} pads...")
        midi_out.send_message(sysex_message)

        # Wait a bit, then clear all pads
        time.sleep(5)

        # Clear all pads in one batch
        clear_colors = [(i, 0, 0, 0) for i in range(64)]
        midi_out.send_message(create_pad_sysex(clear_colors))

        print("Test completed!")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        midi_out.close_port()
        midi_in.close_port()
        del midi_out
        del midi_in


if __name__ == "__main__":
    main()
