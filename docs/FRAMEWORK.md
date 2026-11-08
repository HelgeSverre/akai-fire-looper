# Building an application

`AkaiFireApp` is a sensible foundation for a controller application: it owns the connection lifecycle and display loop so each app can focus on its controls. Add mixins only when they remove work your app actually needs. Circuit uses the base runtime while keeping its musical clock and domain-specific modes; the synth editor and MIDI Scope use the base runtime directly.

## Lifecycle and ownership

| Hook | When it runs | Typical work |
| --- | --- | --- |
| `on_init()` | During construction, before default subscriptions are installed | Initialize state, mixins and app resources |
| `on_start()` | At the start of `run()` | Draw the first screen, initialize LEDs |
| `on_update(dt)` | At `FPS` (default 30), with elapsed monotonic seconds | Update UI state and draw the canvas |
| `on_stop()` | Once during shutdown | Stop app workers, silence instruments, close app-owned resources |

`run(duration=2)` is a bounded run for a smoke test. `quit()` asks the loop to exit; `shutdown()` performs cleanup immediately. Shutdown is idempotent. An app cannot run again after shutdown. The optional startup banner is disabled by default; set `STARTUP_SECONDS` to enable it. The banner runs before `on_start()` so it cannot erase the app's first screen.

The base renders the canvas after each update and handles pygame events on the foreground thread. It removes the subscriptions it created. Removal errors are reported after every owned handler has been disabled/attempted; app stop and controller cleanup still run. If you pass `fire=...`, you own that controller and must close it yourself. Without an injected controller, the app owns and closes the connection. The app clears controller LEDs on shutdown, including when the controller was borrowed.

Resources acquired inside `on_init()` need local rollback if initialization fails. `on_stop()` is not a constructor rollback hook. App-created raw `fire.on_*` subscriptions also need explicit removal; prefer the base event hooks for ordinary input.

## Input

```python
class MyApp(AkaiFireApp):
    def on_pad_press(self, pad, velocity):
        # Only positive-velocity presses reach this hook.
        self.fire.set_pad_color(pad, 0, velocity, 0)

    def on_button_press(self, button_id, event):
        if event == "press" and button_id == self.fire.BUTTON_STOP:
            self.quit()

    def on_encoder_turn(self, encoder_id, direction, velocity):
        delta = velocity if direction == "clockwise" else -velocity
        print(encoder_id, delta)
```

Hardware callbacks normally run on the driver's executor, while `on_update()` runs on the foreground thread. Protect shared compound state with a lock or put events in your own queue. Setting `async_handlers=False` executes callbacks on the MIDI polling thread, **not** the frame thread. Mocks usually dispatch inline, so a passing mock test alone does not prove thread safety.

The hardware driver currently exposes pad presses, not pad releases. Use bounded auditions when driving a synth, as in [the editor](../examples/apps/synth_editor/midi.py), rather than starting indefinitely held notes. Button press/release and encoder turns are available; rotary-touch callbacks are available through the driver.

## Optional building blocks

| Building block | What it owns | What the app still supplies |
| --- | --- | --- |
| `ModeManagerMixin` | Mode registration, entry/exit, event forwarding | Call `init_mode_manager`, register handlers, route hooks and render |
| `ScreenMixin` | Common headers, values, menus and progress layouts | Content and refresh policy |
| `GridMixin` | Pad coordinates, row/column colors, batched patterns | Meaning of the grid |
| `TransportMixin` | Stopped/armed/playing/recording state and LEDs | A clock, recording engine and MIDI output |

`setup_transport_buttons()` installs standard PLAY/STOP/REC behavior and removes it with the app's subscriptions. If the app has custom record semantics, route those buttons once in `on_button_press()` instead of stacking another REC callback. The [clip-state demo](../examples/apps/looper/looper_app.py) shows that pattern.

Mode handlers receive encoder names after mixin mapping, while the base app receives numeric device constants. Mode switching does not provide rollback if a custom entry/exit hook fails. Keep hooks small and acquire resources outside mode transitions where possible.

## Testing without hardware

```python
from akai_fire_testing import MockAkaiFire
from examples.apps.pad_counter import PadCounterApp

fire = MockAkaiFire()
with PadCounterApp(fire) as app:
    fire.simulate_pad_press(3, 100)
    assert app.count == 1
    app.run(duration=0)
fire.close()
```

Use a separate fake instrument output for MIDI apps. Assert the emitted bytes, not only the displayed label. The [app tests](../tests/test_example_apps.py) cover routing, cancellation, snapshot validation and exported data. Test the hardware driver with mocked MIDI ports as well, because mocks do not reproduce its callback executor.

## Is it feature-complete?

For small controller tools, the foundation is enough. For larger applications, these are the most valuable missing capabilities:

1. A foreground event queue with documented ordering and modifier snapshots. Today each app must handle cross-thread state itself.
2. Public pad-release events with parity across hardware and mocks. This would enable held keyboards instead of timed auditions.
3. Explicit disconnect/reconnect notifications and app recovery hooks. The driver can reconnect, but the app runtime has no recovery policy.
4. A small owned-resource/subscription API for app-created workers and external MIDI. Current hooks cover cleanup, but acquisition rollback is manual.

Configuration persistence, patch formats, musical clocks, MIDI routing, and synth profiles should stay with the applications until multiple real consumers justify a common module. Adding them to the base class now would make every simple app depend on music-specific policy.
