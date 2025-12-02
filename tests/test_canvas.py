import unittest
import os
import tempfile
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import Canvas


class TestCanvas(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()

    def test_initialization(self):
        """Test canvas initialization"""
        self.assertEqual(self.canvas.WIDTH, 128)
        self.assertEqual(self.canvas.HEIGHT, 64)
        self.assertIsNotNone(self.canvas.image)
        self.assertIsNotNone(self.canvas.draw)

    def test_clear(self):
        """Test canvas clear operation"""
        # Draw something first
        self.canvas.fill_rect(0, 0, 10, 10, color=0)
        # Clear
        self.canvas.clear()
        # Check all pixels are white (1)
        for x in range(10):
            for y in range(10):
                self.assertEqual(self.canvas.image.getpixel((x, y)), 1)

    def test_draw_pixel(self):
        """Test pixel drawing"""
        self.canvas.set_pixel(10, 20, 0)
        self.assertEqual(self.canvas.image.getpixel((10, 20)), 0)

        # Test bounds checking
        self.canvas.set_pixel(-1, 0, 0)  # Should not crash
        self.canvas.set_pixel(128, 0, 0)  # Should not crash
        self.canvas.set_pixel(0, -1, 0)  # Should not crash
        self.canvas.set_pixel(0, 64, 0)  # Should not crash

    def test_draw_rect(self):
        """Test rectangle drawing"""
        self.canvas.draw_rect(10, 10, 20, 15, color=0)

        # Check corners
        self.assertEqual(self.canvas.image.getpixel((10, 10)), 0)
        self.assertEqual(self.canvas.image.getpixel((29, 10)), 0)
        self.assertEqual(self.canvas.image.getpixel((10, 24)), 0)
        self.assertEqual(self.canvas.image.getpixel((29, 24)), 0)

        # Check inside (should be white)
        self.assertEqual(self.canvas.image.getpixel((15, 15)), 1)

    def test_fill_rect(self):
        """Test filled rectangle"""
        self.canvas.fill_rect(20, 20, 10, 10, color=0)

        # Check inside is filled
        self.assertEqual(self.canvas.image.getpixel((25, 25)), 0)
        self.assertEqual(self.canvas.image.getpixel((20, 20)), 0)
        self.assertEqual(self.canvas.image.getpixel((29, 29)), 0)

    def test_draw_rect_bounds(self):
        """Test rectangle with zero or negative dimensions"""
        # Should not crash with zero width/height
        self.canvas.draw_rect(10, 10, 0, 10)
        self.canvas.draw_rect(10, 10, 10, 0)
        self.canvas.fill_rect(10, 10, 0, 10)
        self.canvas.fill_rect(10, 10, 10, 0)

    def test_draw_line(self):
        """Test line drawing"""
        # Horizontal line
        self.canvas.draw_line(10, 10, 20, 10, color=0)
        for x in range(10, 21):
            self.assertEqual(self.canvas.image.getpixel((x, 10)), 0)

        # Vertical line
        self.canvas.draw_line(30, 10, 30, 20, color=0)
        for y in range(10, 21):
            self.assertEqual(self.canvas.image.getpixel((30, y)), 0)

        # Diagonal line
        self.canvas.draw_line(40, 10, 50, 20, color=0)
        # Should have drawn pixels along the diagonal

    def test_draw_circle(self):
        """Test circle drawing"""
        self.canvas.draw_circle(64, 32, 10, color=0)

        # Check some points on the circle
        # Top point
        self.assertEqual(self.canvas.image.getpixel((64, 22)), 0)
        # Right point
        self.assertEqual(self.canvas.image.getpixel((74, 32)), 0)

    def test_fill_circle(self):
        """Test filled circle"""
        self.canvas.fill_circle(64, 32, 5, color=0)

        # Check center is filled
        self.assertEqual(self.canvas.image.getpixel((64, 32)), 0)
        # Check inside is filled
        self.assertEqual(self.canvas.image.getpixel((63, 32)), 0)
        self.assertEqual(self.canvas.image.getpixel((65, 32)), 0)

    def test_draw_text(self):
        """Test text drawing"""
        self.canvas.draw_text("Test", 10, 10, color=0)
        # Text should have drawn some black pixels
        # Check that some pixels in the text area are black
        found_black = False
        for x in range(10, 40):
            for y in range(10, 20):
                if self.canvas.image.getpixel((x, y)) == 0:
                    found_black = True
                    break
            if found_black:
                break
        self.assertTrue(found_black)

    def test_draw_border(self):
        """Test border drawing"""
        self.canvas.draw_border(thickness=2, color=0)

        # Check corners
        self.assertEqual(self.canvas.image.getpixel((0, 0)), 0)
        self.assertEqual(self.canvas.image.getpixel((127, 0)), 0)
        self.assertEqual(self.canvas.image.getpixel((0, 63)), 0)
        self.assertEqual(self.canvas.image.getpixel((127, 63)), 0)

    def test_draw_page(self):
        """Test page drawing method"""
        self.canvas.draw_page("Test Page", ["Line 1", "Line 2", "Line 3"])

        # Should have drawn something - check that some pixels are black
        found_black = False
        for x in range(0, 128, 10):
            for y in range(0, 64, 10):
                if self.canvas.image.getpixel((x, y)) == 0:
                    found_black = True
                    break
            if found_black:
                break
        self.assertTrue(found_black)

    def test_clone(self):
        """Test canvas cloning"""
        # Draw something on original
        self.canvas.draw_text("Original", 10, 10, color=0)
        self.canvas.fill_rect(50, 50, 10, 10, color=0)

        # Clone
        cloned = self.canvas.clone()

        # Verify clone has same content
        self.assertEqual(cloned.WIDTH, self.canvas.WIDTH)
        self.assertEqual(cloned.HEIGHT, self.canvas.HEIGHT)

        # Check some pixels match
        for x in range(0, 128, 10):
            for y in range(0, 64, 10):
                self.assertEqual(
                    cloned.image.getpixel((x, y)), self.canvas.image.getpixel((x, y))
                )

        # Modify clone and verify original unchanged
        cloned.clear()
        self.assertEqual(
            self.canvas.image.getpixel((55, 55)), 0
        )  # Original still black
        self.assertEqual(cloned.image.getpixel((55, 55)), 1)  # Clone is white

    def test_complex_drawing(self):
        """Test complex drawing operations"""
        # Create a complex scene
        self.canvas.draw_rect(10, 10, 108, 44, color=0)  # Border
        self.canvas.fill_circle(32, 32, 10, color=0)  # Left circle
        self.canvas.fill_circle(96, 32, 10, color=0)  # Right circle
        self.canvas.draw_line(32, 32, 96, 32, color=0)  # Connection
        self.canvas.draw_text("FIRE", 48, 28, color=0)  # Text in middle

        # Should not crash and should have drawn content
        # Check that we have both black and white pixels
        black_count = 0
        white_count = 0
        for x in range(0, 128, 4):
            for y in range(0, 64, 4):
                if self.canvas.image.getpixel((x, y)) == 0:
                    black_count += 1
                else:
                    white_count += 1

        self.assertGreater(black_count, 0)
        self.assertGreater(white_count, 0)


if __name__ == "__main__":
    unittest.main()
