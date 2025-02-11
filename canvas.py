import os

from PIL import Image, ImageDraw, ImageFont

from akai_fire import AkaiFireBitmap, AkaiFire


class Canvas:
    """Generic drawing canvas for Akai Fire OLED or BMP output."""

    WIDTH, HEIGHT = 128, 64

    def __init__(self):
        self.image = Image.new('1', (self.WIDTH, self.HEIGHT), 1)  # 1 = white background
        self.draw = ImageDraw.Draw(self.image)

    def clear(self):
        """Clear the canvas."""
        self.image = Image.new('1', (self.WIDTH, self.HEIGHT), 1)
        self.draw = ImageDraw.Draw(self.image)

    def set_pixel(self, x, y, color=0):
        """Set a pixel on the canvas."""
        self.image.putpixel((x, y), color)

    def draw_rect(self, x, y, width, height, color=0):
        """Draw rectangle outline."""
        self.draw.rectangle([x, y, x + width, y + height], outline=color)

    def fill_rect(self, x, y, width, height, color=0):
        """Draw filled rectangle."""
        self.draw.rectangle([x, y, x + width, y + height], fill=color)

    def draw_text(self, text, x, y, font=None, color=0):
        """Draw text."""
        if font is None:
            font = ImageFont.load_default()

        self.draw.text((x, y), text, fill=color, font=font)


class FireRenderer:
    """Renderer to send Canvas drawings to Akai Fire OLED."""

    def __init__(self, akai_fire):
        self.akai_fire = akai_fire
        self.bitmap = AkaiFireBitmap()

    def render_canvas(self, canvas):
        """Render the canvas on the Akai Fire OLED."""
        for y in range(canvas.HEIGHT):
            for x in range(canvas.WIDTH):
                pixel = canvas.image.getpixel((x, y))
                self.bitmap.set_pixel(x, y, 1 - pixel)  # Invert since OLED 0=on, PIL 0=black
        self.akai_fire.send_bitmap(self.bitmap)


class BMPRenderer:
    """Renderer to save Canvas drawings as BMP for debugging."""

    def __init__(self, output_dir="_screens"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def render_canvas(self, canvas, filename="debug_screen.bmp"):
        """Save the canvas as a BMP file."""
        canvas.image.save(os.path.join(self.output_dir, filename), format="BMP")


if __name__ == "__main__":
    # Initialize Akai Fire and Canvas
    fire = AkaiFire()
    canvas = Canvas()

    # Draw something on the canvas

    canvas.draw_text("Hello Fire", 20, 20)

    # Render to OLED
    fire_renderer = FireRenderer(fire)
    fire_renderer.render_canvas(canvas)

    # Render to BMP for debugging
    bmp_renderer = BMPRenderer()
    bmp_renderer.render_canvas(canvas, "test_output.bmp")
