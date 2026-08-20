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


from akai_fire import Canvas
from akai_fire.device import AkaiFireDevice
from akai_fire.errors import InvalidParameterError


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

        # Remember whether pygame was already initialized before us so
        # close() only tears down what we own (another mock instance or
        # an embedding app may share the process-global pygame state).
        self._we_initialized_pygame = not pygame.get_init()

        # Register cleanup handlers
        atexit.register(self._cleanup_atexit)
        self._install_signal_handlers()

        # Fonts
        self.tiny_font = pygame.font.Font(None, 9)
        self.small_font = pygame.font.Font(None, 10)
        self.medium_font = pygame.font.Font(None, 12)

        # Colors
        self.bg_color = (20, 20, 20)
        self.panel_color = (40, 40, 40)

        # Canvas
        self.canvas = Canvas()

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

    def _install_signal_handlers(self):
        """Route SIGINT/SIGTERM into a clean shutdown.

        The previous handlers are remembered so :meth:`close` can
        restore them — a mock must not permanently swallow Ctrl-C for
        the whole process. Installation is skipped when not on the main
        thread (``signal.signal`` raises ``ValueError`` there).
        """
        try:
            self._previous_signal_handlers = {
                sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)
            }
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # Not on the main thread — leave process signal handling alone.
            self._previous_signal_handlers = None

    def _restore_signal_handlers(self):
        previous = getattr(self, "_previous_signal_handlers", None)
        if not previous:
            return
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        self._previous_signal_handlers = None

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
    def set_pad_color(self, index: int, red: int, green: int, blue: int) -> bool:
        """Set pad color.

        Raises:
            InvalidParameterError: If pad index is out of range
                (matching real hardware).
        """
        if not isinstance(index, int) or not (0 <= index <= 63):
            raise InvalidParameterError(f"Pad index must be integer 0-63, got: {index}")

        def update():
            self.pad_colors[index] = [red, green, blue]

        with self.queue_lock:
            self.event_queue.append(update)
        return True

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

    def set_button_led(self, button_id: int, value: int) -> bool:
        """Set button LED.

        Raises:
            InvalidParameterError: If button_id is not an addressable
                LED button (matching real hardware).
        """
        if button_id not in self.BUTTON_LED_IDS:
            raise InvalidParameterError(
                f"Invalid button ID: {button_id}. "
                f"Valid buttons: {sorted(self.BUTTON_LED_IDS)}"
            )
        value = max(0, min(2, value))

        def update():
            self.button_leds[button_id] = value

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def set_track_led(self, track_number: int, value: int) -> bool:
        """Set track LED (1-4). ``value`` is a RECTANGLE_LED_* constant (0-4)."""
        if not (1 <= track_number <= 4):
            return False
        value = max(0, min(4, value))

        def update():
            self.track_leds[track_number - 1] = value

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def clear_all_pads(self) -> bool:
        """Clear all pads."""
        for i in range(64):
            self.set_pad_color(i, 0, 0, 0)
        return True

    def clear_all_button_leds(self) -> bool:
        """Clear all button LEDs."""
        for button_id in self.button_rects:
            self.set_button_led(button_id, 0)
        return True

    def clear_all_track_leds(self) -> bool:
        """Clear track LEDs."""
        for i in range(1, 5):
            self.set_track_led(i, 0)
        return True

    def clear_control_bank_leds(self) -> bool:
        """Clear control bank LEDs."""
        return self.set_control_bank_leds(0)

    def set_control_bank_leds(self, state: int) -> bool:
        """Set control bank state."""

        def update():
            self.control_bank_state = state

        with self.queue_lock:
            self.event_queue.append(update)
        return True

    def clear_all(self):
        """Clear everything."""
        self.clear_all_pads()
        self.clear_all_button_leds()
        self.clear_all_track_leds()
        self.clear_control_bank_leds()
        self.canvas.clear()

    # get_canvas / render_to_display / render_to_bmp / clear_display
    # are inherited from AkaiFireDevice.

    def new_canvas(self):
        """New canvas."""
        self.canvas = Canvas()
        return self.canvas

    def _deliver_display(self, canvas) -> None:
        """No-op: the pygame draw loop reads ``self.canvas`` directly each frame."""

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

        self._restore_signal_handlers()

        try:
            # Only tear down the display; never pygame.quit() the whole
            # module — other consumers (a second mock instance, or an
            # embedding app) may share the process-global pygame state.
            if pygame.display.get_init():
                pygame.display.quit()
            if self._we_initialized_pygame and pygame.get_init():
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
