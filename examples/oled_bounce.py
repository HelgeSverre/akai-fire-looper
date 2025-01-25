import time

from akai_fire import AkaiFireBitmap

fire_bitmap = AkaiFireBitmap()
port_name = "FL STUDIO FIRE 10"
midi_out = rtmidi.MidiOut()

# Find and open the MIDI port
available_ports = midi_out.get_ports()
fire_port = None

for index, name in enumerate(available_ports):
    if port_name in name:
        fire_port = index
        break

if fire_port is None:
    print(f"MIDI port '{port_name}' not found. Available ports: {available_ports}")
    return

midi_out.open_port(fire_port)

# Bouncing Ball Parameters
x, y = 64, 32
radius = 10
dx, dy = 2, 1  # Velocity

try:
    for _ in range(500):  # 500 frames for ~3 seconds at ~60 FPS
        fire_bitmap.clear()
        fire_bitmap.fill_circle(x, y, radius, 1)
        fire_bitmap.send_to_device(midi_out)

        # Update position
        x += dx
        y += dy

        # Bounce off walls
        if x - radius <= 0 or x + radius >= 128:
            dx = -dx
        if y - radius <= 0 or y + radius >= 64:
            dy = -dy

        time.sleep(0.01)  # ~20 FPS

finally:
    midi_out.close_port()
