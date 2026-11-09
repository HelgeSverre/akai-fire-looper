"""Small generated preview synth. No external MIDI ports or sample downloads."""

import math
import random
from array import array
from collections import OrderedDict


class PreviewSound:
    def __init__(self, enabled=True):
        self.available = False
        self.reason = "Audio disabled"
        self._owned = False
        self._cache = OrderedDict()
        self._voices = {}
        if not enabled:
            return
        try:
            import pygame

            self._pygame = pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=256)
                self._owned = True
            pygame.mixer.set_num_channels(max(48, pygame.mixer.get_num_channels()))
            self.rate, size, self.channels = pygame.mixer.get_init()
            if size != -16 or self.channels not in (1, 2):
                raise RuntimeError("Preview needs 16-bit mono/stereo audio")
            self.available = True
            self.reason = "Computer preview"
        except Exception as exc:  # noqa: BLE001 - preview failure must leave controls usable
            self.close()
            self.reason = f"Audio unavailable: {exc}"
            print(self.reason)

    def _sound(self, track, pitch):
        key = (track, pitch)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        frequency = 440 * 2 ** ((pitch - 69) / 12)
        drum = track < 3
        # Tonal buffers contain whole periods so looping has no seam.
        length = (
            int(self.rate * 0.25)
            if drum
            else max(16, round(self.rate / frequency * 16))
        )
        samples = array("h")
        noise = random.Random(pitch)
        for i in range(length):
            t = i / self.rate
            if track == 0:
                wave = math.sin(
                    math.tau * (48 * t + 2 * (1 - math.exp(-t * 35)))
                ) * math.exp(-t * 20)
            elif track == 1:
                wave = (
                    0.75 * noise.uniform(-1, 1) + 0.25 * math.sin(math.tau * 180 * t)
                ) * math.exp(-t * 24)
            elif track == 2:
                wave = noise.uniform(-1, 1) * math.exp(-t * 65) * 0.5
            else:
                phase = math.tau * i * 16 / length
                wave = math.sin(phase)
                wave += (0.3 if track in (3, 5) else 0.12) * math.sin(phase * 2)
                wave *= 0.55 if track == 7 else 0.8
            value = round(wave * 3000)
            samples.extend([value] * self.channels)
        sound = self._pygame.mixer.Sound(buffer=samples.tobytes())
        self._cache[key] = sound
        if len(self._cache) > 192:
            self._cache.popitem(last=False)
        return sound

    def note_on(self, track, pitch, velocity):
        if not self.available:
            return
        self.note_off(track, pitch)
        sound = self._sound(track, pitch)
        channel = sound.play(loops=0 if track < 3 else -1, fade_ms=3)
        if channel is not None:
            channel.set_volume(velocity / 127)
            self._voices[track, pitch] = (channel, sound)

    def note_off(self, track, pitch):
        voice = self._voices.pop((track, pitch), None)
        if voice is not None:
            channel, sound = voice
            if channel.get_sound() is sound:
                channel.stop()

    def stop(self):
        for key in list(self._voices):
            self.note_off(*key)

    def close(self):
        self.stop()
        if self._owned:
            self._pygame.mixer.quit()
        self._owned = False
        self.available = False
        self._cache.clear()
