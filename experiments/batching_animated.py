import math
import time

import rtmidi


def find_fire_ports():
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    input_port = output_port = None
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
    sysex_header = [0xF0, 0x47, 0x7F, 0x43, 0x65]
    length = len(pad_colors) * 4
    length_high = (length >> 7) & 0x7F
    length_low = length & 0x7F

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


def animate_fire():
    midi_in, midi_out, in_port, out_port = find_fire_ports()

    if in_port is None or out_port is None:
        print("Error: Couldn't find Akai Fire ports!")
        return

    midi_out.open_port(out_port)

    try:
        print("Starting animations...")

        frame = 0
        while True:
            pad_colors = []

            # Create different animation patterns based on frame number
            animation_type = (frame // 100) % 4  # Switch animation every 100 frames

            if animation_type == 0:
                # Rotating rainbow
                for i in range(64):
                    row = i // 16
                    col = i % 16
                    angle = (frame * 0.1 + (col + row * 16) * (360 / 64)) % 360

                    # Convert HSV to RGB (simplified)
                    h = angle / 60
                    x = int(127 * (1 - abs(h % 2 - 1)))
                    if h < 1:
                        rgb = (127, x, 0)
                    elif h < 2:
                        rgb = (x, 127, 0)
                    elif h < 3:
                        rgb = (0, 127, x)
                    elif h < 4:
                        rgb = (0, x, 127)
                    elif h < 5:
                        rgb = (x, 0, 127)
                    else:
                        rgb = (127, 0, x)

                    pad_colors.append((i, *rgb))

            elif animation_type == 1:
                # Expanding/contracting circles
                center_x, center_y = 7.5, 1.5  # Center of the grid
                radius = 2 + math.sin(frame * 0.1) * 2  # Pulsing radius

                for i in range(64):
                    row = i // 16
                    col = i % 16
                    distance = math.sqrt((col - center_x) ** 2 + (row - center_y) ** 2)
                    intensity = max(
                        0, min(127, int(127 * (1 - abs(distance - radius))))
                    )

                    pad_colors.append((i, intensity, 0, intensity))

            elif animation_type == 2:
                # Wave pattern
                for i in range(64):
                    row = i // 16
                    col = i % 16
                    wave = math.sin(frame * 0.1 + (col + row) * 0.5) * 127
                    red = max(0, min(127, int(wave)))
                    green = max(0, min(127, int(wave * 0.5)))
                    blue = max(0, min(127, int(-wave)))
                    pad_colors.append((i, red, green, blue))

            else:
                # Matrix-style rain
                for i in range(64):
                    row = i // 16
                    col = i % 16
                    drop = (col * 7 + frame) % 80  # Different speeds for each column
                    if drop < 64:
                        intensity = max(
                            0, min(127, int(127 * (1 - abs(row * 16 - drop) / 16)))
                        )
                        pad_colors.append((i, 0, intensity, 0))
                    else:
                        pad_colors.append((i, 0, 0, 0))

            # Send the batch update
            midi_out.send_message(create_pad_sysex(pad_colors))

            # Control animation speed
            time.sleep(0.03)
            frame += 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        # Clear all pads before exiting
        clear_colors = [(i, 0, 0, 0) for i in range(64)]
        midi_out.send_message(create_pad_sysex(clear_colors))
    finally:
        midi_out.close_port()
        midi_in.close_port()
        del midi_out
        del midi_in


if __name__ == "__main__":
    animate_fire()
