# Changelog

All notable changes to the AKAI Fire Python library will be documented in this file.

## [Unreleased] - 2025-08-06

### Added
- **Screen Manager System**: New `screen_manager.py` module providing high-level screen abstractions
  - TextScreen for simple text display
  - MenuScreen with scrollable selection
  - ProgressScreen with progress bars
  - GridScreen for pad visualization
  - ValueScreen for displaying labeled values
  - ScreenManager for managing multiple screens and transitions

- **Performance Improvements**
  - Batch processing for pad color updates for smoother animations
  - Optimized screen rendering with animation utilities
  - New performance demos showing efficient update patterns

- **Enhanced Canvas API**
  - Added `clone()` method for canvas copying
  - New drawing primitives: circles, filled circles, diagonal lines
  - Improved text rendering with border support
  - BMP export functionality for development without hardware

- **New Examples**
  - `screen_animated_wave.py` - Animated wave interference patterns
  - `screen_pages.py` - Multi-page navigation demo
  - `screen_showcase.py` - Comprehensive screen features demo
  - `pad_toggle_on_press.py` - Toggle pad colors on press
  - `control_bank_leds.py` - Control bank LED states
  - `track_led_cycle.py` - Track LED cycling animation
  - `track_led_rain.py` - Track LED rain effect
  - `water_ripple.py` - Water ripple animation effect
  - `batch_animation.py` - Batch update performance demo
  - Multiple groovebox examples demonstrating sequencer patterns

- **Mock GUI Improvements**
  - New PyGame-based mock GUI (`mock_gui_pygame.py`)
  - Added encoder knob visualization
  - Better visual representation of hardware

- **Utility Functions**
  - New `utils.py` module with helper functions
  - Track selection detection helpers
  - Animation utility functions

### Changed
- Migrated all examples to use Canvas-based rendering instead of direct pixel manipulation
- Improved event system with better decorator support (`@fire.on_button`, `@fire.on_pad`)
- Enhanced MIDI channel selection functionality
- Better error handling and logging throughout

### Fixed
- Fixed broken listener registration after adding decorator-based event handlers
- Fixed state parameter naming inconsistencies
- Corrected import paths in various examples
- Fixed MIDI channel selection issues

### Documentation
- Updated README with new examples and features
- Added comprehensive docstrings to new modules
- Created structured example categories

## [0.1.0] - 2025-01-25

### Added
- Initial release of AKAI Fire Python library
- Core `AkaiFire` class for hardware control
- Canvas abstraction for OLED display (128x64 monochrome)
- Event system for pad, button, and encoder interactions
- Basic drawing primitives (pixels, lines, rectangles, text)
- Hardware communication via rtmidi
- Mock GUI support for development without hardware
- Example applications:
  - Hello World display
  - Pad color cycling
  - Screen snow effect
  - Screen bounce animation
  - Simple event handling
  - Basic looper functionality

### Dependencies
- python-rtmidi==1.5.8
- pillow~=11.1.0
- black==25.1.0 (development)
- transitions~=0.9.2 (for state machines)
- tkdial~=0.0.7 (for mock GUI)