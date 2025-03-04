import queue
import tkinter as tk
from collections import defaultdict
from tkinter import Canvas

from PIL import Image, ImageDraw, ImageFont


class MockCanvas:
    WIDTH, HEIGHT = 128, 64

    def __init__(self):
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 1)
        self.draw = ImageDraw.Draw(self.image)

    def clear(self, color: int = 1):
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), color)
        self.draw = ImageDraw.Draw(self.image)

    def set_pixel(self, x, y, color: int = 0):
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.image.putpixel((x, y), color)

    def draw_text(self, text, x, y, font=None, color: int = 0):
        if font is None:
            font = ImageFont.load_default()
        try:
            self.draw.text((x, y), str(text), fill=color, font=font)
        except Exception:
            pass

    def draw_rect(self, x, y, width, height, color: int = 0):
        try:
            self.draw.rectangle([x, y, x + width, y + height], outline=color)
        except Exception:
            pass

    def fill_rect(self, x, y, width, height, color: int = 0):
        try:
            self.draw.rectangle([x, y, x + width, y + height], fill=color)
        except Exception:
            pass


class MockAkaiFire:
    # Constants (same as before)
    ROTARY_VOLUME = 0x10
    ROTARY_PAN = 0x11
    ROTARY_FILTER = 0x12
    ROTARY_RESONANCE = 0x13
    ROTARY_SELECT = 0x76

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

    LED_OFF = 0x00
    LED_DULL_RED = 0x01
    LED_HIGH_RED = 0x02
    LED_DULL_GREEN = 0x01
    LED_HIGH_GREEN = 0x02

    def __init__(self, port_name=None):
        # Initialize collections
        self.pad_listeners = defaultdict(list)
        self.button_listeners = defaultdict(list)
        self.rotary_listeners = defaultdict(list)
        self.rotary_touch_listeners = defaultdict(list)

        # Initialize canvas
        self.canvas = MockCanvas()

        # GUI state
        self.running = True
        self.command_queue = queue.Queue()

        # Build GUI on main thread
        self.root = tk.Tk()
        self.root.title("Akai Fire Mock GUI")
        self.root.configure(bg="#222")

        # Initialize GUI elements
        self._setup_display()
        self._setup_knobs()
        self._setup_pads()
        self._setup_mode_buttons()
        self._setup_transport()

        # Store previous knob values
        self.previous_knob_values = {
            self.ROTARY_VOLUME: 64,
            self.ROTARY_PAN: 64,
            self.ROTARY_FILTER: 64,
            self.ROTARY_RESONANCE: 64,
            self.ROTARY_SELECT: 64,
        }

        # Start processing queue
        self._process_queue()

    def _process_queue(self):
        """Process commands from the queue"""
        try:
            while not self.command_queue.empty():
                cmd, args = self.command_queue.get_nowait()
                if cmd and hasattr(self, cmd):
                    getattr(self, cmd)(*args)
                self.command_queue.task_done()
        except queue.Empty:
            pass
        finally:
            if self.running:
                self.root.after(10, self._process_queue)

    def _enqueue_command(self, cmd, *args):
        """Add command to queue for main thread processing"""
        self.command_queue.put((cmd, args))

    def _setup_display(self):
        self.display = Canvas(self.root, width=128, height=64, bg="#333")
        self.display.grid(row=0, column=2, columnspan=4, pady=10)
        self.display.create_text(
            64, 32, text="Mock Fire", fill="white", font=("Courier", 10)
        )

    def _setup_knobs(self):
        self.knob_frame = tk.Frame(self.root, bg="#222")
        self.knob_frame.grid(row=1, column=0, columnspan=8, pady=5)

        knob_mapping = {
            "Volume": self.ROTARY_VOLUME,
            "Pan": self.ROTARY_PAN,
            "Filter": self.ROTARY_FILTER,
            "Resonance": self.ROTARY_RESONANCE,
            "Select": self.ROTARY_SELECT,
        }

        self.knobs = {}
        for name, rotary_id in knob_mapping.items():
            tk.Label(self.knob_frame, text=name, fg="white", bg="#222").grid(
                row=0, column=len(self.knobs)
            )
            knob = tk.Scale(
                self.knob_frame,
                from_=0,
                to=127,
                orient="vertical",
                bg="#444",
                fg="white",
                length=100,
            )
            knob.grid(row=1, column=len(self.knobs), padx=5)
            knob.set(64)

            knob.bind("<B1-Motion>", lambda e, r=rotary_id: self._handle_knob_change(r))
            self.knobs[rotary_id] = knob

    def _setup_pads(self):
        self.pads_frame = tk.Frame(self.root, bg="#222")
        self.pads_frame.grid(row=2, column=1, columnspan=6)
        self.pads = []

        for row in range(4):
            row_pads = []
            for col in range(16):
                pad = tk.Button(
                    self.pads_frame,
                    bg="#444",
                    activebackground="green",
                    width=2,
                    height=1,
                    command=lambda r=row, c=col: self._handle_pad_press(r, c),
                )
                pad.grid(row=row, column=col, padx=1, pady=1)
                row_pads.append(pad)
            self.pads.append(row_pads)

    def _setup_mode_buttons(self):
        self.mode_frame = tk.Frame(self.root, bg="#222")
        self.mode_frame.grid(row=3, column=1, columnspan=6, pady=5)

        self.mode_buttons = {}
        mode_buttons = {
            "Step": self.BUTTON_STEP,
            "Note": self.BUTTON_NOTE,
            "Drum": self.BUTTON_DRUM,
            "Pattern": self.BUTTON_PATTERN,
            "Shift": self.BUTTON_SHIFT,
            "Alt": self.BUTTON_ALT,
        }

        for name, code in mode_buttons.items():
            btn = tk.Button(
                self.mode_frame,
                text=name,
                bg="yellow",
                width=6,
                height=2,
                command=lambda c=code: self._handle_button_press(c),
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.mode_buttons[code] = btn

    def _setup_transport(self):
        self.transport_frame = tk.Frame(self.root, bg="#222")
        self.transport_frame.grid(row=4, column=1, columnspan=6, pady=5)

        self.transport_buttons = {}
        transport_configs = [
            (self.BUTTON_PLAY, "▶"),
            (self.BUTTON_STOP, "■"),
            (self.BUTTON_REC, "●"),
        ]

        for button_id, symbol in transport_configs:
            btn = tk.Button(
                self.transport_frame,
                text=symbol,
                bg="gray",
                width=4,
                height=2,
                command=lambda b=button_id: self._handle_button_press(b),
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.transport_buttons[button_id] = btn

    # ... (rest of the methods from previous implementation)

    def update(self):
        """Process GUI events"""
        if self.running:
            self.root.update()

    def close(self):
        """Clean up resources"""
        self.running = False
        if hasattr(self, "root"):
            self.root.quit()
            self.root.destroy()

    def start(self):
        """Start the GUI mainloop"""
        if self.running:
            self.root.mainloop()


if __name__ == "__main__":
    mock = MockAkaiFire()

    @mock.on_pad()
    def handle_pad(pad_index, velocity):
        print(f"Pad {pad_index} pressed with velocity {velocity}")

    @mock.on_button()
    def handle_button(button_id, event):
        print(f"Button {button_id} {event}")

    @mock.on_rotary_turn()
    def handle_rotary(rotary_id, direction, velocity):
        print(f"Rotary {rotary_id} turned {direction} at velocity {velocity}")

    mock.start()
