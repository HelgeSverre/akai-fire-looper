# Architecture

This document provides a deep-dive into the AKAI Fire library architecture.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  (Examples: Circuit Sequencer, Groovebox, Custom Apps)       │
├─────────────────────────────────────────────────────────────┤
│                    Framework Layer                           │
│  AkaiFireApp, ModeManager, ScreenMixin, GridMixin           │
├─────────────────────────────────────────────────────────────┤
│                       Core Library                           │
│  AkaiFire, Canvas, ScreenManager, MockAkaiFire              │
├─────────────────────────────────────────────────────────────┤
│                     Hardware/MIDI Layer                      │
│  python-rtmidi, pygame (mock)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### AkaiFire (`akai_fire/hardware.py`)

The main interface to the AKAI Fire MIDI controller.

**Responsibilities:**
- MIDI port discovery and connection
- Pad color control (64 RGB pads)
- Button LED control
- Track LED control
- Control bank LED control
- OLED screen updates via Canvas
- Event registration (decorators and listeners)

**Key Methods:**
```python
# Pad control
set_pad_color(index, r, g, b)
set_multiple_pad_colors([(index, r, g, b), ...])
clear_all_pads()

# Button/LED control
set_button_led(button_id, value)
set_track_led(track_number, value)
set_control_bank_leds(state)

# Screen
get_canvas() -> Canvas
render_to_display()

# Events (decorators)
@fire.on_pad(pad_index=None)
@fire.on_button(button_id=None)
@fire.on_rotary_turn(rotary_id=None)
```

### Canvas (`akai_fire/canvas.py`)

128x64 monochrome OLED display abstraction.

**Drawing Primitives:**
```python
clear(color=1)
set_pixel(x, y, color=0)
draw_line(x0, y0, x1, y1)
draw_rect(x, y, width, height)
fill_rect(x, y, width, height)
draw_circle(x0, y0, radius)
fill_circle(x0, y0, radius)
draw_text(text, x, y, font=None)
```

**Typography Constants:**
```python
HEADER_HEIGHT = 16
TEXT_MARGIN_Y = 3
CONTENT_GAP = 2
CONTENT_START = 18  # HEADER_HEIGHT + CONTENT_GAP
```

### MockAkaiFire (`mock_gui_pygame.py`)

Pygame-based hardware simulator with identical API to AkaiFire.

**Features:**
- Visual simulation of all 64 pads
- Button click handling
- Encoder drag simulation
- OLED display rendering (2x scaled)
- Event system compatible with real hardware

**Auto-detection:**
```python
from akai_fire import get_akai_fire

# Returns MockAkaiFire if hardware unavailable
fire = get_akai_fire()
```

### ScreenManager (`screen_manager.py`)

High-level screen management with pre-built screen types.

**Screen Types:**
- `TextScreen` - Simple text display
- `MenuScreen` - Scrollable menu with selection
- `ProgressScreen` - Progress bar visualization
- `GridScreen` - Grid-based information display
- `ValueScreen` - Value with bar visualization

---

## Event System

### Decorator Pattern
```python
@fire.on_pad()
def handle_all_pads(pad, velocity):
    print(f"Pad {pad} pressed")

@fire.on_pad(pad_index=0)
def handle_pad_zero(velocity):
    print(f"Pad 0 pressed with velocity {velocity}")

@fire.on_button(fire.BUTTON_PLAY)
def handle_play(event):
    if event == "press":
        start_playback()
```

### Listener Pattern
```python
fire.add_listener([0, 1, 2], callback)
fire.add_button_listener(fire.BUTTON_PLAY, callback)
fire.add_rotary_listener(fire.ROTARY_VOLUME, callback)
```

---

## Circuit Example Architecture

The Circuit Tracks sequencer demonstrates best practices for complex apps.

### Layer Diagram
```
CircuitSequencer (main.py)
├── Core Engine
│   ├── Sequencer         - 4-track MIDI sequencing
│   ├── TimingEngine      - BPM, swing, quantization
│   ├── MidiManager       - MIDI I/O
│   └── Track/Pattern     - Data structures
│
└── UI Layer
    ├── ScreenManager     - OLED rendering
    ├── GridManager       - Pad visualization
    └── ModeManager       - Mode dispatch
        └── Mode Handlers
            ├── NoteMode      - Scale keyboard
            ├── MixerMode     - Track mixing
            ├── PatternMode   - Pattern chains
            ├── StepEditMode  - Step editing
            └── SettingsMode  - Configuration
```

### Mode Handler Pattern

All modes implement a common interface:

```python
class ModeHandler(ABC):
    @abstractmethod
    def handle_pad_press(self, pad, velocity) -> bool: pass

    @abstractmethod
    def handle_encoder_turn(self, encoder, direction, velocity): pass

    @abstractmethod
    def handle_button_press(self, button) -> bool: pass

    @abstractmethod
    def get_display_info(self) -> Dict[str, Any]: pass

    def on_enter(self, previous_mode): pass
    def on_exit(self): pass
```

### State Management

**Three-tier architecture:**

1. **Core State** (Sequencer) - Source of truth
   - `sequencer.current_track`
   - `sequencer.transport_state`
   - `track.patterns[]`

2. **Mode State** (per-mode)
   - `mode_manager.mode_state[mode]`
   - Transient selections, edit parameters

3. **Display State** (for rendering)
   - Cached values for animation
   - Current pad colors

---

## Grid Layout

The 4x16 pad grid uses consistent row assignments:

```
Row 0: STEP_ROW        - 16-step sequencer
Row 1: TRACK_PATTERN   - Track/pattern selection
Row 2: INPUT_ROW_1     - Keyboard/input (upper)
Row 3: INPUT_ROW_2     - Keyboard/input (lower)
```

**Coordinate Conversion:**
```python
# Index to position
row = pad_index // 16
col = pad_index % 16

# Position to index
index = row * 16 + col
```

---

## Button Constants

```python
# Transport
BUTTON_PLAY = 0x33
BUTTON_STOP = 0x34
BUTTON_REC = 0x35

# Mode switching
BUTTON_STEP = 0x2C
BUTTON_NOTE = 0x2D
BUTTON_DRUM = 0x2E
BUTTON_PERFORM = 0x2F

# Navigation
BUTTON_GRID_LEFT = 0x22
BUTTON_GRID_RIGHT = 0x23
BUTTON_PAT_UP = 0x1F
BUTTON_PAT_DOWN = 0x20

# Solo/Track
BUTTON_SOLO_1 = 0x24
BUTTON_SOLO_2 = 0x25
BUTTON_SOLO_3 = 0x26
BUTTON_SOLO_4 = 0x27

# Encoders
ROTARY_VOLUME = 0x10
ROTARY_PAN = 0x11
ROTARY_FILTER = 0x12
ROTARY_RESONANCE = 0x13
ROTARY_SELECT = 0x76
```

---

## File Structure

```
akai-fire-looper/
├── akai_fire/             # Core library package
│   ├── constants.py       # Authoritative MIDI constants
│   ├── errors.py          # Exception hierarchy
│   ├── canvas.py          # OLED canvas abstraction (128x64)
│   ├── device.py          # AkaiFireDevice base (dispatch, listeners)
│   ├── hardware.py        # AkaiFire (rtmidi I/O, SysEx, polling)
│   └── __init__.py        # Lazy public re-exports
├── akai_fire_framework/   # App framework (app, grid, mode, screen, transport)
├── akai_fire_testing/     # Headless testing mocks + assertions
│
├── mock_gui_pygame.py     # Interactive pygame mock (dev convenience)
├── mock_gui_tui.py        # Terminal-UI mock (rich)
├── screen_manager.py      # High-level screen management
├── animation_utils.py     # Animation helpers for examples
│
├── examples/
│   ├── circuit/           # Circuit Tracks sequencer
│   │   ├── main.py        # App entry point
│   │   ├── core/          # Sequencer engine
│   │   └── ui/            # UI components
│   ├── groovebox/         # Groovebox example
│   └── *.py               # Basic examples
│
├── tests/                 # Test suite (unittest)
│   ├── test_akai_fire.py      # Hardware impl + dispatch/threading
│   ├── test_sysex_encoder.py  # OLED encoder golden vectors
│   ├── test_device_contract.py# Cross-implementation parity
│   ├── test_canvas.py
│   └── ...
│
└── docs/                  # Documentation
    ├── ARCHITECTURE.md    # This file
    ├── CHANGELOG.md
    └── ROADMAP.md
```
