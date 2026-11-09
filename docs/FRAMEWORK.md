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

Resources acquired inside `on_init()` need local rollback if initialization fails. `on_stop()` is not a constructor rollback hook. App-created raw `fire.on_*` subscriptions also need explicit removal; prefer the base event hooks for ordinary input.

## Input

```python
from akai_fire_framework import AkaiFireApp


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

For state that belongs to the frame thread, enqueue input and draw from `on_update()`. Capture modifier state inside the callback, where it belongs to that event:

```python
from queue import Empty, SimpleQueue
from akai_fire_framework import AkaiFireApp


class PadLog(AkaiFireApp):
    def on_init(self):
        self.inputs = SimpleQueue()
        self.last = "Press a pad"

    def on_pad_press(self, pad, velocity):
        self.inputs.put((pad, self.fire.is_shift_pressed()))

    def on_update(self, dt):
        for _ in range(64):  # Leave time to render during a burst of input.
            try:
                pad, shifted = self.inputs.get_nowait()
            except Empty:
                break
            self.last = f"Pad {pad}" + (" + SHIFT" if shifted else "")
        self.canvas.clear()
        self.canvas.draw_text_fitted(self.last, 4, 24)
```

This queue transfers state safely to the frame thread; it does not reorder concurrently dispatched hardware callbacks. Inject a controller configured with `max_workers=1` if FIFO dispatch is required. For a model protected by a lock and rendered through two views, see [Snake](../examples/apps/snake/README.md).

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
from akai_fire_framework import AkaiFireApp, EncoderMenu, MenuItem


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

    def on_encoder_turn(self, encoder_id, direction, velocity):
        if encoder_id == self.fire.ROTARY_SELECT:
            self.menu.turn(velocity if direction == "clockwise" else -velocity)

    def on_button_press(self, button_id, event):
        if button_id == self.fire.BUTTON_SELECT and event == "press":
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
    fire.simulate_pad_press(3, 100)
    fire.assert_pad_color(3, (0, 100, 0))
    app.run(duration=0)
```

Use a separate fake instrument output for MIDI apps. Assert the emitted bytes, not only the displayed label. The [app tests](../tests/test_example_apps.py) cover routing, cancellation, snapshot validation and exported data. Test the hardware driver with mocked MIDI ports as well, because mocks do not reproduce its callback executor.

## Current limits

For small controller tools, the foundation is enough. For larger applications, these are the most valuable missing capabilities:

1. A foreground event queue with documented ordering and modifier snapshots. Today each app must handle cross-thread state itself.
2. Public pad-release events with parity across hardware and mocks. This would enable held keyboards instead of timed auditions.
3. Explicit disconnect/reconnect notifications and app recovery hooks. The driver can reconnect, but the app runtime has no recovery policy.
4. A small owned-resource/subscription API for app-created workers and external MIDI. Current hooks cover cleanup, but acquisition rollback is manual.

Configuration persistence, patch formats, musical clocks, MIDI routing, and synth profiles should stay with the applications until multiple real consumers justify a common module. Adding them to the base class now would make every simple app depend on music-specific policy.
