"""The 16×4 game board, independent of the controller and frame loop."""

import random
from collections import deque
from enum import Enum


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


class State(Enum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    OVER = "over"
    WON = "won"


class SnakeGame:
    WIDTH = 16
    HEIGHT = 4

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.best = 0
        self.reset()

    def reset(self):
        self.snake = deque([(7, 2), (6, 2), (5, 2)])  # head first
        self.direction = Direction.RIGHT
        self.pending_direction = None
        self.score = 0
        self.state = State.READY
        self.food = self._place_food()

    def _place_food(self):
        occupied = set(self.snake)
        empty = [
            (x, y)
            for y in range(self.HEIGHT)
            for x in range(self.WIDTH)
            if (x, y) not in occupied
        ]
        return self.rng.choice(empty) if empty else None

    def turn(self, direction):
        if self.state not in (State.READY, State.RUNNING):
            return
        dx, dy = self.direction.value
        if direction.value == (-dx, -dy):
            return
        # Accept one turn per movement tick. Two quick presses must not let
        # the head reverse into its neck before the board advances.
        if self.pending_direction is None and direction != self.direction:
            self.pending_direction = direction
        if self.state == State.READY:
            self.state = State.RUNNING

    def toggle_pause(self):
        if self.state in (State.OVER, State.WON):
            self.reset()
        self.state = State.PAUSED if self.state == State.RUNNING else State.RUNNING

    def step(self):
        if self.state != State.RUNNING:
            return
        if self.pending_direction is not None:
            self.direction = self.pending_direction
            self.pending_direction = None
        x, y = self.snake[0]
        dx, dy = self.direction.value
        head = (x + dx, y + dy)
        grows = head == self.food
        # The tail vacates its cell on a normal move, so entering it is legal.
        occupied = self.snake if grows else list(self.snake)[:-1]
        if (
            not (0 <= head[0] < self.WIDTH and 0 <= head[1] < self.HEIGHT)
            or head in occupied
        ):
            self.state = State.OVER
            return
        self.snake.appendleft(head)
        if grows:
            self.score += 1
            self.best = max(self.best, self.score)
            self.food = self._place_food()
            if self.food is None:
                self.state = State.WON
        else:
            self.snake.pop()
