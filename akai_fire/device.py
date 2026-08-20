"""Abstract base class for AKAI Fire implementations.

Four implementations share this base: the real hardware (:class:`AkaiFire`),
the interactive pygame mock, the terminal-UI mock, and the headless
testing mock. All inherit MIDI constants via the ``@install_constants``
decorator and share state for modifier keys + a lock for registry guarding.

Later commits extend the base with the shared listener registries,
decorators, and dispatch helpers. For now it owns the utilities that
never needed duplicating in the first place — pad geometry, solo-button
lookup, modifier state, and the ``list_midi_ports()`` stub.
"""

from __future__ import annotations

import abc
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from akai_fire.constants import install as _install_constants

logger = logging.getLogger(__name__)


@_install_constants
class AkaiFireDevice(abc.ABC):
    """Shared base for every AKAI Fire implementation.

    MIDI constants (``BUTTON_*``, ``ROTARY_*``, ``LED_*``, ``FIELD_*``,
    ``CONTROL_BANK_*``, ``SOLO_BUTTONS``, ``NOTE_ON``/``NOTE_OFF``/``CC``,
    ``PAD_COUNT``, ``PAD_NOTE_BASE``) are installed from
    :mod:`akai_fire.constants` at class-definition time. Subclasses
    inherit them automatically — do not redefine.

    Subclasses MUST call ``super().__init__()`` to set up ``_lock`` and
    the modifier flags.
    """

    def __init__(self) -> None:
        # Guards the listener registries + modifier state. Held only
        # during the snapshot portion of dispatch; never while a user
        # handler is executing.
        self._lock = threading.RLock()

        # Modifier latch state. Updated inline during button dispatch so
        # any pad/button/rotary handler sees coherent state for the
        # SAME event.
        self._shift_pressed: bool = False
        self._alt_pressed: bool = False

        # Listener registries. The ``"global"`` key reserves a slot for
        # handlers registered without a specific id (the decorator
        # variants ``on_pad()`` / ``on_button()`` / etc).
        self.pad_listeners: Dict[Any, List[Callable]] = defaultdict(list)
        self.button_listeners: Dict[Any, List[Callable]] = defaultdict(list)
        self.rotary_listeners: Dict[Any, List[Callable]] = defaultdict(list)
        self.rotary_touch_listeners: Dict[Any, List[Callable]] = defaultdict(list)

        # Handler dispatcher (real AkaiFire constructs a
        # ``_HandlerDispatcher`` here; mocks leave it ``None`` so
        # handlers run inline on the thread that decoded the event).
        self._dispatcher: Optional[Any] = None

    # --------------------------------------------------------------
    # OLED / canvas — authored once; ``render_to_display(canvas=None)``
    # signature lives here, so it cannot drift again. Subclasses
    # implement :meth:`_deliver_display` and :meth:`new_canvas`.
    # --------------------------------------------------------------

    @abc.abstractmethod
    def _deliver_display(self, canvas) -> None:
        """Render the given canvas to the OLED / display surface.

        Real hardware encodes the bitmap as SysEx; mocks mark their
        render-state dirty or record a draw operation.
        """

    @abc.abstractmethod
    def new_canvas(self):
        """Replace ``self.canvas`` with a fresh instance and return it.

        Each subclass knows what kind of canvas it wants (real
        :class:`Canvas`, :class:`PygameCanvas`, headless
        :class:`MockCanvas`).
        """

    def get_canvas(self):
        """Return the current canvas (``self.canvas`` by convention)."""
        return self.canvas

    def render_to_display(self, canvas=None) -> None:
        """Push ``canvas`` (or the current internal one) to the display.

        Authored once on the base so the ``canvas=None`` signature is
        structural — subclasses cannot drift from it.
        """
        if canvas is not None:
            self.canvas = canvas
        self._deliver_display(self.canvas)

    def render_to_bmp(self, filename: str, image_format: str = "BMP") -> None:
        """Save the current canvas to an image file."""
        self.canvas.image.save(filename, image_format)

    def clear_display(self) -> None:
        """Clear the OLED / display canvas."""
        if getattr(self, "canvas", None) is not None:
            self.canvas.clear()
            self._deliver_display(self.canvas)

    # --------------------------------------------------------------
    # Lifecycle — default no-ops (AkaiFire overrides start_listening)
    # --------------------------------------------------------------

    def start_listening(self) -> None:
        """Start the input loop.

        No-op on mocks; the real :class:`AkaiFire` overrides this to
        spawn the MIDI polling thread. Decorators call it so users don't
        have to remember to start listening.
        """

    # --------------------------------------------------------------
    # Handler dispatch — the seam concrete implementations call into
    # --------------------------------------------------------------

    def _invoke(self, handler: Callable, *args: Any) -> None:
        """Dispatch a user handler with per-handler exception isolation.

        If ``self._dispatcher`` is set (real AkaiFire with async handlers
        enabled), submit to the thread pool; otherwise run inline. A
        raised exception is logged but never prevents sibling handlers
        from running.
        """
        if self._dispatcher is not None:
            self._dispatcher.submit(handler, *args)
            return
        try:
            handler(*args)
        except Exception:
            logger.exception("Handler %r raised", handler)

    def _dispatch_pad(self, pad_index: int, velocity: int) -> None:
        with self._lock:
            specific = list(self.pad_listeners[pad_index])
            globals_ = list(self.pad_listeners["global"])
        for h in specific:
            self._invoke(h, velocity)
        for h in globals_:
            self._invoke(h, pad_index, velocity)

    def _dispatch_button(self, button_id: int, event: str) -> None:
        """Dispatch a button press/release, latching modifiers first.

        The modifier-first invariant lives here — ``_shift_pressed`` /
        ``_alt_pressed`` are updated *before* any handler runs, so a
        pad handler that reads :meth:`is_shift_pressed` observes a
        coherent value for the same event.
        """
        if button_id == self.BUTTON_SHIFT:
            self._shift_pressed = event == "press"
        elif button_id == self.BUTTON_ALT:
            self._alt_pressed = event == "press"

        with self._lock:
            specific = list(self.button_listeners[button_id])
            globals_ = list(self.button_listeners["global"])
        for h in specific:
            self._invoke(h, event)
        for h in globals_:
            self._invoke(h, button_id, event)

    def _dispatch_rotary_turn(
        self, rotary_id: int, direction: str, velocity: int
    ) -> None:
        with self._lock:
            specific = list(self.rotary_listeners[rotary_id])
            globals_ = list(self.rotary_listeners["global"])
        for h in specific:
            self._invoke(h, direction, velocity)
        for h in globals_:
            self._invoke(h, rotary_id, direction, velocity)

    def _dispatch_rotary_touch(self, rotary_id: int, event: str) -> None:
        with self._lock:
            specific = list(self.rotary_touch_listeners[rotary_id])
            globals_ = list(self.rotary_touch_listeners["global"])
        for h in specific:
            self._invoke(h, event)
        for h in globals_:
            self._invoke(h, rotary_id, event)

    # --------------------------------------------------------------
    # Decorators
    # --------------------------------------------------------------

    def on_pad(self, pad_index: Any = None):
        """Register a pad handler.

        ``pad_index=None`` → global pad handler (receives
        ``(pad_index, velocity)``). An ``int`` registers for a single
        pad (receives ``(velocity,)``). A ``list``/``tuple`` of ints
        registers the same handler for each pad (receives
        ``(pad_index, velocity)``).
        """

        def decorator(func):
            with self._lock:
                if pad_index is None:
                    self.pad_listeners["global"].append(func)
                elif isinstance(pad_index, (list, tuple)):
                    for idx in pad_index:
                        if not (0 <= idx <= 63):
                            raise ValueError("Pad index must be between 0 and 63")
                        self.pad_listeners[idx].append(func)
                else:
                    if not (0 <= pad_index <= 63):
                        raise ValueError("Pad index must be between 0 and 63")
                    self.pad_listeners[pad_index].append(func)
            self.start_listening()
            return func

        return decorator

    def on_button(self, button_id: Optional[int] = None):
        """Register a button handler. ``button_id=None`` → global."""

        def decorator(func):
            with self._lock:
                key = "global" if button_id is None else button_id
                self.button_listeners[key].append(func)
            self.start_listening()
            return func

        return decorator

    def on_rotary_turn(self, rotary_id: Optional[int] = None):
        """Register a rotary-turn handler. ``rotary_id=None`` → global."""
        valid_ids = (
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
            self.ROTARY_SELECT,
        )

        def decorator(func):
            with self._lock:
                if rotary_id is None:
                    self.rotary_listeners["global"].append(func)
                else:
                    if rotary_id not in valid_ids:
                        raise ValueError("Invalid rotary ID")
                    self.rotary_listeners[rotary_id].append(func)
            self.start_listening()
            return func

        return decorator

    def on_rotary_touch(self, rotary_id: Optional[int] = None):
        """Register a rotary-touch handler. ``rotary_id=None`` → global.

        Note: ``ROTARY_SELECT`` has no touch event on real hardware.
        """
        valid_ids = (
            self.ROTARY_VOLUME,
            self.ROTARY_PAN,
            self.ROTARY_FILTER,
            self.ROTARY_RESONANCE,
        )

        def decorator(func):
            with self._lock:
                if rotary_id is None:
                    self.rotary_touch_listeners["global"].append(func)
                else:
                    if rotary_id not in valid_ids:
                        raise ValueError("Invalid rotary ID")
                    self.rotary_touch_listeners[rotary_id].append(func)
            self.start_listening()
            return func

        return decorator

    def on_solo(self, index: Optional[int] = None):
        """Register a solo-button handler. ``index`` is 1..4 or None."""

        def decorator(func):
            with self._lock:
                if index is None:
                    # Wrap so the user's handler gets (index, event) not (button_id, event).
                    def wrapper(button_id, event):
                        if button_id in self.SOLO_BUTTONS.values():
                            solo_index = self.get_solo_index(button_id)
                            if solo_index is not None:
                                func(solo_index, event)

                    self.button_listeners["global"].append(wrapper)
                else:
                    if not isinstance(index, int) or index not in self.SOLO_BUTTONS:
                        raise ValueError("Solo button index must be 1-4")
                    button_id = self.SOLO_BUTTONS[index]
                    self.button_listeners[button_id].append(func)
            self.start_listening()
            return func

        return decorator

    # --------------------------------------------------------------
    # Non-decorator listener adders
    # --------------------------------------------------------------

    def add_listener(self, pad_indices: Any, callback: Callable) -> None:
        with self._lock:
            if isinstance(pad_indices, (list, tuple)):
                for idx in pad_indices:
                    if not (0 <= idx <= 63):
                        raise ValueError("Pad index must be between 0 and 63")
                    self.pad_listeners[idx].append(callback)
            else:
                if not (0 <= pad_indices <= 63):
                    raise ValueError("Pad index must be between 0 and 63")
                self.pad_listeners[pad_indices].append(callback)
        self.start_listening()

    def add_global_listener(self, callback: Callable) -> None:
        with self._lock:
            self.pad_listeners["global"].append(callback)
        self.start_listening()

    def add_button_listener(self, button_id: int, callback: Callable) -> None:
        with self._lock:
            self.button_listeners[button_id].append(callback)
        self.start_listening()

    def add_rotary_listener(self, rotary_id: int, callback: Callable) -> None:
        with self._lock:
            self.rotary_listeners[rotary_id].append(callback)
        self.start_listening()

    def add_rotary_touch_listener(self, rotary_id: int, callback: Callable) -> None:
        with self._lock:
            self.rotary_touch_listeners[rotary_id].append(callback)
        self.start_listening()

    # --------------------------------------------------------------
    # Listener removal — safe to call from inside a handler; the
    # change takes effect on the next event (dispatch works on a
    # snapshot taken under the lock).
    # --------------------------------------------------------------

    def remove_listener(self, pad_indices: Any, callback: Callable) -> None:
        """Remove a previously added pad listener (single index or list)."""
        indices = (
            pad_indices if isinstance(pad_indices, (list, tuple)) else [pad_indices]
        )
        with self._lock:
            for idx in indices:
                listeners = self.pad_listeners.get(idx)
                if listeners:
                    try:
                        listeners.remove(callback)
                    except ValueError:
                        pass

    def remove_global_listener(self, callback: Callable) -> None:
        """Remove a previously added global pad listener."""
        with self._lock:
            listeners = self.pad_listeners.get("global")
            if listeners:
                try:
                    listeners.remove(callback)
                except ValueError:
                    pass

    def remove_button_listener(self, button_id: int, callback: Callable) -> None:
        """Remove a previously added button listener."""
        with self._lock:
            listeners = self.button_listeners.get(button_id)
            if listeners:
                try:
                    listeners.remove(callback)
                except ValueError:
                    pass

    def remove_rotary_listener(self, rotary_id: int, callback: Callable) -> None:
        """Remove a previously added rotary-turn listener."""
        with self._lock:
            listeners = self.rotary_listeners.get(rotary_id)
            if listeners:
                try:
                    listeners.remove(callback)
                except ValueError:
                    pass

    def remove_rotary_touch_listener(self, rotary_id: int, callback: Callable) -> None:
        """Remove a previously added rotary-touch listener."""
        with self._lock:
            listeners = self.rotary_touch_listeners.get(rotary_id)
            if listeners:
                try:
                    listeners.remove(callback)
                except ValueError:
                    pass

    # --------------------------------------------------------------
    # Modifier-key state
    # --------------------------------------------------------------

    def is_shift_pressed(self) -> bool:
        """True while SHIFT is currently latched."""
        return self._shift_pressed

    def is_alt_pressed(self) -> bool:
        """True while ALT is currently latched."""
        return self._alt_pressed

    @property
    def shift_pressed(self) -> bool:
        return self._shift_pressed

    @property
    def alt_pressed(self) -> bool:
        return self._alt_pressed

    # --------------------------------------------------------------
    # Pad geometry utilities
    # --------------------------------------------------------------

    @staticmethod
    def pad_position(pad_index: int) -> Tuple[int, int]:
        """Return ``(row, column)`` 0-indexed for a pad index 0-63.

        Row is 0..3, column is 0..15. This matches the ``(row, col)``
        convention used by :class:`akai_fire_framework.grid.GridMixin`
        and the example apps.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return pad_index // 16, pad_index % 16

    @staticmethod
    def get_pad_column(pad_index: int) -> int:
        """Column number (1..16) for a pad index 0-63.

        One-indexed, matching the real hardware's documented coordinate
        system. ``pad_index`` is still 0-indexed.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index % 16) + 1

    @staticmethod
    def get_pad_row(pad_index: int) -> int:
        """Row number (1..4) for a pad index 0-63.

        One-indexed, matching the real hardware's documented coordinate
        system.
        """
        if not (0 <= pad_index <= 63):
            raise ValueError("Pad index must be between 0 and 63")
        return (pad_index // 16) + 1

    # --------------------------------------------------------------
    # Button utilities
    # --------------------------------------------------------------

    @classmethod
    def get_solo_index(cls, button_id: int) -> Optional[int]:
        """Convert a SOLO button ID to its 1..4 index, or None."""
        for index, bid in cls.SOLO_BUTTONS.items():
            if bid == button_id:
                return index
        return None

    # --------------------------------------------------------------
    # MIDI port listing — base returns empty; real AkaiFire overrides
    # --------------------------------------------------------------

    @staticmethod
    def list_midi_ports() -> Dict[str, List[str]]:
        """List available MIDI input/output ports.

        Base implementation returns empty lists (mocks don't have real
        ports). The hardware :class:`AkaiFire` subclass overrides this
        to enumerate ports via rtmidi.
        """
        return {"input": [], "output": []}
