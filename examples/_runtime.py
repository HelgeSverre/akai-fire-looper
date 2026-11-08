"""Event-aware delays for the small, procedural examples."""

import threading
import time


def wait(fire, seconds):
    """Wait without freezing a pygame mock; window close acts like Ctrl+C.

    GUI events belong to the main thread. Worker animations only sleep; their
    owning application's foreground loop is responsible for pumping events.
    """
    process = getattr(fire, "process_events", None)
    if process is None or threading.current_thread() is not threading.main_thread():
        time.sleep(seconds)
        return
    deadline = time.monotonic() + seconds
    while True:
        if not process():
            raise KeyboardInterrupt
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.01))


def close_controller(fire):
    """Clear LEDs, but always release the connection if the device disconnected."""
    try:
        fire.clear_all()
    finally:
        fire.close()
