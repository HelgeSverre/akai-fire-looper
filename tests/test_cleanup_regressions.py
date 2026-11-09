"""Deterministic regressions for driver and framework lifecycle ownership."""

import threading
import unittest
from unittest.mock import Mock, patch

from akai_fire import AkaiFire
from akai_fire.errors import MIDIConnectionError
from akai_fire_framework import AkaiFireApp, TransportMixin
from tests.test_akai_fire import MockMidiPort


class HardwareLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.input = MockMidiPort()
        self.output = MockMidiPort()
        self.in_factory = patch("rtmidi.MidiIn", return_value=self.input).start()
        self.out_factory = patch("rtmidi.MidiOut", return_value=self.output).start()
        self.addCleanup(patch.stopall)
        self.fire = AkaiFire(async_handlers=False)
        self.addCleanup(self.fire.close)

    def test_read_failure_marks_listener_stopped_and_allows_restart(self):
        self.input.get_message = Mock(side_effect=RuntimeError("disconnected"))
        with self.assertLogs("akai_fire", level="ERROR"):
            self.fire.start_listening()
            first = self.fire.listening_thread
            first.join(1)
        self.assertFalse(first.is_alive())
        self.assertFalse(self.fire.listening)
        self.input.get_message = Mock(return_value=None)
        self.fire.start_listening()
        self.assertIsNot(self.fire.listening_thread, first)
        self.assertTrue(self.fire.listening)

    def test_inline_handler_can_close(self):
        done = threading.Event()
        errors = []

        def close_from_handler(velocity):
            try:
                self.fire.close()
            except RuntimeError as exc:
                errors.append(exc)
            finally:
                done.set()

        self.fire.add_listener(0, close_from_handler)
        self.input.messages.append([0x90, 54, 100])
        self.assertTrue(done.wait(1))
        self.fire.listening_thread.join(1)
        self.assertEqual(errors, [])
        self.assertFalse(self.input.is_port_open)
        self.assertFalse(self.output.is_port_open)

    def test_retired_poll_read_cannot_dispatch_after_reconnect(self):
        entered = threading.Event()
        release = threading.Event()
        received = []

        def blocked_read():
            entered.set()
            release.wait(3)
            return ([0x90, 54, 100], 0)

        self.input.get_message = blocked_read
        self.fire.add_listener(0, received.append)
        old_thread = self.fire.listening_thread
        self.assertTrue(entered.wait(1))
        self.in_factory.return_value = MockMidiPort()
        self.out_factory.return_value = MockMidiPort()
        try:
            # Exercise the documented bounded join without a two-second delay.
            with patch.object(old_thread, "join"):
                self.assertTrue(self.fire.reconnect())
            release.set()
            old_thread.join(1)
            self.assertFalse(old_thread.is_alive())
            self.assertEqual(received, [])
            self.assertTrue(self.fire.listening)
        finally:
            release.set()

    def test_context_exit_closes_even_if_display_send_fails(self):
        with (
            patch.object(self.fire, "clear_display", side_effect=RuntimeError("OLED")),
            self.assertRaises(RuntimeError),
            self.fire,
        ):
            pass
        self.assertFalse(self.input.is_port_open)
        self.assertFalse(self.output.is_port_open)

    def test_failed_constructor_closes_partially_open_output(self):
        self.input.open_port = Mock(side_effect=RuntimeError("input unavailable"))
        with self.assertRaises(MIDIConnectionError):
            AkaiFire()
        self.assertFalse(self.output.is_port_open)

    def test_failed_reconnect_closes_partially_open_output(self):
        replacement_input = MockMidiPort()
        replacement_output = MockMidiPort()
        replacement_input.open_port = Mock(
            side_effect=RuntimeError("input unavailable")
        )
        self.in_factory.return_value = replacement_input
        self.out_factory.return_value = replacement_output
        with self.assertLogs("akai_fire", level="ERROR"):
            self.assertFalse(self.fire.reconnect())
        self.assertFalse(replacement_output.is_port_open)
        self.assertFalse(self.fire.listening)


class AppLifecycleTests(unittest.TestCase):
    def make_app(self, owned=False):
        fire = Mock()
        fire.process_events.return_value = False
        with patch("akai_fire_framework.app.get_akai_fire", return_value=fire):
            app = AkaiFireApp() if owned else AkaiFireApp(fire)
        app.on_stop = Mock()
        app._show_startup_screen = Mock()
        return app, fire

    def test_run_and_context_exit_stop_only_once(self):
        app, fire = self.make_app(owned=True)
        with app:
            app.run()
        app.on_stop.assert_called_once()
        fire.close.assert_called_once()

    def test_failed_start_still_releases_owned_device(self):
        app, fire = self.make_app(owned=True)
        app.on_start = Mock(side_effect=RuntimeError("start"))
        with self.assertRaisesRegex(RuntimeError, "start"):
            app.run()
        self.assertFalse(app.running)
        fire.close.assert_called_once()

    def test_failing_stop_hook_still_releases_owned_device(self):
        app, fire = self.make_app(owned=True)
        app.on_stop.side_effect = RuntimeError("stop")
        with self.assertRaisesRegex(RuntimeError, "stop"):
            app.shutdown()
        fire.close.assert_called_once()

    def test_failing_goodbye_still_releases_owned_device(self):
        app, fire = self.make_app(owned=True)
        fire.clear_all.side_effect = RuntimeError("disconnected")
        app.shutdown()
        fire.close.assert_called_once()

    def test_first_frame_uses_elapsed_time(self):
        app, _ = self.make_app()
        app.on_update = Mock(side_effect=lambda dt: app.quit())
        # Both clocks patched to make the before/after comparison deterministic.
        with (
            patch("time.monotonic", side_effect=[100.0, 100.05]),
            patch("time.time", return_value=100.05),
        ):
            app.run()
        self.assertAlmostEqual(app.on_update.call_args.args[0], 0.05)


class TransportTests(unittest.TestCase):
    def test_callback_can_remove_itself_without_skipping_sibling(self):
        transport = TransportMixin()
        transport.init_transport()
        calls = []

        def first(new, old):
            calls.append("first")
            transport.remove_transport_callback(first)

        transport.add_transport_callback(first)
        transport.add_transport_callback(lambda new, old: calls.append("second"))
        transport.play()
        self.assertEqual(calls, ["first", "second"])


class CallbackAndCacheTests(unittest.TestCase):
    def make_fire(self, **kwargs):
        input_port, output_port = MockMidiPort(), MockMidiPort()
        with (
            patch("rtmidi.MidiIn", return_value=input_port),
            patch("rtmidi.MidiOut", return_value=output_port),
        ):
            fire = AkaiFire(**kwargs)
        self.addCleanup(fire.close)
        return fire, output_port

    def test_invalid_multi_registration_has_no_partial_effects(self):
        for method in ("on_pad", "add_listener"):
            with self.subTest(method=method):
                fire, _ = self.make_fire(async_handlers=False)
                callback = Mock()
                with self.assertRaises(ValueError):
                    if method == "on_pad":
                        fire.on_pad([0, 64])(callback)
                    else:
                        fire.add_listener([0, 64], callback)
                fire._process_message([[0x90, 54, 100], 0])
                callback.assert_not_called()

    def test_multi_pad_decorator_passes_pad_and_can_be_removed(self):
        fire, _ = self.make_fire(async_handlers=False)
        callback = Mock()
        fire.on_pad([0, 1])(callback)
        fire._process_message([[0x90, 54, 100], 0])
        fire._process_message([[0x90, 55, 80], 0])
        self.assertEqual(
            [call.args for call in callback.call_args_list], [(0, 100), (1, 80)]
        )
        fire.remove_listener([0, 1], callback)
        fire._process_message([[0x90, 54, 100], 0])
        self.assertEqual(callback.call_count, 2)

    def test_async_handler_observes_event_modifier_snapshot(self):
        fire, _ = self.make_fire(max_workers=1)
        entered, release, done = (threading.Event() for _ in range(3))
        observed = []

        def blocker(velocity):
            entered.set()
            release.wait(2)

        def observe(velocity):
            observed.append((fire.is_shift_pressed(), fire.alt_pressed))
            done.set()

        fire.add_listener(0, blocker)
        fire.add_listener(1, observe)
        try:
            fire._process_message([[0x90, 54, 100], 0])
            self.assertTrue(entered.wait(1))
            fire._process_message([[0x90, fire.BUTTON_SHIFT, 127], 0])
            fire._process_message([[0x90, fire.BUTTON_ALT, 127], 0])
            fire._process_message([[0x90, 55, 100], 0])
            fire._process_message([[0x80, fire.BUTTON_SHIFT, 0], 0])
            fire._process_message([[0x80, fire.BUTTON_ALT, 0], 0])
            release.set()
            self.assertTrue(done.wait(1))
            self.assertEqual(observed, [(True, True)])
            self.assertFalse(fire.shift_pressed)
            self.assertFalse(fire.alt_pressed)
        finally:
            release.set()

    def test_serial_dispatch_preserves_fifo_at_capacity(self):
        fire, _ = self.make_fire(max_workers=1, handler_queue_size=2)
        entered, release, attempted, done = (threading.Event() for _ in range(4))
        received = []

        def handler(pad, velocity):
            if pad == 0:
                entered.set()
                release.wait(2)
            received.append(pad)
            if len(received) == 3:
                done.set()

        fire.on_pad()(handler)
        fire._process_message([[0x90, 54, 100], 0])
        self.assertTrue(entered.wait(1))
        fire._process_message([[0x90, 55, 100], 0])
        original_acquire = fire._dispatcher._sem.acquire

        def acquire(*args, **kwargs):
            attempted.set()
            return original_acquire(*args, **kwargs)

        with patch.object(fire._dispatcher._sem, "acquire", side_effect=acquire):
            producer = threading.Thread(
                target=fire._process_message, args=([[0x90, 56, 100], 0],)
            )
            producer.start()
            try:
                self.assertTrue(attempted.wait(1))
            finally:
                release.set()
            producer.join(1)
        self.assertTrue(done.wait(1))
        self.assertEqual(received, [0, 1, 2])

    def test_pad_wire_order_matches_cached_state(self):
        fire, port = self.make_fire(async_handlers=False)
        delivered, release, second_started = (threading.Event() for _ in range(3))
        original_send = port.send_message

        def send(message):
            original_send(message)
            if threading.current_thread().name == "first-pad-write":
                delivered.set()
                release.wait(2)

        port.send_message = send
        first = threading.Thread(
            target=fire.set_pad_color, args=(0, 127, 0, 0), name="first-pad-write"
        )

        def second_write():
            second_started.set()
            fire.set_pad_color(0, 0, 127, 0)

        second = threading.Thread(target=second_write)
        first.start()
        try:
            self.assertTrue(delivered.wait(1))
            second.start()
            self.assertTrue(second_started.wait(1))
            # On fixed code the second send is serialized behind the first.
            # On baseline wait for its completion before allowing cache commit.
            if not hasattr(fire, "_io_lock"):
                second.join(1)
        finally:
            release.set()
        first.join(1)
        second.join(1)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(tuple(port.messages[-1][8:11]), fire._last_pad_states[0])
        count = len(port.messages)
        fire.set_pad_color(0, 127, 0, 0)
        self.assertEqual(len(port.messages), count + 1)


class FrameworkInitializationTests(unittest.TestCase):
    def test_event_registration_occurs_after_user_initialization(self):
        from akai_fire_testing import MockAkaiFire

        class ImmediateFire(MockAkaiFire):
            def start_listening(self):
                self._dispatch_pad(0, 100)

        calls = []

        class App(AkaiFireApp):
            def on_init(self):
                self.ready = True

            def on_pad_press(self, pad, velocity):
                calls.append(getattr(self, "ready", False))

        App(ImmediateFire())
        self.assertTrue(calls)
        self.assertTrue(all(calls))

    def test_record_toggle_cancels_arm(self):
        from akai_fire_framework import TransportState

        transport = TransportMixin()
        transport.init_transport()
        transport.toggle_record()
        self.assertEqual(transport.transport_state, TransportState.ARMED)
        transport.toggle_record()
        self.assertEqual(transport.transport_state, TransportState.STOPPED)


class ModeAndBorrowedDeviceTests(unittest.TestCase):
    def test_zero_valued_mode_exits_normally(self):
        from enum import IntEnum

        from akai_fire_framework import ModeManagerMixin

        class Mode(IntEnum):
            FIRST = 0
            SECOND = 1

        modes = ModeManagerMixin()
        modes.init_mode_manager(Mode, Mode.FIRST)
        first, second = Mock(), Mock()
        modes.register_mode(Mode.FIRST, first)
        modes.register_mode(Mode.SECOND, second)
        modes.set_mode(Mode.FIRST)
        modes.set_mode(Mode.SECOND)
        first.on_exit.assert_called_once()
        second.on_enter.assert_called_once_with(first)

    def test_shutdown_detaches_handlers_from_borrowed_device(self):
        from akai_fire_testing import MockAkaiFire

        fire = MockAkaiFire()
        app = AkaiFireApp(fire)
        app.on_pad_press = Mock()
        app.shutdown()
        fire._dispatch_pad(0, 100)
        app.on_pad_press.assert_not_called()
        self.assertEqual(fire.pad_listeners["global"], [])
        self.assertEqual(fire.button_listeners["global"], [])
        self.assertEqual(fire.rotary_listeners["global"], [])


class ChallengeRegressions(unittest.TestCase):
    def test_nested_dispatch_uses_new_latch_but_siblings_keep_event_snapshot(self):
        from akai_fire_testing import MockAkaiFire

        fire = MockAkaiFire()
        observations = []

        @fire.on_pad(0)
        def first(velocity):
            fire._dispatch_button(fire.BUTTON_SHIFT, "release")
            fire._dispatch_pad(1, 100)
            observations.append(("outer", fire.shift_pressed))

        @fire.on_pad(0)
        def sibling(velocity):
            observations.append(("sibling", fire.shift_pressed))

        @fire.on_pad(1)
        def nested(velocity):
            observations.append(("nested", fire.shift_pressed))

        fire._dispatch_button(fire.BUTTON_SHIFT, "press")
        fire._dispatch_pad(0, 100)
        self.assertEqual(
            observations, [("nested", False), ("outer", True), ("sibling", True)]
        )
        self.assertFalse(fire.shift_pressed)

    def test_zero_sized_serial_queue_is_rejected_before_opening_ports(self):
        with (
            patch("rtmidi.MidiIn") as input_factory,
            self.assertRaisesRegex(ValueError, "handler_queue_size"),
        ):
            AkaiFire(max_workers=1, handler_queue_size=0)
        input_factory.assert_not_called()

    def test_falsey_mode_handler_exits_and_receives_events(self):
        from enum import Enum

        from akai_fire_framework import ModeHandler, ModeManagerMixin

        class Mode(Enum):
            FIRST = "first"
            SECOND = "second"

        class Handler(ModeHandler):
            def __init__(self):
                self.calls = []

            def __bool__(self):
                return False

            def on_exit(self):
                self.calls.append("exit")

            def handle_pad_press(self, pad, velocity):
                self.calls.append("pad")
                return True

            def handle_encoder_turn(self, *args):
                self.calls.append("encoder")

            def handle_button_press(self, button):
                self.calls.append("button")
                return True

            def on_step(self, step):
                self.calls.append("step")

            def on_transport_change(self, state):
                self.calls.append("transport")

            def get_display_info(self):
                return {}

        modes, handler = ModeManagerMixin(), Handler()
        modes.init_mode_manager(Mode, Mode.FIRST)
        modes.register_mode(Mode.FIRST, handler)
        modes.register_mode(Mode.SECOND, Mock())
        modes.set_mode(Mode.FIRST)
        self.assertTrue(modes.dispatch_pad_press(0, 100))
        modes.dispatch_encoder_turn(0x10, "clockwise", 1)
        self.assertTrue(modes.dispatch_button_press("play"))
        modes.dispatch_step(0)
        modes.dispatch_transport_change("playing")
        modes.set_mode(Mode.SECOND)
        self.assertEqual(
            handler.calls, ["pad", "encoder", "button", "step", "transport", "exit"]
        )


class TransportOwnershipTests(unittest.TestCase):
    def test_borrowed_app_detaches_standard_transport_buttons(self):
        from akai_fire_framework import TransportState
        from akai_fire_testing import MockAkaiFire

        class App(AkaiFireApp, TransportMixin):
            def on_init(self):
                self.init_transport()
                self.setup_transport_buttons()
                self.setup_transport_buttons()

        fire = MockAkaiFire()
        app = App(fire)
        self.assertEqual(len(fire.button_listeners[fire.BUTTON_PLAY]), 1)
        app.shutdown()
        fire._dispatch_button(fire.BUTTON_PLAY, "press")
        self.assertEqual(app.transport_state, TransportState.STOPPED)
        for button in (fire.BUTTON_PLAY, fire.BUTTON_STOP, fire.BUTTON_REC):
            self.assertEqual(fire.button_listeners[button], [])


class FailedRegistrationTests(unittest.TestCase):
    def test_failed_app_registration_removes_partial_callbacks(self):
        from akai_fire_testing import MockAkaiFire

        for transport in (False, True):
            for failure_number in range(1, 7 if transport else 4):
                with self.subTest(transport=transport, registration=failure_number):

                    class App(AkaiFireApp, TransportMixin):
                        def on_init(self, transport=transport):
                            if transport:
                                self.init_transport()
                                self.setup_transport_buttons()

                    fire = MockAkaiFire()
                    fire.start_listening = Mock(
                        side_effect=[None] * (failure_number - 1)
                        + [RuntimeError("start")]
                    )
                    with self.assertRaisesRegex(RuntimeError, "start"):
                        App(fire)
                    for registry in (
                        fire.pad_listeners,
                        fire.button_listeners,
                        fire.rotary_listeners,
                    ):
                        self.assertFalse(any(registry.values()))


class StandaloneTransportRegistrationTests(unittest.TestCase):
    def test_transport_feedback_uses_primary_colors_not_amber(self):
        from akai_fire_testing import MockAkaiFire

        transport = TransportMixin()
        with MockAkaiFire() as fire:
            transport.fire = fire
            transport.init_transport()
            transport.play()
            transport.update_transport_leds()
            fire.assert_button_led(fire.BUTTON_PLAY, fire.DUAL_LED_BRIGHT_PRIMARY)
            transport.record()
            transport.update_transport_leds()
            fire.assert_button_led(fire.BUTTON_REC, fire.DUAL_LED_BRIGHT_PRIMARY)
            fire.assert_button_led(fire.BUTTON_PLAY, fire.DUAL_LED_DIM_PRIMARY)
            transport.stop()
            transport.update_transport_leds()
            fire.assert_button_led(fire.BUTTON_PLAY, 0)
            fire.assert_button_led(fire.BUTTON_REC, 0)
            fire.assert_button_led(fire.BUTTON_STOP, 1)

    def test_failed_setup_rolls_back_and_can_retry(self):
        from akai_fire_testing import MockAkaiFire

        transport = TransportMixin()
        transport.fire = MockAkaiFire()
        transport.init_transport()
        with (
            patch.object(
                transport.fire, "start_listening", side_effect=RuntimeError("start")
            ),
            self.assertRaises(RuntimeError),
        ):
            transport.setup_transport_buttons()
        self.assertFalse(any(transport.fire.button_listeners.values()))
        transport.setup_transport_buttons()
        transport.fire._dispatch_button(transport.fire.BUTTON_PLAY, "press")
        self.assertTrue(transport.is_playing)


class SubscriptionOwnershipTests(unittest.TestCase):
    def test_shutdown_disables_queued_app_callback_and_preserves_user_listener(self):
        from akai_fire_testing import MockAkaiFire

        fire = MockAkaiFire()
        user_callback = Mock()
        fire.add_global_listener(user_callback)
        app = AkaiFireApp(fire)
        app.on_pad_press = Mock()
        queued = fire.pad_listeners["global"][-1]
        app.shutdown()
        queued(0, 100)
        fire._dispatch_pad(0, 100)
        app.on_pad_press.assert_not_called()
        user_callback.assert_called_once_with(0, 100)

    def test_rolled_back_transport_callbacks_stay_inactive_after_retry(self):
        from akai_fire_testing import MockAkaiFire

        transport = TransportMixin()
        transport.fire = MockAkaiFire()
        transport.init_transport()
        queued = []

        def fail_start():
            queued.extend(transport.fire.button_listeners[transport.fire.BUTTON_PLAY])
            raise RuntimeError("start")

        with (
            patch.object(transport.fire, "start_listening", side_effect=fail_start),
            self.assertRaises(RuntimeError),
        ):
            transport.setup_transport_buttons()
        self.assertEqual(len(queued), 1)
        transport.setup_transport_buttons()
        queued[0]("press")
        self.assertTrue(transport.is_stopped)
        transport.fire._dispatch_button(transport.fire.BUTTON_PLAY, "press")
        self.assertTrue(transport.is_playing)
