from akai_fire import AkaiFire
import math
import time
import random


def draw_matrix_rain(canvas, frame):
    canvas.clear()
    # Matrix-style digital rain
    drops = [(x, (frame * 2 + x * 7) % 80) for x in range(0, 128, 3)]
    for x, y in drops:
        length = random.randint(5, 15)
        for i in range(length):
            if 0 <= y - i < 64:
                intensity = 1 if i == 0 else random.random() > 0.5
                canvas.set_pixel(x, int(y - i), intensity)


def draw_spinning_tunnel(canvas, frame):
    canvas.clear()
    center_x, center_y = 64, 32
    t = frame * 0.1
    # Create concentric rotating squares
    for r in range(5, 50, 5):
        angle = t + r * 0.1
        for i in range(4):
            x = center_x + r * math.cos(angle + i * math.pi / 2)
            y = center_y + r * math.sin(angle + i * math.pi / 2)
            size = int(r * 0.3)
            canvas.draw_rectangle(int(x - size / 2), int(y - size / 2), size, size)


def draw_plasma(canvas, frame):
    canvas.clear()
    t = frame * 0.1
    for y in range(64):
        for x in range(0, 128, 2):
            v = math.sin(x * 0.04 + t)
            v += math.sin(y * 0.05 + t)
            v += math.sin((x + y) * 0.07 + t)
            v += math.sin(math.sqrt((x - 64) ** 2 + (y - 32) ** 2) * 0.1)
            if v > 0:
                canvas.set_pixel(
                    x,
                    y,
                )


def draw_demoscene(canvas, frame):
    canvas.clear(0)
    t = frame * 0.1

    # 1. Draw rotating tunnels of different sizes
    center_x, center_y = 64, 32
    for r in range(4, 40, 8):
        angle = t * (1 + r * 0.02)
        points = []
        for i in range(6):  # Hexagonal tunnel
            x = center_x + r * math.cos(angle + i * math.pi / 3)
            y = center_y + r * math.sin(angle + i * math.pi / 3)
            points.append((int(x), int(y)))

        # Connect points to form tunnel segments
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            canvas.draw_line(x1, y1, x2, y2, 1)

    # 2. Add floating sine text effect
    phase = t * 2
    for x in range(0, 128, 4):
        y_offset = math.sin(x * 0.1 + phase) * 10
        y = int(32 + y_offset)
        # Draw vertical bars that follow sine wave
        if 0 <= y < 64:
            height = int(8 + math.sin(x * 0.2 + t) * 4)
            canvas.draw_vertical_line(x, y - height // 2, height, 1)

    # 3. Add spinning star/corona effect
    num_rays = 12
    for i in range(num_rays):
        angle = t + i * (2 * math.pi / num_rays)
        length = 20 + math.sin(t * 2) * 10
        x1 = center_x + math.cos(angle) * length
        y1 = center_y + math.sin(angle) * length
        x2 = center_x + math.cos(angle) * (length * 0.5)
        y2 = center_y + math.sin(angle) * (length * 0.5)
        canvas.draw_line(int(x1), int(y1), int(x2), int(y2), 1)

    # 4. Add interference pattern overlay
    for y in range(0, 64, 2):
        for x in range(0, 128, 2):
            if (math.sin(x * 0.2 + t) + math.sin(y * 0.2 + t)) > 1.8:
                canvas.set_pixel(x, y, 1)

    # 5. Add bouncing spheres
    for i in range(3):
        sphere_t = t + i * 2.094  # 2π/3 phase difference
        sphere_x = int(center_x + math.cos(sphere_t) * 30)
        sphere_y = int(center_y + math.sin(sphere_t * 1.5) * 15)
        radius = int(3 + math.sin(t * 2) * 2)
        canvas.draw_circle(sphere_x, sphere_y, radius, 1)

        # Add trailing effect
        trail_length = 3
        for j in range(trail_length):
            trail_t = sphere_t - j * 0.2
            trail_x = int(center_x + math.cos(trail_t) * 30)
            trail_y = int(center_y + math.sin(trail_t * 1.5) * 15)
            canvas.set_pixel(trail_x, trail_y, 1)

    # 6. Add pulsing corner accents
    corner_size = int(5 + math.sin(t * 3) * 3)
    for x, y in [
        (0, 0),
        (127 - corner_size, 0),
        (0, 63 - corner_size),
        (127 - corner_size, 63 - corner_size),
    ]:
        canvas.fill_rectangle(x, y, corner_size, corner_size, 1)


def draw_particle_explosion(canvas, frame):
    canvas.clear()
    particles = [
        (math.cos(i * 0.7) * frame, math.sin(i * 0.7) * frame) for i in range(20)
    ]
    center_x, center_y = 64, 32
    for dx, dy in particles:
        x = int(center_x + dx * math.cos(frame * 0.05))
        y = int(center_y + dy * math.sin(frame * 0.05))
        if 0 <= x < 128 and 0 <= y < 64:
            canvas.fill_circle(x, y, 2, 1)
            # Add trailing lines
            canvas.draw_line(center_x, center_y, x, y)


def draw_beat_demo(canvas, frame):
    canvas.clear()
    t = frame * 0.1

    # Beat timing (120 BPM simulation)
    beat = math.sin(t * 1.2)  # Basic beat pulse
    # noinspection PyTypeChecker
    beat_intensity = max(0, beat)  # Sharp attack, soft decay
    hard_beat = 1 if frame % 20 < 3 else 0  # Sharp on/off beat

    # Center coordinates with beat-driven displacement
    center_x = 64 + math.sin(t * 0.7) * 10 * beat_intensity
    center_y = 32 + math.cos(t * 0.5) * 8 * beat_intensity

    # 1. Explosive beat rings
    if hard_beat:
        for r in range(0, 60, 6):
            canvas.draw_circle(int(center_x), int(center_y), r)

    # 2. Rotating aggressive star burst
    num_spikes = 16
    spike_length = 30 + beat_intensity * 20
    for i in range(num_spikes):
        angle = t * 2 + i * (2 * math.pi / num_spikes)
        x1 = center_x + math.cos(angle) * spike_length
        y1 = center_y + math.sin(angle) * spike_length
        x2 = center_x + math.cos(angle + 0.2) * (spike_length * 0.3)
        y2 = center_y + math.sin(angle + 0.2) * (spike_length * 0.3)
        canvas.draw_line(int(x1), int(y1), int(x2), int(y2))

    # 3. Beat-driven tunnel effect
    tunnel_layers = 8
    for r in range(tunnel_layers):
        size = (r * 8 + frame * 2) % 64
        angle = t * (1 - r * 0.1) + beat_intensity * 0.5
        points = []
        num_sides = 6 + hard_beat * 2  # Changes shape on beat
        for i in range(num_sides):
            x = center_x + (size + beat_intensity * 10) * math.cos(
                angle + i * 2 * math.pi / num_sides
            )
            y = center_y + (size + beat_intensity * 10) * math.sin(
                angle + i * 2 * math.pi / num_sides
            )
            points.append((int(x), int(y)))

        # Connect points
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            canvas.draw_line(x1, y1, x2, y2)

    # 4. Beat-synchronized corner explosions
    if hard_beat:
        for corner in [(0, 0), (127, 0), (0, 63), (127, 63)]:
            for i in range(5):
                angle = random.random() * 2 * math.pi
                length = random.randint(5, 15)
                end_x = corner[0] + int(math.cos(angle) * length)
                end_y = corner[1] + int(math.sin(angle) * length)
                if 0 <= end_x < 128 and 0 <= end_y < 64:
                    canvas.draw_line(corner[0], corner[1], end_x, end_y)

    # 5. Oscillating diagonal grid
    grid_spacing = 16
    grid_offset = math.sin(t * 2) * 8 * beat_intensity
    for i in range(-128, 128, grid_spacing):
        x1 = max(0, min(127, i + int(grid_offset)))
        x2 = max(0, min(127, i + grid_spacing + int(grid_offset)))
        canvas.draw_line(x1, 0, x2, 63)
        canvas.draw_line(x1, 63, x2, 0)

    # 6. Central beat indicator
    core_size = int(10 + beat_intensity * 8)
    canvas.fill_circle(int(center_x), int(center_y), core_size)

    # 7. Pulsing text effect
    text_y = 32 + math.sin(t * 3) * 10
    for x in range(0, 128, 8):
        height = int(4 + beat_intensity * 12)
        canvas.draw_vertical_line(x, int(text_y - height / 2), height)

    # 8. Beat-driven particle storm
    num_particles = int(20 * (1 + beat_intensity))
    for _ in range(num_particles):
        angle = random.random() * 2 * math.pi
        dist = random.random() * 40 * (1 + beat_intensity)
        px = center_x + math.cos(angle) * dist
        py = center_y + math.sin(angle) * dist
        if 0 <= px < 128 and 0 <= py < 64:
            canvas.set_pixel(int(px), int(py))


def draw_tron_humanoid(canvas, frame):
    canvas.clear()
    t = frame * 0.1

    # Grid system with perspective
    horizon = 32
    grid_spacing = 16
    for z in range(8):  # Depth layers
        depth = 1 + z * 0.5
        y_pos = horizon + (z * 8)  # Grid lines get closer together in distance
        # Horizontal lines with perspective
        for x in range(-64, 192, grid_spacing):
            # Apply perspective transformation
            x_left = int(64 + (x - 64) / depth)
            x_right = int(64 + (x + grid_spacing - 64) / depth)
            if 0 <= y_pos < 64:
                canvas.draw_line(x_left, int(y_pos), x_right, int(y_pos))

        # Vertical lines with perspective
        for x in range(-64, 192, grid_spacing):
            x_transformed = int(64 + (x - 64) / depth)
            if 0 <= x_transformed < 128:
                y_bottom = min(63, y_pos + grid_spacing)
                canvas.draw_line(
                    x_transformed, int(y_pos), x_transformed, int(y_bottom), 1
                )

    # Humanoid figure
    center_x = 64 + math.sin(t * 0.7) * 20
    center_y = 32 + math.sin(t * 0.5) * 5

    # Head
    head_size = 4
    canvas.fill_circle(int(center_x), int(center_y - 12), head_size)

    # Body with energy core
    canvas.draw_line(
        int(center_x), int(center_y - 8), int(center_x), int(center_y + 6), 1
    )
    core_y = center_y - 2
    core_size = 2 + math.sin(t * 3) * 1  # Pulsing core
    canvas.fill_circle(int(center_x), int(core_y), int(core_size))

    # Arms
    arm_angle = math.sin(t * 2) * 0.5
    arm_length = 10
    # Left arm
    lax = center_x + math.cos(math.pi + arm_angle) * arm_length
    lay = center_y + math.sin(math.pi + arm_angle) * arm_length
    canvas.draw_line(int(center_x), int(center_y), int(lax), int(lay))
    # Right arm
    rax = center_x + math.cos(arm_angle) * arm_length
    ray = center_y + math.sin(arm_angle) * arm_length
    canvas.draw_line(int(center_x), int(center_y), int(rax), int(ray))

    # Legs with running animation
    leg_cycle = math.sin(t * 3)
    for side in [-1, 1]:  # Left and right legs
        leg_angle = leg_cycle * 0.5 * side
        leg_length = 12
        # Upper leg
        lx = center_x + math.cos(math.pi / 2 + leg_angle) * leg_length * 0.5 * side
        ly = center_y + 6 + math.sin(math.pi / 2 + leg_angle) * leg_length * 0.5
        canvas.draw_line(int(center_x), int(center_y + 6), int(lx), int(ly))
        # Lower leg
        lx2 = lx + math.cos(math.pi / 2 + leg_angle * 2) * leg_length * 0.5 * side
        ly2 = ly + math.sin(math.pi / 2 + leg_angle * 2) * leg_length * 0.5
        canvas.draw_line(int(lx), int(ly), int(lx2), int(ly2))

    # Energy trails
    trail_length = 5
    for i in range(trail_length):
        trail_t = t - i * 0.2
        trail_x = 64 + math.sin(trail_t * 0.7) * 20
        alpha = 1 if i == 0 else 0.5
        if random.random() < alpha:
            canvas.set_pixel(int(trail_x), int(center_y - 2))

    # Power lines extending from core
    num_lines = 3
    for i in range(num_lines):
        angle = t * 2 + i * (2 * math.pi / num_lines)
        length = 4 + math.sin(t * 5 + i) * 2
        end_x = center_x + math.cos(angle) * length
        end_y = core_y + math.sin(angle) * length
        if random.random() < 0.7:  # Flickering effect
            canvas.draw_line(int(center_x), int(core_y), int(end_x), int(end_y))

    # Edge highlights on grid intersections
    for x in range(0, 128, grid_spacing):
        for y in range(horizon, 64, grid_spacing):
            if random.random() < 0.3:  # Random highlight effect
                canvas.set_pixel(
                    x,
                    y,
                )


class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.prev_x = x
        self.prev_y = y


def draw_fluid_simulation(canvas, frame):
    canvas.clear()

    # Initialize particles if first frame
    if frame == 0:
        particles = []
        num_particles = 40
        for i in range(num_particles):
            x = 64 + random.uniform(-20, 20)
            y = 32 + random.uniform(-20, 20)
            particles.append(Particle(x, y))
        draw_fluid_simulation.particles = particles

    particles = draw_fluid_simulation.particles

    # Physics parameters
    gravity = 0.2
    bounce = 0.8
    connection_strength = 0.3
    fluid_radius = 15

    # Update particle positions
    for p in particles:
        # Save previous position
        p.prev_x = p.x
        p.prev_y = p.y

        # Apply velocity
        p.x += p.vx
        p.y += p.vy

        # Apply gravity
        p.vy += gravity

        # Apply mouse-like force (circular motion)
        center_x = 64 + math.sin(frame * 0.05) * 20
        center_y = 32 + math.cos(frame * 0.05) * 15
        dx = center_x - p.x
        dy = center_y - p.y
        dist = math.sqrt(dx * dx + dy * dy)
        force = 0.5 * (1.0 - min(1.0, dist / 50.0))
        p.vx += dx * force * 0.1
        p.vy += dy * force * 0.1

        # Boundaries
        if p.x < 0:
            p.x = 0
            p.vx *= -bounce
        elif p.x > 127:
            p.x = 127
            p.vx *= -bounce
        if p.y < 0:
            p.y = 0
            p.vy *= -bounce
        elif p.y > 63:
            p.y = 63
            p.vy *= -bounce

        # Apply drag
        p.vx *= 0.98
        p.vy *= 0.98

    # Particle interactions (metaball-like)
    for i, p1 in enumerate(particles):
        for p2 in particles[i + 1 :]:
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < fluid_radius:
                # Draw connection if particles are close
                strength = 1 - (dist / fluid_radius)
                if strength > 0.3:  # Only draw stronger connections
                    canvas.draw_line(
                        int(p1.x),
                        int(p1.y),
                        int(p2.x),
                        int(p2.y),
                    )

                # Apply forces to create fluid-like behavior
                force = (fluid_radius - dist) * connection_strength
                angle = math.atan2(dy, dx)
                fx = math.cos(angle) * force
                fy = math.sin(angle) * force

                p1.vx -= fx
                p1.vy -= fy
                p2.vx += fx
                p2.vy += fy

    # Draw particles with different sizes based on velocity
    for p in particles:
        velocity = math.sqrt(p.vx * p.vx + p.vy * p.vy)
        size = int(1 + min(velocity * 0.5, 2))
        # Draw with slight motion blur
        canvas.draw_line(int(p.prev_x), int(p.prev_y), int(p.x), int(p.y))
        canvas.fill_circle(int(p.x), int(p.y), size)


def main():
    fire = AkaiFire()
    canvas = fire.new_canvas()

    animations = [
        ("Demoscene", draw_demoscene),
        ("Fluid Simulation", draw_fluid_simulation),
        ("Matrix Rain", draw_matrix_rain),
        ("Spinning Tunnel", draw_spinning_tunnel),
        ("Plasma Effect", draw_plasma),
        ("Beat Demo", draw_beat_demo),
        ("Tron Humanoid", draw_tron_humanoid),
        ("Particle Explosion", draw_particle_explosion),
    ]

    try:
        while True:
            for name, draw_func in animations:
                print(f"Playing: {name}")
                start_time = time.time()
                frame = 0

                while time.time() - start_time < 5:  # Play each animation for 5 seconds
                    draw_func(canvas, frame)
                    fire.render_to_display()
                    time.sleep(0.03)
                    frame += 1

                fire.clear_display()
                time.sleep(0.5)  # Brief pause between animations

    except KeyboardInterrupt:
        fire.clear_display()
        fire.close()


if __name__ == "__main__":
    main()
