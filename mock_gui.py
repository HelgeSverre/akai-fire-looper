import tkinter as tk
from tkinter import Canvas


class AkaiFireMockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Akai Fire Mock GUI")

        # Configure grid layout
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Main frame
        self.main_frame = tk.Frame(self.root, bg="black")
        self.main_frame.grid(sticky="nsew")

        # Display (OLED simulation)
        self.display_canvas = Canvas(self.main_frame, width=128, height=64, bg="white")
        self.display_canvas.grid(row=0, column=2, columnspan=4, pady=5)

        # Rotary knobs simulation
        self.knob_frame = tk.Frame(self.main_frame, bg="black")
        self.knob_frame.grid(row=1, column=0, columnspan=8, pady=5)
        self.knobs = {
            "Volume": tk.Scale(self.knob_frame, from_=0, to=127, orient="horizontal"),
            "Pan": tk.Scale(self.knob_frame, from_=-64, to=63, orient="horizontal"),
            "Filter": tk.Scale(self.knob_frame, from_=-64, to=63, orient="horizontal"),
            "Resonance": tk.Scale(self.knob_frame, from_=-64, to=63, orient="horizontal"),
            "Select": tk.Scale(self.knob_frame, from_=0, to=127, orient="horizontal")
        }
        for idx, (name, scale) in enumerate(self.knobs.items()):
            tk.Label(self.knob_frame, text=name, fg="white", bg="black").grid(row=0, column=idx)
            scale.grid(row=1, column=idx, padx=5)

        # Pad grid (8x4)
        self.pads_frame = tk.Frame(self.main_frame, bg="black")
        self.pads_frame.grid(row=2, column=1, columnspan=6)
        self.pads = []
        for row in range(4):
            row_pads = []
            for col in range(8):
                pad = tk.Button(
                    self.pads_frame,
                    bg="gray20",
                    activebackground="green",
                    width=6,
                    height=3,
                    command=lambda r=row, c=col: self.pad_pressed(r, c)
                )
                pad.grid(row=row, column=col, padx=2, pady=2)
                row_pads.append(pad)
            self.pads.append(row_pads)

        # Side buttons (Solo/Mute)
        self.side_buttons_frame = tk.Frame(self.main_frame, bg="black")
        self.side_buttons_frame.grid(row=2, column=0, padx=5)
        self.side_buttons = [tk.Button(self.side_buttons_frame, text=f"S{i + 1}", width=4,
                                       command=lambda i=i: self.side_button_pressed(i)) for i in range(4)]
        for idx, btn in enumerate(self.side_buttons):
            btn.grid(row=idx, column=0, pady=5)

        # Navigation and function buttons
        self.nav_frame = tk.Frame(self.main_frame, bg="black")
        self.nav_frame.grid(row=3, column=1, columnspan=6, pady=5)
        self.nav_buttons = {
            "Step": tk.Button(self.nav_frame, text="Step", command=self.step_pressed),
            "Note": tk.Button(self.nav_frame, text="Note", command=self.note_pressed),
            "Drum": tk.Button(self.nav_frame, text="Drum", command=self.drum_pressed),
            "Perform": tk.Button(self.nav_frame, text="Perform", command=self.perform_pressed),
            "Shift": tk.Button(self.nav_frame, text="Shift", command=self.shift_pressed),
            "Alt": tk.Button(self.nav_frame, text="Alt", command=self.alt_pressed)
        }
        for idx, (name, btn) in enumerate(self.nav_buttons.items()):
            btn.grid(row=0, column=idx, padx=5)

        # Transport and other buttons
        self.transport_frame = tk.Frame(self.main_frame, bg="black")
        self.transport_frame.grid(row=4, column=1, columnspan=6, pady=5)
        self.buttons = {
            "Play": tk.Button(self.transport_frame, text="Play", command=self.play_pressed),
            "Stop": tk.Button(self.transport_frame, text="Stop", command=self.stop_pressed),
            "Rec": tk.Button(self.transport_frame, text="Rec", command=self.rec_pressed),
            "Browser": tk.Button(self.transport_frame, text="Browser", command=self.browser_pressed),
            "Pattern": tk.Button(self.transport_frame, text="Pattern", command=self.pattern_pressed),
            "Grid Left": tk.Button(self.transport_frame, text="Grid Left", command=self.grid_left_pressed),
            "Grid Right": tk.Button(self.transport_frame, text="Grid Right", command=self.grid_right_pressed)
        }
        for idx, (name, btn) in enumerate(self.buttons.items()):
            btn.grid(row=0, column=idx, padx=5)

    def pad_pressed(self, row, col):
        print(f"Pad pressed: Row {row + 1}, Column {col + 1}")
        self.pads[row][col].config(bg="green")
        self.root.after(200, lambda: self.pads[row][col].config(bg="gray20"))

    def side_button_pressed(self, idx):
        print(f"Side button S{idx + 1} pressed")

    def play_pressed(self):
        print("Play pressed")

    def stop_pressed(self):
        print("Stop pressed")

    def rec_pressed(self):
        print("Rec pressed")

    def browser_pressed(self):
        print("Browser pressed")

    def pattern_pressed(self):
        print("Pattern pressed")

    def grid_left_pressed(self):
        print("Grid Left pressed")

    def grid_right_pressed(self):
        print("Grid Right pressed")

    def step_pressed(self):
        print("Step pressed")

    def note_pressed(self):
        print("Note pressed")

    def drum_pressed(self):
        print("Drum pressed")

    def perform_pressed(self):
        print("Perform pressed")

    def shift_pressed(self):
        print("Shift pressed")

    def alt_pressed(self):
        print("Alt pressed")


if __name__ == "__main__":
    root = tk.Tk()
    app = AkaiFireMockGUI(root)
    root.mainloop()
