"""Interactive pygame-based mock of the AKAI Fire controller.

Use this mock when developing without hardware and you want a clickable
window that visualizes pad/LED/OLED state. It's what ``get_akai_fire()``
falls back to when no device is found.

For automated tests (headless CI, pytest, etc.) prefer the canonical
testing mock at :class:`akai_fire_testing.mocks.MockAkaiFire`, which
has no pygame dependency, records events, and exposes ``simulate_*``
helpers for deterministic event injection.
"""

import atexit
import math
import signal
import threading

import pygame

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
        self.width = 1120
        self.height = 640
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
        font = pygame.font.get_default_font()
        self.tiny_font = pygame.font.Font(font, 9)
        self.small_font = pygame.font.Font(font, 11)
        self.medium_font = pygame.font.Font(font, 13)
        self.brand_font = pygame.font.Font(font, 32)
        self.fire_font = pygame.font.SysFont("helvetica neue,helvetica,arial", 36)

        # Colors
        self.bg_color = (21, 23, 26)
        self.panel_color = (31, 32, 34)
        self.label_color = (218, 221, 219)
        self.secondary_color = (164, 171, 172)
        self.unlit_color = (159, 175, 181)
        self.red = (255, 46, 36)
        self.green = (112, 240, 44)
        self.yellow = (255, 213, 52)

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
        self._pressed_buttons = set()
        self._pressed_pad = None
        self._drag_rotary = None

        # Thread safety
        self.event_queue = []
        self.queue_lock = threading.Lock()

        self._create_layout()

        # Modifier state (self._shift_pressed / self._alt_pressed) is
        # latched directly in _handle_mouse_down / _handle_mouse_up;
        # no separate listener registration is required.

    def _create_layout(self):
        """One coordinate map for drawing and hit testing, based on the top panel.

        Pads are taller than they are wide, with four groups of four steps.
        SELECT is the encoder's push switch, not a separate panel button.
        """
        self.panel_rect = pygame.Rect(24, 24, 1072, 564)
        self.oled_rect = pygame.Rect(642, 82, 128, 64)
        self.pad_rects = [
            pygame.Rect(132 + col * 58, 192 + row * 75, 40, 56)
            for row in range(4)
            for col in range(16)
        ]
        self.track_led_rects = [
            pygame.Rect(105, self.pad_rects[row * 16].centery - 14, 8, 28)
            for row in range(4)
        ]
        self.rotary_data = {
            rotary: {"pos": (x, 112), "value": 64, "name": name, "radius": 29}
            for rotary, x, name in (
                (self.ROTARY_VOLUME, 164, "VOLUME"),
                (self.ROTARY_PAN, 284, "PAN"),
                (self.ROTARY_FILTER, 404, "FILTER"),
                (self.ROTARY_RESONANCE, 524, "RESONANCE"),
                (self.ROTARY_SELECT, 886, "SELECT"),
            )
        }
        self.button_rects = {
            self.BUTTON_BANK: pygame.Rect(52, 144, 44, 20),
            self.BUTTON_PAT_UP: pygame.Rect(578, 74, 44, 22),
            self.BUTTON_PAT_DOWN: pygame.Rect(578, 138, 44, 22),
            self.BUTTON_BROWSER: pygame.Rect(790, 94, 44, 36),
            self.BUTTON_SELECT: pygame.Rect(857, 83, 58, 58),
            self.BUTTON_GRID_LEFT: pygame.Rect(940, 101, 44, 22),
            self.BUTTON_GRID_RIGHT: pygame.Rect(1018, 101, 44, 22),
        }
        for row in range(4):
            self.button_rects[self.BUTTON_SOLO_1 + row] = pygame.Rect(
                60, self.pad_rects[row * 16].centery - 14, 28, 28
            )
        for button, x in (
            (self.BUTTON_STEP, 52),
            (self.BUTTON_NOTE, 132),
            (self.BUTTON_DRUM, 212),
            (self.BUTTON_PERFORM, 292),
            (self.BUTTON_SHIFT, 372),
            (self.BUTTON_ALT, 452),
            (self.BUTTON_PATTERN, 778),
            (self.BUTTON_PLAY, 858),
            (self.BUTTON_STOP, 938),
            (self.BUTTON_REC, 1018),
        ):
            self.button_rects[button] = pygame.Rect(x, 518, 44, 36)

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
            self.clock.tick(60)

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
                elif event.type == pygame.MOUSEWHEEL:
                    self._handle_mouse_wheel(event)
                elif event.type == pygame.WINDOWFOCUSLOST:
                    self._release_input()

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

    def _rotary_at(self, pos):
        for rotary_id, data in self.rotary_data.items():
            x, y = data["pos"]
            if math.hypot(pos[0] - x, pos[1] - y) <= data["radius"] + 3:
                return rotary_id
        return None

    def _turn_rotary(self, rotary_id, delta):
        if delta:
            data = self.rotary_data[rotary_id]
            data["value"] = max(0, min(127, data["value"] + delta))
            direction = "clockwise" if delta > 0 else "counterclockwise"
            self._dispatch_rotary_turn(rotary_id, direction, abs(delta))

    def _handle_mouse_down(self, event):
        """Capture a knob drag; a SELECT click is its separate push switch."""
        mouse_button = getattr(event, "button", 1)
        if mouse_button != 1:
            return
        rotary = self._rotary_at(event.pos)
        if rotary is not None:
            self._drag_rotary = rotary
            self._rotary_moved = False
            self._dispatch_rotary_touch(rotary, "touch")
            return
        for index, rect in enumerate(self.pad_rects):
            if rect.collidepoint(event.pos):
                self._pressed_pad = index
                self._dispatch_pad(index, 100)
                return
        for button_id, rect in self.button_rects.items():
            if button_id != self.BUTTON_SELECT and rect.collidepoint(event.pos):
                self._pressed_buttons.add(button_id)
                self._dispatch_button(button_id, "press")
                return

    def _handle_mouse_up(self, event):
        if getattr(event, "button", 1) != 1:
            return
        if self._drag_rotary is not None:
            rotary = self._drag_rotary
            self._drag_rotary = None
            self._dispatch_rotary_touch(rotary, "release")
            if (
                rotary == self.ROTARY_SELECT
                and not self._rotary_moved
                and self._rotary_at(event.pos) == rotary
            ):
                self._dispatch_button(self.BUTTON_SELECT, "press")
                self._dispatch_button(self.BUTTON_SELECT, "release")
        self._pressed_pad = None
        # Release the captured button even when the mouse has left its bounds.
        hit = next(
            (
                button
                for button in self._pressed_buttons
                if self.button_rects[button].collidepoint(event.pos)
            ),
            None,
        )
        released = {hit} if hit is not None else self._pressed_buttons.copy()
        for button in released:
            self._pressed_buttons.discard(button)
            self._dispatch_button(button, "release")

    def _handle_mouse_motion(self, event):
        if not event.buttons[0]:
            return
        rotary = (
            self._drag_rotary
            if self._drag_rotary is not None
            else self._rotary_at(event.pos)
        )
        if rotary is not None:
            delta = -event.rel[1]
            if delta:
                self._rotary_moved = True
                self._turn_rotary(rotary, delta)

    def _handle_mouse_wheel(self, event):
        rotary = self._rotary_at(pygame.mouse.get_pos())
        if rotary is not None:
            self._turn_rotary(rotary, event.y)

    def _release_input(self):
        """Losing focus must not leave a modifier or knob touch held down."""
        self._pressed_pad = None
        if self._drag_rotary is not None:
            rotary, self._drag_rotary = self._drag_rotary, None
            self._dispatch_rotary_touch(rotary, "release")
        for button in tuple(self._pressed_buttons):
            self._pressed_buttons.discard(button)
            self._dispatch_button(button, "release")

    def _text(self, text, center, font=None, color=None):
        font = font or self.small_font
        surface = font.render(text, True, color or self.label_color)
        self.screen.blit(surface, surface.get_rect(center=center))

    @staticmethod
    def _mix(first, second, amount):
        return tuple(round(a + (b - a) * amount) for a, b in zip(first, second))

    def _button_color(self, button_id):
        # The MIDI value is brightness (0/1/2); the physical button fixes its hue.
        state = self.button_leds.get(button_id, 0)
        if not state:
            return self.unlit_color
        if button_id in (
            self.BUTTON_REC,
            self.BUTTON_PAT_UP,
            self.BUTTON_PAT_DOWN,
            self.BUTTON_GRID_LEFT,
            self.BUTTON_GRID_RIGHT,
        ):
            hue = self.red
        elif (
            button_id == self.BUTTON_PLAY
            or self.BUTTON_SOLO_1 <= button_id <= self.BUTTON_SOLO_4
        ):
            hue = self.green
        else:
            hue = self.yellow
        return self._mix(self.unlit_color, hue, 0.45 if state == 1 else 1)

    def _draw_key(self, rect, color, pressed=False):
        """A recessed socket and translucent cap, with a restrained lit center."""
        pygame.draw.rect(self.screen, (12, 13, 14), rect.inflate(6, 6), border_radius=5)
        pygame.draw.rect(
            self.screen, self._mix(color, (52, 59, 63), 0.45), rect, border_radius=3
        )
        cap = rect.inflate(-4, -4)
        if pressed:
            color = self._mix(color, (255, 255, 255), 0.25)
        pygame.draw.rect(self.screen, color, cap, border_radius=2)
        # Small successive insets suggest the LED diffusing through rubber.
        for inset in range(1, 5):
            inner = cap.inflate(-inset * 2, -inset * 2)
            if inner.width > 0 and inner.height > 0:
                pygame.draw.rect(
                    self.screen,
                    self._mix(color, (243, 247, 239), inset * 0.025),
                    inner,
                    border_radius=2,
                )
        pygame.draw.line(
            self.screen,
            self._mix(color, (255, 255, 255), 0.38),
            (cap.left + 2, cap.top),
            (cap.right - 3, cap.top),
        )

    def _draw(self):
        """Draw a top-down Fire; all input rectangles are shared with the renderer."""
        if self._closed or not pygame.display.get_init():
            return
        self.screen.fill(self.bg_color)
        pygame.draw.rect(
            self.screen, (11, 12, 14), self.panel_rect.move(0, 5), border_radius=8
        )
        pygame.draw.rect(self.screen, (66, 69, 71), self.panel_rect, border_radius=6)
        pygame.draw.rect(
            self.screen,
            self.panel_color,
            self.panel_rect.inflate(-4, -4),
            border_radius=5,
        )
        pygame.draw.line(self.screen, (79, 81, 82), (31, 27), (1088, 27))

        self._draw_control_bank()
        self._draw_mute_solo()

        # The hardware divides the sequencer into four groups of four steps.
        for col in (4, 8, 12):
            x = self.pad_rects[col].left - 9
            pygame.draw.line(self.screen, (69, 73, 75), (x, 188), (x, 477))
        for index, rect in enumerate(self.pad_rects):
            rgb = self.pad_colors[index]
            color = self.unlit_color
            if any(rgb):
                color = tuple(round(18 + max(0, min(127, c)) * 237 / 127) for c in rgb)
            self._draw_key(rect, color, index == self._pressed_pad)
            # Small black registration mark on each physical pad.
            mark = pygame.Rect(rect.centerx - 7, rect.top + 9, 14, 4)
            pygame.draw.rect(self.screen, (45, 50, 51), mark, border_radius=1)

        for rotary_id, data in self.rotary_data.items():
            self._draw_rotary(rotary_id, data)
        self._draw_oled()

        for button_id, rect in self.button_rects.items():
            if (
                button_id == self.BUTTON_SELECT
                or self.BUTTON_SOLO_1 <= button_id <= self.BUTTON_SOLO_4
            ):
                continue
            self._draw_key(
                rect, self._button_color(button_id), button_id in self._pressed_buttons
            )

        self._draw_legends()
        self._text("AKAI", (668, 536), self.brand_font)
        self._text("P R O F E S S I O N A L", (668, 561), self.tiny_font)
        self._text("FIRE", (1000, 61), self.fire_font)
        self._text(
            "Click pads / buttons   ·   Drag knobs vertically   ·   Scroll to turn   ·   Click SELECT to press",
            (560, 615),
            self.small_font,
            self.secondary_color,
        )
        pygame.display.flip()

    def _draw_rotary(self, rotary_id, data):
        x, y = data["pos"]
        radius = data["radius"]
        pygame.draw.circle(self.screen, (13, 14, 16), (x, y + 3), radius + 5)
        pygame.draw.circle(self.screen, (82, 86, 88), (x, y), radius + 1)
        pygame.draw.circle(self.screen, (38, 41, 44), (x, y), radius)
        for tick in range(28):
            angle = tick * math.tau / 28
            start = (
                x + math.sin(angle) * (radius - 4),
                y + math.cos(angle) * (radius - 4),
            )
            end = (
                x + math.sin(angle) * (radius - 1),
                y + math.cos(angle) * (radius - 1),
            )
            pygame.draw.line(self.screen, (97, 101, 103), start, end)
        pygame.draw.circle(self.screen, (65, 69, 73), (x, y), radius - 7)
        pygame.draw.circle(self.screen, (77, 81, 84), (x - 2, y - 3), radius - 12)
        angle = (data["value"] - 64) / 64 * math.radians(135)
        start = (x + math.sin(angle) * 13, y - math.cos(angle) * 13)
        end = (x + math.sin(angle) * 23, y - math.cos(angle) * 23)
        pygame.draw.line(self.screen, self.label_color, start, end, 2)
        if rotary_id == self._drag_rotary:
            pygame.draw.circle(self.screen, self.label_color, (x, y), radius + 2, 1)
        if rotary_id == self.ROTARY_SELECT:
            self._text("SELECT", (x, 159), self.tiny_font)
        else:
            self._text(data["name"], (x, 51), self.tiny_font)
            secondary = {
                self.ROTARY_VOLUME: "VOLUME",
                self.ROTARY_PAN: "PAN",
                self.ROTARY_FILTER: "LOW EQ",
                self.ROTARY_RESONANCE: "HIGH EQ",
            }
            self._text(
                secondary[rotary_id], (x, 70), self.tiny_font, self.secondary_color
            )

    def _draw_control_bank(self):
        controls = (
            ("CHANNEL", self.FIELD_CHANNEL),
            ("MIXER", self.FIELD_MIXER),
            ("USER 1", self.FIELD_USER1),
            ("USER 2", self.FIELD_USER2),
        )
        # USER2 has a dedicated wire value, not the usual field bit mask.
        fields = (
            self.FIELD_USER2
            if self.control_bank_state == self.CONTROL_BANK_USER2
            else self.control_bank_state
        )
        pygame.draw.lines(
            self.screen, (115, 121, 122), False, [(43, 50), (43, 154), (50, 154)]
        )
        for index, (label, field) in enumerate(controls):
            y = 51 + index * 20
            color = self.red if fields & field else self.unlit_color
            pygame.draw.circle(self.screen, (13, 14, 15), (54, y), 6)
            pygame.draw.circle(self.screen, color, (54, y), 4)
            surface = self.tiny_font.render(label, True, self.label_color)
            self.screen.blit(surface, (64, y - surface.get_height() // 2))
        pygame.draw.line(self.screen, (80, 84, 85), (118, 61), (556, 61))

    def _draw_mute_solo(self):
        pygame.draw.line(self.screen, (87, 92, 94), (43, 192), (43, 473))
        for row, led_rect in enumerate(self.track_led_rects):
            button_id = self.BUTTON_SOLO_1 + row
            rect = self.button_rects[button_id]
            pygame.draw.circle(self.screen, (13, 14, 16), rect.center, 17)
            color = self._button_color(button_id)
            pygame.draw.circle(self.screen, color, rect.center, 14, 3)
            center_color = (
                (76, 81, 83) if button_id in self._pressed_buttons else (41, 44, 46)
            )
            pygame.draw.circle(self.screen, center_color, rect.center, 10)
            colors = {
                0: self.unlit_color,
                1: self._mix(self.red, (39, 39, 39), 0.55),
                2: self._mix(self.green, (39, 39, 39), 0.55),
                3: self.red,
                4: self.green,
            }
            self._draw_key(led_rect, colors.get(self.track_leds[row], self.unlit_color))
        self._text("MUTE", (65, 324), self.tiny_font)
        self._text("SOLO", (65, 338), self.tiny_font)

    def _draw_legends(self):
        modes = (
            (self.BUTTON_STEP, "STEP", "ACCENT"),
            (self.BUTTON_NOTE, "NOTE", "SNAP"),
            (self.BUTTON_DRUM, "DRUM", "TAP"),
            (self.BUTTON_PERFORM, "PERFORM", "OVERVIEW"),
            (self.BUTTON_SHIFT, "", "SHIFT"),
            (self.BUTTON_ALT, "", "ALT"),
            (self.BUTTON_PATTERN, "PATTERN / SONG", "METRONOME"),
            (self.BUTTON_PLAY, "", "WAIT"),
            (self.BUTTON_STOP, "", "COUNTDOWN"),
            (self.BUTTON_REC, "", "LOOP REC"),
        )
        for button_id, label, shifted in modes:
            rect = self.button_rects[button_id]
            if label:
                if button_id == self.BUTTON_PATTERN:
                    self._text("PATTERN", (rect.centerx, 494), self.tiny_font)
                    self._text("SONG", (rect.centerx, 505), self.tiny_font)
                else:
                    self._text(label, (rect.centerx, 503), self.tiny_font)
            text = self.tiny_font.render(
                shifted,
                True,
                self.panel_color if button_id != self.BUTTON_ALT else self.label_color,
            )
            dest = text.get_rect(center=(rect.centerx, 570))
            if button_id != self.BUTTON_ALT:
                pygame.draw.rect(
                    self.screen, self.label_color, dest.inflate(4, 2), border_radius=1
                )
            self.screen.blit(text, dest)
        self._text("PATTERN", (600, 118), self.tiny_font)
        self._text(
            "BROWSER",
            (self.button_rects[self.BUTTON_BROWSER].centerx, 146),
            self.tiny_font,
        )
        self._text("GRID", (1001, 112), self.tiny_font)
        # Draw icons as geometry so their shape is independent of installed fonts.
        for button_id, direction in (
            (self.BUTTON_PAT_UP, "up"),
            (self.BUTTON_PAT_DOWN, "down"),
            (self.BUTTON_GRID_LEFT, "left"),
            (self.BUTTON_GRID_RIGHT, "right"),
        ):
            rect = self.button_rects[button_id]
            if direction == "up":
                points = [
                    (rect.centerx, rect.top - 13),
                    (rect.centerx - 4, rect.top - 6),
                    (rect.centerx + 4, rect.top - 6),
                ]
            elif direction == "down":
                points = [
                    (rect.centerx, rect.bottom + 13),
                    (rect.centerx - 4, rect.bottom + 6),
                    (rect.centerx + 4, rect.bottom + 6),
                ]
            elif direction == "left":
                points = [
                    (rect.left - 12, rect.centery),
                    (rect.left - 5, rect.centery - 4),
                    (rect.left - 5, rect.centery + 4),
                ]
            else:
                points = [
                    (rect.right + 12, rect.centery),
                    (rect.right + 5, rect.centery - 4),
                    (rect.right + 5, rect.centery + 4),
                ]
            pygame.draw.polygon(self.screen, self.label_color, points)
        x = self.button_rects[self.BUTTON_PLAY].centerx
        pygame.draw.polygon(
            self.screen, self.label_color, [(x - 5, 495), (x - 5, 507), (x + 6, 501)]
        )
        x = self.button_rects[self.BUTTON_STOP].centerx
        pygame.draw.rect(self.screen, self.label_color, (x - 5, 496, 10, 10))
        x = self.button_rects[self.BUTTON_REC].centerx
        pygame.draw.circle(self.screen, self.label_color, (x, 501), 6)

    def _draw_oled(self):
        """Native 128×64 pixels, with zero lit as on the physical OLED."""
        rect = self.oled_rect
        bezel = rect.inflate(20, 24)
        pygame.draw.rect(self.screen, (12, 14, 15), bezel, border_radius=5)
        pygame.draw.rect(self.screen, (64, 68, 69), bezel, 1, border_radius=5)
        # Map the two image values through a palette instead of looping over
        # every scaled pixel in Python on every frame.
        image = self.canvas.image.convert("L").point(
            lambda value: 1 if value < 128 else 0, "P"
        )
        image.putpalette([5, 10, 11, 220, 235, 230] + [0] * (256 * 3 - 6))
        rgb = image.convert("RGB")
        surface = pygame.image.fromstring(rgb.tobytes(), rgb.size, "RGB")
        self.screen.blit(surface, rect)

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
    canvas.draw_text("Click a pad", 25, 25)
    canvas.draw_text("Drag a knob", 25, 45)
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
