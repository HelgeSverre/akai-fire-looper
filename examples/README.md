# Examples

These examples demonstrate the `akai_fire` device library, the optional
`akai_fire_framework` application layer and the mock/testing tools. Start with a
single-feature example to learn an API, or use an app as a starting point for your
own controller software. Each app's behavior belongs to that example.

Run from the repository root after `uv sync --all-extras`:

```sh
uv run python -m examples.oled_wave
uv run python -m examples.apps.synth_editor
# Or: just example oled_wave / just app synth_editor
```

Names describe the device feature: `pads_*`, `oled_*`, `events_*`, `leds_*`, `midi_*`, `mock_*`, and `benchmark_*`. Multi-file or application-sized demos live in `apps/`. Use module commands, not direct `.py` paths; examples no longer patch `sys.path`.

## Example applications

| Module | Purpose and status |
| --- | --- |
| `apps.pixel_editor` | [Tutorial app](apps/pixel_editor/README.md). Color painting, shared pad/OLED state, SELECT editing and JSON save/load. Defaults to pygame; hardware requires `--hardware`. |
| `apps.circuit` | [Four-track sequencer](apps/circuit/README.md). Real MIDI output/recording, explicit ports; timing limitations documented. |
| `apps.synth_editor` | [JT-4000 CC editor](apps/synth_editor/README.md). Parameter pages, OLED shapes, auditions, snapshots. Replaces the unfinished modular Groovebox. |
| `apps.midi_scope` | [Controller diagnostics](apps/MIDI_SCOPE.md). Event log, graphs, pad activity, CSV. |
| `apps.snake` | [Snake game](apps/snake/README.md). One 16×4 board rendered on pads and OLED, with directional buttons, pause and restart. |
| `apps.pad_counter` | Smallest framework app: count pads, STOP to exit. |
| `apps.modal_demo` | Mode/transport/screen teaching demo. Settings menu demonstrates navigation, not persistent configuration. |
| `apps.looper` | Clip-state teaching demo. Arm/record/play state and normalized event timing; no external MIDI input/output. |

## Pads and LEDs

| Module | What it demonstrates |
| --- | --- |
| `pads_color_cycle` | Sweep red, green and blue across every pad at brightness 32, 64, 96 and 127 |
| `pads_color_fades` | Smooth whole-grid color fades (formerly the misleading `display_hello_world`) |
| `pads_random_blink` | Random pad and button LED animation |
| `pads_batch_animation` | Batched RGB animation |
| `pads_interactive_ripple` | Ripples triggered by pad input |
| `pads_toggle` | Toggle pad state and trigger color animation |
| `leds_track_cycle` / `leds_track_rain` | Rectangular track LEDs and corresponding pad rows |
| `leds_control_bank` | Control-bank LED bit fields |
| `controller_clear` | Clear controller output |

## OLED

| Module | What it demonstrates |
| --- | --- |
| `oled_wave` | Animated wave drawing |
| `oled_bounce` | Bouncing ball with a bounded animation |
| `oled_snow` | Pixel noise |
| `oled_pages` | Interactive screen pages |
| `oled_gallery` | Several graphics effects in rotation |
| `oled_clawd` | Procedural mascot drawing; `--preview-only` exports a BMP |
| `oled_clawd_animation` | Convert and animate the bundled 113-frame Clawd GIF on the OLED |
| `oled_scrolling_text` | Scrolling, waving text with the same animated mascot |

Both GIF examples use [the original animation bundled in this repository](assets/README.md); no Claude installation or download is needed at runtime. `oled_clawd_animation /path/to/file.gif` also accepts an explicit file. Both support `--preview-only` for image previews without a controller. Foreground animation delays pump mock events, so closing the window exits rather than freezing the UI.

## Events, MIDI and mocks

| Module | What it demonstrates / requirements |
| --- | --- |
| `events_basic` | Correct pad, button and encoder callback signatures |
| `events_all_controls` | Event monitor with OLED feedback and a session summary |
| `controller_diagnostics` | Interactive controller checks using the older root screen manager |
| `sequencer_basic` | Transport/menu state-machine teaching example, without instrument output; use Circuit for sequencing |
| `midi_batch_basics` / `midi_batch_animation` | Raw SysEx batching; **Fire hardware required** |
| `midi_raw_ripple` | Low-level MIDI input and batched ripple output; **Fire hardware required** |
| `benchmark_pad_batches` / `benchmark_midi_throughput` | Compare message strategies; mock timings are not hardware throughput measurements |
| `mock_pygame_automation` | Programmatic GUI interaction and screenshots |
| `mock_terminal` | Terminal mock; requires the `tui` extra |

## Earlier experiments

`legacy.circuit_standalone`, `legacy.groovebox_standalone`, and `legacy.looper_standalone` retain the large earlier experiments. They are not the recommended starting points and have not had full musical behavior validation. Their dependencies are installed by `--all-extras`. New work belongs in the maintained apps above; these files remain available for comparison rather than presenting several overlapping grooveboxes as equally complete products.

## Validation and conventions

`uv run python -m unittest discover` includes import checks across examples, interaction tests for maintained apps, and Circuit's model/UI suite. Tests mock MIDI; physical Fire/synth behavior remains a separate check. Finite tests do not establish every visual animation, musical timing edge case, or legacy workflow.

For a new small demo, use a context-managed controller and `examples._runtime.wait` for foreground delays. For an app, use `AkaiFireApp` hooks. Add comments for protocol details, ownership, timing, or non-obvious mappings; the code should explain straightforward assignments itself. Document partial functionality beside the run command.

## Renamed entry points

- `examples.circuit.main` → `examples.apps.circuit`
- `examples.groovebox.app` → `examples.apps.synth_editor` (repurposed)
- `event_handling_*` → `events_*`
- `screen_*` → `oled_*` (`screen_showcase` → `oled_gallery`)
- `track_led_*` → `leds_track_*`
- `animation_pad_blink_random` → `pads_random_blink`
- `animation_water_ripple_interactive` → `pads_interactive_ripple`
- `animation_water_ripple_batch` → `midi_raw_ripple`
- `batch_animation` → `pads_batch_animation`
- `batch_performance` → `benchmark_pad_batches`
- `performance_demo` → `benchmark_midi_throughput`
- `music_sequencer` → `sequencer_basic`; larger `music_*` experiments moved to `legacy/`

`run_circuit.py` remains a small compatibility launcher for Circuit.
