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


class TestCanvasPrimitives(unittest.TestCase):
    """Line helpers and the composite rectangle methods."""

    def setUp(self):
        self.canvas = Canvas()

    def _on(self, x, y):
        return self.canvas.image.getpixel((x, y)) == 0

    def test_draw_horizontal_line_sets_correct_pixels(self):
        self.canvas.draw_horizontal_line(10, 20, 30)
        for x in range(10, 40):
            self.assertTrue(self._on(x, 20), f"pixel ({x}, 20) should be lit")
        self.assertFalse(self._on(9, 20))
        self.assertFalse(self._on(40, 20))
        self.assertFalse(self._on(25, 19))
        self.assertFalse(self._on(25, 21))

    def test_draw_horizontal_line_clips_at_width(self):
        self.canvas.draw_horizontal_line(120, 0, 50)  # would extend to x=169
        # Rightmost lit pixel is WIDTH-1 = 127
        self.assertTrue(self._on(127, 0))

    def test_draw_horizontal_line_ignores_out_of_bounds_row(self):
        self.canvas.draw_horizontal_line(0, -1, 10)   # y off top
        self.canvas.draw_horizontal_line(0, 64, 10)   # y off bottom
        # Canvas should still be blank
        self.assertFalse(any(
            self._on(x, y) for x in range(128) for y in range(64)
        ))

    def test_draw_vertical_line_sets_correct_pixels(self):
        self.canvas.draw_vertical_line(5, 10, 20)
        for y in range(10, 30):
            self.assertTrue(self._on(5, y))
        self.assertFalse(self._on(5, 9))
        self.assertFalse(self._on(5, 30))

    def test_draw_vertical_line_clips_at_height(self):
        self.canvas.draw_vertical_line(0, 60, 20)  # would extend to y=79
        self.assertTrue(self._on(0, 63))

    def test_draw_rectangle_outline_has_border_not_interior(self):
        self.canvas.draw_rectangle(10, 10, 20, 15)
        # Top-left corner, top edge, left edge, bottom-right corner all lit
        self.assertTrue(self._on(10, 10))
        self.assertTrue(self._on(29, 10))
        self.assertTrue(self._on(10, 24))
        self.assertTrue(self._on(29, 24))
        # Interior unlit
        self.assertFalse(self._on(20, 17))

    def test_fill_rectangle_fills_interior(self):
        self.canvas.fill_rectangle(5, 5, 10, 10)
        for x in range(5, 15):
            for y in range(5, 15):
                self.assertTrue(self._on(x, y))
        # Outside unlit
        self.assertFalse(self._on(15, 10))
        self.assertFalse(self._on(10, 15))


class TestCanvasHighLevel(unittest.TestCase):
    """Composite drawing helpers used by the ScreenManager/Framework."""

    def setUp(self):
        self.canvas = Canvas()

    def _on(self, x, y):
        return self.canvas.image.getpixel((x, y)) == 0

    def _count_lit(self, x0, y0, x1, y1):
        return sum(
            1 for x in range(x0, x1) for y in range(y0, y1) if self._on(x, y)
        )

    # --- draw_value_page ----------------------------------------------
    def test_draw_value_page_header_is_inverted(self):
        self.canvas.draw_value_page("Volume", 64, 0, 127, show_bar=True)
        # Inverted header => big black region at the top
        header_lit = self._count_lit(0, 0, 128, Canvas.HEADER_HEIGHT)
        self.assertGreater(header_lit, 128 * Canvas.HEADER_HEIGHT // 2)

    def test_draw_value_page_bar_width_scales_with_value(self):
        low = Canvas()
        low.draw_value_page("Volume", 10, 0, 100, show_bar=True)
        high = Canvas()
        high.draw_value_page("Volume", 90, 0, 100, show_bar=True)

        def bar_filled(canvas):
            # The bar lives at y=40..48; count filled pixels in that row
            return sum(
                1 for x in range(128)
                if canvas.image.getpixel((x, 43)) == 0
            )

        self.assertGreater(bar_filled(high), bar_filled(low))

    def test_draw_value_page_without_bar(self):
        # Should not raise when show_bar=False or bounds missing
        self.canvas.draw_value_page("Volume", "N/A", show_bar=False)
        self.canvas.draw_value_page("Volume", 50, show_bar=True)  # no min/max

    # --- draw_menu ----------------------------------------------------
    def test_draw_menu_highlights_selected_item(self):
        items = ["Alpha", "Beta", "Gamma", "Delta"]
        self.canvas.draw_menu("Select", items, selected_index=1)
        # Selected row (index 1) is drawn highlighted (inverted fill_rect)
        # at y_offset = CONTENT_START, line_height=12. Heuristic: the
        # selected row has significantly more lit pixels than neighbours.
        row_y = Canvas.CONTENT_START + 0 * 12     # first visible row
        selected_y = Canvas.CONTENT_START + 1 * 12  # second visible row (selected)
        self.assertGreater(
            self._count_lit(0, selected_y, 128, selected_y + 12),
            self._count_lit(0, row_y, 128, row_y + 12),
        )

    def test_draw_menu_with_empty_items(self):
        # Must not raise.
        self.canvas.draw_menu("Empty", [], selected_index=0)

    # --- draw_grid_info ----------------------------------------------
    def test_draw_grid_info_draws_outline_and_cells(self):
        self.canvas.draw_grid_info(
            "Grid", rows=2, cols=2, cell_info=[(0, 0, "A"), (1, 1, "B")]
        )
        # Outline: at least the top header row and the grid's top border.
        # The top-most horizontal grid line is at y=16 per draw_grid_info impl.
        top_line_lit = sum(1 for x in range(128) if self._on(x, 16))
        self.assertGreater(top_line_lit, 50)

    # --- draw_split_screen -------------------------------------------
    def test_draw_split_screen_has_middle_divider(self):
        self.canvas.draw_split_screen(
            "Split", ["Left 1", "Left 2"], ["Right 1", "Right 2"]
        )
        mid_x = Canvas.WIDTH // 2
        # The vertical divider runs from y=15 to HEIGHT.
        divider_lit = sum(1 for y in range(15, 64) if self._on(mid_x, y))
        self.assertGreater(divider_lit, 30)


if __name__ == "__main__":
    unittest.main()
