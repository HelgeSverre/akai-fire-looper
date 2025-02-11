"""
Basic pixel font implementation for AKAI Fire OLED display.
Using a 5x7 pixel font format which is common for small displays.
"""

from akai_fire import AkaiFire, AkaiFireBitmap


class OLEDDisplay:
    def __init__(self, fire):
        self.fire = fire
        self.bitmap = AkaiFireBitmap()
        self.clear()
        self.SCREEN_HEIGHT = 64
        self.SCREEN_WIDTH = 128

    def clear(self):
        """Clear the display"""
        self.bitmap.clear()
        self.fire.send_bitmap(self.bitmap)

    def draw_char(self, char, x, y, size=1):
        """Draw a single character at the specified position"""
        if char not in PIXEL_FONT:
            char = "?"  # Default to question mark for unknown characters

        char_data = PIXEL_FONT[char]
        char_height = 7 * size

        # Adjust y coordinate to account for OLED's bottom-left origin
        y = self.SCREEN_HEIGHT - y - char_height

        for row in range(7):  # 7 pixels tall
            for col in range(5):  # 5 pixels wide
                pixel = (char_data[col] >> row) & 1  # Changed from (6-row) to row
                if pixel:
                    # Draw pixel at scaled size
                    for dy in range(size):
                        for dx in range(size):
                            self.bitmap.set_pixel(
                                x + col * size + dx, y + row * size + dy, 1
                            )

    def draw_text(self, text, x, y, size=1):
        """Draw text string at the specified position"""
        current_x = x
        for (
            char
        ) in text.upper():  # Convert to uppercase since we only have uppercase font
            if char == "\n":  # Handle newlines
                y += 8 * size  # Move down by character height + 1 pixel spacing
                current_x = x  # Reset x position
                continue

            self.draw_char(char, current_x, y, size)
            current_x += 6 * size  # 5 pixels + 1 pixel spacing between characters

            # Wrap text if it would exceed display width
            if current_x > self.SCREEN_WIDTH - 6:
                y += 8 * size
                current_x = x

        # Update display
        self.fire.send_bitmap(self.bitmap)

    def draw_text_centered(self, text, y, size=1):
        """Draw text centered horizontally on the display"""
        text_width = len(text) * 6 * size
        x = (self.SCREEN_WIDTH - text_width) // 2
        self.draw_text(text, x, y, size)


class MidiLooperDisplay:
    """Higher level display manager for the MIDI Looper application"""

    def __init__(self, fire):
        self.display = OLEDDisplay(fire)
        self.current_bpm = 120
        self.current_clip = None
        self.recording = False

    def update_main_screen(self):
        """Update the main screen with current status"""
        self.display.clear()

        # Draw BPM at the top
        self.display.draw_text_centered(f"BPM: {self.current_bpm:.1f}", 8, size=1)

        # Draw clip status if applicable
        if self.current_clip is not None:
            status = "REC" if self.recording else "ARMED"
            self.display.draw_text_centered(
                f"CLIP {self.current_clip + 1}: {status}", 24, size=1
            )

    def show_message(self, message, duration=1.0):
        """Temporarily show a message on screen"""
        self.display.clear()
        self.display.draw_text_centered(message, 28, size=1)
        print(message)


if __name__ == "__main__":
    # Initialize AKAI Fire and display manager
    fire = AkaiFire()
    display = MidiLooperDisplay(fire)

    # Update main screen with initial status
    display.update_main_screen()
