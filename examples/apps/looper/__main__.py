#!/usr/bin/env python3
"""Entry point for running the looper as a module."""

from .looper_app import LooperApp

if __name__ == "__main__":
    print("Starting MIDI Looper...")
    print()
    print("Controls:")
    print("  Pads: Select/trigger clips")
    print("  REC: Arm/start recording")
    print("  PLAY: Start/stop playback")
    print("  STOP: Stop all clips")
    print("  SOLO 1-4: Select track")
    print("  Volume encoder: Adjust BPM")
    print("  NOTE: Main mode")
    print("  BROWSER: Settings mode")
    print()

    with LooperApp() as app:
        app.run()
