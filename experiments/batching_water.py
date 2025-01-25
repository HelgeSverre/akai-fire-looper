import colorsys
import math
import random
import time
from dataclasses import dataclass
from threading import Thread, Lock
from typing import List

import rtmidi


@dataclass
class Droplet:
    x: float
    y: float
    age: float
    intensity: float
    impact: float


def find_fire_ports():
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    input_port = output_port = None
    for i, port_name in enumerate(midi_in.get_ports()):
        if "FL STUDIO FIRE" in port_name:
            input_port = i
            print(f"Found Akai Fire MIDI INPUT port: {port_name}")
    for i, port_name in enumerate(midi_out.get_ports()):
        if "FL STUDIO FIRE" in port_name:
            output_port = i
            print(f"Found Akai Fire MIDI OUTPUT port: {port_name}")
    return midi_in, midi_out, input_port, output_port


class SmoothedValue:
    def __init__(self, initial_value: float, smoothing: float = 0.15):
        self.current = initial_value
        self.target = initial_value
        self.smoothing = smoothing

    def update(self):
        if abs(self.current - self.target) > 0.0001:
            self.current += (self.target - self.current) * self.smoothing
        return self.current

    def set_target(self, value: float):
        self.target = value


def create_pad_sysex(pad_colors):
    sysex_header = [0xF0, 0x47, 0x7F, 0x43, 0x65]
    length = len(pad_colors) * 4
    length_high = (length >> 7) & 0x7F
    length_low = length & 0x7F

    payload = []
    for index, red, green, blue in pad_colors:
        payload.extend(
            [
                index & 0x3F,
                red & 0x7F,
                green & 0x7F,
                blue & 0x7F,
            ]
        )
    return sysex_header + [length_high, length_low] + payload + [0xF7]


def create_random_droplet() -> Droplet:
    """Create a new ambient droplet with random properties"""
    x = random.uniform(0, 15)
    y = random.uniform(0, 3)
    return Droplet(
        x=x, y=y, age=0, intensity=1.0, impact=0.5
    )  # Lower impact for ambient drops


def create_tap_droplet(pad_index: int, velocity: int) -> Droplet:
    """Create a droplet from a pad tap"""
    x = pad_index % 16
    y = pad_index // 16

    # Scale velocity to impact (32 is min velocity on Fire, max is 127)
    # Segment into 5 "impact" levels for more interesting visuals (0.25, 0.50, 0.70, 1.5, 2.0)

    # Linear mapping from [32, 127] to [0.25, 2.0]
    if velocity == 127:
        scaled_impact = 2.01
    else:
        scaled_impact = 0.25 + (velocity - 32) / 95 * 1.75

    print(
        f"Pad {pad_index} tapped with velocity {velocity}, creating droplet with impact {scaled_impact}"
    )

    return Droplet(
        x=x, y=y, age=0, intensity=1.0, impact=scaled_impact
    )  # Higher impact for tapped drops


class DropletAnimation:
    def __init__(self):
        self.midi_in, self.midi_out, in_port, out_port = find_fire_ports()
        if in_port is None or out_port is None:
            raise RuntimeError("Couldn't find Akai Fire ports!")

        self.midi_out.open_port(out_port)
        self.midi_in.open_port(in_port)

        # Replace animation_speed with wave_frequency
        self.wave_frequency = SmoothedValue(2.0)  # Volume encoder (0.5 to 8.0)
        self.color_hue = SmoothedValue(0.66)  # Pan encoder (0.0 to 1.0)
        self.radius_multiplier = SmoothedValue(2.0)  # Filter encoder (0.5 to 4.0)
        self.age_decay = SmoothedValue(0.4)  # Resonance encoder (0.1 to 1.0)

        # Fixed animation frame rate
        self.frame_rate = 0.03  # ~30fps

        self.debug_lanes = set()
        self.solo_buttons = {
            0x24: 0,  # SOLO_1 -> lane 0
            0x25: 1,  # SOLO_2 -> lane 1
            0x26: 2,  # SOLO_3 -> lane 2
            0x27: 3,  # SOLO_4 -> lane 3
        }

        # Clear all LEDs on startup
        self.clear_all_leds()

        self.encoder_touched = {
            "volume": False,
            "pan": False,
            "filter": False,
            "resonance": False,
        }

        self.droplets: List[Droplet] = []
        self.droplets_lock = Lock()
        self.running = True

    def clear_all_leds(self):
        """Clear all LEDs on the device"""
        # Clear track LEDs (the narrow LEDs between solo buttons and pads)
        for i in range(4):
            control_change = 0x28 + i
            self.midi_out.send_message([0xB0, control_change, 0])

        # Clear transport buttons (PLAY, STOP, REC)
        for button in [0x33, 0x34, 0x35]:
            self.midi_out.send_message([0xB0, button, 0])

        # Clear other function buttons
        for button in [
            0x2C,
            0x2D,
            0x2E,
            0x2F,
            0x30,
            0x31,
            0x32,
        ]:  # STEP, NOTE, DRUM, etc.
            self.midi_out.send_message([0xB0, button, 0])

        # Clear pattern navigation buttons
        for button in [0x1F, 0x20, 0x22, 0x23]:  # PAT UP/DOWN, GRID LEFT/RIGHT
            self.midi_out.send_message([0xB0, button, 0])

        # Clear solo buttons
        for button in self.solo_buttons.keys():
            self.midi_out.send_message([0xB0, button, 0])

        # Clear all pads
        clear_colors = [(i, 0, 0, 0) for i in range(64)]
        self.midi_out.send_message(create_pad_sysex(clear_colors))

    def handle_encoder_rotation(self, encoder_id: int, direction: str, velocity: int):
        """Handle rotary encoder movements"""
        change = velocity / 127 * (0.1 if direction == "clockwise" else -0.1) * 100

        if encoder_id == 0x10:  # Volume - now controls wave frequency
            new_freq = max(0.5, min(8.0, self.wave_frequency.current + change))
            self.wave_frequency.set_target(new_freq)
            print(f"Wave frequency target: {new_freq:.2f}")

        elif encoder_id == 0x11:  # Pan
            new_hue = (self.color_hue.current + change) % 1.0
            self.color_hue.set_target(new_hue)
            print(f"Color hue target: {new_hue:.3f}")

        elif encoder_id == 0x12:  # Filter
            new_radius = max(0.5, min(4.0, self.radius_multiplier.current + change * 4))
            self.radius_multiplier.set_target(new_radius)
            print(f"Radius multiplier target: {new_radius:.2f}")

        elif encoder_id == 0x13:  # Resonance
            new_decay = max(0.01, min(1.0, self.age_decay.current + change))
            self.age_decay.set_target(new_decay)
            print(f"Age decay target: {new_decay:.3f}")

    def handle_solo_button(self, button_id: int, pressed: bool):
        """Handle solo button presses for debug lanes"""
        if button_id in self.solo_buttons:
            lane = self.solo_buttons[button_id]
            if pressed:
                if lane in self.debug_lanes:
                    self.debug_lanes.remove(lane)
                    print(f"Debug lane {lane} disabled")
                else:
                    self.debug_lanes.add(lane)
                    print(f"Debug lane {lane} enabled")

    def handle_midi_input(self):
        """Thread function to handle MIDI input"""
        while self.running:
            msg = self.midi_in.get_message()
            if msg:
                message, _ = msg

                # Handle pad presses
                if message[0] == 0x90 and message[2] > 0:
                    pad_index = message[1] - 54  # Akai Fire pad offset
                    if 0 <= pad_index < 64:
                        with self.droplets_lock:
                            self.droplets.append(
                                create_tap_droplet(pad_index, message[2])
                            )

                    # Handle solo buttons
                    if message[1] in self.solo_buttons:
                        self.handle_solo_button(message[1], True)

                # Handle encoder controls
                encoder_map = {
                    0x10: "volume",
                    0x11: "pan",
                    0x12: "filter",
                    0x13: "resonance",
                }

                if message[1] in encoder_map:
                    if message[0] == 0x90:  # Touch start
                        self.encoder_touched[encoder_map[message[1]]] = True
                    elif message[0] == 0x80:  # Touch end
                        self.encoder_touched[encoder_map[message[1]]] = False

                if message[0] == 0xB0 and message[1] in encoder_map:
                    value = message[2]
                    direction = "clockwise" if value < 0x40 else "counterclockwise"
                    velocity = value if value < 0x40 else (0x80 - value)
                    self.handle_encoder_rotation(message[1], direction, velocity)

            time.sleep(0.001)

    def run(self):
        try:
            print("Starting interactive droplet animation...")
            print("Tap pads to create ripples!")
            print("Use encoders to control animation:")
            print("- Volume: Wave frequency - Controls ripple wave speed")
            print("- Pan: Color hue - Change the color")
            print("- Filter: Ripple radius")
            print("- Resonance: Decay speed")
            print("\nDebug features:")
            print("- Press SOLO buttons to toggle constant illumination of lanes")

            input_thread = Thread(target=self.handle_midi_input, daemon=True)
            input_thread.start()

            while self.running:
                # Update smoothed values
                current_freq = self.wave_frequency.update()
                current_hue = self.color_hue.update()
                current_radius = self.radius_multiplier.update()
                current_decay = self.age_decay.update()

                # Update existing droplets
                pad_intensities = [[0.0] for _ in range(64)]

                # Add debug lane illumination
                for lane in self.debug_lanes:
                    for col in range(16):
                        pad_index = lane * 16 + col
                        pad_intensities[pad_index][0] = 0.5

                with self.droplets_lock:
                    active_droplets = []
                    for drop in self.droplets:
                        drop.age += 0.1  # Fixed age increment
                        drop.intensity = math.exp(-drop.age * current_decay)

                        if drop.intensity > 0.05:
                            active_droplets.append(drop)

                            for row in range(4):
                                for col in range(16):
                                    pad_index = row * 16 + col
                                    distance = math.sqrt(
                                        (col - drop.x) ** 2 + (row - drop.y) ** 2
                                    )

                                    # Use wave_frequency for ripple animation
                                    ripple = (
                                        math.sin(distance * current_freq - drop.age * 4)
                                        * 0.5
                                        + 0.5
                                    )
                                    effect = (
                                        drop.intensity
                                        * drop.impact
                                        * ripple
                                        * math.exp(-distance * 0.5)
                                    )

                                    pad_intensities[pad_index][0] += effect

                    self.droplets = active_droplets

                # Convert intensities to colors
                pad_colors = []
                for i in range(64):
                    intensity = min(1.0, max(0.0, pad_intensities[i][0]))
                    rgb = colorsys.hsv_to_rgb(current_hue, 1.0, intensity)
                    r, g, b = [int(x * 127) for x in rgb]
                    pad_colors.append((i, r, g, b))

                self.midi_out.send_message(create_pad_sysex(pad_colors))
                time.sleep(self.frame_rate)

        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        clear_colors = [(i, 0, 0, 0) for i in range(64)]
        self.midi_out.send_message(create_pad_sysex(clear_colors))
        self.midi_out.close_port()
        self.midi_in.close_port()
        del self.midi_out
        del self.midi_in


if __name__ == "__main__":
    animation = DropletAnimation()
    animation.run()
