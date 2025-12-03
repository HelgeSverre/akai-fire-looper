"""
MIDI Looper application using AkaiFireApp framework.

A simple loop recorder with:
- 4 tracks x 16 clips grid
- Record/play/overdub per clip
- Quantization options
- Visual feedback on pads
"""

from .looper_app import LooperApp

__all__ = ["LooperApp"]
