import rtmidi

# Constants
BITMAP_SIZE = 1171  # For OLED 128x64, calculated as ceil(128*64/7)
BITMUTATE = [
    [13, 0, 1, 2, 3, 4, 5, 6],
    [19, 20, 7, 8, 9, 10, 11, 12],
    [25, 26, 27, 14, 15, 16, 17, 18],
    [31, 32, 33, 34, 21, 22, 23, 24],
    [37, 38, 39, 40, 41, 28, 29, 30],
    [43, 44, 45, 46, 47, 48, 35, 36],
    [49, 50, 51, 52, 53, 54, 55, 42],
]


class AkaiFireBitmap:
    def __init__(self):
        self.bitmap = [0] * BITMAP_SIZE

    def clear(self):
        """Clear the bitmap."""
        self.bitmap = [0] * BITMAP_SIZE

    def set_pixel(self, x: int, y: int, color: int):
        """
        Set a pixel on the OLED display.
        :param x: X coordinate (0-127).
        :param y: Y coordinate (0-63).
        :param color: 0 for black, nonzero for white.
        """
        if 0 <= x < 128 and 0 <= y < 64:
            x = x + int(128 * (y // 8))
            y %= 8
            rb = BITMUTATE[int(x % 7)][y]
            index = int((x // 7) * 8 + (rb // 7))
            if color > 0:
                self.bitmap[index] |= 1 << (rb % 7)
            else:
                self.bitmap[index] &= ~(1 << (rb % 7))

    def send_to_device(self, midi_out):
        """
        Send the bitmap to the Akai Fire device using MIDI SysEx.
        :param midi_out: The RtMidi output instance.
        """
        chunk_size = BITMAP_SIZE + 4
        sysex_data = [
            0xF0,  # Start of SysEx
            0x47,  # Manufacturer ID (Akai)
            0x7F,  # All-Call address
            0x43,  # Akai Fire product ID
            0x0E,  # OLED Write command
            chunk_size >> 7,  # Payload length (MSB)
            chunk_size & 0x7F,  # Payload length (LSB)
            0,
            0x07,  # Start and end band
            0,
            0x7F,  # Start and end column
        ]
        sysex_data.extend(self.bitmap)
        sysex_data.append(0xF7)  # End of SysEx
        midi_out.send_message(sysex_data)

    def draw_horizontal_line(self, x: int, y: int, length: int):
        """Draw a horizontal line."""
        for i in range(length):
            self.set_pixel(x + i, y, 1)

    def draw_vertical_line(self, x: int, y: int, length: int):
        """Draw a vertical line."""
        for i in range(length):
            self.set_pixel(x, y + i, 1)


# Example usage
def main():
    # Initialize the bitmap
    fire_bitmap = AkaiFireBitmap()

    # Clear the bitmap
    fire_bitmap.clear()

    # Draw a single white line
    fire_bitmap.draw_horizontal_line(0, 10, 128)  # Draw a horizontal line at row 10

    # Open MIDI output
    port_name = "FL STUDIO FIRE 10"
    midi_out = rtmidi.MidiOut()
    available_ports = midi_out.get_ports()
    fire_port = None

    for index, name in enumerate(available_ports):
        if port_name in name:
            fire_port = index
            break

    if fire_port is None:
        print(f"MIDI port '{port_name}' not found. Available ports: {available_ports}")
        return

    midi_out.open_port(fire_port)

    # Send bitmap to the device
    fire_bitmap.send_to_device(midi_out)
    print("Bitmap sent to the device!")

    # Close the MIDI port
    midi_out.close_port()


if __name__ == "__main__":
    main()
