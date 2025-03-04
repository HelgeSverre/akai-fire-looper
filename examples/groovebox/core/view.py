from abc import ABC, abstractmethod



class View(ABC):
    def __init__(self, app: 'MainApp'):
        self.app = app
        self.active = False

    @abstractmethod
    def activate(self):
        """Called when view becomes active"""
        self.active = True

    @abstractmethod
    def deactivate(self):
        """Called when view becomes inactive"""
        self.active = False

    @abstractmethod
    def update_display(self):
        """Update OLED display for this view"""
        pass

    @abstractmethod
    def update_pads(self):
        """Update pad colors for this view"""
        pass

    @abstractmethod
    def handle_pad(self, pad: int, velocity: int):
        """Handle pad press in this view"""
        pass

    def handle_encoder(self, encoder: int, value: int):
        """Handle encoder movement (optional)"""
        pass
