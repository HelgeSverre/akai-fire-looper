# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- JT-4000 MICRO CC editor with parameter pages, OLED graphs, short auditions and validated local snapshots.
- MIDI Scope with input history, encoder traces, freeze/clear controls and CSV export.
- Snake with a shared 16×4 game model, pad/OLED views and Pattern/Grid directional controls.
- `AkaiFireApp.run(duration=...)` for bounded runs.
- `Canvas.fit_text()` and `draw_text_fitted()` for labels constrained by pixel width.
- Animated app previews, screenshots and the original bundled Clawd GIF.
- Callback/lifecycle, OLED encoding, app behavior and text-layout regression tests.

### Changed

- Project documentation now describes the device library, optional application framework and headless testing package separately from the example apps.
- Circuit moved to `examples/apps/circuit` and uses the application runtime. The unfinished modular Groovebox was replaced by the synth editor. Older standalone experiments remain under `examples/legacy`.
- Example names use feature prefixes and module commands; see the [catalog](../examples/README.md).
- Pygame mock uses a 1120×640 hardware-inspired panel, native 128×64 OLED, consistent hit targets and button-specific LED hues.
- Circuit OLED screens use bounded rows and separate header regions. Shared pages/menus fit three complete rows; split screens bound each column. Long labels use an ellipsis.
- `akai_fire` is a package with lazy public imports. The wheel includes the device, framework and testing packages; interactive root mocks and examples require a checkout.
- `pad_position()` returns `(row, col)`. Common single-pad/button validation and setter return types have cross-backend contract coverage.
- Development uses uv, Python 3.12 and Ruff. Default unittest discovery includes Circuit.

### Fixed

- Hardware-verified button LED range: two-color buttons now accept values 0–4, with matching pygame colors and corrected example indicators. Bank clearing sends `0x10` rather than selecting CHANNEL with `0x00`; `DUAL_LED_*` constants distinguish primary colors from amber.
- Application initialization/shutdown and subscription teardown preserve ownership when callbacks or removers fail.
- Circuit clock progression, note gates/cancellation, mute/solo phase, step writes, settings routing, recording input and pattern shrinking.
- Circuit automated demos run the normal frame hook and arm recording before entering notes.
- Circuit note output no longer deadlocks when recording activity under the MIDI lock.
- Looper record-button double registration and BPM normalization; legacy looper listener signatures now permit startup and input dispatch.
- OLED header/body overlap, off-screen menu rows, overflowing labels and stale content in example views, including legacy displays.
- Gallery rain, particles and the humanoid body use the correct lit-pixel polarity; particle explosions repeat before disappearing.
- Legacy Circuit FX rendering no longer redraws 32 times per refresh; Tempo mode updates its display.
- Pad color-cycle demo reaches visible MIDI brightness instead of using only values 0–3.
- Mock encoder drag capture, SELECT click/drag distinction and focus-loss input cleanup.
- Track-LED range includes high green (4), reconnect restores async dispatch, and value bars handle degenerate ranges.

Older entries retain their original version labels and describe earlier project states. The current distribution version is defined in `pyproject.toml`.

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
