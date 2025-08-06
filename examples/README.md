# AKAI Fire Examples

This directory contains example applications demonstrating various features of the AKAI Fire Python library.

## Example Categories

### Basic Display Examples
- `display_hello_world.py` - Simple "Hello, World!" text on screen
- `clear_all.py` - Clear all pads, buttons, and LEDs

### Screen Animations
- `screen_animated_wave.py` - Animated sine wave interference patterns
- `screen_bounce.py` - Bouncing ball animation
- `screen_snow.py` - TV static/snow effect
- `screen_pages.py` - Multi-page screen management demo
- `screen_showcase.py` - Advanced showcase with dynamic effects

### Pad Animations
- `animation_pad_blink_random.py` - Random color blinking on all pads
- `animation_water_ripple_interactive.py` - Interactive water ripple effect
- `animation_water_ripple_batch.py` - Optimized batch water ripple animation
- `pad_color_cycle.py` - Cycle through RGB color intensities
- `pad_toggle_on_press.py` - Toggle pad colors on press

### LED Control
- `control_bank_leds.py` - Control bank LED patterns
- `track_led_cycle.py` - Cycle animations on track LEDs
- `track_led_rain.py` - Rain effect on track LEDs

### Event Handling
- `event_handling_basic.py` - Basic event handling demonstration
- `event_handling_comprehensive.py` - Comprehensive event handling examples

### Music Applications
- `music_looper_advanced.py` - MIDI looper with screen interface
- `music_sequencer.py` - Step sequencer with state management
- `music_groovebox.py` - Advanced groovebox with generative features
- `music_circuit_sequencer.py` - Comprehensive sequencer with multiple modes

### Performance & Testing
- `performance_demo.py` - Performance optimization demonstrations
- `performance_batch_basics.py` - Basic batch update examples
- `performance_batch_animation.py` - Animated patterns using batch updates
- `batch_animation.py` - Rainbow wave batch animation
- `batch_performance.py` - Performance comparison demo
- `comprehensive_test.py` - Hardware test for all components

## Archived Examples

The `dupes/` directory contains older or duplicate examples that have been superseded by the examples above:
- Basic examples that were replaced with better implementations
- Earlier versions of sequencers and loopers
- Duplicate functionality examples

## Running Examples

Most examples can be run directly:
```bash
uv run python examples/display_hello_world.py
```

Examples will automatically use the mock GUI if hardware is not available (requires pygame for visual mock).