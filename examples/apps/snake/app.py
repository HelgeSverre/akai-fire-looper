"""Two views of one SnakeGame: RGB pads and a monochrome OLED board."""

from akai_fire.constants import (
    BUTTON_GRID_LEFT,
    BUTTON_GRID_RIGHT,
    BUTTON_PAT_DOWN,
    BUTTON_PAT_UP,
    BUTTON_PLAY,
    BUTTON_STOP,
)
from akai_fire_framework import AkaiFireApp, on

from .game import Direction, SnakeGame, State


class SnakeApp(AkaiFireApp):
    APP_NAME = "Snake"
    BODY_COLOR = (0, 65, 35)
    HEAD_COLOR = (100, 127, 25)
    FOOD_COLOR = (127, 20, 0)
    CRASH_COLOR = (127, 0, 0)

    def on_init(self):
        self.game = SnakeGame()
        self._elapsed = 0.0
        self._directions = {
            self.fire.BUTTON_PAT_UP: Direction.UP,
            self.fire.BUTTON_PAT_DOWN: Direction.DOWN,
            self.fire.BUTTON_GRID_LEFT: Direction.LEFT,
            self.fire.BUTTON_GRID_RIGHT: Direction.RIGHT,
        }
        self._draw()

    @on.button((BUTTON_PAT_UP, BUTTON_PAT_DOWN, BUTTON_GRID_LEFT, BUTTON_GRID_RIGHT))
    def steer(self, event):
        self.game.turn(self._directions[event.button])

    @on.button(BUTTON_PLAY)
    def toggle_pause(self, event):
        self.game.toggle_pause()
        self._elapsed = 0.0

    @on.button(BUTTON_STOP)
    def reset(self, event):
        self.game.reset()
        self._elapsed = 0.0

    def on_update(self, dt):
        if self.game.state == State.RUNNING:
            interval = max(0.12, 0.32 - self.game.score * 0.008)
            # A stalled frame advances at most one cell, rather than
            # replaying several missed moves before the player can steer.
            self._elapsed += min(max(dt, 0), interval)
            if self._elapsed >= interval:
                self._elapsed -= interval
                self.game.step()
        self._draw()

    def _draw(self):
        self._draw_pads()
        self._draw_oled()
        direction = self.game.pending_direction or self.game.direction
        for button, value in self._directions.items():
            self.fire.set_button_led(button, 2 if value == direction else 0)
        self.fire.set_button_led(
            self.fire.BUTTON_PLAY,
            self.fire.DUAL_LED_BRIGHT_PRIMARY
            if self.game.state == State.RUNNING
            else 1
            if self.game.state == State.PAUSED
            else 0,
        )
        self.fire.set_button_led(
            self.fire.BUTTON_REC,
            self.fire.DUAL_LED_BRIGHT_PRIMARY if self.game.state == State.OVER else 0,
        )

    def _draw_pads(self):
        colors = [(0, 0, 0)] * (self.game.WIDTH * self.game.HEIGHT)
        for x, y in self.game.snake:
            colors[y * self.game.WIDTH + x] = self.BODY_COLOR
        x, y = self.game.snake[0]
        colors[y * self.game.WIDTH + x] = (
            self.CRASH_COLOR if self.game.state == State.OVER else self.HEAD_COLOR
        )
        if self.game.food is not None:
            x, y = self.game.food
            colors[y * self.game.WIDTH + x] = self.FOOD_COLOR
        self.fire.set_multiple_pad_colors(
            [(pad, *color) for pad, color in enumerate(colors)]
        )

    def _draw_oled(self):
        canvas = self.canvas
        canvas.clear()
        canvas.draw_text_fitted(f"Score {self.game.score}  Best {self.game.best}", 1, 0)
        messages = {
            State.READY: "Arrow / PLAY starts",
            State.RUNNING: "SNAKE   PLAY pauses",
            State.PAUSED: "PAUSED  PLAY resumes",
            State.OVER: "CRASH!  PLAY retries",
            State.WON: "YOU WIN! PLAY again",
        }
        canvas.draw_text_fitted(messages[self.game.state], 1, 11)
        canvas.draw_rect(0, 24, 128, 40)
        # Cell (x, y) is pad y*16+x and the same OLED cell in both views.
        for x, y in self.game.snake:
            canvas.fill_rect(x * 8 + 1, 24 + y * 10 + 1, 6, 8)
        x, y = self.game.snake[0]
        canvas.fill_rect(x * 8 + 3, 24 + y * 10 + 3, 2, 2, color=1)
        if self.game.food is not None:
            x, y = self.game.food
            canvas.draw_circle(x * 8 + 4, 24 + y * 10 + 5, 2)


def main():
    print("Snake: PATTERN up/down and GRID left/right steer. PLAY pauses; STOP resets.")
    with SnakeApp() as app:
        app.run()
