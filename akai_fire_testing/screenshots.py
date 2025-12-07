"""
Screenshot comparison utilities for visual regression testing.

This module provides Playwright-style screenshot comparison for
testing AKAI Fire screen rendering.

Classes:
    ComparisonResult: Result of a screenshot comparison
    ScreenshotComparator: Compare screenshots against baselines
"""

from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass
import os

if TYPE_CHECKING:
    from .mocks import MockCanvas


@dataclass
class ComparisonResult:
    """
    Result of a screenshot comparison.

    Attributes:
        matches: True if screenshots match within threshold
        diff_percentage: Percentage of pixels that differ
        diff_pixels: Count of differing pixels
        baseline_path: Path to baseline image
        actual_path: Path to actual (captured) image
        diff_path: Path to diff image (if generated)
    """

    matches: bool
    diff_percentage: float
    diff_pixels: int
    baseline_path: str
    actual_path: str
    diff_path: Optional[str] = None

    def save_diff(self, path: str) -> str:
        """
        Save a diff image highlighting differences.

        Note: Requires PIL for diff visualization.

        Args:
            path: Output path for diff image

        Returns:
            Path where diff was saved
        """
        try:
            from PIL import Image

            # Load both images
            if not os.path.exists(self.baseline_path):
                raise FileNotFoundError(f"Baseline not found: {self.baseline_path}")
            if not os.path.exists(self.actual_path):
                raise FileNotFoundError(f"Actual not found: {self.actual_path}")

            baseline = Image.open(self.baseline_path)
            actual = Image.open(self.actual_path)

            # Create diff image
            # Red = only in baseline, Green = only in actual, Yellow = both different
            width = max(baseline.width, actual.width)
            height = max(baseline.height, actual.height)
            diff = Image.new("RGB", (width, height), (0, 0, 0))
            diff_pixels = diff.load()

            for y in range(height):
                for x in range(width):
                    base_pixel = (
                        baseline.getpixel((x, y))
                        if x < baseline.width and y < baseline.height
                        else (0, 0, 0)
                    )
                    act_pixel = (
                        actual.getpixel((x, y))
                        if x < actual.width and y < actual.height
                        else (0, 0, 0)
                    )

                    # Convert to grayscale comparison
                    base_val = (
                        sum(base_pixel[:3]) // 3
                        if isinstance(base_pixel, tuple)
                        else base_pixel
                    )
                    act_val = (
                        sum(act_pixel[:3]) // 3
                        if isinstance(act_pixel, tuple)
                        else act_pixel
                    )

                    if base_val != act_val:
                        if base_val > act_val:
                            diff_pixels[x, y] = (255, 0, 0)  # Red: in baseline only
                        else:
                            diff_pixels[x, y] = (0, 255, 0)  # Green: in actual only
                    else:
                        # Same - show dimmed
                        val = base_val // 4
                        diff_pixels[x, y] = (val, val, val)

            # Ensure directory exists
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            diff.save(path)
            self.diff_path = path
            return path

        except ImportError:
            raise RuntimeError("PIL required for diff visualization")

    def save_actual(self, path: str) -> str:
        """
        Copy actual image to a new location.

        Args:
            path: Destination path

        Returns:
            Destination path
        """
        import shutil

        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        shutil.copy(self.actual_path, path)
        return path


class ScreenshotComparator:
    """
    Compare screenshots for visual regression testing.

    Similar to Playwright's screenshot testing, this allows you to
    capture canvas state and compare against baseline images.

    Features:
        - Automatic baseline management
        - Configurable difference threshold
        - Diff visualization
        - Works with or without PIL

    Example:
        >>> comparator = ScreenshotComparator("tests/baselines")
        >>> canvas = MockCanvas()
        >>> render_menu(canvas, items=["A", "B", "C"], selected=1)
        >>> result = comparator.compare(canvas, "menu_selected_b")
        >>> if not result.matches:
        ...     result.save_diff("tests/failures/menu_diff.bmp")
        ...     pytest.fail(f"Screenshot mismatch: {result.diff_percentage}%")
    """

    def __init__(self, baseline_dir: str, threshold: float = 0.0, scale: int = 4):
        """
        Initialize comparator.

        Args:
            baseline_dir: Directory containing baseline images
            threshold: Maximum allowed difference (0.0 = exact match required)
            scale: Scale factor for screenshots (default 4)
        """
        self.baseline_dir = baseline_dir
        self.threshold = threshold
        self.scale = scale
        self._actual_dir = os.path.join(baseline_dir, ".actual")

        # Create directories
        os.makedirs(baseline_dir, exist_ok=True)
        os.makedirs(self._actual_dir, exist_ok=True)

    def compare(self, canvas: "MockCanvas", name: str) -> ComparisonResult:
        """
        Compare canvas to baseline.

        If baseline doesn't exist, it will be created and the test
        will pass (first run behavior).

        Args:
            canvas: MockCanvas with rendered content
            name: Baseline name (without extension)

        Returns:
            ComparisonResult with match status and details
        """
        baseline_path = os.path.join(self.baseline_dir, f"{name}.bmp")
        actual_path = os.path.join(self._actual_dir, f"{name}.bmp")

        # Save actual screenshot
        canvas.save_screenshot(actual_path, scale=self.scale)

        # Check if baseline exists
        if not os.path.exists(baseline_path):
            # First run - create baseline
            canvas.save_screenshot(baseline_path, scale=self.scale)
            return ComparisonResult(
                matches=True,
                diff_percentage=0.0,
                diff_pixels=0,
                baseline_path=baseline_path,
                actual_path=actual_path,
            )

        # Compare images
        diff_pixels, total_pixels = self._compare_images(baseline_path, actual_path)
        diff_percentage = (
            (diff_pixels / total_pixels * 100) if total_pixels > 0 else 0.0
        )
        matches = diff_percentage <= self.threshold

        return ComparisonResult(
            matches=matches,
            diff_percentage=diff_percentage,
            diff_pixels=diff_pixels,
            baseline_path=baseline_path,
            actual_path=actual_path,
        )

    def _compare_images(self, path1: str, path2: str) -> tuple:
        """
        Compare two BMP images pixel by pixel.

        Returns:
            Tuple of (differing_pixels, total_pixels)
        """
        try:
            from PIL import Image

            return self._compare_with_pil(path1, path2)
        except ImportError:
            return self._compare_raw_bmp(path1, path2)

    def _compare_with_pil(self, path1: str, path2: str) -> tuple:
        """Compare using PIL."""
        from PIL import Image

        img1 = Image.open(path1)
        img2 = Image.open(path2)

        # Size mismatch = all pixels different
        if img1.size != img2.size:
            return (img1.width * img1.height, img1.width * img1.height)

        diff_count = 0
        total = img1.width * img1.height

        for y in range(img1.height):
            for x in range(img1.width):
                p1 = img1.getpixel((x, y))
                p2 = img2.getpixel((x, y))

                # Compare as tuples
                if isinstance(p1, int):
                    p1 = (p1, p1, p1)
                if isinstance(p2, int):
                    p2 = (p2, p2, p2)

                if p1[:3] != p2[:3]:
                    diff_count += 1

        return (diff_count, total)

    def _compare_raw_bmp(self, path1: str, path2: str) -> tuple:
        """Compare BMP files without PIL."""
        import struct

        def read_bmp_pixels(path):
            """Read pixel data from BMP file."""
            with open(path, "rb") as f:
                # Read header
                f.read(10)  # Magic + file size + reserved
                offset = struct.unpack("<I", f.read(4))[0]

                f.read(4)  # Header size
                width = struct.unpack("<i", f.read(4))[0]
                height = struct.unpack("<i", f.read(4))[0]

                # Seek to pixel data
                f.seek(offset)

                # Read pixels (bottom-up, BGR, with row padding)
                row_size = ((abs(width) * 3 + 3) // 4) * 4
                pixels = []
                for y in range(abs(height)):
                    row = f.read(row_size)
                    for x in range(abs(width)):
                        b, g, r = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
                        pixels.append((r, g, b))

                return width, abs(height), pixels

        try:
            w1, h1, p1 = read_bmp_pixels(path1)
            w2, h2, p2 = read_bmp_pixels(path2)
        except Exception:
            return (1, 1)  # Error = mismatch

        if w1 != w2 or h1 != h2:
            return (w1 * h1, w1 * h1)

        diff_count = sum(1 for i in range(len(p1)) if p1[i] != p2[i])
        return (diff_count, len(p1))

    def update_baseline(self, canvas: "MockCanvas", name: str) -> str:
        """
        Update or create baseline from canvas.

        Use this to accept new screenshots as the new baseline.

        Args:
            canvas: MockCanvas with rendered content
            name: Baseline name (without extension)

        Returns:
            Path to saved baseline
        """
        baseline_path = os.path.join(self.baseline_dir, f"{name}.bmp")
        return canvas.save_screenshot(baseline_path, scale=self.scale)

    def list_baselines(self) -> List[str]:
        """
        List all baseline names.

        Returns:
            List of baseline names (without extension)
        """
        baselines = []
        if os.path.exists(self.baseline_dir):
            for f in os.listdir(self.baseline_dir):
                if f.endswith(".bmp"):
                    baselines.append(f[:-4])  # Remove .bmp
        return sorted(baselines)

    def delete_baseline(self, name: str) -> bool:
        """
        Delete a baseline.

        Args:
            name: Baseline name (without extension)

        Returns:
            True if deleted, False if not found
        """
        path = os.path.join(self.baseline_dir, f"{name}.bmp")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def clean_actuals(self):
        """Remove all actual screenshots."""
        import shutil

        if os.path.exists(self._actual_dir):
            shutil.rmtree(self._actual_dir)
            os.makedirs(self._actual_dir)
