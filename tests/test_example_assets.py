"""Bundled GIF demos must run without a Claude installation or caller-relative paths."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from akai_fire_testing import MockAkaiFire
from examples import oled_clawd_animation, oled_scrolling_text


class BundledAnimationTests(unittest.TestCase):
    def test_original_animation_loads_from_another_working_directory(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                frames = oled_clawd_animation.load_frames(
                    oled_clawd_animation.DEFAULT_GIF
                )
                self.assertEqual(len(frames), 113)
                self.assertTrue(
                    all(f.mode == "1" and f.size == (128, 64) for f in frames)
                )
                self.assertGreater(len({f.tobytes() for f in frames}), 1)
                self.assertTrue(
                    any(min(f.getdata()) == 0 < max(f.getdata()) for f in frames)
                )
            finally:
                os.chdir(previous)

    def test_both_demos_render_and_close_with_the_bundled_animation(self):
        for module in (oled_clawd_animation, oled_scrolling_text):
            with self.subTest(module=module.__name__):
                fire = MockAkaiFire()
                fire.render_to_display = Mock()
                fire.clear_display = Mock()
                with patch.object(module, "get_akai_fire", return_value=fire):
                    if module is oled_clawd_animation:
                        frames = module.load_frames(module.DEFAULT_GIF)
                        module.play_on_hardware(frames, duration=0)
                    else:
                        module.play(duration=0)
                fire.render_to_display.assert_called_once()
                fire.clear_display.assert_called_once()
                self.assertTrue(fire._closed)


if __name__ == "__main__":
    unittest.main()
