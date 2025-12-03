# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

#### Circuit Sequencer Example
- **E2E Visual Demo** (`demo_e2e.py`) - Automated visual testing with DemoRunner class
- **Pygame Smoke Test** (`test_pygame_smoke.py`) - Quick 3-second GUI verification
- **Comprehensive Core Tests** - Pattern, Step, Sequencer, Track test coverage
- **Settings Mode** - Full settings menu with BPM, swing, quantization, MIDI config
- **Pattern Mode Improvements** - Pattern chain editing, copy/paste/clear operations
- **Enhanced Pattern System** - PlayOrder (forward/reverse/ping-pong/random), SyncRate
- **SOLO Button Track Selection** - Use SOLO_1-4 buttons instead of pads for track selection
- **Track LED Display** - Visual feedback for selected track via track LEDs

#### Mock GUI (Pygame)
- **Larger Window** - Increased from 900x350 to 1100x500 pixels
- **2x OLED Scaling** - 256x128 display for better visibility
- **Repositioned Elements** - OLED above pads, buttons without overlap
- **Improved API Compatibility** - Better match with real AkaiFire interface

#### Testing Infrastructure
- Testing utilities module (`akai_fire_testing.py`)
- Comprehensive test suite for Canvas and ScreenManager
- Mock MIDI ports for hardware-free testing

### Changed
- Refactored examples to use context managers
- Applied black formatting across codebase
- Improved error handling with specific exception types

### Fixed
- MockAkaiFire API compatibility issues
- Button listener registration after decorator changes
- Import issues in examples

---

## [0.2.0] - 2024-09-01

### Added
- **Screen Manager System** - High-level screen management with pre-built screen types
  - TextScreen, MenuScreen, ProgressScreen, GridScreen, ValueScreen
  - Screen transitions and lifecycle management
- **Enhanced Canvas API** - New drawing methods and typography constants
- **Mock GUI (Pygame)** - Full visual simulation for development without hardware
- **Groovebox Example** - Complete sequencer application with views and state machines

### Changed
- Architecture refactoring for better separation of concerns
- API standardization across modules

---

## [0.1.0] - 2024-08-01

### Added
- **AkaiFire Class** - Main interface to MIDI controller
  - Pad colors (64 RGB pads)
  - Button LEDs
  - OLED screen updates via Canvas
  - Event decorators (`@fire.on_pad()`, `@fire.on_button()`, `@fire.on_rotary_turn()`)
- **Canvas Class** - 128x64 monochrome screen abstraction
  - Drawing primitives (pixels, lines, rectangles, circles, text)
  - BMP export for development
- **Basic Examples** - Hello world, pad colors, button handling
- **MIDI Communication** - rtmidi integration for hardware control
