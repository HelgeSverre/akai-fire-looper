"""Bounded particle scenes and a shared light field, independent of hardware."""

import colorsys
import math
import random
from dataclasses import dataclass

WIDTH, HEIGHT = 128, 32
SCENES = ("FIREWORKS", "RIPPLES", "ORBIT")


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    hue: float


@dataclass
class Ring:
    x: float
    y: float
    radius: float
    life: float
    hue: float


class World:
    MAX_PARTICLES = 384
    MAX_RINGS = 24
    MAX_ATTRACTORS = 4

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.scene = 0
        self.energy = 55
        self.gravity = 35
        self.trails = 65
        self.color = 190
        self.particles = []
        self.rings = []
        self.attractors = []
        self.light = [0.0] * (WIDTH * HEIGHT)
        self.hues = [0.0] * (WIDTH * HEIGHT)
        self.paused = False
        self.auto = True
        self.elapsed = 0.0
        self.next_burst = 0.0

    @staticmethod
    def position(row, column):
        return column * 8 + 4, row * 8 + 4

    def clear(self):
        self.particles.clear()
        self.rings.clear()
        self.attractors.clear()
        self.light = [0.0] * (WIDTH * HEIGHT)
        self.hues = [0.0] * (WIDTH * HEIGHT)
        self.auto = False

    def change_scene(self, delta):
        self.scene = (self.scene + delta) % len(SCENES)
        self.clear()
        self.auto = True
        self.paused = False
        self.next_burst = 0.0

    def attract(self, row, column):
        point = self.position(row, column)
        if point in self.attractors:
            self.attractors.remove(point)
        else:
            self.attractors.append(point)
            self.attractors = self.attractors[-self.MAX_ATTRACTORS :]

    def burst(self, row, column, *, manual=True):
        if manual:
            self.auto = False
        x, y = self.position(row, column)
        hue = ((self.color + column * 5 + row * 18) % 360) / 360
        if self.scene == 1:
            self.rings.append(Ring(x, y, 1, 2.4, hue))
            self.rings = self.rings[-self.MAX_RINGS :]
        else:
            count = 10 + self.energy // 3
            for i in range(count):
                angle = math.tau * i / count + self.random.uniform(-0.15, 0.15)
                speed = self.random.uniform(8, 15 + self.energy * 0.5)
                self.particles.append(
                    Particle(
                        x,
                        y,
                        math.cos(angle) * speed,
                        math.sin(angle) * speed,
                        1.5 + self.energy / 35,
                        hue,
                    )
                )
            self.particles = self.particles[-self.MAX_PARTICLES :]
        self._light(x, y, 1, hue)

    def _light(self, x, y, value, hue):
        x, y = int(x), int(y)
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            index = y * WIDTH + x
            if value >= self.light[index]:
                self.light[index] = min(1.0, value)
                self.hues[index] = hue

    def update(self, dt):
        if self.paused:
            return
        # A stalled UI frame must not fling particles across the entire world.
        dt = max(0, min(dt, 0.05))
        self.elapsed += dt
        if self.auto:
            self.next_burst -= dt
            if self.next_burst <= 0:
                self.burst(
                    self.random.randrange(4), self.random.randrange(16), manual=False
                )
                self.next_burst = 0.35 + (100 - self.energy) / 180
        decay = math.exp(-dt / (0.04 + self.trails / 110))
        self.light = [v * decay if v > 0.015 else 0.0 for v in self.light]
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            if self.scene == 0:
                p.vy += self.gravity * 0.8 * dt
            centers = self.attractors or ([(64, 16)] if self.scene == 2 else [])
            for cx, cy in centers:
                dx, dy = cx - p.x, cy - p.y
                distance = max(8, math.hypot(dx, dy))
                force = (20 + self.gravity * 2) / distance
                p.vx += (dx * force - dy * (0.8 if self.scene == 2 else 0)) * dt
                p.vy += (dy * force + dx * (0.8 if self.scene == 2 else 0)) * dt
            p.vx *= math.exp(-dt * 0.35)
            p.vy *= math.exp(-dt * 0.35)
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.x < 0 or p.x >= WIDTH:
                p.vx *= -0.7
                p.x = max(0, min(WIDTH - 1, p.x))
            if p.y < 0 or p.y >= HEIGHT:
                p.vy *= -0.7
                p.y = max(0, min(HEIGHT - 1, p.y))
            self._light(p.x, p.y, min(1, p.life), p.hue)
        self.particles = [p for p in self.particles if p.life > 0]
        for ring in self.rings:
            ring.life -= dt
            ring.radius += (8 + self.energy * 0.2 + self.gravity * 0.05) * dt
            steps = max(24, int(ring.radius * 5))
            for i in range(steps):
                angle = math.tau * i / steps
                self._light(
                    ring.x + math.cos(angle) * ring.radius,
                    ring.y + math.sin(angle) * ring.radius,
                    max(0, min(1, ring.life)),
                    ring.hue,
                )
        self.rings = [r for r in self.rings if r.life > 0]

    def pad_colors(self):
        colors = [[0.0, 0.0, 0.0] for _ in range(64)]
        for i, value in enumerate(self.light):
            if value < 0.02:
                continue
            x, y = i % WIDTH, i // WIDTH
            pad = (y // 8) * 16 + x // 8
            rgb = colorsys.hsv_to_rgb(self.hues[i], 0.88, value)
            for channel in range(3):
                colors[pad][channel] += rgb[channel] * 0.6
        result = []
        for pad, rgb in enumerate(colors):
            peak = max(rgb)
            # Normalize before tone mapping: dense trails should stay colorful,
            # rather than clipping all three channels to white.
            scale = (1 - math.exp(-peak)) / peak if peak else 0
            result.append((pad, *(round(c * scale * 127) for c in rgb)))
        for x, y in self.attractors:
            pad = (y // 8) * 16 + x // 8
            result[pad] = (pad, 127, 127, 127)
        return result
