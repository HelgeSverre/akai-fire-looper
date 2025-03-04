# Groovebox Application Structure

A modular MIDI sequencer/groovebox application designed for the Akai Fire controller.

## Core Architecture

The application is built around a view-based architecture with clear separation of concerns:

### View System

- Each screen/mode is a self-contained View class
- Views manage their own state and UI
- Common interface ensures consistent behavior
- Clean activation/deactivation lifecycle

```python
class View(ABC):
    def activate(self) -> None

        def deactivate(self) -> None

        def update_display(self) -> None

        def update_pads(self) -> None

        def handle_pad(self, pad: int, velocity: int) -> None

        def handle_encoder(self, encoder: int, value: int) -> None
```

### Display Abstraction

The Screen class provides a clean abstraction for the OLED display:

- Buffer management
- Common UI elements (headers, parameters, progress bars)
- Consistent rendering pipeline
- Hardware-independent drawing primitives

### Settings Management

Centralized settings handling through AppSettings:

- Type-safe settings access
- Serialization support
- Runtime configuration

### Application Core

The GrooveboxApp class manages:

- View switching
- Hardware interaction
- Global state
- Main timing loop

## Adding New Views

1. Add new view ID:

```python
class ViewID(Enum):
    NEW_VIEW = auto()
```

2. Create view class:

```python
class NewView(View):
    def __init__(self, app: GrooveboxApp):
        super().__init__(app)
        # View-specific initialization

    def activate(self):
        super().activate()
        # Setup view state

    def update_display(self):

    # Update OLED display

    def update_pads(self):

    # Update pad colors

    def handle_pad(self, pad: int, velocity: int):
# Handle pad interactions
```

3. Register view in app:

```python
def _setup_views(self):
    self.views[ViewID.NEW_VIEW] = NewView(self)
```

## View Lifecycle

1. **Activation**
    - Previous view deactivated
    - New view activated
    - Display and pads updated

2. **Active State**
    - Handles pad input
    - Updates display
    - Manages view-specific state

3. **Deactivation**
    - Clean up view state
    - Save any necessary data

## Hardware Integration

The application abstracts hardware interaction through:

- Screen class for OLED display
- Standardized pad color management
- Encoder input handling
- Common hardware events

## State Management

Each component manages its own state:

- Views manage view-specific state
- App manages global state
- Settings manage configuration
- Hardware manages device state

## Display Pipeline

1. View requests display update
2. Screen buffer updated
3. Common UI elements drawn
4. View-specific content added
5. Buffer rendered to hardware

## Event Flow

1. Hardware event received
2. Routed to current view
3. View processes event
4. State updated
5. Display/pads refreshed

## File Organization

```
groovebox/
├── __init__.py
├── app.py          # Main application
├── views/          # View implementations
│   ├── __init__.py
│   ├── base.py     # View base class
│   ├── main.py     # Main view
│   └── pattern.py  # Pattern view
├── hardware/       # Hardware abstraction
│   ├── __init__.py
│   ├── screen.py   # Screen management
│   └── fire.py     # Akai Fire interface
└── utils/          # Utilities
    ├── __init__.py
    └── settings.py # Settings management
```

## Usage

```python
from groovebox import GrooveboxApp

app = GrooveboxApp()
app.run()
```

## Adding Features

1. Create new view if needed
2. Implement view methods
3. Add necessary settings
4. Update hardware integration
5. Register view in app

## Best Practices

1. Keep views focused and single-purpose
2. Use type hints for clarity
3. Handle all possible states
4. Clean up resources properly
5. Document view-specific behavior