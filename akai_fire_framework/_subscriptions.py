"""Private ownership of framework event registration, rollback and teardown."""

import threading


class _EventSubscriptions:
    def __init__(self):
        self._removers = []
        self._closed = False
        self._lock = threading.RLock()

    def bind_all(self, bindings):
        """Register (decorator, remover, callback) triples as one rollback batch."""
        with self._lock:
            start = len(self._removers)
            try:
                for register, remove, callback in bindings:
                    if self._closed:
                        raise RuntimeError("Event subscriptions have closed")
                    self._bind(register, remove, callback)
            except Exception:
                self._remove_since(start)
                raise

    def _bind(self, register, remove, callback):
        active = True

        def handler(*args):
            if active:
                callback(*args)

        def unsubscribe():
            nonlocal active
            active = False
            remove(handler)

        # Device decorators append before starting input, which can raise.
        self._removers.append(unsubscribe)
        register(handler)

    def _remove_since(self, start):
        removers = self._removers[start:]
        del self._removers[start:]
        error = None
        for remove in reversed(removers):
            try:
                remove()
            except Exception as exc:  # noqa: BLE001 - fence every handler before raising
                if error is None:
                    error = exc
        if error is not None:
            raise error

    def close(self):
        with self._lock:
            self._closed = True
            self._remove_since(0)
