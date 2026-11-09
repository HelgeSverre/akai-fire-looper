# Troubleshooting

## Examples cannot import a module

Run from the repository root, using module notation:

```sh
uv sync --all-extras
uv run python -m examples.apps.circuit
uv run python -m examples.oled_wave
```

Direct paths such as `python examples/apps/circuit/main.py` do not establish the package context. Examples no longer modify `sys.path`. The interactive mocks live at the repository root and are not included in an installed wheel.

## The controller is not found

List MIDI ports:

```sh
uv run python -c 'from akai_fire import AkaiFire; print(AkaiFire.list_midi_ports())'
```

Connect the Fire before starting, check its USB cable, and close applications holding its MIDI ports. The default match is the substring `FL STUDIO FIRE`; use `AkaiFire(port_name="...")` for a different name. `get_akai_fire()` can fall back to pygame; use `get_akai_fire(use_mock=False)` when a missing controller should be an error.

## The mock window freezes or does not repaint

Pygame needs `process_events()` on the main thread. `AkaiFireApp.run()` handles this. Procedural examples use `examples._runtime.wait(fire, seconds)` instead of a long blocking sleep. An `input()` prompt blocks the window; it is suitable only for the hardware-only snippet in the README.

For headless tests use `akai_fire_testing.MockAkaiFire`. For pygame integration tests, set `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy` before importing pygame. The development interpreter is pinned to Python 3.12.

## The OLED is blank or inverted

Draw onto `fire.get_canvas()` and then call `fire.render_to_display()`. The framework does the render after `on_update()`. Pixel `0` is lit; pixel `1` is unlit. Coordinates outside 128×64 do not appear. Use `draw_text_fitted()` for labels: fonts have variable widths, so a character-count limit does not guarantee a fit. Standard pages and menus show three full content rows. Clear the canvas before drawing a different page; use raw `draw_text()` only when handling positioning or scrolling yourself.

## The OLED goes blank after several seconds

The Fire can put its OLED to sleep when it receives no display updates. During a hardware check on 9 November 2026, an image sent once disappeared after approximately eight seconds while the probe remained connected and idle. Treat that timing as an observation from one device, not a guaranteed firmware timeout.

The driver now keeps the display awake by default, resending the last successfully displayed image after two idle seconds. In the hardware check, resending identical image data every two seconds prevented the observed blanking. The [DrivenByMoss Fire driver](https://github.com/git-moss/DrivenByMoss/blob/f9aca50b97efb9d5273e1384b697677b55e309d9/src/main/java/de/mossgrabers/controller/akai/fire/controller/FireDisplay.java) also handles display sleep by resending unchanged data, using a three-second interval.

To allow sleep or handle refresh yourself, construct `AkaiFire(oled_keepalive=False)`. The same option works through `get_akai_fire()`. `render_to_display()` still sends an image on every call. `AkaiFireApp.run()` renders every frame, so its normal loop keeps the display awake even when driver keepalive is disabled. Disabling keepalive does not suppress explicit renders. The mocks do not simulate hardware idle sleep.

Blanking at shutdown is separate: the hardware context manager clears the display, and example cleanup generally clears all outputs. `oled_clawd` intentionally closes after its five-second preview.

## Pads look dim or nearly white in the mock

Pad channels use the full MIDI range 0–127. Values such as `(3, 0, 0)` are very dim; `(127, 0, 0)` is full red. Run `uv run python -m examples.pads_color_cycle` to check the three primary colors. Button LEDs use a different mapping: single-color buttons take 0–2; two-color buttons use 1/3 for dim/bright primary color and 2/4 for dim/bright amber. Use `DUAL_LED_BRIGHT_PRIMARY` for bright green PLAY or bright red REC. See [button LED values](DEVICE.md#button-leds).

## Circuit is silent

Circuit produces MIDI, not computer audio. Set an exact instrument port name from the printed port list:

```sh
CIRCUIT_MIDI_OUTPUT="Your synth port" uv run python -m examples.apps.circuit
```

The Fire's own port is not a synth output. Default track channels are 10, 1, 2 and 3; match your receiving instruments. NOTE pads audition short notes. Press REC before entering notes to record them, or use STEP's pitch parameter to write a step. PLAY alone does not create pattern content.

`CIRCUIT_MIDI_INPUT` selects an optional external keyboard input. Positive note-on input records into the armed recording track while transport is recording; it is not a general MIDI-through router.

## The synth editor is silent or shows question marks

The editor automatically opens an output only when there is exactly one port containing `JT-4000`. Set `SYNTH_MIDI_OUTPUT` and `SYNTH_MIDI_CHANNEL` explicitly otherwise. `DEMO` on the OLED means no MIDI port is connected. Connect the synth's audio output to headphones or your audio system.

A `?` means the editor has not sent that parameter yet. It does not read the current patch from the synth. REC saves the locally known CC values; SELECT sends a saved snapshot. These are not native SysEx preset dumps. See the [editor guide](../examples/apps/synth_editor/README.md).

## Tests or lint fail

```sh
uv run python -m unittest discover
uv run python -m unittest tests.test_example_apps
uv run ruff check .
uv run ruff format --check .
```

The Circuit suite is included in the first command. Tests replace MIDI ports; a hardware connection should never be required. Full Ruff lint still has pre-existing style findings documented in [cleanup evidence](code-cleanup.md). Do not interpret that baseline as permission to ignore new undefined names or broken imports.
