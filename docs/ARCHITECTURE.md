# Architecture

The project is a Python toolkit for controlling the AKAI Fire and building custom applications. It has three installed packages: the device library, an optional application framework, and headless testing tools. Runnable example apps demonstrate how to combine them. Root GUI/TUI modules and `screen_manager.py` are development utilities; they are not included in the wheel.

```text
examples/apps/circuit        musical clock, tracks, MIDI, modes
examples/apps/synth_editor   JT-4000 CC profile, snapshots, auditions
examples/apps/midi_scope     event history, encoder traces, CSV
examples/apps/snake          game rules, pad and OLED views
            │
    akai_fire_framework      lifecycle, frame loop, optional mixins
            │
        akai_fire            device contract, hardware MIDI, OLED canvas
            │
     python-rtmidi + Pillow
```

## Device boundary

`AkaiFireDevice` owns callback registries, modifier snapshots, input dispatch, and common device operations. Hardware and mocks share these input APIs; output rendering, validation and cleanup have [documented differences](DEVICE.md#mocks). `hardware.py` owns MIDI ports, polling, the bounded callback executor, serialized output and pad-message caching. `Canvas` owns the 128×64 monochrome image; the hardware backend encodes it for the OLED.

Callbacks are copied before dispatch so handlers can add/remove subscriptions. Exceptions are logged per handler. The default executor uses four workers, so completion can be concurrent. Configure one worker when FIFO ordering is needed. Modifier state is captured for each dispatch, not read later from an unrelated input event.

The hardware OLED needs periodic traffic to remain awake. With the default `oled_keepalive=True`, the first successful render starts a worker that resends the last encoded frame after two idle seconds. Explicit renders reset its deadline. Both paths use the same I/O lock, and the worker never reads the mutable canvas. Background send failures are logged and retried after the interval. Closing retires the worker and discards its frame before releasing the ports; reconnecting needs an explicit render to start a new worker. Mocks have no idle sleep or refresh worker.

## Application boundary

`AkaiFireApp` creates or borrows a controller, calls initialization hooks, owns its default input subscriptions, runs a monotonic frame loop, and shuts down once. `_EventSubscriptions` is the shared private owner for framework and standard transport callbacks. A failed registration batch rolls back its own listeners. A borrowed controller survives app shutdown; owned hardware is closed even when an app stop hook fails.

The frame loop is an interface refresh loop. It is not a musical clock. Circuit owns its own clock and scheduled-note worker; the synth editor owns short audition deadlines; MIDI Scope has no instrument output. Snake owns its movement timer and game rules; both its pad and OLED renderers read the same board.

## Examples and mocks

- `examples/`: one-topic modules, named by device feature.
- `examples/apps/`: maintained applications and small framework teaching demos.
- `examples/legacy/`: earlier overlapping standalone experiments, retained for reference.
- `akai_fire_testing`: headless mocks and assertions, usable without a GUI.
- `mock_gui_pygame.py` and `mock_gui_tui.py`: repository-only interactive backends.

Run examples with `uv run python -m examples.<module>` so root utilities and package-relative imports resolve consistently. Small procedural animations use `examples._runtime.wait` to pump foreground mock events while waiting; worker threads only sleep. Framework applications get event pumping from `run()`.

See [the framework guide](FRAMEWORK.md) for threading and resource ownership, and [cleanup evidence](code-cleanup.md) for regression coverage and unresolved limits.
