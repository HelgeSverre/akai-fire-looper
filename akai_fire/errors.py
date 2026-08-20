"""Exception classes for the AKAI Fire library.

Separate module so they can be imported without pulling in rtmidi or PIL.
"""


class AkaiFireError(Exception):
    """Base exception for AKAI Fire library."""

    pass


class MIDIConnectionError(AkaiFireError):
    """Raised when MIDI connection fails."""

    pass


class MIDISendError(AkaiFireError):
    """Raised when sending MIDI message fails."""

    pass


class InvalidParameterError(AkaiFireError):
    """Raised when invalid parameters are provided."""

    pass


class HardwareError(AkaiFireError):
    """Raised when hardware communication fails."""

    pass


class StateError(AkaiFireError):
    """Raised when operation is invalid for current state."""

    pass
