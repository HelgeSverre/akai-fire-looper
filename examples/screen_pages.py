import os
import time
from enum import Enum, auto
from akai_fire import AkaiFire


class ScreenDemo(Enum):
    BASIC_PAGE = auto()
    VALUE_PAGE = auto()
    MENU = auto()
    GRID_INFO = auto()
    SPLIT_SCREEN = auto()


class ScreenLayoutDemo:
    def __init__(self):
        self.fire = AkaiFire()
        self.canvas = self.fire.get_canvas()
        self.current_screen = ScreenDemo.BASIC_PAGE
        self.setup_handlers()
        self.setup_demo_data()

        # For saving debug screenshots
        os.makedirs("_screens", exist_ok=True)

    def setup_demo_data(self):
        """Setup example data for each screen type"""
        self.demo_data = {
            ScreenDemo.BASIC_PAGE: {
                "title": "Basic Page Demo",
                "lines": [
                    "This is a basic page layout",
                    "with multiple lines of text",
                    "Press any pad to continue",
                    "to the next demo screen",
                ],
            },
            ScreenDemo.VALUE_PAGE: {
                "title": "Parameter: Filter Cutoff",
                "value": 64,
                "min_val": 0,
                "max_val": 127,
            },
            ScreenDemo.MENU: {
                "title": "Select Mode",
                "items": [
                    "Pattern Mode",
                    "Mixer Mode",
                    "Step Sequencer",
                    "Piano Mode",
                    "Drum Mode",
                    "Settings",
                ],
                "selected": 2,
            },
            ScreenDemo.GRID_INFO: {
                "title": "Drum Pad Layout",
                "info": [
                    (0, 0, "KD"),
                    (0, 1, "SD"),
                    (0, 2, "CH"),
                    (0, 3, "OH"),
                    (1, 0, "TM"),
                    (1, 1, "CP"),
                    (1, 2, "CB"),
                    (1, 3, "CY"),
                ],
            },
            ScreenDemo.SPLIT_SCREEN: {
                "title": "Track Compare",
                "left": ["Track 1:", "Volume: 100", "Pan: C", "FX: Reverb"],
                "right": ["Track 2:", "Volume: 85", "Pan: R15", "FX: Delay"],
            },
        }

    def setup_handlers(self):
        @self.fire.on_pad()
        def handle_pad(pad_index, velocity):
            # Cycle through screens on any pad press
            current_screens = list(ScreenDemo)
            current_idx = current_screens.index(self.current_screen)
            next_idx = (current_idx + 1) % len(current_screens)
            self.current_screen = current_screens[next_idx]

            # Update pad colors to show current screen
            self.update_pad_colors()
            # Draw new screen
            self.draw_current_screen()

    def update_pad_colors(self):
        """Update pad colors to indicate current screen"""
        self.fire.clear_all_pads()
        # Light up pads based on current screen
        screen_colors = {
            ScreenDemo.BASIC_PAGE: (127, 0, 0),  # Red
            ScreenDemo.VALUE_PAGE: (0, 127, 0),  # Green
            ScreenDemo.MENU: (0, 0, 127),  # Blue
            ScreenDemo.GRID_INFO: (127, 127, 0),  # Yellow
            ScreenDemo.SPLIT_SCREEN: (127, 0, 127),  # Purple
        }
        # Light up first row to show current screen
        for i, screen in enumerate(ScreenDemo):
            color = screen_colors.get(screen, (0, 0, 0))
            # Brighten current screen's pad
            brightness = 1.0 if screen == self.current_screen else 0.3
            r, g, b = [int(c * brightness) for c in color]
            self.fire.set_pad_color(i, r, g, b)

    def draw_current_screen(self):
        """Draw the current demo screen"""
        self.fire.clear_display()
        data = self.demo_data[self.current_screen]

        if self.current_screen == ScreenDemo.BASIC_PAGE:
            self.canvas.draw_page(data["title"], data["lines"])

        elif self.current_screen == ScreenDemo.VALUE_PAGE:
            self.canvas.draw_value_page(
                data["title"], data["value"], data["min_val"], data["max_val"]
            )

        elif self.current_screen == ScreenDemo.MENU:
            self.canvas.draw_menu(data["title"], data["items"], data["selected"])

        elif self.current_screen == ScreenDemo.GRID_INFO:
            self.canvas.draw_grid_info(
                data["title"], rows=2, cols=4, cell_info=data["info"]
            )

        elif self.current_screen == ScreenDemo.SPLIT_SCREEN:
            self.canvas.draw_split_screen(data["title"], data["left"], data["right"])

        # Render to display and save debug image

        self.fire.render_to_display()
        self.fire.render_to_bmp(
            os.path.join("_screens", f"{self.current_screen.name.lower()}.bmp")
        )

    def run(self):
        """Run the demo"""
        try:
            print("Screen Layout Demo")
            print("Press any pad to cycle through screen layouts")
            print("Press Ctrl+C to exit")

            # Initial screen setup
            self.update_pad_colors()
            self.draw_current_screen()

            # Keep running until interrupted
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.fire.clear_all()
            self.fire.close()


if __name__ == "__main__":
    demo = ScreenLayoutDemo()
    demo.run()
