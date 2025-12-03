# Roadmap

This document outlines the development priorities for the AKAI Fire library.

## Current Focus: AkaiFireApp Framework

### Phase 1: Framework Core (In Progress)

Create a modular application framework extracted from circuit example patterns:

```
akai_fire_framework/
├── app.py          # AkaiFireApp base class
├── mode.py         # ModeHandler + ModeManagerMixin
├── screen.py       # ScreenMixin
├── grid.py         # GridMixin
├── transport.py    # TransportMixin
└── config.py       # Configuration classes
```

**Goals:**
- [ ] Base class with lifecycle hooks (on_init, on_start, on_update, on_stop)
- [ ] Event routing (on_pad_press, on_button_press, on_encoder_turn)
- [ ] Main loop with FPS control
- [ ] Context manager support
- [ ] Optional mixins for modes, screen, grid, transport

### Phase 2: Example Applications

Build applications to validate and showcase the framework:

#### MIDI Looper
- Pads as clip slots (4 tracks x 16 clips)
- Record/play/overdub per clip
- Simple 2-mode interface

#### MIDI Matrix/Router
- 4x16 pad matrix for routing
- Toggle MIDI connections visually
- Real-time routing display

#### Drum Machine
- 16 drum pads with patterns
- Step sequencer integration
- Kit/Pattern/Song modes

### Phase 3: Circuit Example Refactor

Update the Circuit Tracks sequencer to use the framework:
- Import from akai_fire_framework
- Remove duplicated boilerplate
- Keep domain-specific sequencer logic

---

## Backlog

### Documentation
- [ ] API reference generation from docstrings
- [ ] Video tutorials for complex examples
- [ ] Framework migration guide

### Testing
- [ ] Integration tests with mock hardware
- [ ] Performance benchmarks
- [ ] CI/CD pipeline setup

### Features
- [ ] MIDI clock sync (receive external clock)
- [ ] Project save/load (JSON or similar)
- [ ] MIDI learn mode for button mapping
- [ ] Web-based configuration UI

### Hardware Support
- [ ] Test with different AKAI Fire firmware versions
- [ ] Document any version-specific quirks

---

## Completed

### v0.2.x
- [x] Screen Manager System
- [x] Mock GUI (Pygame)
- [x] Groovebox Example
- [x] Testing Infrastructure

### v0.1.x
- [x] Core AkaiFire class
- [x] Canvas drawing
- [x] Event system
- [x] Basic examples

---

## Contributing

If you'd like to contribute to any roadmap items:
1. Check for existing issues/PRs
2. Open an issue to discuss approach
3. Submit a PR with tests
