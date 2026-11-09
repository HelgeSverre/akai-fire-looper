"""Turn to navigate, press to edit, and press again to finish editing."""

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    """An editable value, an action, or a read-only label.

    ``adjust`` receives a signed encoder delta; the application owns the value,
    its bounds and persistence. ``activate`` runs when an action is pressed.
    """

    label: str
    adjust: Callable[[int], None] | None = None
    activate: Callable[[], None] | None = None

    def __post_init__(self):
        if self.adjust is not None and self.activate is not None:
            raise ValueError(
                "A menu item cannot be both an editable value and an action"
            )


class EncoderMenu:
    """Navigation/edit state independent of MIDI routing and screen drawing.

    Values change live while editing; finishing an edit does not roll them back.
    Input methods serialize state changes and run callbacks on the calling
    thread. Applications render ``selected_index`` and ``editing`` themselves.
    """

    def __init__(self, items: Sequence[MenuItem], *, wrap: bool = False):
        if not items:
            raise ValueError("A menu needs at least one item")
        self.items = tuple(items)
        self.wrap = wrap
        self._selected_index = 0
        self._editing = False
        self._lock = threading.RLock()

    @property
    def selected_index(self) -> int:
        with self._lock:
            return self._selected_index

    @property
    def editing(self) -> bool:
        with self._lock:
            return self._editing

    def select(self, index: int, *, keep_editing: bool = False) -> None:
        """Select directly; optionally carry an active edit to an editable item."""
        if not 0 <= index < len(self.items):
            raise IndexError(index)
        with self._lock:
            self._selected_index = index
            self._editing = (
                self._editing and keep_editing and self.items[index].adjust is not None
            )

    def move(self, delta: int, *, keep_editing: bool = False) -> None:
        """Navigate, optionally keeping an active edit on another editable item."""
        with self._lock:
            index = self._selected_index + delta
            index = (
                index % len(self.items)
                if self.wrap
                else max(0, min(len(self.items) - 1, index))
            )
            self.select(index, keep_editing=keep_editing)

    def turn(self, delta: int) -> None:
        """Navigate normally, or adjust the selected value while editing."""
        with self._lock:
            if not delta:
                return
            if self._editing:
                self.items[self._selected_index].adjust(delta)
            else:
                self.move(delta)

    def press(self) -> None:
        """Enter/finish editing, or execute the selected action."""
        with self._lock:
            item = self.items[self._selected_index]
            if self._editing:
                self._editing = False
            elif item.adjust is not None:
                self._editing = True
            elif item.activate is not None:
                item.activate()

    def finish_editing(self) -> None:
        """Leave edit mode, for example when closing a settings screen."""
        with self._lock:
            self._editing = False
