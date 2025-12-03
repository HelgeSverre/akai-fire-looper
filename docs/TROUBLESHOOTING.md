# Troubleshooting

Common issues and solutions when working with the AKAI Fire library.

---

## Hardware Connection Issues

### "No MIDI ports found"

**Symptoms:**
- `get_akai_fire()` falls back to mock
- Empty port list from `AkaiFire.list_midi_ports()`

**Solutions:**

1. **Check USB connection**
   - Ensure AKAI Fire is connected via USB
   - Try a different USB port/cable
   - Check if the device appears in system audio/MIDI settings

2. **Check for port conflicts**
   - Close FL Studio or other DAWs that might hold the port
   - On macOS: Check Audio MIDI Setup
   - On Windows: Check Device Manager

3. **Verify rtmidi installation**
   ```bash
   pip install python-rtmidi
   # Or with uv:
   uv pip install python-rtmidi
   ```

### "Permission denied" on Linux

**Solution:**
Add user to audio group:
```bash
sudo usermod -aG audio $USER
# Log out and back in
```

Or create udev rule:
```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="09e8", MODE="0666"' | sudo tee /etc/udev/rules.d/99-akai.rules
sudo udevadm control --reload-rules
```

---

## Display Issues

### OLED not updating

**Symptoms:**
- Drawing to canvas but display stays blank
- Canvas works in BMP export but not on device

**Solutions:**

1. **Call `render_to_display()`**
   ```python
   canvas = fire.get_canvas()
   canvas.draw_text("Hello", 10, 10)
   fire.render_to_display()  # Don't forget this!
   ```

2. **Check SysEx is enabled**
   - Some MIDI interfaces filter SysEx
   - Try connecting directly without MIDI interface

### Garbled display

**Solutions:**
- Clear canvas before drawing: `canvas.clear()`
- Check coordinate values are within bounds (0-127 x, 0-63 y)

---

## Mock GUI Issues

### Pygame window not opening

**Symptoms:**
- Script runs but no window appears
- Import error for pygame

**Solutions:**

1. **Install pygame**
   ```bash
   pip install pygame
   # Or with uv:
   uv pip install pygame
   ```

2. **On macOS with Apple Silicon**
   ```bash
   # May need to run with specific Python
   arch -x86_64 python3 script.py
   # Or install native pygame
   pip install pygame --pre
   ```

3. **Check display server (Linux)**
   ```bash
   # If running headless, pygame may fail
   export SDL_VIDEODRIVER=dummy
   ```

### Window appears but is unresponsive

**Solution:**
Make sure to call `process_events()` in your main loop:
```python
while fire.running:
    if not fire.process_events():
        break
    # Your update code
    time.sleep(0.016)
```

---

## Event Handling Issues

### Pad/button events not firing

**Symptoms:**
- Decorators defined but callbacks not called
- Events work in mock but not on hardware

**Solutions:**

1. **Call `start_listening()`**
   ```python
   fire = get_akai_fire()
   # ... setup callbacks ...
   fire.start_listening()  # Required!
   ```

2. **Check decorator syntax**
   ```python
   # Correct - with parentheses
   @fire.on_pad()
   def handler(pad, velocity):
       pass

   # Wrong - missing parentheses
   @fire.on_pad  # Will fail
   def handler(pad, velocity):
       pass
   ```

3. **Verify button IDs**
   ```python
   # Use constants, not magic numbers
   @fire.on_button(fire.BUTTON_PLAY)  # Correct
   @fire.on_button(0x33)              # Works but fragile
   ```

### Multiple callbacks for same event

**Solution:**
Decorators accumulate - don't redefine:
```python
# This creates TWO handlers:
@fire.on_pad(0)
def handler1(velocity):
    pass

@fire.on_pad(0)
def handler2(velocity):
    pass
```

---

## Performance Issues

### Low frame rate / choppy updates

**Solutions:**

1. **Batch pad color updates**
   ```python
   # Slow - 64 individual calls
   for i in range(64):
       fire.set_pad_color(i, r, g, b)

   # Fast - single batch call
   colors = [(i, r, g, b) for i in range(64)]
   fire.set_multiple_pad_colors(colors)
   ```

2. **Reduce update frequency**
   ```python
   # Only update at 30 FPS
   if time.time() - last_update > 0.033:
       update_display()
       last_update = time.time()
   ```

3. **Minimize canvas redraws**
   - Only redraw when state changes
   - Use dirty rectangles if possible

---

## Circuit Example Issues

### "ModuleNotFoundError: No module named 'core'"

**Solution:**
Run from the circuit directory:
```bash
cd examples/circuit
python main.py
```

Or use the correct Python path:
```bash
python examples/circuit/main.py  # May need path fixes
```

### Demo crashes immediately

**Symptoms:**
- `demo_e2e.py` exits with error
- Mock window closes instantly

**Solutions:**

1. **Check pygame installation** (see above)

2. **Run with timeout**
   ```bash
   timeout 10 python examples/circuit/demo_e2e.py --demo intro
   ```

3. **Check error output**
   ```bash
   python examples/circuit/demo_e2e.py 2>&1 | head -50
   ```

---

## Testing Issues

### Tests fail with MIDI errors

**Solution:**
Tests should mock MIDI - check for missing patches:
```python
from unittest.mock import patch

@patch("rtmidi.MidiIn")
@patch("rtmidi.MidiOut")
def test_something(mock_out, mock_in):
    # Test code here
    pass
```

### Tests hang indefinitely

**Solution:**
Add timeouts to test runner:
```bash
pytest --timeout=10 tests/
```

---

## Getting Help

If your issue isn't covered here:

1. **Check existing issues**: [GitHub Issues](https://github.com/HelgeSverre/akai-fire-looper/issues)
2. **Search the codebase**: Many edge cases are handled in examples
3. **Open a new issue**: Include:
   - Python version
   - OS and version
   - Full error traceback
   - Minimal reproduction code
