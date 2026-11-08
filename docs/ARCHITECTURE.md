# Architecture

The repository has three installed packages and a set of runnable examples. Root GUI/TUI modules and `screen_manager.py` are development utilities; they are not included in the wheel.

```text
examples/apps/circuit        musical clock, tracks, MIDI, modes
examples/apps/synth_editor   JT-4000 CC profile, snapshots, auditions
examples/apps/midi_scope     event history, encoder traces, CSV
            │
    akai_fire_framework      lifecycle, frame loop, optional mixins
            │
        akai_fire            device contract, hardware MIDI, OLED canvas
            │
     python-rtmidi + Pillow
```

## Device boundary

`AkaiFireDevice` owns callback registries, modifier snapshots, input dispatch, and common device operations. Hardware and mocks share this contract. `hardware.py` owns MIDI ports, polling, the bounded callback executor, serialized output and pad-message caching. `Canvas` owns the 128×64 monochrome image; the hardware backend encodes it for the OLED.

Callbacks are copied before dispatch so handlers can add/remove subscriptions. Exceptions are logged per handler. The default executor uses four workers, so completion can be concurrent. Configure one worker when FIFO ordering is needed. Modifier state is captured for each dispatch, not read later from an unrelated input event.

## Application boundary

`AkaiFireApp` creates or borrows a controller, calls initialization hooks, owns its default input subscriptions, runs a monotonic frame loop, and shuts down once. `_EventSubscriptions` is the shared private owner for framework and standard transport callbacks. A failed registration batch rolls back its own listeners. A borrowed controller survives app shutdown; owned hardware is closed even when an app stop hook fails.

The frame loop is an interface refresh loop. It is not a musical clock. Circuit owns its own clock and scheduled-note worker; the synth editor owns short audition deadlines; MIDI Scope has no instrument output.

## Examples and mocks

- `examples/`: one-topic modules, named by device feature.
- `examples/apps/`: maintained applications and small framework teaching demos.
- `examples/legacy/`: earlier overlapping standalone experiments, retained for reference.
- `akai_fire_testing`: headless mocks and assertions, usable without a GUI.
- `mock_gui_pygame.py` and `mock_tui.py`: repository-only interactive backends.

Run examples with `uv run python -m examples.<module>` so root utilities and package-relative imports resolve consistently. Small procedural animations use `examples._runtime.wait` to pump foreground mock events while waiting; worker threads only sleep. Framework applications get event pumping from `run()`.

See [the framework guide](FRAMEWORK.md) for threading and resource ownership, and [cleanup evidence](code-cleanup.md) for regression coverage and unresolved limits.
