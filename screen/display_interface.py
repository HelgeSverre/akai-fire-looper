import os
from abc import ABC, abstractmethod

from PIL import Image

from akai_fire import AkaiFireBitmap, BITMAP_PIXEL_MAPPING, AkaiFire
from screen.screen_templates import ScreenTemplates
from screen.text_renderer import TextStyle

COLOR_WHITE = 1  # Pixel on
COLOR_BLACK = 0  # Pixel off


class DisplayInterface(ABC):
    """Abstract base class defining the display interface"""

    SCREEN_HEIGHT = 64
    SCREEN_WIDTH = 128

    @abstractmethod
    def update(self):
        """Update internal bitmap with pixel modifications"""
        pass

    @abstractmethod
    def render(self):
        """Render the display (either to hardware or file)"""
        pass

    @abstractmethod
    def clear(self):
        """Clear the display"""
        pass

    @abstractmethod
    def set_pixel(self, x: int, y: int, color: int):
        """Set a single pixel"""
        pass

    # Drawing primitives
    @abstractmethod
    def draw_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw a rectangle outline"""
        pass

    @abstractmethod
    def fill_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw a filled rectangle"""
        pass

    # Common UI components
    def draw_progress_bar(
        self, x: int, y: int, width: int, height: int, progress: float
    ):
        """Draw a progress bar"""
        self.draw_rect(x, y, width, height, COLOR_WHITE)
        fill_width = int((width - 2) * progress)
        if fill_width > 0:
            self.fill_rect(x + 1, y + 1, fill_width, height - 2, COLOR_WHITE)

    def draw_level_meter(
        self, x: int, y: int, width: int, height: int, level: float, peak=None
    ):
        """Draw a level meter with optional peak indicator"""
        segments = 16
        segment_width = (width - segments + 1) // segments

        for i in range(segments):
            segment_x = x + i * (segment_width + 1)
            threshold = i / segments

            if level >= threshold:
                if threshold < 0.75:
                    color = COLOR_WHITE
                elif threshold < 0.9:
                    self.draw_rect(segment_x, y, segment_width, height, COLOR_WHITE)
                else:
                    self.fill_rect(segment_x, y, segment_width, height, COLOR_WHITE)

        if peak is not None and peak > 0:
            peak_x = x + int(peak * width)
            self.fill_rect(peak_x, y, 2, height, COLOR_WHITE)

    def draw_text(self, text: str, x: int, y: int, style=None):
        """Draw text with optional style"""
        from text_renderer import TextStyle, render_text

        style = style or TextStyle()
        render_text(self, text, x, y, style)

    def draw_text_centered(self, text: str, y: int, style=None):
        """Draw horizontally centered text"""
        style = style or TextStyle()
        text_width = len(text) * 6 * style.size
        x = (self.SCREEN_WIDTH - text_width) // 2
        self.draw_text(text, x, y, style)


class FireDisplay(DisplayInterface):
    """Hardware Akai Fire OLED display implementation"""

    def __init__(self, fire):
        self.fire = fire
        self.bitmap = AkaiFireBitmap()
        self.clear()

    def update(self):
        """Update internal bitmap"""
        pass  # Bitmap is updated directly via set_pixel

    def render(self):
        """Send bitmap to hardware display"""
        self.fire.send_bitmap(self.bitmap)

    def clear(self):
        """Clear the display"""
        self.bitmap.clear()
        self.render()

    def set_pixel(self, x: int, y: int, color: int):
        """Set a pixel in the bitmap"""
        self.bitmap.set_pixel(x, y, color)

    def draw_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw rectangle outline"""
        self.bitmap.draw_rectangle(x, y, width, height, color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw filled rectangle"""
        self.bitmap.fill_rectangle(x, y, width, height, color)


class DebugDisplay(DisplayInterface):
    """Debug display implementation that saves to image files"""

    def __init__(self, output_dir="_screens"):
        self.image = Image.new("L", (self.SCREEN_WIDTH, self.SCREEN_HEIGHT), 255)
        self.bitmap = AkaiFireBitmap()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.clear()

    def update(self):
        """Update preview image from bitmap"""
        for y in range(self.SCREEN_HEIGHT):
            for x in range(self.SCREEN_WIDTH):
                x_mapped = x + int(128 * (y // 8))
                y_mapped = y % 8
                rb = BITMAP_PIXEL_MAPPING[int(x_mapped % 7)][y_mapped]
                index = int((x_mapped // 7) * 8 + (rb // 7))
                pixel = (self.bitmap.bitmap[index] >> (rb % 7)) & 1
                # Convert OLED pixels to grayscale (WHITE=0, BLACK=255)
                gray = 0 if pixel == COLOR_WHITE else 255  # Proper inversion for display
                self.image.putpixel((x, y), gray)

    def render(self, filename=None):
        """Save current display state as bitmap file"""
        self.update()
        if filename:
            filepath = os.path.join(self.output_dir, filename)
            self.image.save(filepath, format="BMP")

    def clear(self):
        """Clear both bitmap and image"""
        self.bitmap.clear()
        self.image = Image.new("L", (self.SCREEN_WIDTH, self.SCREEN_HEIGHT), 255)
        self.update()

    def set_pixel(self, x: int, y: int, color: int):
        """Set a pixel in both bitmap and image"""
        self.bitmap.set_pixel(x, y, color)

    def draw_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw rectangle outline"""
        self.bitmap.draw_rectangle(x, y, width, height, color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: int):
        """Draw filled rectangle"""
        self.bitmap.fill_rectangle(x, y, width, height, color)


# # Example usage
# if __name__ == "__main__":
#     # Test with debug display
#     display = DebugDisplay()

# Draw some test patterns
# display.draw_rect(10, 10, 108, 44, COLOR_WHITE)
# display.draw_text("TEST PATTERN", 20, 20)
# display.draw_progress_bar(20, 30, 88, 8, 0.7)
# display.draw_level_meter(20, 44, 88, 6, 0.8, peak=0.9)
#
# # Save the result
# display.render("test_pattern.bmp")


if __name__ == "__main__":
    # Initialize Akai Fire hardware
    fire = AkaiFire()
    # display = FireDisplay(fire)
    display = DebugDisplay()
    screens = ScreenTemplates(display)

    # # Test main screen
    print("Showing main screen...")
    screens.show_main_screen(bpm=120.5, current_bar=1, playing=True)
    #
    # # Test recording screen
    print("Showing recording screen...")
    screens.show_recording_screen(clip_num=1, time="0:00", level=0.6, peak=0.8)
    #
    # # Test clip info screen
    print("Showing clip info screen...")
    screens.show_clip_info_screen()

    # Test mixer screen
    print("Showing mixer screen...")
    screens.show_mixer_screen(track_levels=[0.8, 0.5, 0.8, 0.3])
    display.render("test_mixer.bmp")
    # Clean up
    fire.close()
