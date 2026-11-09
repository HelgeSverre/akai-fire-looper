"""Declarative handlers through real subscriptions and foreground frames."""

import threading
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from akai_fire.constants import BUTTON_PLAY, BUTTON_SHIFT, ROTARY_SELECT
from akai_fire_framework import AkaiFireApp, on
from akai_fire_testing import MockAkaiFire


class AppEventsTests(unittest.TestCase):
    def make(self, cls):
        fire = MockAkaiFire()
        self.addCleanup(fire.close)
        app = cls(fire)
        self.addCleanup(app.shutdown)
        return fire, app

    def test_worker_input_is_frozen_and_delivered_before_update_on_frame_thread(self):
        calls = []

        class App(AkaiFireApp):
            @on.pad(3)
            def paint(self, event):
                calls.append(("pad", event, threading.get_ident()))

            @on.encoder(ROTARY_SELECT)
            def turn(self, event):
                calls.append(("turn", event, threading.get_ident()))

            def on_update(self, dt):
                calls.append(("update", dt, threading.get_ident()))

        fire, app = self.make(App)

        def produce():
            fire.simulate_button_press(BUTTON_SHIFT)
            fire.simulate_pad_press(3)
            fire.simulate_rotary_turn(ROTARY_SELECT, "counterclockwise", 4)
            fire.simulate_button_release(BUTTON_SHIFT)

        worker = threading.Thread(target=produce)
        worker.start()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, [])
        app.tick(0.1)
        self.assertEqual([c[0] for c in calls], ["pad", "turn", "update"])
        self.assertTrue(all(c[2] == threading.get_ident() for c in calls))
        self.assertTrue(calls[0][1].shift)
        self.assertTrue(calls[1][1].shift)
        self.assertEqual(calls[1][1].delta, -4)
        with self.assertRaises(FrozenInstanceError):
            calls[0][1].pad = 9

    def test_filters_edges_stacked_decorators_and_legacy_delivery(self):
        calls = []

        class App(AkaiFireApp):
            def on_button_press(self, button, action):
                calls.append(("legacy", button, action))

            @on.button(BUTTON_PLAY)
            def play(self, event):
                calls.append(("play", event.action))

            @on.button(BUTTON_PLAY, action="release")
            def release(self, event):
                calls.append(("release", event.action))

            @on.pad([0, 1], shift=True, alt=False)
            @on.pad(0, shift=True)
            def shifted(self, event):
                calls.append(("pad", event.pad))

        fire, app = self.make(App)
        fire.simulate_button_press(BUTTON_PLAY)
        fire.simulate_button_release(BUTTON_PLAY)
        self.assertEqual([c[0] for c in calls], ["legacy", "legacy"])
        fire.simulate_pad_press(0)
        fire.simulate_button_press(BUTTON_SHIFT)
        fire.simulate_pad_press(0)
        fire.simulate_pad_press(1)
        fire.simulate_button_release(BUTTON_SHIFT)
        app.tick(0)
        self.assertEqual(
            [c for c in calls if c[0] != "legacy"],
            [("play", "press"), ("release", "release"), ("pad", 0), ("pad", 1)],
        )

    def test_inheritance_override_and_instance_isolation(self):
        class Base(AkaiFireApp):
            def on_init(self):
                self.seen = []

            @on.pad()
            def paint(self, event):
                self.seen.append(("base", event.pad))

        class Removed(Base):
            def paint(self, event):
                raise AssertionError("Undecorated override should not subscribe")

        class Replaced(Base):
            @on.pad(1)
            def paint(self, event):
                self.seen.append(("child", event.pad))

        fa, a = self.make(Base)
        fb, b = self.make(Replaced)
        fc, c = self.make(Removed)
        for fire in (fa, fb, fc):
            fire.simulate_pad_press(0)
            fire.simulate_pad_press(1)
        for app in (a, b, c):
            app.tick(0)
        self.assertEqual(a.seen, [("base", 0), ("base", 1)])
        self.assertEqual(b.seen, [("child", 1)])
        self.assertEqual(c.seen, [])

    def test_batch_limit_and_recursive_input_wait_for_next_frame(self):
        class App(AkaiFireApp):
            INPUTS_PER_FRAME = 2

            def on_init(self):
                self.seen = []

            @on.pad()
            def paint(self, event):
                self.seen.append(event.pad)
                if event.pad == 0:
                    self.fire.simulate_pad_press(3)

        fire, app = self.make(App)
        for pad in (0, 1, 2):
            fire.simulate_pad_press(pad)
        app.tick(0)
        self.assertEqual(app.seen, [0, 1])
        app.tick(0)
        self.assertEqual(app.seen, [0, 1, 2, 3])

    def test_handler_does_not_block_worker_enqueue(self):
        class App(AkaiFireApp):
            @on.pad(0)
            def paint(self, event):
                worker = threading.Thread(
                    target=lambda: self.fire.simulate_pad_press(1)
                )
                worker.start()
                worker.join(1)
                if worker.is_alive():
                    raise AssertionError("Frame held the input lock during user code")

            @on.pad(1)
            def other(self, event):
                self.received = True

        fire, app = self.make(App)
        fire.simulate_pad_press(0)
        app.tick(0)
        app.tick(0)
        self.assertTrue(app.received)

    def test_overflow_fails_on_foreground_and_run_cleans_up(self):
        class App(AkaiFireApp):
            INPUT_QUEUE_SIZE = 2

            def on_start(self):
                for pad in range(3):
                    self.fire.simulate_pad_press(pad)

            @on.pad()
            def paint(self, event):
                raise AssertionError("Overflow must surface before consuming events")

        fire, app = self.make(App)
        with self.assertRaisesRegex(RuntimeError, "input queue overflow"):
            app.run()
        self.assertTrue(app._shutdown)
        self.assertFalse(fire.pad_listeners["global"])
        self.assertTrue(fire.is_connected())

    def test_shutdown_and_late_callbacks_discard_pending_events(self):
        class App(AkaiFireApp):
            @on.pad()
            def paint(self, event):
                raise AssertionError("Retired event executed")

        fire, app = self.make(App)
        late = fire.pad_listeners["global"][0]
        fire.simulate_pad_press(0)
        app.shutdown()
        late(1, 127)
        app._receive_pad(
            2, 127
        )  # A receiver already in flight crosses the queue fence.
        self.assertFalse(app._input_router._queue)
        with self.assertRaisesRegex(RuntimeError, "shut down"):
            app.tick(0)

    def test_quit_or_shutdown_in_handler_prevents_more_handlers_and_update(self):
        for stop in ("quit", "shutdown"):
            calls = []

            class App(AkaiFireApp):
                log = calls
                stop_method = stop

                @on.pad()
                def first(self, event):
                    self.log.append("first")
                    getattr(self, self.stop_method)()

                @on.pad()
                def second(self, event):
                    self.log.append("second")

                def on_update(self, dt):
                    self.log.append("update")

            fire, app = self.make(App)
            fire.simulate_pad_press(0)
            fire.simulate_pad_press(1)
            app.tick(0)
            self.assertEqual(calls, ["first"])

    def test_decorated_legacy_name_is_not_also_called_with_old_signature(self):
        class App(AkaiFireApp):
            @on.pad()
            def on_pad_press(self, event):
                self.pad = event.pad

        fire, app = self.make(App)
        fire.simulate_pad_press(4)
        app.tick(0)
        self.assertEqual(app.pad, 4)

    def test_callback_failure_propagates_and_run_unsubscribes(self):
        class App(AkaiFireApp):
            def on_start(self):
                self.fire.simulate_pad_press(0)

            @on.pad()
            def fail(self, event):
                raise ValueError("broken application handler")

        fire, app = self.make(App)
        with self.assertRaisesRegex(ValueError, "broken application handler"):
            app.run()
        self.assertFalse(fire.pad_listeners["global"])
        self.assertTrue(app._shutdown)

    def test_tick_rejects_invalid_time_and_reentrancy(self):
        _, app = self.make(AkaiFireApp)
        for dt in (-1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                app.tick(dt)
        with (
            patch.object(app, "on_update", side_effect=lambda dt: app.tick(dt)),
            self.assertRaisesRegex(RuntimeError, "already active"),
        ):
            app.tick(0)
        self.assertFalse(app._ticking)

    def test_invalid_filters_fail_before_registration(self):
        for declaration in (
            lambda: on.pad(64),
            lambda: on.pad(True),
            lambda: on.pad([]),
            lambda: on.button(action="down"),
            lambda: on.encoder(0),
            lambda: on.pad(shift=1),
        ):
            with self.assertRaises(ValueError):
                declaration()

    def test_invalid_method_shapes_fail_without_leaking_subscriptions(self):
        class Static(AkaiFireApp):
            @staticmethod
            @on.pad()
            def pad(event):
                pass

        class WrongArity(AkaiFireApp):
            @on.pad()
            def pad(self, pad, velocity):
                pass

        for cls in (Static, WrongArity):
            with MockAkaiFire() as fire:
                with self.assertRaises(TypeError):
                    cls(fire)
                self.assertFalse(fire.pad_listeners["global"])
                self.assertTrue(fire.is_connected())

    def test_owned_decorator_apps_choose_serial_workers_without_changing_legacy_apps(
        self,
    ):
        class Decorated(AkaiFireApp):
            @on.pad()
            def pad(self, event):
                pass

        class Removed(Decorated):
            def pad(self, event):
                pass

        for cls, options in (
            (Decorated, {"max_workers": 1}),
            (AkaiFireApp, {}),
            (Removed, {}),
        ):
            fire = MockAkaiFire()
            with patch(
                "akai_fire_framework.app.get_akai_fire", return_value=fire
            ) as factory:
                with cls() as app:
                    self.assertTrue(app._owns_fire)
                factory.assert_called_once_with(**options)
            self.assertFalse(fire.is_connected())

    def test_factory_applies_worker_count_only_to_hardware_including_fallback(self):
        from akai_fire import get_akai_fire
        from akai_fire.errors import MIDIConnectionError

        with patch("akai_fire.hardware.AkaiFire") as hardware:
            self.assertIs(
                get_akai_fire(use_mock=False, max_workers=1), hardware.return_value
            )
            hardware.assert_called_once_with(oled_keepalive=True, max_workers=1)
        with patch("mock_gui_pygame.MockAkaiFire") as mock:
            self.assertIs(
                get_akai_fire(use_mock="pygame", max_workers=1), mock.return_value
            )
            mock.assert_called_once_with()
        with (
            patch(
                "akai_fire.hardware.AkaiFire",
                side_effect=MIDIConnectionError("offline"),
            ),
            patch("mock_gui_pygame.MockAkaiFire") as mock,
        ):
            self.assertIs(get_akai_fire(max_workers=1), mock.return_value)
            mock.assert_called_once_with()
