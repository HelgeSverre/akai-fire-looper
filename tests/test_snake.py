"""Game rules and shared pad/OLED rendering, without physical MIDI ports."""

import random
import unittest
from collections import deque

from akai_fire import Canvas
from akai_fire_testing import MockAkaiFire
from examples.apps.snake.app import SnakeApp
from examples.apps.snake.game import Direction, SnakeGame, State


class SnakeRules(unittest.TestCase):
    def setUp(self):
        self.game = SnakeGame(random.Random(7))

    def test_ready_and_paused_do_not_move(self):
        before = list(self.game.snake)
        self.game.step()
        self.assertEqual(list(self.game.snake), before)
        self.game.toggle_pause()
        self.game.toggle_pause()
        self.game.step()
        self.assertEqual(self.game.state, State.PAUSED)
        self.assertEqual(list(self.game.snake), before)

    def test_reverse_and_second_turn_are_ignored_until_next_move(self):
        self.game.turn(Direction.LEFT)
        self.assertEqual(self.game.state, State.READY)
        self.game.turn(Direction.UP)
        self.game.turn(Direction.LEFT)
        self.game.turn(Direction.DOWN)
        self.game.step()
        self.assertEqual(self.game.snake[0], (7, 1))
        self.game.turn(Direction.LEFT)
        self.game.step()
        self.assertEqual(self.game.snake[0], (6, 1))

    def test_eating_grows_and_places_food_on_an_empty_cell(self):
        self.game.food = (8, 2)
        self.game.toggle_pause()
        self.game.step()
        self.assertEqual(
            (len(self.game.snake), self.game.score, self.game.best), (4, 1, 1)
        )
        self.assertNotIn(self.game.food, self.game.snake)
        self.game.reset()
        self.assertEqual((self.game.score, self.game.best), (0, 1))
        self.assertEqual(self.game.state, State.READY)

    def test_wall_crash_stops_until_restart(self):
        self.game.turn(Direction.UP)
        for _ in range(3):
            self.game.step()
        self.assertEqual(self.game.state, State.OVER)
        self.assertEqual(self.game.snake[0], (7, 0))
        self.game.turn(Direction.RIGHT)
        self.game.step()
        self.assertEqual(self.game.snake[0], (7, 0))
        self.game.toggle_pause()
        self.assertEqual(self.game.state, State.RUNNING)
        self.assertEqual(len(self.game.snake), 3)

    def test_self_collision_but_vacated_tail_is_legal(self):
        self.game.snake = deque([(2, 1), (2, 2), (1, 2), (1, 1)])
        self.game.direction = Direction.UP
        self.game.food = (15, 3)
        self.game.turn(Direction.LEFT)
        self.game.step()
        self.assertEqual(self.game.state, State.RUNNING)
        self.assertEqual(self.game.snake[0], (1, 1))
        self.game.snake.append((0, 1))
        self.game.turn(Direction.DOWN)
        self.game.step()
        self.assertEqual(self.game.state, State.OVER)

    def test_filling_board_wins_without_food_spawn_loop(self):
        # Head at (1, 0), one empty cell to its left, a continuous body behind it.
        path = [(x, 0) for x in range(1, 16)]
        for y in range(1, 4):
            path.extend((x, y) for x in (range(15, -1, -1) if y % 2 else range(16)))
        self.game.snake = deque(path)
        self.game.direction = Direction.LEFT
        self.game.food = (0, 0)
        self.game.state = State.RUNNING
        self.game.step()
        self.assertEqual(self.game.state, State.WON)
        self.assertEqual(len(self.game.snake), 64)
        self.assertIsNone(self.game.food)


class SnakeController(unittest.TestCase):
    def setUp(self):
        self.fire = MockAkaiFire()
        self.fire.canvas = Canvas()  # Check real pixels, not recorded draw operations.
        self.app = SnakeApp(self.fire)
        self.addCleanup(self.fire.close)
        self.addCleanup(self.app.shutdown)

    def press(self, button):
        self.fire.simulate_button_press(button)
        self.fire.simulate_button_release(button)
        self.app.tick(0)

    def test_pattern_and_grid_controls_pause_and_reset(self):
        for button, expected in (
            (self.fire.BUTTON_PAT_UP, (7, 1)),
            (self.fire.BUTTON_GRID_LEFT, (6, 1)),
            (self.fire.BUTTON_PAT_DOWN, (6, 2)),
            (self.fire.BUTTON_GRID_RIGHT, (7, 2)),
        ):
            self.press(button)
            self.app.tick(0.32)
            self.assertEqual(self.app.game.snake[0], expected)
        self.press(self.fire.BUTTON_PLAY)
        self.app.tick(5)
        self.assertEqual(self.app.game.state, State.PAUSED)
        self.assertEqual(self.app.game.snake[0], (7, 2))
        self.press(self.fire.BUTTON_PLAY)
        self.app.tick(0.32)
        self.assertEqual(self.app.game.snake[0], (8, 2))
        self.press(self.fire.BUTTON_STOP)
        self.assertEqual(self.app.game.state, State.READY)
        self.assertEqual(self.app.game.snake[0], (7, 2))

    def test_stalled_frame_advances_only_one_cell(self):
        self.press(self.fire.BUTTON_PLAY)
        self.app.tick(20)
        self.assertEqual(self.app.game.snake[0], (8, 2))

    def test_both_views_follow_the_same_board_after_eating(self):
        self.app.game.food = (8, 2)
        self.press(self.fire.BUTTON_PLAY)
        self.app.tick(0.32)
        game = self.app.game
        for y in range(4):
            for x in range(16):
                with self.subTest(cell=(x, y)):
                    color = self.fire.pad_colors[y * 16 + x]
                    # Interior sample avoids the head marker and food outline.
                    pixel = self.fire.canvas.get_pixel(x * 8 + 1, 25 + y * 10)
                    if (x, y) == game.snake[0]:
                        self.assertEqual(color, self.app.HEAD_COLOR)
                        self.assertEqual(pixel, 0)
                    elif (x, y) in game.snake:
                        self.assertEqual(color, self.app.BODY_COLOR)
                        self.assertEqual(pixel, 0)
                    elif (x, y) == game.food:
                        self.assertEqual(color, self.app.FOOD_COLOR)
                        self.assertEqual(
                            self.fire.canvas.get_pixel(x * 8 + 4, 27 + y * 10), 0
                        )
                    else:
                        self.assertEqual(color, (0, 0, 0))
                        self.assertEqual(pixel, 1)
        self.assertEqual(game.score, 1)

    def test_bounded_run_releases_handlers_but_leaves_borrowed_controller_open(self):
        self.app.run(duration=0.04)
        self.assertFalse(self.fire._closed)
        self.assertEqual(self.fire.button_listeners["global"], [])
        self.assertEqual(self.fire.pad_colors, [(0, 0, 0)] * 64)


if __name__ == "__main__":
    unittest.main()
