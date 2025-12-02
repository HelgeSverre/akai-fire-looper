from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AppSettings:
    tempo: float = 120.0
    swing: float = 0.5
    quantize: bool = True
    midi_in_channel: int = 0
    midi_out_channel: int = 0
    record_quantize: bool = True
    default_velocity: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tempo": self.tempo,
            "swing": self.swing,
            "quantize": self.quantize,
            "midi_in_channel": self.midi_in_channel,
            "midi_out_channel": self.midi_out_channel,
            "record_quantize": self.record_quantize,
            "default_velocity": self.default_velocity,
        }
