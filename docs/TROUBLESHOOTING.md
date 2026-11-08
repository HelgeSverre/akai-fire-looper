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

Draw onto `fire.get_canvas()` and then call `fire.render_to_display()`. The framework does the render after `on_update()`. Pixel `0` is lit; pixel `1` is unlit. Coordinates outside 128×64 do not appear. Keep a text line within about 21 characters at the default font size; use short labels or scrolling for longer content.

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
