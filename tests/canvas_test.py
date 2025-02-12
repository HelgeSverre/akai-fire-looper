import unittest

from akai_fire import Canvas


class TestCanvas(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()

    def test_clear(self):
        """Test canvas clear operation"""
        self.canvas.draw_rect(0, 0, 10, 10)  # Draw something
        self.canvas.clear()
        # Check some pixels are white (1)
        self.assertEqual(self.canvas.image.getpixel((0, 0)), 1)
        self.assertEqual(self.canvas.image.getpixel((5, 5)), 1)

    def test_draw_operations(self):
        """Test basic drawing operations"""
        # Test rectangle
        self.canvas.draw_rect(0, 0, 10, 10)
        self.assertEqual(
            self.canvas.image.getpixel((0, 0)), 0
        )  # Border should be black (0)

        # Test filled rectangle
        self.canvas.fill_rect(20, 20, 10, 10)
        self.assertEqual(
            self.canvas.image.getpixel((25, 25)), 0
        )  # Inside should be black

        # Test text
        self.canvas.draw_text("Test", 40, 40)
        # Text verification would need more sophisticated image analysis


class TestBitmapOperations(unittest.TestCase):
    """Test bitmap operations for OLED display"""

    def setUp(self):
        self.canvas = Canvas()

    def test_pixel_boundaries(self):
        """Test pixel operations at display boundaries"""
        # Test corners
        corners = [(0, 0), (127, 0), (0, 63), (127, 63)]
        for x, y in corners:
            self.canvas.set_pixel(x, y, 1)
            # Verify no exception raised

        # Test out of bounds
        out_of_bounds = [(-1, 0), (128, 0), (0, -1), (0, 64)]
        for x, y in out_of_bounds:
            self.canvas.set_pixel(x, y, 1)
            # Should silently ignore

    def test_bitmap_patterns(self):
        """Test complex bitmap patterns"""
        # Draw horizontal lines
        for y in range(0, 64, 8):
            for x in range(128):
                self.canvas.set_pixel(x, y, 1)

        # Draw vertical lines
        for x in range(0, 128, 16):
            for y in range(64):
                self.canvas.set_pixel(x, y, 1)


if __name__ == "__main__":
    unittest.main()
