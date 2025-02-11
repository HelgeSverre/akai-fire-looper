from text_renderer import TextStyle


class StatusBar:
    """Status bar that can be positioned at top or bottom of screen"""

    def __init__(self, display, height=8):
        self.display = display
        self.height = height
        self.items = []

    def draw(self, y_position=0):
        """Draw status bar with items"""
        self.display.fill_rect(0, y_position, 128, self.height, 0)

        # Draw items
        x = 2
        for text in self.items:
            style = TextStyle(invert=True)
            self.display.draw_text(text, x, y_position + 1, style)

            x += len(text) * 6 + 4


class IconButton:
    """Button with icon and optional label"""

    def __init__(self, display, x, y, icon, label=None, width=20, height=20):
        self.display = display
        self.x = x
        self.y = y
        self.icon = icon
        self.label = label
        self.width = width
        self.height = height

    def draw(self, selected=False):
        """Draw button with optional selection state"""
        # Draw button background/border
        self.display.draw_rect(self.x, self.y, self.width, self.height, 1)
        if selected:
            self.display.fill_rect(
                self.x + 2, self.y + 2, self.width - 4, self.height - 4, 1
            )

        # Draw icon (simplified for demo)
        icon_x = self.x + (self.width - len(self.icon) * 6) // 2
        icon_y = self.y + (self.height - 7) // 2
        self.display.draw_text(self.icon, icon_x, icon_y, TextStyle(invert=selected))

        # Draw label if provided
        if self.label:
            label_y = self.y + self.height + 2
            self.display.draw_text_centered(self.label, label_y)


class TabBar:
    """Horizontal tab bar with selectable items"""

    def __init__(self, display, y, height=12):
        self.display = display
        self.y = y
        self.height = height
        self.tabs = []
        self.selected_tab = 0

    def set_tabs(self, tabs):
        """Set tab labels"""
        self.tabs = tabs
        self.selected_tab = 0

    def draw(self):
        """Draw tab bar with current selection"""
        tab_width = self.display.SCREEN_WIDTH // len(self.tabs)

        for i, tab in enumerate(self.tabs):
            x = i * tab_width
            # Draw tab background
            if i == self.selected_tab:
                self.display.fill_rect(x, self.y, tab_width, self.height, 1)
                style = TextStyle(invert=True)
            else:
                self.display.draw_rect(x, self.y, tab_width, self.height, 1)
                style = TextStyle()

            # Draw tab label
            text_x = x + (tab_width - len(tab) * 6) // 2
            text_y = self.y + (self.height - 7) // 2
            self.display.draw_text(tab, text_x, text_y, style)
