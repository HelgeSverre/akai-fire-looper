# AKAI Fire for Python

A **Python library and application framework** for controlling the AKAI Fire and building your own controller applications.

Read pads, buttons and encoders; control RGB LEDs; draw on the 128×64 OLED; and give the hardware whatever behavior your application needs. Build custom control surfaces, interactive displays, MIDI tools, sequencers or other integrations. The library communicates directly over USB MIDI—FL Studio is not required.

[![An example application built with the framework, running in the interactive Fire mock](docs/images/mock-demo.gif)](docs/images/mock-demo.png)

*One example of the framework in use: the JT-4000 editor running in the pygame mock, with pad faders, OLED graphs and note activity. [Still PNG](docs/images/mock-demo.png) · [Mock controls and hardware comparison](docs/MOCK_GUI.md)*

## Library, framework and testing tools

Use the device library inside an existing program, or build an application with the optional framework. All three packages ship together:

| Package | Use it to |
| --- | --- |
| `akai_fire` | Connect to the controller, handle input events, set pad/button/track LEDs, and draw on the OLED with `Canvas` |
| `akai_fire_framework` | Build apps with `AkaiFireApp`: lifecycle hooks, a display loop, input routing, cleanup, and optional mode/screen/grid/transport helpers |
| `akai_fire_testing` | Test your code without hardware using headless controller/MIDI mocks, simulated input and output assertions |

The repository also includes clickable pygame and terminal mocks, small API examples, and example applications. You can develop and test controller behavior before connecting a physical Fire.

## Get started

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). The repository pins 3.12 because pygame's font support was problematic on 3.14 during development.

```sh
git clone https://github.com/HelgeSverre/akai-fire-looper.git
cd akai-fire-looper
uv sync --all-extras
uv run python -m examples.apps.pad_counter
```

With a Fire connected, the example uses its MIDI ports. Otherwise it opens the clickable pygame mock. Close the window or press Ctrl+C to exit.

To open the mock on its own:

```sh
uv run python mock_gui_pygame.py
```

## Build your own application

Save this as `my_fire_app.py` in the repository root and run `uv run python my_fire_app.py`:

```python
from akai_fire_framework import AkaiFireApp


class PadLights(AkaiFireApp):
    def on_init(self):
        self.canvas.draw_text("Press a pad", 28, 20)
        self.canvas.draw_text("STOP to exit", 24, 38)

    def on_pad_press(self, pad, velocity):
        self.fire.set_pad_color(pad, 0, 100, 30)

    def on_button_press(self, button, event):
        if button == self.fire.BUTTON_STOP and event == "press":
            self.quit()


if __name__ == "__main__":
    with PadLights() as app:
        app.run()
```

Your app defines the behavior. The framework runs the display loop, pumps mock events, removes its handlers on shutdown, and closes connections it owns. Use `on_update(dt)` for ongoing UI changes and `on_encoder_turn(...)` for knob input. The [framework guide](docs/FRAMEWORK.md) covers these hooks, optional mixins, threading and resource ownership.

## Use the library in another project

Add the packages from this repository to an existing uv project:

```sh
uv add "akai-fire-looper @ git+https://github.com/HelgeSverre/akai-fire-looper.git"
```

The repository and distribution retain the original `akai-fire-looper` name. Import the Python APIs from `akai_fire`, `akai_fire_framework` and `akai_fire_testing`.

For direct hardware control:

```python
from akai_fire import AkaiFire

with AkaiFire() as fire:
    fire.set_multiple_pad_colors([(0, 127, 0, 0), (1, 0, 127, 0)])
    canvas = fire.get_canvas()
    canvas.draw_text("Hello Fire", 30, 24)
    fire.render_to_display()
    input("Press Enter to close the hardware connection...")
```

`AkaiFire()` requires hardware. Pads use indices 0–63 and RGB channels 0–127. OLED pixels use `0` for lit and `1` for unlit. The device context manager clears the display and closes MIDI; call `clear_all()` when you also want LEDs cleared.

The installed distribution includes all three library packages. Interactive GUI/TUI mocks and examples are repository tools; run them from a checkout. In the checkout, `get_akai_fire()` can select hardware or an interactive mock. For hardware-free tests in any project, use `akai_fire_testing.MockAkaiFire`. You can also pass a controller explicitly to a framework app, for example `PadLights(AkaiFire())`; the caller owns that connection.

## Explore the examples

The examples show ways to use the library and framework, from a single input callback to a multi-mode application. Start with the [example catalog](examples/README.md) for pad colors, OLED graphics, buttons, encoders, LEDs, batching and mocks.

| Example app | What it demonstrates | Run from the checkout |
| --- | --- | --- |
| [Circuit](examples/apps/circuit/README.md) | A four-track MIDI sequencer with a separate musical clock, step editing and mode-based controls | `uv run python -m examples.apps.circuit` |
| [JT-4000 editor](examples/apps/synth_editor/README.md) | Parameter pages, pad faders, OLED visualizations, MIDI CC output and local snapshots | `uv run python -m examples.apps.synth_editor` |
| [MIDI Scope](examples/apps/MIDI_SCOPE.md) | Input handling, encoder traces, live/frozen views and CSV export | `uv run python -m examples.apps.midi_scope` |

Circuit needs an explicitly selected instrument output for sound. The editor connects automatically only when exactly one JT-4000 output is present; otherwise it runs in preview mode. These apps send MIDI and do not generate computer audio. Their README files cover controls, prerequisites and limitations.

The clip looper and modal demo teach state management. Earlier standalone sequencer experiments live in `examples/legacy`. Instrument profiles, musical clocks, recording logic and persistence belong to the apps that need them.

## Project status

The library and framework are under active development. Hardware callbacks can run on worker threads; applications must coordinate shared state with the display thread. The framework provides a UI frame loop; musical scheduling belongs to the application. Pad-release events and app-level reconnect notifications are current gaps. See the [framework guide](docs/FRAMEWORK.md) and [roadmap](docs/ROADMAP.md).

Automated tests exercise mocked MIDI ports and controller implementations. Physical Fire/JT-4000 behavior for the example apps still needs hardware validation.

## Documentation

- [Device API](docs/DEVICE.md): connections, callbacks, LED values, canvas and errors
- [Build an application](docs/FRAMEWORK.md): lifecycle, mixins, testing and current gaps
- [Example catalog](examples/README.md): commands, prerequisites, status and naming
- [Interactive mock](docs/MOCK_GUI.md): hardware comparison, screenshots and mouse controls
- [Architecture](docs/ARCHITECTURE.md): package boundaries and resource ownership
- [Troubleshooting](docs/TROUBLESHOOTING.md): ports, mock windows, displays and silent instruments
- [Roadmap](docs/ROADMAP.md): library/framework priorities and example-app follow-ups

## Development

```sh
uv sync --all-extras
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv build
```

Discovery includes library, framework, mock and example-app tests. Ruff's full lint gate currently reports existing repository-wide style debt; see the [cleanup evidence](docs/code-cleanup.md) for the measured baseline and verification limits.

With [just](https://github.com/casey/just), use `just test`, `just example oled_wave`, or `just app synth_editor`.

## Credits

Built by [Helge Sverre](https://github.com/HelgeSverre). This is an independent Python project for the AKAI Fire. AKAI, FL Studio and Behringer product names identify the hardware and software used by the examples.
