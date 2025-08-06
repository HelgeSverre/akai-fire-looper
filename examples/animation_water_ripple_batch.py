import colorsys
import math
import time
from dataclasses import dataclass
from pprint import pprint
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


def create_tap_droplet(pad_index: int, velocity: int) -> Droplet:
    """Create a droplet from a pad tap"""
    x = pad_index % 16
    y = pad_index // 16

    # Scale velocity to impact (32 is min velocity on Fire, max is 127)
    # Linear mapping from [32, 127] to [0.25, 2.0]
    if velocity == 127:
        scaled_impact = 2.01
    else:
        scaled_impact = 0.25 + (velocity - 32) / 95 * 1.75

    print(
        f"Pad {pad_index} tapped with velocity {velocity}, creating droplet with impact {scaled_impact}"
    )
    return Droplet(x=x, y=y, age=0, intensity=1.0, impact=scaled_impact)


class DropletAnimation:
    def __init__(self):
        self.midi_in, self.midi_out, in_port, out_port = find_fire_ports()
        if in_port is None or out_port is None:
            raise RuntimeError("Couldn't find Akai Fire ports!")

        self.midi_out.open_port(out_port)
        self.midi_in.open_port(in_port)

        # Smoothed animation parameters
        self.wave_frequency = SmoothedValue(1.0)  # Volume encoder (0.5 to 8.0)
        self.color_hue = SmoothedValue(0.66)  # Pan encoder (0.0 to 1.0)
        self.radius_multiplier = SmoothedValue(1.0)  # Filter encoder (0.5 to 6.0)
        self.age_decay = SmoothedValue(0.05)  # Resonance encoder (0.05 to 2.0)

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
        """Handle rotary encoder movements with improved scaling"""
        # Increased base scaling for faster response
        base_scaling = 0.3

        if direction == "clockwise":
            change = (velocity / 63) * base_scaling
        else:
            change = -(velocity / 63) * base_scaling

        if encoder_id == 0x10:  # Volume - Wave frequency
            # Exponential scaling for wave frequency
            current = math.log2(self.wave_frequency.current)
            new_freq = math.pow(2, current + change)
            new_freq = max(0.5, min(8.0, new_freq))
            self.wave_frequency.set_target(new_freq)
            print(
                f"Wave frequency: {new_freq:.2f}Hz - Controls how many ripples appear in the wave pattern"
            )

        elif encoder_id == 0x11:  # Pan - Color hue
            # Smoother hue transitions with proper wrapping
            new_hue = self.color_hue.current + change * 5.0
            if new_hue >= 1.0:
                new_hue -= 1.0
            elif new_hue < 0.0:
                new_hue += 1.0
            self.color_hue.set_target(new_hue)
            # Convert hue to descriptive color name
            color_names = {
                0.0: "Red",
                0.08: "Orange",
                0.17: "Yellow",
                0.33: "Green",
                0.5: "Cyan",
                0.67: "Blue",
                0.83: "Purple",
                0.92: "Pink",
            }
            closest_color = min(color_names.keys(), key=lambda x: abs(x - new_hue))
            print(f"Color: {color_names[closest_color]} (Hue: {new_hue:.3f})")

        elif encoder_id == 0x12:  # Filter - Ripple spacing
            new_radius = self.radius_multiplier.current + change * 4
            new_radius = max(0.5, min(6.0, new_radius))
            self.radius_multiplier.set_target(new_radius)
            if new_radius < 1.0:
                desc = "Very tight ripples"
            elif new_radius < 2.0:
                desc = "Compact ripples"
            elif new_radius < 4.0:
                desc = "Medium spread"
            else:
                desc = "Wide ripples"
            print(f"Ripple spacing: {new_radius:.2f} - {desc}")

        elif encoder_id == 0x13:  # Resonance - Decay speed
            new_decay = self.age_decay.current * math.exp(change)
            new_decay = max(0.05, min(2.0, new_decay))
            self.age_decay.set_target(new_decay)
            if new_decay < 0.2:
                desc = "Very long trails"
            elif new_decay < 0.5:
                desc = "Long-lasting ripples"
            elif new_decay < 1.0:
                desc = "Medium decay"
            else:
                desc = "Quick fadeout"
            print(f"Decay speed: {new_decay:.2f} - {desc}")

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

                # if stop is pressed, clear screen
                if message[0] == 0xB0 and message[1] == 0x34 and message[2] == 127:
                    print("------ STOP PRESSED ------")
                    self.clear_all_leds()

            time.sleep(0.001)

    def calculate_ripple_effect(self, distance, age, current_freq, current_decay):
        """Calculate ripple effect with more pronounced parameters"""
        # More pronounced frequency effect
        wave = math.sin(distance * current_freq - age * 4)

        # Sharper wave peaks
        wave = math.pow(abs(wave), 0.7) * math.copysign(1, wave)

        # Normalize and enhance contrast
        ripple = wave * 0.5 + 0.5
        ripple = math.pow(ripple, 0.8)  # Enhance contrast

        return ripple

    def run(self):
        try:
            print("\n=== Akai Fire Ripple Animation ===")
            print("\nControls:")
            print("\n1. VOLUME KNOB - Wave Frequency")
            print("   - LOW: Slow, undulating waves (0.5Hz)")
            print("   - MID: Natural ripple motion (2-4Hz)")
            print("   - HIGH: Fast, energetic patterns (8Hz)")

            print("\n2. PAN KNOB - Color Selection")
            print("   - Smoothly transition through the color spectrum")
            print("   - Full rotation cycles through all colors")
            print(
                "   - Common colors: Red → Orange → Yellow → Green → Cyan → Blue → Purple → Pink"
            )

            print("\n3. FILTER KNOB - Ripple Spacing")
            print("   - LOW: Tight, dense ripple patterns")
            print("   - MID: Natural water-like spacing")
            print("   - HIGH: Wide, spread out waves")

            print("\n4. RESONANCE KNOB - Decay Speed")
            print("   - LOW: Long-lasting trails (like syrup)")
            print("   - MID: Natural water-like decay")
            print("   - HIGH: Quick fadeout (like splashing)")

            print("\nInteraction:")
            print("- Tap pads to create ripples")
            print("- Harder taps create stronger ripples")
            print("- Use SOLO buttons to illuminate full lanes for debugging")

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
