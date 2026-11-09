"""Short synthesized voices through pygame; no sample downloads or MIDI ports."""

import math
import sys
from array import array


class Sound:
    def __init__(self, enabled=True):
        self.available = False
        self._owned = False
        self._voices = {}
        if not enabled:
            return
        try:
            import pygame

            self._pygame = pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                self._owned = True
            self.rate, sample_format, self.channels = pygame.mixer.get_init()
            if sample_format != -16 or self.channels not in (1, 2):
                raise RuntimeError("Audio requires signed 16-bit mono or stereo output")
            self.available = True
        except (ImportError, RuntimeError) as exc:
            self.close()
            print(f"Firestorm is running silently: {exc}")
        except Exception as exc:  # noqa: BLE001 - unavailable audio must not disable visuals
            self.close()
            print(f"Firestorm is running silently: {exc}")

    def play(self, row, column):
        if not self.available:
            return
        key = (row, column)
        if key not in self._voices:
            scale = (0, 2, 4, 7, 9)
            note = 48 + 12 * (column // 5) + scale[column % 5]
            frequency = 440 * 2 ** ((note - 69) / 12)
            samples = array("h")
            length = int(self.rate * 0.35)
            for i in range(length):
                t = i / self.rate
                envelope = min(1, t / 0.008) * math.exp(-t * (8 + row * 2))
                wave = math.sin(math.tau * frequency * t)
                wave += 0.25 * math.sin(math.tau * frequency * (row + 2) * t)
                value = round(wave * envelope * 2200)
                samples.extend([value] * self.channels)
            if sys.byteorder != "little":
                samples.byteswap()
            self._voices[key] = self._pygame.mixer.Sound(buffer=samples.tobytes())
        self._voices[key].play()

    def stop(self):
        for voice in self._voices.values():
            voice.stop()

    def close(self):
        self.stop()
        if self._owned:
            self._pygame.mixer.quit()
        self._owned = False
        self.available = False
        self._voices.clear()
