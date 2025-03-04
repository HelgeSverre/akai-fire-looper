import threading
import time
import tkinter as tk
from collections import defaultdict
from queue import Queue
from typing import Callable, Dict, List, Optional, Tuple


class MockCanvas:
    """A canvas implementation that simulates the OLED display on the Akai Fire."""

    WIDTH, HEIGHT = 128, 64

    def __init__(self, tkinter_root=None):
        """Initialize the canvas with optional Tkinter integration."""
        self.width = self.WIDTH
        self.height = self.HEIGHT
        self.pixels = [[1 for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]
        self.tk_root = tkinter_root
        self.tk_canvas = None
        self.tk_frame = None
        self.pending_operations = []

        if self.tk_root:
            self.tk_frame = tk.Frame(self.tk_root)
            self.tk_frame.pack(pady=10)
            self.tk_canvas = tk.Canvas(
                self.tk_frame,
                width=self.WIDTH,
                height=self.HEIGHT,
                bg="#222222",
                highlightthickness=0,
            )
            self.tk_canvas.pack()

        self.text_elements = []

    def clear(self, color: int = 1):
        """Clear the canvas with the specified color (1=white background, 0=black)."""
        self.pixels = [[color for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]
        self.text_elements = []

        if self.tk_canvas:
            bg_color = "#222222" if color == 1 else "white"
            self.pending_operations.append(
                lambda: self.tk_canvas.configure(bg=bg_color)
            )
            self.pending_operations.append(lambda: self.tk_canvas.delete("all"))

    def set_pixel(self, x: int, y: int, color: int = 0):
        """Set a pixel to the specified color (0=black, 1=white)."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.pixels[y][x] = color

            if self.tk_canvas:
                fill_color = "white" if color == 0 else "#222222"
                self.pending_operations.append(
                    lambda x=x, y=y, fc=fill_color: self.tk_canvas.create_rectangle(
                        x, y, x + 1, y + 1, fill=fc, outline=fc
                    )
                )

    def fill_rect(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Draw a filled rectangle."""
        for i in range(height):
            for j in range(width):
                self.set_pixel(x + j, y + i, color)

        if self.tk_canvas:
            fill_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x=x, y=y, w=width, h=height, fc=fill_color: self.tk_canvas.create_rectangle(
                    x, y, x + w, y + h, fill=fc, outline=fc
                )
            )

    def draw_rect(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Draw a rectangle outline."""
        # Top and bottom edges
        for j in range(width):
            self.set_pixel(x + j, y, color)
            self.set_pixel(x + j, y + height - 1, color)

        # Left and right edges
        for i in range(height):
            self.set_pixel(x, y + i, color)
            self.set_pixel(x + width - 1, y + i, color)

        if self.tk_canvas:
            outline_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x=x, y=y, w=width, h=height, oc=outline_color: self.tk_canvas.create_rectangle(
                    x, y, x + w, y + h, fill="", outline=oc
                )
            )

    def draw_text(self, text: str, x: int, y: int, color: int = 0):
        """Draw text at the specified position."""
        self.text_elements.append((text, x, y, color))

        if self.tk_canvas:
            fill_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda t=text, x=x, y=y, fc=fill_color: self.tk_canvas.create_text(
                    x, y, text=t, fill=fc, anchor=tk.NW, font=("Arial", 9)
                )
            )

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 0):
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        if self.tk_canvas:
            line_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x0=x0, y0=y0, x1=x1, y1=y1, lc=line_color: self.tk_canvas.create_line(
                    x0, y0, x1, y1, fill=lc
                )
            )

    def draw_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Draw a circle using the midpoint circle algorithm."""
        x = radius
        y = 0
        decision = 1 - x

        while y <= x:
            self.set_pixel(x0 + x, y0 + y, color)
            self.set_pixel(x0 + y, y0 + x, color)
            self.set_pixel(x0 - y, y0 + x, color)
            self.set_pixel(x0 - x, y0 + y, color)
            self.set_pixel(x0 - x, y0 - y, color)
            self.set_pixel(x0 - y, y0 - x, color)
            self.set_pixel(x0 + y, y0 - x, color)
            self.set_pixel(x0 + x, y0 - y, color)
            y += 1
            if decision <= 0:
                decision += 2 * y + 1
            else:
                x -= 1
                decision += 2 * (y - x) + 1

        if self.tk_canvas:
            outline_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x0=x0, y0=y0, r=radius, oc=outline_color: self.tk_canvas.create_oval(
                    x0 - r, y0 - r, x0 + r, y0 + r, outline=oc
                )
            )

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a horizontal line."""
        for i in range(length):
            self.set_pixel(x + i, y, color)

        if self.tk_canvas:
            line_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x=x, y=y, l=length, lc=line_color: self.tk_canvas.create_line(
                    x, y, x + l, y, fill=lc
                )
            )

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a vertical line."""
        for i in range(length):
            self.set_pixel(x, y + i, color)

        if self.tk_canvas:
            line_color = "white" if color == 0 else "#222222"
            self.pending_operations.append(
                lambda x=x, y=y, l=length, lc=line_color: self.tk_canvas.create_line(
                    x, y, x, y + l, fill=lc
                )
            )

    def draw_border(self, thickness: int = 1, color: int = 0):
        """Draw a border around the entire canvas."""
        for i in range(thickness):
            self.draw_rect(i, i, self.WIDTH - 2 * i, self.HEIGHT - 2 * i, color)

    def process_pending_operations(self):
        """Process any pending drawing operations in the main thread."""
        if self.tk_canvas:
            for op in self.pending_operations:
                try:
                    op()
                except Exception as e:
                    print(f"Canvas operation error: {e}")
            self.pending_operations = []


class MockAkaiFire:
    """A mock implementation of the Akai Fire controller for development and testing."""

    # Button Constants (matching actual Akai Fire)
    BUTTON_PLAY = 0x33
    BUTTON_STOP = 0x34
    BUTTON_REC = 0x35
    BUTTON_SHIFT = 0x30
    BUTTON_ALT = 0x31
    BUTTON_STEP = 0x2C
    BUTTON_NOTE = 0x2D
    BUTTON_DRUM = 0x2E
    BUTTON_PERFORM = 0x2F
    BUTTON_PATTERN = 0x32
    BUTTON_BROWSER = 0x21
    BUTTON_GRID_LEFT = 0x22
    BUTTON_GRID_RIGHT = 0x23
    BUTTON_BANK = 0x1A
    BUTTON_SELECT = 0x19
    BUTTON_SOLO_1 = 0x24
    BUTTON_SOLO_2 = 0x25
    BUTTON_SOLO_3 = 0x26
    BUTTON_SOLO_4 = 0x27
    BUTTON_PAT_UP = 0x1F
    BUTTON_PAT_DOWN = 0x20

    # Rotary Controls
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

    # LED Values
    LED_OFF = 0x00
    LED_DULL_RED = 0x01
    LED_HIGH_RED = 0x02
    LED_DULL_GREEN = 0x01
    LED_HIGH_GREEN = 0x02
    LED_DULL_YELLOW = 0x01
    LED_HIGH_YELLOW = 0x02

    def __init__(self, use_gui=True):
        """Initialize the mock Akai Fire controller."""
        self.canvas = MockCanvas()
        self.listeners = {}
        self.pad_listeners = defaultdict(list)
        self.global_pad_listeners = []
        self.button_listeners = defaultdict(list)
        self.global_button_listeners = []
        self.rotary_listeners = defaultdict(list)
        self.global_rotary_listeners = []
        self.rotary_touch_listeners = defaultdict(list)
        self.global_rotary_touch_listeners = []

        # Track states
        self.pad_colors = [[0, 0, 0] for _ in range(64)]  # 4x16 grid, RGB values
        self.button_states = {}  # button_id -> LED state
        self.rotary_positions = {
            self.ROTARY_VOLUME: 64,
            self.ROTARY_PAN: 64,
            self.ROTARY_FILTER: 64,
            self.ROTARY_RESONANCE: 64,
            self.ROTARY_SELECT: 64,
        }

        # Threading and communication
        self.gui_queue = Queue()
        self.gui_running = True

        # Set up GUI if requested
        self.use_gui = use_gui
        self.root = None
        if self.use_gui:
            self.init_gui()

    def init_gui(self):
        """Create the root window but don't run mainloop."""
        self.root = tk.Tk()
        self.root.title("Mock Akai Fire Controller")
        self.root.configure(bg="#333333")
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # OLED Display
        self.canvas = MockCanvas(self.root)

        # Create frames for different sections
        top_frame = tk.Frame(self.root, bg="#333333")
        top_frame.pack(pady=10)

        # Rotary knobs at the top
        rotary_frame = tk.Frame(top_frame, bg="#333333")
        rotary_frame.pack(pady=5)

        self.rotary_knobs = {}
        rotary_names = {
            self.ROTARY_VOLUME: "Volume",
            self.ROTARY_PAN: "Pan",
            self.ROTARY_FILTER: "Filter",
            self.ROTARY_RESONANCE: "Res",
            self.ROTARY_SELECT: "Select",
        }

        for i, (rotary_id, name) in enumerate(rotary_names.items()):
            frame = tk.Frame(rotary_frame, bg="#333333")
            frame.grid(row=0, column=i, padx=10)

            label = tk.Label(frame, text=name, fg="white", bg="#333333")
            label.pack()

            knob = tk.Scale(
                frame,
                from_=0,
                to=127,
                orient=tk.VERTICAL,
                length=100,
                bg="#333333",
                fg="white",
                troughcolor="#555555",
                command=lambda value, rid=rotary_id: self._on_rotary_change(
                    rid, int(value)
                ),
            )
            knob.set(64)  # Default middle position
            knob.pack()

            self.rotary_knobs[rotary_id] = knob

        # Create main button section
        button_frame = tk.Frame(self.root, bg="#333333")
        button_frame.pack(pady=5)

        # Transport buttons
        transport_frame = tk.Frame(button_frame, bg="#333333")
        transport_frame.grid(row=0, column=0, padx=10, pady=5)

        transport_buttons = {
            self.BUTTON_PLAY: "Play",
            self.BUTTON_STOP: "Stop",
            self.BUTTON_REC: "Rec",
        }

        for i, (button_id, label) in enumerate(transport_buttons.items()):
            btn = self._create_button(transport_frame, label, button_id)
            btn.grid(row=0, column=i, padx=5)

        # Modifier buttons
        modifier_frame = tk.Frame(button_frame, bg="#333333")
        modifier_frame.grid(row=0, column=1, padx=10, pady=5)

        modifier_buttons = {self.BUTTON_SHIFT: "Shift", self.BUTTON_ALT: "Alt"}

        for i, (button_id, label) in enumerate(modifier_buttons.items()):
            btn = self._create_button(modifier_frame, label, button_id)
            btn.grid(row=0, column=i, padx=5)

        # View buttons
        view_frame = tk.Frame(button_frame, bg="#333333")
        view_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        view_buttons = {
            self.BUTTON_STEP: "Step",
            self.BUTTON_NOTE: "Note",
            self.BUTTON_DRUM: "Drum",
            self.BUTTON_PERFORM: "Perform",
            self.BUTTON_PATTERN: "Pattern",
            self.BUTTON_BROWSER: "Browser",
            self.BUTTON_GRID_LEFT: "◀",
            self.BUTTON_GRID_RIGHT: "▶",
        }

        for i, (button_id, label) in enumerate(view_buttons.items()):
            btn = self._create_button(view_frame, label, button_id)
            btn.grid(row=i // 4, column=i % 4, padx=5, pady=2)

        # Create solo buttons
        solo_frame = tk.Frame(self.root, bg="#333333")
        solo_frame.pack(side=tk.LEFT, padx=10)

        solo_buttons = {
            self.BUTTON_SOLO_1: "S1",
            self.BUTTON_SOLO_2: "S2",
            self.BUTTON_SOLO_3: "S3",
            self.BUTTON_SOLO_4: "S4",
        }

        for i, (button_id, label) in enumerate(solo_buttons.items()):
            btn = self._create_button(solo_frame, label, button_id)
            btn.grid(row=i, column=0, pady=2)

        # Create the pad grid (4x16)
        grid_frame = tk.Frame(self.root, bg="#333333")
        grid_frame.pack(pady=10)

        self.pad_buttons = []
        for row in range(4):
            row_buttons = []
            for col in range(16):
                pad_idx = row * 16 + col
                btn = tk.Button(
                    grid_frame,
                    width=4,
                    height=2,
                    bg="#222222",
                    activebackground="#444444",
                    relief=tk.RAISED,
                    borderwidth=2,
                    command=lambda idx=pad_idx: self._on_pad_press(idx),
                )
                btn.grid(row=row, column=col, padx=2, pady=2)
                row_buttons.append(btn)
            self.pad_buttons.append(row_buttons)

        # Schedule the first update
        self.root.after(50, self.update_gui)

    def update_gui(self):
        """Update the GUI - this runs in the main thread."""
        if not self.gui_running:
            return

        # Update pad colors
        for row in range(4):
            for col in range(16):
                pad_idx = row * 16 + col
                r, g, b = self.pad_colors[pad_idx]
                # Convert RGB to hex color
                color = f"#{r:02x}{g:02x}{b:02x}"
                try:
                    self.pad_buttons[row][col].configure(bg=color)
                except:
                    pass  # Ignore errors if pads were destroyed

        # Process canvas operations
        self.canvas.process_pending_operations()

        # Process items in the queue
        try:
            while not self.gui_queue.empty():
                func = self.gui_queue.get_nowait()
                func()
                self.gui_queue.task_done()
        except:
            pass

        # Schedule next update if still running
        if self.gui_running and self.root:
            self.root.after(50, self.update_gui)

    def on_window_close(self):
        """Handle window close event."""
        self.gui_running = False
        self.root.destroy()
        self.root = None

    def _create_button(self, parent, label, button_id):
        """Helper method to create a button with consistent styling."""
        btn = tk.Button(
            parent,
            text=label,
            width=6,
            height=2,
            bg="#222222",
            fg="white",
            activebackground="#444444",
            activeforeground="white",
            relief=tk.RAISED,
            borderwidth=2,
            command=lambda: self._on_button_press(button_id),
        )
        return btn

    def _on_button_press(self, button_id):
        """Handle button press events from the GUI."""
        # Call any registered listeners
        for listener in self.button_listeners[button_id]:
            listener("press")

        for listener in self.global_button_listeners:
            listener(button_id, "press")

        # Simulate button release after a short delay
        def release():
            for listener in self.button_listeners[button_id]:
                listener("release")

            for listener in self.global_button_listeners:
                listener(button_id, "release")

        threading.Timer(0.15, release).start()

    def _on_pad_press(self, pad_idx):
        """Handle pad press events from the GUI."""
        # Default velocity
        velocity = 100

        # Call any registered listeners for this specific pad
        for listener in self.pad_listeners.get(pad_idx, []):
            listener(velocity)

        # Call global pad listeners
        for listener in self.global_pad_listeners:
            listener(pad_idx, velocity)

    def _on_rotary_change(self, rotary_id, value):
        """Handle rotary knob changes from the GUI."""
        prev_value = self.rotary_positions.get(rotary_id, 64)

        if value != prev_value:
            # Determine direction
            direction = "clockwise" if value > prev_value else "counterclockwise"
            # Calculate velocity (speed of rotation)
            velocity = min(abs(value - prev_value), 10)

            # Store new position
            self.rotary_positions[rotary_id] = value

            # Call any registered listeners
            for listener in self.rotary_listeners[rotary_id]:
                listener(direction, velocity)

            for listener in self.rotary_listeners.get("global", []):
                listener(rotary_id, direction, velocity)

    def on_pad(self, pad_index=None):
        """
        Decorator for pad presses. Supports multiple listeners per pad.

        Usage:
            @fire.on_pad(0)  # Single pad
            def handle_pad(velocity):
                print(f"Pad pressed with velocity {velocity}")

            @fire.on_pad([0,1,2,3])  # Multiple pads
            def handle_pads(pad_index, velocity):
                print(f"Pad {pad_index} pressed with velocity {velocity}")

            @fire.on_pad()  # All pads
            def handle_any_pad(pad_index, velocity):
                print(f"Pad {pad_index} pressed with velocity {velocity}")
        """

        def decorator(func):
            if pad_index is None:
                self.global_pad_listeners.append(func)
            elif isinstance(pad_index, (list, tuple)):
                for idx in pad_index:
                    if not (0 <= idx <= 63):
                        raise ValueError("Pad index must be between 0 and 63")
                    self.pad_listeners[idx].append(func)
            else:
                if not (0 <= pad_index <= 63):
                    raise ValueError("Pad index must be between 0 and 63")
                self.pad_listeners[pad_index].append(func)
            return func

        return decorator

    def on_button(self, button_id=None):
        """
        Decorator for button events.

        Usage:
            @fire.on_button(BUTTON_PLAY)  # Specific button
            def handle_play(event):
                print(f"Play button {event}")

            @fire.on_button()  # Global button handler
            def handle_any_button(button_id, event):
                print(f"Button {button_id} {event}")
        """

        def decorator(func):
            if button_id is None:
                self.global_button_listeners.append(func)
            else:
                self.button_listeners[button_id].append(func)
            return func

        return decorator

    def on_rotary_turn(self, rotary_id=None):
        """
        Decorator for rotary knob turns.

        Usage:
            @fire.on_rotary_turn(ROTARY_VOLUME)  # Specific rotary
            def handle_volume(direction, velocity):
                print(f"Volume turned {direction} at {velocity}")

            @fire.on_rotary_turn()  # Global rotary handler
            def handle_any_rotary(rotary_id, direction, velocity):
                print(f"Rotary {rotary_id} turned {direction} at {velocity}")
        """

        def decorator(func):
            if rotary_id is None:
                self.rotary_listeners["global"].append(func)
            else:
                self.rotary_listeners[rotary_id].append(func)
            return func

        return decorator

    def on_rotary_touch(self, rotary_id=None):
        """
        Decorator for rotary touch events.

        Usage:
            @fire.on_rotary_touch(ROTARY_VOLUME)  # Specific rotary
            def handle_volume_touch(event):
                print(f"Volume knob {event}")

            @fire.on_rotary_touch()  # Global touch handler
            def handle_any_touch(rotary_id, event):
                print(f"Rotary {rotary_id} {event}")
        """

        def decorator(func):
            if rotary_id is None:
                self.rotary_touch_listeners["global"].append(func)
            else:
                self.rotary_touch_listeners[rotary_id].append(func)
            return func

        return decorator

    def get_canvas(self):
        """Get the canvas for drawing."""
        return self.canvas

    def set_pad_color(self, index, red, green, blue):
        """Sets the color of a single pad."""
        if 0 <= index < 64:
            self.pad_colors[index] = [red, green, blue]

    def set_multiple_pad_colors(self, pad_colors):
        """Sets colors for multiple pads at once.

        Args:
            pad_colors: List of (pad_index, red, green, blue) tuples.
        """
        for pad_data in pad_colors:
            index, red, green, blue = pad_data
            self.set_pad_color(index, red, green, blue)

    def reset_pads(self, red=0, green=0, blue=0):
        """Resets all pads to a specific color or turns them off."""
        for i in range(64):
            self.set_pad_color(i, red, green, blue)

    def clear_all_pads(self):
        """Turns off all pads."""
        self.reset_pads(0, 0, 0)

    def set_button_led(self, button_id, value):
        """
        Sets the LED state for a button.

        Args:
            button_id: One of the BUTTON_* constants.
            value: One of the LED_* constants (e.g., LED_OFF, LED_HIGH_RED).
        """
        self.button_states[button_id] = value

    def clear_all_button_leds(self):
        """Turns off all button LEDs."""
        for button_id in self.button_states:
            self.set_button_led(button_id, self.LED_OFF)

    def clear_all(self):
        """Turns off all LEDs, Pads, Buttons and the Screen."""
        self.clear_all_pads()
        self.clear_all_button_leds()
        self.canvas.clear()

    def render_to_display(self):
        """Render the canvas to the display."""
        # The canvas updates are processed in the update_gui method
        pass

    def start_gui(self):
        """Start the GUI main loop in the current thread."""
        if self.use_gui and self.root:
            try:
                self.root.mainloop()
            except Exception as e:
                print(f"GUI error: {e}")
            finally:
                self.gui_running = False

    def close(self):
        """Close the mock controller."""
        self.gui_running = False
        if self.use_gui and self.root:
            try:
                self.root.destroy()
                self.root = None
            except:
                pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# For testing the mock implementation
if __name__ == "__main__":
    fire = MockAkaiFire()

    @fire.on_pad()
    def handle_pad(pad_idx, velocity):
        print(f"Pad {pad_idx} pressed with velocity {velocity}")
        # Set this pad to red
        fire.set_pad_color(pad_idx, 127, 0, 0)

    @fire.on_button(fire.BUTTON_PLAY)
    def handle_play(event):
        print(f"Play button {event}")
        if event == "press":
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_HIGH_GREEN)
        else:
            fire.set_button_led(fire.BUTTON_PLAY, fire.LED_OFF)

    @fire.on_rotary_turn(fire.ROTARY_VOLUME)
    def handle_volume(direction, velocity):
        print(f"Volume turned {direction} at {velocity}")

    # Draw something on the OLED display
    canvas = fire.get_canvas()
    canvas.clear()
    canvas.draw_text("Mock Akai Fire", 5, 5)
    canvas.draw_text("Test Interface", 5, 20)
    canvas.draw_rect(2, 2, 124, 60)
    fire.render_to_display()

    # Start the GUI
    fire.start_gui()
