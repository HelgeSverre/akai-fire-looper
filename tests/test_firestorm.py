"""Particle bounds, real decorated input, two outputs and bounded audio."""

import math
import os
import unittest
from unittest.mock import Mock, patch

from akai_fire_testing import MockAkaiFire
from examples.apps.firestorm.app import FirestormApp
from examples.apps.firestorm.audio import Sound
from examples.apps.firestorm.model import WIDTH, World
from tests import test_oled_layouts as layouts


class WorldTests(unittest.TestCase):
    def test_every_scene_is_deterministic_bounded_and_renders_color(self):
        for scene in range(3):
            with self.subTest(scene=scene):
                a, b = World(5), World(5)
                for world in (a, b):
                    world.change_scene(scene)
                    world.energy = 100
                    for _ in range(70):
                        world.burst(1, 8)
                    world.attract(2, 4)
                    for _ in range(30):
                        world.update(0.033)
                    self.assertLessEqual(len(world.particles), world.MAX_PARTICLES)
                    self.assertLessEqual(len(world.rings), world.MAX_RINGS)
                    self.assertTrue(
                        all(math.isfinite(v) and 0 <= v <= 1 for v in world.light)
                    )
                    colors = world.pad_colors()
                    self.assertEqual(len(colors), 64)
                    self.assertTrue(any(any(rgb) for _, *rgb in colors))
                    self.assertTrue(
                        all(0 <= v <= 127 for _, *rgb in colors for v in rgb)
                    )
                self.assertEqual(a.light, b.light)
                self.assertEqual(a.pad_colors(), b.pad_colors())

    def test_dense_trails_preserve_hue_instead_of_clipping_to_white(self):
        world = World(1)
        world.light = [1.0] * (WIDTH * 32)
        world.hues = [0.5] * (WIDTH * 32)
        for _, red, green, blue in world.pad_colors():
            self.assertLess(red, 20)
            self.assertGreater(green, 120)
            self.assertEqual(green, blue)

    def test_pause_clear_and_dt_cap(self):
        world = World(0)
        world.burst(1, 8)
        world.update(0.03)
        before = list(world.light)
        world.paused = True
        world.update(100)
        self.assertEqual(world.light, before)
        world.paused = False
        elapsed = world.elapsed
        world.update(100)
        self.assertAlmostEqual(world.elapsed - elapsed, 0.05)
        world.clear()
        world.update(0.03)
        self.assertFalse(world.auto)
        self.assertFalse(any(world.light))
        self.assertFalse(world.particles)
        self.assertFalse(world.rings)
        self.assertFalse(world.attractors)

    def test_attractors_toggle_and_remain_bounded(self):
        world = World(1)
        for col in range(8):
            world.attract(0, col)
        self.assertEqual(len(world.attractors), 4)
        world.attract(0, 7)
        self.assertEqual(len(world.attractors), 3)


class FirestormTests(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.sound = Mock()
        self.app = FirestormApp(self.fire, sound=self.sound, seed=5)
        self.addCleanup(self.fire.close)
        self.addCleanup(self.app.shutdown)
        self.app.on_start()

    def press(self, button):
        self.fire.simulate_button_press(button)
        self.fire.simulate_button_release(button)
        self.app.tick(0.033)

    def test_pad_and_modifier_use_framework_queue_and_audio_is_manual_only(self):
        self.app.tick(0.03)
        self.sound.play.assert_not_called()
        before = len(self.app.world.particles)
        self.fire.simulate_pad_press(18)
        self.assertEqual(len(self.app.world.particles), before)
        self.app.tick(0.03)
        self.assertFalse(self.app.world.auto)
        self.sound.play.assert_called_once_with(1, 2)
        self.fire.simulate_button_press(self.fire.BUTTON_SHIFT)
        self.fire.simulate_pad_press(18)
        self.fire.simulate_button_release(self.fire.BUTTON_SHIFT)
        self.app.tick(0.03)
        self.assertIn((20, 12), self.app.world.attractors)
        self.assertEqual(self.sound.play.call_count, 1)

    def test_scene_knobs_pause_clear_and_auto_through_decorators(self):
        for encoder, name in (
            (self.fire.ROTARY_VOLUME, "energy"),
            (self.fire.ROTARY_PAN, "gravity"),
            (self.fire.ROTARY_FILTER, "trails"),
        ):
            self.fire.simulate_rotary_turn(encoder, "clockwise", 100)
            self.app.tick(0.03)
            self.assertEqual(getattr(self.app.world, name), 100)
            self.fire.simulate_rotary_turn(encoder, "counterclockwise", 200)
            self.app.tick(0.03)
            self.assertEqual(getattr(self.app.world, name), 0)
        self.fire.simulate_rotary_turn(self.fire.ROTARY_RESONANCE, "clockwise", 200)
        self.fire.simulate_rotary_turn(self.fire.ROTARY_SELECT, "clockwise", 1)
        self.app.tick(0.03)
        self.assertEqual(self.app.world.scene, 1)
        self.assertTrue(0 <= self.app.world.color < 360)
        self.press(self.fire.BUTTON_PLAY)
        frozen = list(self.app.world.light)
        self.app.tick(0.5)
        self.assertEqual(self.app.world.light, frozen)
        self.press(self.fire.BUTTON_STOP)
        self.assertFalse(any(self.app.world.light))
        self.assertFalse(self.app.world.paused)
        self.press(self.fire.BUTTON_REC)
        self.assertTrue(self.app.world.auto)
        self.press(self.fire.BUTTON_SELECT)
        self.assertEqual(self.app.world.scene, 2)

    def test_one_pad_batch_and_shared_oled_field_with_readable_text(self):
        canvas = layouts.MeasuredCanvas()
        self.app.canvas = canvas
        self.app.world.clear()
        self.app.world.light[12 * WIDTH + 20] = 1
        with patch.object(
            self.fire,
            "set_multiple_pad_colors",
            wraps=self.fire.set_multiple_pad_colors,
        ) as batch:
            self.app.tick(0)
        self.assertEqual(batch.call_count, 1)
        self.assertEqual(canvas.image.getpixel((20, 30)), 0)
        self.assertTrue(any(self.fire.pad_colors[18]))
        for scene in range(3):
            self.app.world.change_scene(scene)
            self.app.tick(0.03)
            layouts.OledLayouts().assert_readable(canvas)
        self.press(self.fire.BUTTON_BROWSER)
        layouts.OledLayouts().assert_readable(canvas)

    def test_synthesized_audio_is_short_cached_and_closed(self):
        with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
            sound = Sound()
            try:
                self.assertTrue(sound.available)
                sound.play(0, 0)
                sound.play(0, 0)
                sound.play(3, 15)
                self.assertEqual(len(sound._voices), 2)
                self.assertTrue(
                    all(0.34 < s.get_length() < 0.36 for s in sound._voices.values())
                )
                self.assertTrue(all(any(s.get_raw()) for s in sound._voices.values()))
            finally:
                sound.close()
            self.assertFalse(sound.available)

    def test_silent_audio_does_not_initialize_pygame(self):
        with patch(
            "pygame.mixer.init", side_effect=AssertionError("Unexpected audio init")
        ):
            sound = Sound(enabled=False)
            sound.play(0, 0)
            sound.close()
            self.assertFalse(sound.available)
