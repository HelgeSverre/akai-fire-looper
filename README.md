# AKAI Fire for Python

[![JT-4000 editor running in the interactive Fire mock](docs/images/mock-demo.gif)](docs/images/mock-demo.png)

The actual JT-4000 editor in preview mode: moving pad faders, OLED graphs and note activity. [Still PNG](docs/images/mock-demo.png) · [Mock controls and hardware comparison](docs/MOCK_GUI.md)

Turn the AKAI Fire into a sequencer, synth controller, or a custom control surface. Drive its 64 RGB pads and 128×64 OLED, handle buttons and encoders, and develop against a mock when the controller is unplugged.

```python
from akai_fire_framework import AkaiFireApp


class PadCounter(AkaiFireApp):
    def on_init(self):
        self.count = 0

    def on_pad_press(self, pad, velocity):
        self.count += 1
        self.fire.set_pad_color(pad, 0, 100, 30)
        self.canvas.clear()
        self.canvas.draw_text(f"Pad {pad} / count {self.count}", 4, 24)


if __name__ == "__main__":
    with PadCounter() as app:
        app.run()
```

The framework runs the display loop, pumps mock events, removes its handlers on shutdown, and closes connections it owns. Your app supplies the behavior.

## Try it

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). The repository pins 3.12 because pygame's font support was problematic on 3.14 during development.

```sh
git clone https://github.com/HelgeSverre/akai-fire-looper.git
cd akai-fire-looper
uv sync --all-extras
uv run python -m examples.apps.pad_counter
```

With a Fire connected, this uses its MIDI ports. Otherwise it opens the clickable pygame mock. Close the window or press Ctrl+C to exit. Run examples as modules from the repository root; the GUI mocks and examples are repository tools, not installed library packages.

## Choose an app

| App | What you can do | Run |
| --- | --- | --- |
| [Circuit](examples/apps/circuit/README.md) | Build four-track MIDI patterns, record notes, edit steps, mix and chain patterns | `uv run python -m examples.apps.circuit` |
| [JT-4000 editor](examples/apps/synth_editor/README.md) | Edit 16 synth parameters, use pad faders, audition notes, save CC snapshots | `uv run python -m examples.apps.synth_editor` |
| [MIDI Scope](examples/apps/MIDI_SCOPE.md) | Inspect controller input, graph encoder movement, freeze and export an event log | `uv run python -m examples.apps.midi_scope` |

Circuit needs an explicitly selected instrument output for sound. The editor connects automatically only when exactly one JT-4000 output is present; otherwise it runs in preview mode. Neither app generates audio on the computer. The editor's mappings come from Behringer's JT-4000 MICRO manual; physical synth behavior still needs hardware validation.

Smaller [examples](examples/README.md) cover OLED graphics, pad animation, LED control, events, batching, and mocks. The clip looper and modal demo teach state management; their menus and MIDI integration have explicit limits. Earlier overlapping sequencer experiments live under `examples/legacy`.

## Use the driver directly

```python
from akai_fire import AkaiFire

with AkaiFire() as fire:
    fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
    canvas = fire.get_canvas()
    canvas.draw_text("Hello Fire", 30, 24)
    fire.render_to_display()
    input("Press Enter to close the hardware connection...")
```

`AkaiFire()` requires hardware. `get_akai_fire()` chooses hardware or a repository mock. Pads use indices 0–63 and RGB channels 0–127. OLED pixels use `0` for lit and `1` for unlit. The driver context manager clears the display and closes MIDI; call `clear_all()` yourself when you also want LEDs cleared.

## What is included?

| Package | Responsibility |
| --- | --- |
| `akai_fire` | MIDI transport, event subscriptions, LEDs, OLED canvas, reconnect and error handling |
| `akai_fire_framework` | Application lifecycle, frame loop, modes, screen/grid helpers, transport state |
| `akai_fire_testing` | Headless controller/MIDI mocks, event simulation, drawing and output assertions |

This is an early library for building controller software. The application framework is a useful runtime, but it is not an audio engine or a real-time MIDI scheduler. Device callbacks can run on worker threads; the framework does not automatically serialize application state onto its frame thread. See the [framework guide](docs/FRAMEWORK.md) for ownership, threading, and feature boundaries.

## Documentation

- [Device API](docs/DEVICE.md): connections, callbacks, LED values, canvas and errors
- [Build an application](docs/FRAMEWORK.md): lifecycle, mixins, testing and current gaps
- [Example catalog](examples/README.md): commands, prerequisites, status and naming
- [Interactive mock](docs/MOCK_GUI.md): hardware comparison, screenshots and mouse controls
- [Architecture](docs/ARCHITECTURE.md): package boundaries and resource ownership
- [Troubleshooting](docs/TROUBLESHOOTING.md): ports, mock windows, displays and silent instruments
- [Roadmap](docs/ROADMAP.md): implemented capabilities and remaining priorities

## Development

```sh
uv sync --all-extras
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv build
```

Discovery includes driver/framework tests and Circuit's app tests. MIDI ports are mocked in automated tests. Ruff's full lint gate currently reports existing repository-wide style debt; see the [cleanup evidence](docs/code-cleanup.md) for the measured baseline and verification limits.

With [just](https://github.com/casey/just), use `just test`, `just example oled_wave`, or `just app synth_editor`.

## Credits

Built by [Helge Sverre](https://github.com/HelgeSverre). The Fire is an AKAI controller; the JT-4000 is a Behringer synthesizer. Circuit is an independent example inspired by a four-track hardware workflow, not a Novation product or an implementation of every Circuit Tracks feature.
