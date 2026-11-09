# Application framework reference

For a step-by-step introduction, follow [Build an application: a pixel editor](BUILDING_AN_APP.md). It starts with a runnable pad-toggle app, then adds shared state, an OLED view, settings, persistence and tests. This page is the reference for lifecycle, ownership and reusable framework pieces.

`akai_fire_framework` is the optional application layer above the `akai_fire` device library. Its `AkaiFireApp` base class owns the connection lifecycle, input subscriptions and display loop so your app can define what the controller does. Use the device library directly when integrating with an existing program; use the framework when you want these application services provided for you.

Mixins add modes, screen layouts, grid helpers and transport state as needed. The example apps demonstrate these choices: Circuit keeps its musical clock and domain-specific modes; the synth editor, MIDI Scope and Snake use the base runtime directly.

## Lifecycle and ownership

| Hook | When it runs | Typical work |
| --- | --- | --- |
| `on_init()` | During construction, before default subscriptions are installed | Initialize state, mixins and app resources |
| `on_start()` | At the start of `run()` | Draw the first screen, initialize LEDs |
| `on_update(dt)` | Up to `FPS` (default 30), with elapsed monotonic seconds | Update UI state and draw the canvas |
| `on_stop()` | Once during shutdown | Stop app workers, silence instruments, close app-owned resources |

`run(duration=2)` is a bounded run for a smoke test. `quit()` asks the loop to exit; `shutdown()` performs cleanup immediately. Shutdown is idempotent. An app cannot run again after shutdown. The optional startup banner is disabled by default; set `STARTUP_SECONDS` to enable it. The banner runs before `on_start()` so it cannot erase the app's first screen.

The base renders the canvas after each update and handles pygame events on the foreground thread. It removes the subscriptions it created. Removal errors are reported after every owned handler has been disabled/attempted; app stop and controller cleanup still run. If you pass `fire=...`, you own that controller and must close it yourself. Without an injected controller, the app owns and closes the connection. The app clears controller LEDs and renders a goodbye screen on shutdown, including when the controller was borrowed.

Resources acquired inside `on_init()` need local rollback if initialization fails. `on_stop()` is not a constructor rollback hook. App-created raw `fire.on_*` subscriptions also need explicit removal; prefer app decorators for ordinary input.

## Declarative input

```python
from akai_fire.constants import BUTTON_STOP, ROTARY_SELECT
from akai_fire_framework import AkaiFireApp, on


class MyApp(AkaiFireApp):
    @on.pad()
    def paint(self, event):
        self.fire.set_pad_color(event.pad, 0, event.velocity, 0)

    @on.button(BUTTON_STOP)
    def stop(self, event):
        self.quit()

    @on.encoder(ROTARY_SELECT)
    def turn(self, event):
        print(event.delta, event.shift)
```

These decorators attach metadata to instance methods. The framework binds them after `on_init()`; no connection or subscription is created at import time. Device callbacks enqueue frozen events. `tick(dt)` dispatches them on the foreground thread, calls `on_update(dt)`, then renders the OLED. `run()` uses that same tick path.

| Declaration | Filter | Event fields |
| --- | --- | --- |
| `@on.pad()` | Positive-velocity presses; all pads by default | `pad`, `velocity`, `shift`, `alt` |
| `@on.button()` | Presses by default; `action="release"` or `action=None` for both edges | `button`, `action`, `shift`, `alt` |
| `@on.encoder()` | All encoder turns by default | `encoder`, signed `delta`, `shift`, `alt` |

Pass one control ID or an iterable to select controls. All decorators accept `shift=True/False` and `alt=True/False`; omitted modifiers do not filter. Snapshots retain modifier state from the original input event. A selected-control handler still receives the same one-event signature. `PadEvent`, `ButtonEvent` and `EncoderEvent` are exported for type annotations.

All matching methods run. Stacked matching decorators on the same method call it only once per event. Discovery follows the Python MRO, with derived-class methods first and definition order within each class. An override replaces a base handler; an undecorated override removes its declaration. Each app has separate bindings and queued input.

`INPUT_QUEUE_SIZE` defaults to 1024 matching events; `INPUTS_PER_FRAME` defaults to 64. Both must be positive integers. Input beyond capacity latches an error, raised by the next tick before dispatch; shutdown and create a new app after overflow. There is no silent dropping or automatic recovery. Exceptions from decorated handlers propagate just like `on_update()` exceptions; `run()` always shuts down in its `finally` block. A manual caller of `tick()` must use an app context manager or handle shutdown itself. `quit()` or `shutdown()` inside a handler prevents further handlers and update work in that frame.

Use `tick(dt)` on the foreground thread; recursive frames are rejected. It accepts finite, nonnegative elapsed seconds. For deterministic tests, call `on_start()` once, simulate input, and call `tick(dt)`. Closing the app rejects late input, discards queued events and removes its subscriptions. Injected controllers remain borrowed.

The queue preserves callback arrival order. Inject `AkaiFire(max_workers=1)` when strict hardware input ordering matters; a multi-worker driver can reorder callbacks before they reach the queue. The Pixel Editor and Firestorm hardware launchers use one worker.

### Legacy hooks and raw decorators

Existing `on_pad_press(pad, velocity)`, `on_button_press(button, action)` and `on_encoder_turn(encoder, direction, velocity)` overrides retain immediate delivery on the device callback thread. They are not foreground-safe merely because the app now supports decorators. Apps using these hooks must keep their own synchronization. If one of these method names is itself decorated, it uses only the declared event signature and queued path.

Raw `@fire.on_pad()` and related driver decorators remain useful outside the app runtime. App-created raw subscriptions require explicit removal. Setting `async_handlers=False` runs raw callbacks on the MIDI polling thread, not the frame thread. Mixing legacy hooks and separate decorated methods can execute both for an event; prefer one style for each behavior.

The driver exposes pad presses, not pad releases. Use short timed notes for a synthesizer. Button edges and encoder turns are available through app decorators; rotary touch remains a driver API.

## Optional building blocks

| Building block | What it owns | What the app still supplies |
| --- | --- | --- |
| `ModeManagerMixin` | Mode registration, entry/exit, event forwarding | Call `init_mode_manager`, register handlers, route hooks and render |
| `ScreenMixin` | Common headers, values, menus and progress layouts | Content and refresh policy |
| `GridMixin` | Pad coordinates, row/column colors, batched patterns | Meaning of the grid |
| `TransportMixin` | Stopped/armed/playing/recording state and LEDs | A clock, recording engine and MIDI output |
| `EncoderMenu` / `MenuItem` | Selection and press-to-edit transitions | Value storage, bounds, input routing and drawing |

`ScreenMixin.draw_header()` reserves four pixels on both horizontal edges by default. Override `HEADER_PADDING_X` on your app or screen class to change that inset. Header alignment and fitted canvas text use monochrome font measurements, matching the OLED's actual glyph spacing.

`setup_transport_buttons()` installs standard PLAY/STOP/REC behavior and removes it with the app's subscriptions. If the app has custom record semantics, route those buttons once in `on_button_press()` instead of stacking another REC callback. The [clip-state demo](../examples/apps/looper/looper_app.py) shows that pattern.

Mode handlers receive encoder names after mixin mapping, while the base app receives numeric device constants. Mode switching does not provide rollback if a custom entry/exit hook fails. Keep hooks small and acquire resources outside mode transitions where possible.

## Press-to-edit menus

`EncoderMenu` implements turn to navigate, press to edit, turn to adjust, and press again to finish. Circuit uses it for Settings. Changes apply live; finishing an edit does not roll them back.

```python
from akai_fire.constants import BUTTON_SELECT, ROTARY_SELECT
from akai_fire_framework import AkaiFireApp, EncoderMenu, MenuItem, on


class TempoMenu(AkaiFireApp):
    def on_init(self):
        self.bpm = 120
        self.menu = EncoderMenu(
            [
                MenuItem("Tempo", adjust=self.adjust_tempo),
                MenuItem("Exit", activate=self.quit),
            ]
        )

    def adjust_tempo(self, delta):
        self.bpm = max(30, min(300, self.bpm + delta))

    @on.encoder(ROTARY_SELECT)
    def turn(self, event):
        self.menu.turn(event.delta)

    @on.button(BUTTON_SELECT)
    def press(self, event):
        self.menu.press()

    def on_update(self, dt):
        label = self.menu.items[self.menu.selected_index].label
        self.canvas.clear()
        self.canvas.draw_text_fitted(label, 4, 4)
        self.canvas.draw_text_fitted(str(self.bpm), 4, 24)
        hint = "Press: done" if self.menu.editing else "Press: select"
        self.canvas.draw_text_fitted(hint, 4, 44)
```

Navigation stops at the first and last item unless `wrap=True`. By default, `move(delta)` and `select(index)` end editing. An app can keep editing while moving between values instead:

```python
# Route GRID RIGHT to the next setting, retaining an active edit.
menu.move(1, keep_editing=True)
# Direct selection, such as a pad shortcut, supports the same policy.
menu.select(2, keep_editing=True)
```

`keep_editing` preserves an existing edit; it does not start one during navigation. Moving onto an action or read-only item always leaves edit mode, without executing the action. A clamped move at the list boundary preserves the edit when requested. Circuit currently uses the default finish-on-navigation behavior.

Call `finish_editing()` when leaving a screen. Items with `activate` execute on press; items with neither callback are read-only. An item cannot have both callbacks. Finishing an edit keeps its live changes; applications that need cancel/rollback must own a saved value and restore it explicitly.

The menu serializes its own transitions, but callbacks run on the calling thread. Applications remain responsible for synchronizing their model and drawing, as described under Input. For a compound display snapshot, hold an app-owned lock around input and rendering, as Circuit does.

## Testing without hardware

```python
from akai_fire_testing import MockAkaiFire

# MyApp is the class defined in the Input example above.
with MockAkaiFire() as fire, MyApp(fire) as app:
    app.on_start()
    fire.simulate_pad_press(3, 100)
    app.tick(1 / 30)
    fire.assert_pad_color(3, (0, 100, 0))
    app.run(duration=0)
```

Use a separate fake instrument output for MIDI apps. Assert the emitted bytes, not only the displayed label. The [app tests](../tests/test_example_apps.py) cover routing, cancellation, snapshot validation and exported data. Test the hardware driver with mocked MIDI ports as well, because mocks do not reproduce its callback executor.

## Current limits

For small controller tools, the foundation is enough. For larger applications, these are the most valuable missing capabilities:

1. Public pad-release events with parity across hardware and mocks. This would enable held keyboards instead of timed auditions.
2. Explicit disconnect/reconnect notifications and app recovery hooks. The driver can reconnect, but the app runtime has no recovery policy.
3. A small owned-resource/subscription API for app-created workers and external MIDI. Current hooks cover cleanup, but acquisition rollback is manual.

Configuration persistence, patch formats, musical clocks, MIDI routing, and synth profiles should stay with the applications until multiple real consumers justify a common module. Adding them to the base class now would make every simple app depend on music-specific policy.
