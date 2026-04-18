"""Interactive pygame-based mock of the AKAI Fire controller.

Use this mock when developing without hardware and you want a clickable
window that visualizes pad/LED/OLED state. It's what ``get_akai_fire()``
falls back to when no device is found.

For automated tests (headless CI, pytest, etc.) prefer the canonical
testing mock at :class:`akai_fire_testing.mocks.MockAkaiFire`, which
has no pygame dependency, records events, and exposes ``simulate_*``
helpers for deterministic event injection.
"""

import pygame
import math
import threading
import signal
import sys
import atexit
from collections import defaultdict
from typing import Optional, Callable, List, Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
import time


class PygameCanvas:
    """Canvas implementation compatible with the main library's Canvas class."""

    # Standard dimensions (matching real AKAI Fire OLED)
    WIDTH, HEIGHT = 128, 64

    # Typography constants for consistent spacing (matching real Canvas)
    HEADER_HEIGHT = 16  # Standard header height
    TEXT_MARGIN_Y = 3  # Top margin for header text
    CONTENT_GAP = 2  # Gap between header and content
    CONTENT_START = HEADER_HEIGHT + CONTENT_GAP  # Y=18

    def __init__(self):
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), 1)
        self.draw = ImageDraw.Draw(self.image)

    def clone(self):
        """Create a copy of the current canvas."""
        cloned_canvas = PygameCanvas()
        cloned_canvas.image = self.image.copy()
        cloned_canvas.draw = ImageDraw.Draw(cloned_canvas.image)
        return cloned_canvas

    def clear(self, color: int = 1):
        """Clear the canvas."""
        self.image = Image.new("1", (self.WIDTH, self.HEIGHT), color)
        self.draw = ImageDraw.Draw(self.image)

    def get_pixel(self, x, y):
        """Get a pixel from the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            return self.image.getpixel((x, y))
        return None

    def set_pixel(self, x, y, color: int = 0):
        """Set a pixel on the canvas."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.image.putpixel((x, y), color)

    def draw_rect(self, x, y, width, height, color: int = 0):
        """Draw rectangle outline."""
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], outline=color)

    def fill_rect(self, x, y, width, height, color: int = 0):
        """Draw filled rectangle."""
        self.draw.rectangle([x, y, x + width - 1, y + height - 1], fill=color)

    def draw_text(self, text, x, y, font=None, color: int = 0):
        """Draw text."""
        if font is None:
            font = ImageFont.load_default()
        self.draw.text((x, y), text, fill=color, font=font)

    def draw_border(self, thickness: int = 1, color: int = 0):
        """Draw a border around the entire canvas."""
        for i in range(thickness):
            self.draw_rect(i, i, self.WIDTH - 2 * i, self.HEIGHT - 2 * i, color)

    def draw_horizontal_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a horizontal line."""
        self.draw.line([(x, y), (x + length - 1, y)], fill=color)

    def draw_vertical_line(self, x: int, y: int, length: int, color: int = 0):
        """Draw a vertical line."""
        self.draw.line([(x, y), (x, y + length - 1)], fill=color)

    def draw_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Draw a circle."""
        self.draw.ellipse(
            [x0 - radius, y0 - radius, x0 + radius, y0 + radius], outline=color
        )

    def fill_circle(self, x0: int, y0: int, radius: int, color: int = 0):
        """Fill a circle."""
        self.draw.ellipse(
            [x0 - radius, y0 - radius, x0 + radius, y0 + radius], fill=color
        )

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 0):
        """Draw a line."""
        self.draw.line([(x0, y0), (x1, y1)], fill=color)

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Draw a rectangle outline (compatibility method)."""
        self.draw_rect(x, y, width, height, color)

    def fill_rectangle(self, x: int, y: int, width: int, height: int, color: int = 0):
        """Fill a rectangle (compatibility method)."""
        self.fill_rect(x, y, width, height, color)

    # High-level drawing methods for compatibility
    def draw_page(self, title: str, lines: list[str], header_inverted: bool = True):
        """Draw a page with title and lines."""
        self.clear()

        # Header
        if header_inverted:
            self.fill_rect(0, 0, self.WIDTH, 12, color=0)
            self.draw_text(title, 2, 2, color=1)
        else:
            self.draw_text(title, 2, 2, color=0)

        # Lines
        y_offset = 15
        for i, line in enumerate(lines[:4]):  # Max 4 lines
            self.draw_text(line, 2, y_offset + i * 12, color=0)

    def draw_value_page(
        self,
        title: str,
        value,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        show_bar: bool = True,
    ):
        """
        Draw a page showing a value with optional bar visualization.

        Args:
            title: Title text for the header
            value: Current value to display
            min_val: Minimum value for bar scaling (if showing bar)
            max_val: Maximum value for bar scaling (if showing bar)
            show_bar: Whether to show a progress bar
        """
        # Header
        self.fill_rect(0, 0, self.WIDTH, self.HEADER_HEIGHT, color=0)
        self.draw_text(title, 2, self.TEXT_MARGIN_Y, color=1)

        # Large value display
        value_text = str(value)
        self.draw_text(value_text, 2, 20, color=0)

        # Optional bar visualization
        if show_bar and min_val is not None and max_val is not None:
            bar_y = 40
            bar_height = 8
            try:
                normalized = (float(value) - min_val) / (max_val - min_val)
                normalized = max(0.0, min(1.0, normalized))  # Clamp to 0-1
            except (TypeError, ZeroDivisionError):
                normalized = 0.0
            bar_width = int(normalized * (self.WIDTH - 4))

            # Bar outline
            self.draw_rect(2, bar_y, self.WIDTH - 4, bar_height)
            # Bar fill
            if bar_width > 0:
                self.fill_rect(2, bar_y, bar_width, bar_height)

    def draw_menu(self, title: str, items: list[str], selected_index: int):
        """Draw a menu."""
        self.clear()

        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Items
        y_offset = 15
        visible_items = 4
        start_idx = max(0, selected_index - visible_items // 2)

        for i in range(visible_items):
            idx = start_idx + i
            if idx >= len(items):
                break

            y = y_offset + i * 12
            if idx == selected_index:
                self.fill_rect(0, y - 1, self.WIDTH, 12, color=0)
                self.draw_text(f"> {items[idx]}", 2, y, color=1)
            else:
                self.draw_text(f"  {items[idx]}", 2, y, color=0)

    def draw_grid_info(self, title: str, rows: int, cols: int, cell_info: list):
        """Draw grid information."""
        self.clear()

        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Simple grid representation
        y_offset = 15
        self.draw_text(f"Grid: {rows}x{cols}", 2, y_offset, color=0)

        # Show some cell info
        for i, (row, col, text) in enumerate(cell_info[:3]):
            y = y_offset + 15 + i * 10
            self.draw_text(f"[{row},{col}]: {text}", 2, y, color=0)

    def draw_split_screen(
        self, title: str, left_content: list[str], right_content: list[str]
    ):
        """Draw split screen."""
        self.clear()

        # Header
        self.fill_rect(0, 0, self.WIDTH, 12, color=0)
        self.draw_text(title, 2, 2, color=1)

        # Divider
        self.draw_vertical_line(self.WIDTH // 2, 12, self.HEIGHT - 12, color=0)

        # Left content
        y_offset = 15
        for i, line in enumerate(left_content[:4]):
            self.draw_text(line[:10], 2, y_offset + i * 12, color=0)

        # Right content
        for i, line in enumerate(right_content[:4]):
            self.draw_text(line[:10], self.WIDTH // 2 + 2, y_offset + i * 12, color=0)


from akai_fire.device import AkaiFireDevice


class MockAkaiFire(AkaiFireDevice):
    """Interactive pygame mock of the AKAI Fire controller.

    Inherits MIDI constants, modifier state, pad-geometry utilities, and
    solo-button lookup from :class:`AkaiFireDevice`. Adds a pygame window
    with mouse-driven pad / button / rotary simulation.
    """

    def __init__(self, port_name: str = "Mock AKAI Fire"):
        """Initialize the mock controller."""
        super().__init__()  # installs self._lock + modifier flags

        # Initialize pygame with proper Mac settings
        pygame.init()
        pygame.display.init()

        # Window setup
        self.width = 1100
        self.height = 500
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("AKAI Fire Controller - Mock")

        # Track if we've been cleaned up
        self._closed = False

        # Register cleanup handlers
        atexit.register(self._cleanup_atexit)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Fonts
        self.tiny_font = pygame.font.Font(None, 9)
        self.small_font = pygame.font.Font(None, 10)
        self.medium_font = pygame.font.Font(None, 12)

        # Colors
        self.bg_color = (20, 20, 20)
        self.panel_color = (40, 40, 40)

        # Canvas
        self.canvas = PygameCanvas()

        # State
        self.running = True
        self.clock = pygame.time.Clock()
        self.pad_colors = [[0, 0, 0] for _ in range(64)]
        self.button_leds = {}
        self.track_leds = [0, 0, 0, 0]
        self.control_bank_state = 0

        # Listener registries (pad_listeners / button_listeners /
        # rotary_listeners / rotary_touch_listeners) are provided by
        # AkaiFireDevice.__init__.

        # UI Elements
        self.pad_rects = []
        self.button_rects = {}
        self.rotary_data = {}

        # Thread safety
        self.event_queue = []
        self.queue_lock = threading.Lock()

        self._create_layout()

        # Modifier state (self._shift_pressed / self._alt_pressed) is
        # latched directly in _handle_mouse_down / _handle_mouse_up;
        # no separate listener registration is required.

    def _create_layout(self):
        """Create the visual layout matching real hardware."""
        # Base positions
        base_x = 50
        base_y = 30

        # Create pads (4x16 grid)
        # Grid is 16 cols × 4 rows, each pad 32px + 2px gap = 544px wide, 136px tall
        pad_size = 32
        pad_gap = 2
        pad_start_x = base_x + 230  # Moved right to make room for SOLO buttons
        pad_start_y = base_y + 170  # Moved down to make room for OLED above

        for row in range(4):
            for col in range(16):
                x = pad_start_x + col * (pad_size + pad_gap)
                y = pad_start_y + row * (pad_size + pad_gap)
                rect = pygame.Rect(x, y, pad_size, pad_size)
                self.pad_rects.append(rect)

        # Rotary encoders (top row, left of OLED)
        rotary_y = base_y + 50
        self.rotary_data = {
            self.ROTARY_VOLUME: {
                "pos": (base_x + 80, rotary_y),
                "value": 64,
                "name": "VOLUME",
            },
            self.ROTARY_PAN: {
                "pos": (base_x + 160, rotary_y),
                "value": 64,
                "name": "PAN",
            },
            self.ROTARY_FILTER: {
                "pos": (base_x + 240, rotary_y),
                "value": 64,
                "name": "FILTER",
            },
            self.ROTARY_RESONANCE: {
                "pos": (base_x + 320, rotary_y),
                "value": 64,
                "name": "RESONANCE",
            },
            self.ROTARY_SELECT: {
                "pos": (base_x + 950, base_y + 200),
                "value": 64,
                "name": "SELECT",
            },
        }

        # Buttons
        # Left side - control bank (above SOLO buttons)
        self.button_rects[self.BUTTON_BANK] = pygame.Rect(
            base_x + 20, base_y + 130, 35, 18
        )
        self.button_rects[self.BUTTON_SELECT] = pygame.Rect(
            base_x + 60, base_y + 130, 40, 18
        )

        # Left side - mute/solo (next to pad grid)
        for i in range(4):
            self.button_rects[self.BUTTON_SOLO_1 + i] = pygame.Rect(
                base_x + 190, base_y + 170 + i * 36, 22, 22
            )

        # Right side - pattern controls (below OLED, right of grid)
        self.button_rects[self.BUTTON_PAT_UP] = pygame.Rect(
            base_x + 830, base_y + 170, 30, 22
        )
        self.button_rects[self.BUTTON_PAT_DOWN] = pygame.Rect(
            base_x + 830, base_y + 196, 30, 22
        )
        self.button_rects[self.BUTTON_PATTERN] = pygame.Rect(
            base_x + 865, base_y + 170, 55, 48
        )

        # Browser (right side, below pattern)
        self.button_rects[self.BUTTON_BROWSER] = pygame.Rect(
            base_x + 830, base_y + 230, 90, 25
        )

        # Grid navigation (right side, below browser)
        self.button_rects[self.BUTTON_GRID_LEFT] = pygame.Rect(
            base_x + 830, base_y + 265, 40, 22
        )
        self.button_rects[self.BUTTON_GRID_RIGHT] = pygame.Rect(
            base_x + 880, base_y + 265, 40, 22
        )

        # Bottom row - mode buttons (below pad grid)
        bottom_y = base_y + 330
        self.button_rects[self.BUTTON_STEP] = pygame.Rect(
            base_x + 230, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_NOTE] = pygame.Rect(
            base_x + 276, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_DRUM] = pygame.Rect(
            base_x + 322, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_PERFORM] = pygame.Rect(
            base_x + 368, bottom_y, 55, 22
        )

        # Shift/Alt (center-right of mode buttons)
        self.button_rects[self.BUTTON_SHIFT] = pygame.Rect(
            base_x + 500, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_ALT] = pygame.Rect(base_x + 546, bottom_y, 35, 22)

        # Transport (right side of bottom row)
        self.button_rects[self.BUTTON_PLAY] = pygame.Rect(
            base_x + 680, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_STOP] = pygame.Rect(
            base_x + 726, bottom_y, 42, 22
        )
        self.button_rects[self.BUTTON_REC] = pygame.Rect(base_x + 772, bottom_y, 42, 22)

    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM for clean shutdown."""
        self.running = False

    def _cleanup_atexit(self):
        """Cleanup handler for atexit."""
        if not self._closed:
            self.close()

    def process_events(self):
        """Process events - must be called from main thread."""
        if not self.running or self._closed:
            return False

        # Check if pygame is still initialized
        if not pygame.display.get_init():
            self.running = False
            return False

        try:
            dt = self.clock.tick(60) / 1000.0

            # Pump events to prevent "not responding" on Mac
            pygame.event.pump()

            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._handle_mouse_up(event)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)

            # Process queued updates
            with self.queue_lock:
                for func in self.event_queue:
                    func()
                self.event_queue.clear()

            # Draw
            self._draw()

            return True

        except pygame.error:
            # Pygame was quit externally
            self.running = False
            return False

    def _handle_mouse_down(self, event):
        """Handle mouse button down."""
        # Check pads
        for i, rect in enumerate(self.pad_rects):
            if rect.collidepoint(event.pos):
                self._dispatch_pad(i, 100)
                return

        # Check buttons — modifier-first latching happens inside _dispatch_button.
        for button_id, rect in self.button_rects.items():
            if rect.collidepoint(event.pos):
                self._dispatch_button(button_id, "press")
                return

    def _handle_mouse_up(self, event):
        """Handle mouse button up."""
        for button_id, rect in self.button_rects.items():
            if rect.collidepoint(event.pos):
                self._dispatch_button(button_id, "release")
                return

    def _handle_mouse_motion(self, event):
        """Handle mouse motion for rotary encoders."""
        if event.buttons[0]:  # Left button held
            for rotary_id, data in self.rotary_data.items():
                x, y = data["pos"]
                if abs(event.pos[0] - x) < 25 and abs(event.pos[1] - y) < 25:
                    delta = -event.rel[1]
                    new_val = max(0, min(127, data["value"] + delta))
                    data["value"] = new_val

                    if delta != 0:
                        direction = "clockwise" if delta > 0 else "counterclockwise"
                        self._dispatch_rotary_turn(rotary_id, direction, abs(delta))

    def _draw(self):
        """Draw the interface."""
        if self._closed or not pygame.display.get_init():
            return

        self.screen.fill(self.bg_color)

        # Main panel
        panel = pygame.Rect(40, 20, self.width - 80, self.height - 40)
        pygame.draw.rect(self.screen, self.panel_color, panel, border_radius=5)

        base_x = 50
        base_y = 30

        # Draw control bank section (left side, above SOLO buttons)
        self._draw_control_bank(base_x + 20, base_y + 40)

        # Draw mute/solo section (left of pad grid)
        self._draw_mute_solo(base_x + 155, base_y + 155)

        # Draw pads
        for i, rect in enumerate(self.pad_rects):
            color = self.pad_colors[i]
            # Convert 0-127 to 0-255
            display_color = [c * 2 for c in color]

            # Draw pad background
            pygame.draw.rect(self.screen, (25, 25, 25), rect)

            # Draw pad surface
            inner = rect.inflate(-4, -4)
            if sum(display_color) > 20:
                pygame.draw.rect(self.screen, display_color, inner, border_radius=2)
            else:
                pygame.draw.rect(self.screen, (45, 45, 45), inner, border_radius=2)

        # Draw rotary encoders
        for rotary_id, data in self.rotary_data.items():
            x, y = data["pos"]
            radius = 18 if rotary_id != self.ROTARY_SELECT else 22

            # Outer ring
            pygame.draw.circle(self.screen, (60, 60, 60), (x, y), radius)
            pygame.draw.circle(self.screen, (80, 80, 80), (x, y), radius, 2)

            # Inner
            pygame.draw.circle(self.screen, (40, 40, 40), (x, y), radius - 4)

            # Position indicator
            angle = (data["value"] - 64) / 64 * 135 * math.pi / 180
            end_x = x + int(math.sin(angle) * (radius - 6))
            end_y = y - int(math.cos(angle) * (radius - 6))
            pygame.draw.line(self.screen, (180, 180, 180), (x, y), (end_x, end_y), 2)

            # Label
            text = self.tiny_font.render(data["name"], True, (140, 140, 140))
            text_rect = text.get_rect(center=(x, y + radius + 10))
            self.screen.blit(text, text_rect)

        # Draw OLED (centered above pad grid, 2x scale)
        # OLED is 256x128 (2x scaled), pad grid starts at base_x + 230
        # Center OLED over pad grid: pad grid is 544px wide, OLED is 256px
        # (544 - 256) / 2 = 144, so OLED x = base_x + 230 + 144 = base_x + 374
        self._draw_oled(base_x + 374, base_y + 10)

        # Draw buttons
        button_labels = {
            self.BUTTON_STEP: "STEP",
            self.BUTTON_NOTE: "NOTE",
            self.BUTTON_DRUM: "DRUM",
            self.BUTTON_PERFORM: "PERFORM",
            self.BUTTON_SHIFT: "SHIFT",
            self.BUTTON_ALT: "ALT",
            self.BUTTON_PLAY: "PLAY",
            self.BUTTON_STOP: "STOP",
            self.BUTTON_REC: "REC",
            self.BUTTON_PATTERN: "PATTERN",
            self.BUTTON_BROWSER: "BROWSER",
            self.BUTTON_BANK: "BANK",
            self.BUTTON_SELECT: "SELECT",
            self.BUTTON_PAT_UP: "UP",
            self.BUTTON_PAT_DOWN: "DOWN",
            self.BUTTON_GRID_LEFT: "L",
            self.BUTTON_GRID_RIGHT: "R",
        }

        for button_id, rect in self.button_rects.items():
            # Skip solo buttons (drawn separately)
            if button_id >= self.BUTTON_SOLO_1 and button_id <= self.BUTTON_SOLO_4:
                continue

            # Button color
            led_state = self.button_leds.get(button_id, 0)
            if led_state == 2:
                color = (200, 100, 0)
            elif led_state == 1:
                color = (100, 50, 0)
            else:
                color = (50, 50, 50)

            pygame.draw.rect(self.screen, color, rect, border_radius=2)
            pygame.draw.rect(self.screen, (80, 80, 80), rect, width=1, border_radius=2)

            # Label
            if button_id in button_labels:
                font = (
                    self.tiny_font
                    if len(button_labels[button_id]) > 4
                    else self.small_font
                )
                text = font.render(button_labels[button_id], True, (180, 180, 180))
                text_rect = text.get_rect(center=rect.center)
                self.screen.blit(text, text_rect)

        # Grid label
        grid_x = (
            self.button_rects[self.BUTTON_GRID_LEFT].right
            + self.button_rects[self.BUTTON_GRID_RIGHT].left
        ) // 2
        grid_y = self.button_rects[self.BUTTON_GRID_LEFT].centery
        grid_text = self.small_font.render("GRID", True, (120, 120, 120))
        grid_rect = grid_text.get_rect(center=(grid_x, grid_y))
        self.screen.blit(grid_text, grid_rect)

        # Branding (bottom right area)
        akai_text = self.medium_font.render("AKAI", True, (200, 200, 200))
        pro_text = self.tiny_font.render("PROFESSIONAL", True, (120, 120, 120))
        self.screen.blit(akai_text, (base_x + 830, base_y + 320))
        self.screen.blit(pro_text, (base_x + 830, base_y + 332))

        fire_text = self.medium_font.render("FIRE", True, (200, 200, 200))
        self.screen.blit(fire_text, (base_x + 980, base_y + 10))

        pygame.display.flip()

    def _draw_control_bank(self, x, y):
        """Draw control bank indicators."""
        controls = [
            ("CHANNEL", self.FIELD_CHANNEL),
            ("MIXER", self.FIELD_MIXER),
            ("USER 1", self.FIELD_USER1),
            ("USER 2", self.FIELD_USER2),
        ]

        for i, (label, field) in enumerate(controls):
            cy = y + i * 18

            # LED
            active = bool(self.control_bank_state & field)
            led_color = (0, 180, 0) if active else (30, 30, 30)
            pygame.draw.circle(self.screen, led_color, (x, cy), 3)
            pygame.draw.circle(self.screen, (60, 60, 60), (x, cy), 3, 1)

            # Label
            text = self.tiny_font.render(label, True, (140, 140, 140))
            self.screen.blit(text, (x + 10, cy - 4))

    def _draw_mute_solo(self, x, y):
        """Draw mute/solo section."""
        # Labels
        mute_text = self.small_font.render("MUTE", True, (120, 120, 120))
        solo_text = self.small_font.render("SOLO", True, (120, 120, 120))
        self.screen.blit(mute_text, (x - 30, y))
        self.screen.blit(solo_text, (x - 30, y + 72))

        # Buttons and track LEDs
        for i in range(4):
            cy = y + 15 + i * 36

            # Track LED
            led_color = (30, 30, 30)
            if self.track_leds[i] == 2:
                led_color = (0, 200, 0)
            elif self.track_leds[i] == 1:
                led_color = (0, 100, 0)

            pygame.draw.circle(self.screen, led_color, (x + 10, cy), 6)
            pygame.draw.circle(self.screen, (60, 60, 60), (x + 10, cy), 6, 1)

            # Solo button
            button_rect = self.button_rects[self.BUTTON_SOLO_1 + i]
            led_state = self.button_leds.get(self.BUTTON_SOLO_1 + i, 0)

            if led_state > 0:
                color = (200, 100, 0)
            else:
                color = (50, 50, 50)

            pygame.draw.circle(self.screen, color, button_rect.center, 10)
            pygame.draw.circle(self.screen, (80, 80, 80), button_rect.center, 10, 1)

            # Number
            text = self.small_font.render(str(i + 1), True, (180, 180, 180))
            text_rect = text.get_rect(center=button_rect.center)
            self.screen.blit(text, text_rect)

    def _draw_oled(self, x, y):
        """Draw OLED display (2x scaled: 256x128)."""
        # Convert canvas to pygame
        pil_image = self.canvas.image.convert("RGB")
        raw_str = pil_image.tobytes("raw", "RGB")
        pygame_image = pygame.image.fromstring(raw_str, (128, 64), "RGB")

        # Scale 2x (256x128)
        scaled = pygame.transform.scale(pygame_image, (256, 128))

        # Apply contrast
        for py in range(128):
            for px in range(256):
                color = scaled.get_at((px, py))
                if color[0] > 128:
                    scaled.set_at((px, py), (0, 0, 0))
                else:
                    scaled.set_at((px, py), (180, 180, 180))

        # Frame (256x128 + 6px border)
        frame_rect = pygame.Rect(x - 3, y - 3, 262, 134)
        pygame.draw.rect(self.screen, (25, 25, 25), frame_rect, border_radius=2)
        pygame.draw.rect(
            self.screen, (60, 60, 60), frame_rect, width=1, border_radius=2
        )

        # Display
        self.screen.blit(scaled, (x, y))

    # Public API
    def set_pad_color(self, index: int, red: int, green: int, blue: int):
        """Set pad color."""
        if 0 <= index < 64:

            def update():
                self.pad_colors[index] = [red, green, blue]

            with self.queue_lock:
                self.event_queue.append(update)

    def set_multiple_pad_colors(self, pad_colors: list):
        """
        Set multiple pad colors efficiently.

        Args:
            pad_colors: List of (index, red, green, blue) tuples

        Returns:
            bool: True if successful
        """

        def update():
            for pad_data in pad_colors:
                if len(pad_data) == 4:
                    index, red, green, blue = pad_data
                    if 0 <= index < 64:
                        # Clamp values to valid range
                        red = max(0, min(127, red))
                        green = max(0, min(127, green))
                        blue = max(0, min(127, blue))
                        self.pad_colors[index] = [red, green, blue]

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def set_pad_color_fast(self, index: int, red: int, green: int, blue: int):
        """Fast path for setting pad color - assumes valid inputs."""

        def update():
            self.pad_colors[index] = [red, green, blue]

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def set_all_pads(self, color: tuple):
        """Set all pads to the same color - optimized version."""
        r, g, b = color

        def update():
            for i in range(64):
                self.pad_colors[i] = [r, g, b]

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def set_button_led(self, button_id: int, value: int):
        """Set button LED."""

        def update():
            self.button_leds[button_id] = value

        with self.queue_lock:
            self.event_queue.append(update)

    def set_track_led(self, track_number: int, value: int):
        """Set track LED."""
        if 1 <= track_number <= 4:

            def update():
                self.track_leds[track_number - 1] = value

            with self.queue_lock:
                self.event_queue.append(update)

    def set_control_bank_leds(self, state: int):
        """Set control bank state."""

        def update():
            self.control_bank_state = state

        with self.queue_lock:
            self.event_queue.append(update)

    def clear_all_pads(self):
        """Clear all pads."""
        for i in range(64):
            self.set_pad_color(i, 0, 0, 0)

    def clear_all_button_leds(self):
        """Clear all button LEDs."""
        for button_id in self.button_rects:
            self.set_button_led(button_id, 0)

    def clear_all_track_leds(self):
        """Clear track LEDs."""
        for i in range(1, 5):
            self.set_track_led(i, 0)

    def clear_control_bank_leds(self):
        """Clear control bank LEDs."""
        self.set_control_bank_leds(0)

    def clear_all(self):
        """Clear everything."""
        self.clear_all_pads()
        self.clear_all_button_leds()
        self.clear_all_track_leds()
        self.clear_control_bank_leds()
        self.canvas.clear()

    def get_canvas(self):
        """Get canvas."""
        return self.canvas

    def new_canvas(self):
        """New canvas."""
        self.canvas = PygameCanvas()
        return self.canvas

    def render_to_display(self, canvas=None):
        """Push the given canvas to the simulated OLED.

        Matches ``AkaiFire.render_to_display`` so code written against
        the hardware works unchanged under the mock. If ``canvas`` is
        supplied, it becomes the mock's current canvas (mirroring the
        real behaviour where the bitmap you pass is what the display
        shows next frame); if omitted, the current internal canvas is
        used.
        """
        if canvas is not None:
            self.canvas = canvas

    def render_to_bmp(self, filename, image_format="BMP"):
        """Save the current canvas to an image file."""
        self.canvas.image.save(filename, image_format)

    def clear_display(self):
        """Clear the OLED display."""
        self.canvas.clear()
        self.render_to_display()

    def close(self):
        """Close mock - safe to call multiple times."""
        if self._closed:
            return

        self._closed = True
        self.running = False

        try:
            # Unregister atexit handler to prevent double cleanup
            atexit.unregister(self._cleanup_atexit)
        except Exception:
            pass

        try:
            if pygame.display.get_init():
                pygame.display.quit()
            if pygame.get_init():
                pygame.quit()
        except Exception:
            pass

    # Decorators, listener adders, on_solo — all inherited from
    # AkaiFireDevice. start_listening is a no-op (already on base).

    # Compatibility helpers (single-pad / single-track clears)

    def reset_pads(self, red=0, green=0, blue=0):
        """Reset all pads."""
        for i in range(64):
            self.set_pad_color(i, red, green, blue)

    def clear_pad(self, index: int) -> bool:
        """Clear a single pad."""
        return self.set_pad_color(index, 0, 0, 0)

    def clear_track_led(self, track_number: int) -> bool:
        """Clear a single track LED."""
        return self.set_track_led(track_number, 0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clears display and closes connection"""
        self.clear_display()
        self.close()


if __name__ == "__main__":
    fire = MockAkaiFire()

    @fire.on_pad()
    def pad_handler(pad_idx, velocity):
        print(f"Pad {pad_idx} pressed")
        import random

        fire.set_pad_color(
            pad_idx,
            random.randint(0, 127),
            random.randint(0, 127),
            random.randint(0, 127),
        )

    @fire.on_button(fire.BUTTON_PLAY)
    def play_handler(event):
        if event == "press":
            fire.set_button_led(fire.BUTTON_PLAY, 2)
        else:
            fire.set_button_led(fire.BUTTON_PLAY, 0)

    # Setup display
    canvas = fire.get_canvas()
    canvas.clear()
    canvas.draw_text("AKAI Fire Mock", 20, 10)
    canvas.draw_text("Final Version", 25, 25)
    canvas.draw_text("Click to test", 25, 45)
    fire.render_to_display()

    # Initial state
    fire.set_control_bank_leds(fire.FIELD_BASE | fire.FIELD_CHANNEL)
    fire.set_track_led(1, 2)

    # Main loop
    try:
        while fire.running:
            if not fire.process_events():
                break
    except KeyboardInterrupt:
        pass
    finally:
        fire.close()
