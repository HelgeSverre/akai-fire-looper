"""Authoritative MIDI constants for the AKAI Fire.

Every AkaiFire implementation (real hardware, pygame mock, TUI mock,
headless testing mock) inherits these values — do NOT redefine them
locally. If you need to change a value, change it here.

Historical note: prior to this module's introduction, each class
copy-pasted the constants independently. ``CONTROL_BANK_USER2`` in
particular had silently drifted between implementations — 0x03 on real
hardware + testing mock, 0x18 in pygame + TUI mocks — because the
latter two computed it via ``FIELD_BASE | FIELD_USER2`` rather than the
hard-coded hardware value. The ``# Note: Real uses 0x03 (different
from pattern)`` comment in the testing mock caught this once; the
others didn't.
"""

from typing import Dict

# --- MIDI message types ---
NOTE_ON = 0x90
NOTE_OFF = 0x80
CC = 0xB0

# --- Pad grid dimensions ---
PAD_COUNT = 64
PAD_NOTE_BASE = 54  # pad index 0 is note 54; pad index N is note (54 + N)

# --- Rotary encoder controller IDs ---
ROTARY_VOLUME = 0x10
ROTARY_PAN = 0x11
ROTARY_FILTER = 0x12
ROTARY_RESONANCE = 0x13
ROTARY_SELECT = 0x76

# --- Button IDs ---
BUTTON_SELECT = 0x19
BUTTON_STEP = 0x2C
BUTTON_NOTE = 0x2D
BUTTON_DRUM = 0x2E
BUTTON_PERFORM = 0x2F
BUTTON_SHIFT = 0x30
BUTTON_ALT = 0x31
BUTTON_PATTERN = 0x32
BUTTON_PLAY = 0x33
BUTTON_STOP = 0x34
BUTTON_REC = 0x35
BUTTON_BANK = 0x1A
BUTTON_BROWSER = 0x21
BUTTON_SOLO_1 = 0x24
BUTTON_SOLO_2 = 0x25
BUTTON_SOLO_3 = 0x26
BUTTON_SOLO_4 = 0x27
BUTTON_PAT_UP = 0x1F
BUTTON_PAT_DOWN = 0x20
BUTTON_GRID_LEFT = 0x22
BUTTON_GRID_RIGHT = 0x23

# --- Solo index (1..4) -> button ID ---
SOLO_BUTTONS: Dict[int, int] = {
    1: BUTTON_SOLO_1,
    2: BUTTON_SOLO_2,
    3: BUTTON_SOLO_3,
    4: BUTTON_SOLO_4,
}

# --- Buttons with an addressable LED (accepted by set_button_led) ---
BUTTON_LED_IDS = frozenset(
    {
        BUTTON_SELECT,
        BUTTON_STEP,
        BUTTON_NOTE,
        BUTTON_DRUM,
        BUTTON_PERFORM,
        BUTTON_SHIFT,
        BUTTON_ALT,
        BUTTON_PATTERN,
        BUTTON_PLAY,
        BUTTON_STOP,
        BUTTON_REC,
        BUTTON_BANK,
        BUTTON_BROWSER,
        BUTTON_SOLO_1,
        BUTTON_SOLO_2,
        BUTTON_SOLO_3,
        BUTTON_SOLO_4,
        BUTTON_PAT_UP,
        BUTTON_PAT_DOWN,
        BUTTON_GRID_LEFT,
        BUTTON_GRID_RIGHT,
    }
)

# --- Button LED values ---
LED_OFF = 0x00
LED_DULL_RED = 0x01
LED_HIGH_RED = 0x02
LED_DULL_GREEN = 0x01
LED_HIGH_GREEN = 0x02
LED_DULL_YELLOW = 0x01
LED_HIGH_YELLOW = 0x02

# --- Rectangle (track) LED values ---
RECTANGLE_LED_OFF = 0x00
RECTANGLE_LED_DULL_RED = 0x01
RECTANGLE_LED_DULL_GREEN = 0x02
RECTANGLE_LED_HIGH_RED = 0x03
RECTANGLE_LED_HIGH_GREEN = 0x04

# --- Control bank fields (bit flags; FIELD_BASE must be set) ---
FIELD_BASE = 0x10
FIELD_CHANNEL = 0x01
FIELD_MIXER = 0x02
FIELD_USER1 = 0x04
FIELD_USER2 = 0x08

# --- Control bank LED state values ---
# Most follow the FIELD_BASE|FIELD_* bit-mask pattern; CONTROL_BANK_USER2 is
# the documented exception (hardware sends 0x03, NOT FIELD_BASE|FIELD_USER2).
CONTROL_BANK_ALL_OFF = 0x10
CONTROL_BANK_ALL_ON = 0x1F
CONTROL_BANK_CHANNEL = 0x11
CONTROL_BANK_CHANNEL_AND_MIXER = 0x13
CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER1 = 0x17
CONTROL_BANK_CHANNEL_AND_MIXER_AND_USER2 = 0x1B
CONTROL_BANK_CHANNEL_AND_USER1 = 0x15
CONTROL_BANK_CHANNEL_AND_USER1_AND_USER2 = 0x1D
CONTROL_BANK_CHANNEL_AND_USER2 = 0x19
CONTROL_BANK_MIXER = 0x12
CONTROL_BANK_MIXER_AND_USER1_AND_USER2 = 0x1E
CONTROL_BANK_MIXER_AND_USER2 = 0x1A
CONTROL_BANK_USER1 = 0x14
CONTROL_BANK_USER1_AND_USER2 = 0x1C
CONTROL_BANK_USER2 = 0x03  # hardware-specific value; NOT FIELD_BASE|FIELD_USER2


def install(cls):
    """Class decorator: install all UPPER_CASE constants onto ``cls``.

    Used by mock implementations to get the authoritative constants as
    class attributes (so ``mock.BUTTON_PLAY`` still works) without
    redefining their values locally. Every implementation — the real
    :class:`AkaiFire` included — gets its constants through this
    decorator via :class:`akai_fire.device.AkaiFireDevice`.
    """
    import sys

    module = sys.modules[__name__]
    for name in dir(module):
        if name.isupper() and not name.startswith("_"):
            setattr(cls, name, getattr(module, name))
    return cls
