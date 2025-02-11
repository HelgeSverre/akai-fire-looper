# TODO: Move into akai_fire_screen
# Constants
BITMAP_SIZE: int = 1171  # For OLED 128x64, calculated as ceil(128*64/7)
BITMAP_PIXEL_MAPPING: list[list[int]] = [
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
        """Set a pixel on the OLED display."""
        if 0 <= x < 128 and 0 <= y < 64:
            x = x + int(128 * (y // 8))
            y %= 8
            rb = BITMAP_PIXEL_MAPPING[int(x % 7)][y]
            index = int((x // 7) * 8 + (rb // 7))
            if color > 0:
                self.bitmap[index] |= 1 << (rb % 7)
            else:
                self.bitmap[index] &= ~(1 << (rb % 7))

    def get_sysex_message(self):
        """Send the bitmap to the Akai Fire device using MIDI SysEx."""
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
        return sysex_data

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int):
        """Draw a horizontal line."""
        for i in range(length):
            self.set_pixel(x + i, y, color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int):
        """Draw a vertical line."""
        for i in range(length):
            self.set_pixel(x, y + i, color)

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: int):
        """Draw a rectangle."""
        self.draw_horizontal_line(x, y, width, color)
        self.draw_horizontal_line(x, y + height - 1, width, color)
        self.draw_vertical_line(x, y, height, color)
        self.draw_vertical_line(x + width - 1, y, height, color)

    def fill_rectangle(self, x: int, y: int, width: int, height: int, color: int):
        """Fill a rectangle."""
        for i in range(height):
            self.draw_horizontal_line(x, y + i, width, color)

    def draw_circle(self, x0: int, y0: int, radius: int, color: int):
        """Draw a circle using the midpoint circle algorithm."""
        x = radius
        y = 0
        decision_over_2 = 1 - x

        while x >= y:
            self.set_pixel(x0 + x, y0 + y, color)
            self.set_pixel(x0 + y, y0 + x, color)
            self.set_pixel(x0 - y, y0 + x, color)
            self.set_pixel(x0 - x, y0 + y, color)
            self.set_pixel(x0 - x, y0 - y, color)
            self.set_pixel(x0 - y, y0 - x, color)
            self.set_pixel(x0 + y, y0 - x, color)
            self.set_pixel(x0 + x, y0 - y, color)
            y += 1
            if decision_over_2 <= 0:
                decision_over_2 += 2 * y + 1
            else:
                x -= 1
                decision_over_2 += 2 * (y - x) + 1

    def fill_circle(self, x0: int, y0: int, radius: int, color: int):
        """Fill a circle."""
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if x ** 2 + y ** 2 <= radius ** 2:
                    self.set_pixel(x0 + x, y0 + y, color)
