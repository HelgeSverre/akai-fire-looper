"""Instance-bound input declarations and foreground event delivery."""

from collections import deque
from dataclasses import dataclass
from inspect import isfunction, signature
from threading import RLock
from typing import Literal

from akai_fire.constants import (
    ROTARY_FILTER,
    ROTARY_PAN,
    ROTARY_RESONANCE,
    ROTARY_SELECT,
    ROTARY_VOLUME,
)


@dataclass(frozen=True)
class PadEvent:
    pad: int
    velocity: int
    shift: bool = False
    alt: bool = False


@dataclass(frozen=True)
class ButtonEvent:
    button: int
    action: Literal["press", "release"]
    shift: bool = False
    alt: bool = False


@dataclass(frozen=True)
class EncoderEvent:
    encoder: int
    delta: int
    shift: bool = False
    alt: bool = False


@dataclass(frozen=True)
class _Binding:
    event_type: type
    controls: frozenset[int] | None
    action: str | None = None
    shift: bool | None = None
    alt: bool | None = None

    def matches(self, event):
        if not isinstance(event, self.event_type):
            return False
        control = (
            event.pad
            if isinstance(event, PadEvent)
            else event.button
            if isinstance(event, ButtonEvent)
            else event.encoder
        )
        return (
            (self.controls is None or control in self.controls)
            and (self.action is None or event.action == self.action)
            and (self.shift is None or event.shift == self.shift)
            and (self.alt is None or event.alt == self.alt)
        )


def _declare(event_type, controls, valid, *, action=None, shift=None, alt=None):
    if controls is not None:
        controls = (controls,) if isinstance(controls, int) else tuple(controls)
        if not controls or any(type(c) is not int or c not in valid for c in controls):
            raise ValueError("Invalid input control")
        controls = frozenset(controls)
    if any(value is not None and type(value) is not bool for value in (shift, alt)):
        raise ValueError("Modifier filters must be True, False or None")
    binding = _Binding(event_type, controls, action, shift, alt)

    def decorate(method):
        if not isfunction(method):
            raise TypeError("App input decorators require an instance method")
        method.__fire_bindings__ = (*getattr(method, "__fire_bindings__", ()), binding)
        return method

    return decorate


class _On:
    def pad(self, pads=None, *, shift=None, alt=None):
        """Handle presses on all pads, one index, or an iterable of indices."""
        return _declare(PadEvent, pads, range(64), shift=shift, alt=alt)

    def button(self, buttons=None, *, action="press", shift=None, alt=None):
        """Handle press (default), release, or both (`action=None`)."""
        if action not in ("press", "release", None):
            raise ValueError("Button action must be press, release or None")
        return _declare(
            ButtonEvent, buttons, range(128), action=action, shift=shift, alt=alt
        )

    def encoder(self, encoders=None, *, shift=None, alt=None):
        """Handle signed encoder deltas; clockwise is positive."""
        return _declare(
            EncoderEvent,
            encoders,
            (ROTARY_VOLUME, ROTARY_PAN, ROTARY_FILTER, ROTARY_RESONANCE, ROTARY_SELECT),
            shift=shift,
            alt=alt,
        )


on = _On()


class _InputRouter:
    """Own queued calls, instance binding, overflow and terminal fencing."""

    def __init__(self, app, capacity):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("INPUT_QUEUE_SIZE must be a positive integer")
        self._handlers = []
        seen = set()
        for cls in type(app).__mro__:
            for name, method in vars(cls).items():
                if name in seen:
                    continue
                seen.add(name)
                if isinstance(method, (staticmethod, classmethod)) and getattr(
                    method.__func__, "__fire_bindings__", ()
                ):
                    raise TypeError("App input decorators require an instance method")
                bindings = getattr(method, "__fire_bindings__", ())
                if bindings:
                    bound = getattr(app, name)
                    signature(bound).bind(object())
                    self._handlers.append((bindings, bound))
        self._capacity = capacity
        self._queue = deque()
        self._lock = RLock()
        self._dispatch_lock = RLock()
        self._closed = False
        self._overflow = False

    def enqueue(self, event):
        with self._lock:
            if self._closed or self._overflow:
                return
            if not any(
                b.matches(event) for bindings, _ in self._handlers for b in bindings
            ):
                return
            if len(self._queue) == self._capacity:
                self._overflow = True
                return
            self._queue.append(event)

    def drain(self, limit, stopped):
        # Fence teardown against active handlers without holding the queue lock
        # during user code: MIDI callbacks must remain free to enqueue.
        with self._dispatch_lock:
            with self._lock:
                if self._overflow and not self._closed:
                    raise RuntimeError(
                        "App input queue overflow; increase INPUT_QUEUE_SIZE or reduce handler work"
                    )
                count = min(limit, len(self._queue))
            for _ in range(count):
                with self._lock:
                    if self._closed or stopped():
                        break
                    event = self._queue.popleft()
                for bindings, method in self._handlers:
                    if self._closed or stopped():
                        break
                    if any(b.matches(event) for b in bindings):
                        method(event)

    def close(self):
        with self._dispatch_lock, self._lock:
            self._closed = True
            self._queue.clear()
            self._handlers.clear()
