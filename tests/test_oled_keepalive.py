"""Hardware OLED refresh, including connection and frame ownership."""

import threading
import unittest
from unittest.mock import patch

from akai_fire import AkaiFire, get_akai_fire
from akai_fire.errors import MIDISendError
from tests.test_sysex_encoder import MockMidiPort


class OledKeepaliveTests(unittest.TestCase):
    def setUp(self):
        self.output = MockMidiPort()
        self.in_factory = patch("rtmidi.MidiIn", side_effect=MockMidiPort).start()
        self.out_factory = patch("rtmidi.MidiOut", return_value=self.output).start()
        # Exercise the real worker with short deadlines, without hardware.
        patch("akai_fire.hardware._OLED_KEEPALIVE_INTERVAL", 0.02, create=True).start()
        self.addCleanup(patch.stopall)

    def make_fire(self, **kwargs):
        fire = AkaiFire(async_handlers=False, **kwargs)
        self.addCleanup(fire.close)
        return fire

    def next_send(self, output=None):
        output = output or self.output
        sent = threading.Event()
        original = output.send_message

        def send(message):
            original(message)
            sent.set()

        output.send_message = send
        return sent

    def test_static_frame_repeats_without_input_or_render_calls(self):
        fire = self.make_fire()
        fire.get_canvas().draw_text("Keep this", 0, 0)
        fire.render_to_display()
        packet = list(self.output.messages[-1])
        fire.get_canvas().clear()  # Unsubmitted edits must not leak to hardware.
        sent = self.next_send()
        self.assertTrue(sent.wait(1), "Static OLED was never refreshed")
        fire.close()
        self.assertEqual(list(self.output.messages[-1]), packet)
        self.assertFalse(fire.listening)

    def test_connection_alone_does_not_start_display_traffic(self):
        fire = self.make_fire()
        self.assertIsNone(fire._oled_thread)
        self.assertFalse(self.next_send().wait(0.08))

    def test_new_render_moves_the_refresh_deadline(self):
        with patch("akai_fire.hardware.time.monotonic", return_value=100.0) as clock:
            fire = self.make_fire()
            fire.render_to_display()
            clock.return_value = 100.015
            fire.get_canvas().draw_text("New", 0, 0)
            fire.render_to_display()
            newest = list(self.output.messages[-1])
            sent = self.next_send()
            # The first frame would now be due, but the newer one is not.
            clock.return_value = 100.025
            self.assertFalse(sent.wait(0.08))
            clock.return_value = 100.04
            self.assertTrue(sent.wait(1))
            fire.close()
            self.assertEqual(list(self.output.messages[-1]), newest)

    def test_background_failure_retries_without_losing_the_frame(self):
        fire = self.make_fire()
        fire.render_to_display()
        recovered = threading.Event()
        original = self.output.send_message
        attempts = []

        def transient_failure(message):
            attempts.append(message)
            if len(attempts) == 1:
                raise RuntimeError("Temporary send failure")
            original(message)
            recovered.set()

        with self.assertLogs("akai_fire.hardware", level="WARNING"):
            self.output.send_message = transient_failure
            self.assertTrue(recovered.wait(1))
            fire.close()
        self.assertEqual(attempts[0], attempts[1])

    def test_factory_passes_opt_out_to_hardware_and_accepts_it_for_mock(self):
        fire = get_akai_fire(use_mock=False, oled_keepalive=False)
        self.addCleanup(fire.close)
        self.assertFalse(fire._oled_keepalive)
        with patch("mock_gui_pygame.MockAkaiFire") as mock:
            self.assertIs(
                get_akai_fire(use_mock=True, oled_keepalive=False), mock.return_value
            )
            mock.assert_called_once_with()

    def test_disabled_keepalive_sends_only_explicit_frames(self):
        fire = self.make_fire(oled_keepalive=False)
        fire.render_to_display()
        sent = self.next_send()
        self.assertFalse(sent.wait(0.08))
        fire.render_to_display()
        self.assertTrue(sent.is_set())
        self.assertEqual(len(self.output.messages), 2)

    def test_clear_replaces_the_frame_and_never_restores_old_content(self):
        fire = self.make_fire()
        fire.get_canvas().draw_text("Old", 0, 0)
        fire.render_to_display()
        fire.clear_display()
        sent = self.next_send()
        self.assertTrue(sent.wait(1))
        fire.close()
        self.assertFalse(any(self.output.messages[-1][11:-1]))

    def test_close_stops_worker_before_closing_returns(self):
        fire = self.make_fire()
        fire.render_to_display()
        worker = fire._oled_thread
        fire.close()
        self.assertFalse(worker.is_alive())
        count = len(self.output.messages)
        self.assertFalse(self.next_send().wait(0.08))
        self.assertEqual(len(self.output.messages), count)

    def test_failed_explicit_send_does_not_replace_last_good_frame(self):
        fire = self.make_fire()
        fire.get_canvas().draw_text("Good", 0, 0)
        fire.render_to_display()
        good = list(self.output.messages[-1])
        with (
            fire._io_lock,
            patch.object(self.output, "send_message", side_effect=RuntimeError("send")),
        ):
            fire.get_canvas().clear()
            with self.assertRaises(MIDISendError):
                fire.render_to_display()
        sent = self.next_send()
        self.assertTrue(sent.wait(1))
        fire.close()
        self.assertEqual(list(self.output.messages[-1]), good)

    def test_reconnect_drops_old_frame_until_an_explicit_render(self):
        fire = self.make_fire()
        fire.render_to_display()
        old_worker = fire._oled_thread
        replacement = MockMidiPort()
        self.out_factory.return_value = replacement
        self.assertTrue(fire.reconnect())
        self.assertFalse(old_worker.is_alive())
        sent = self.next_send(replacement)
        self.assertFalse(sent.wait(0.08))
        fire.render_to_display()
        sent.clear()
        self.assertTrue(sent.wait(1))

    def test_close_waits_for_inflight_send_and_prevents_later_sends(self):
        fire = self.make_fire()
        fire.render_to_display()
        entered, release, closed = (threading.Event() for _ in range(3))
        original = self.output.send_message

        def blocked_send(message):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("Test failed to release MIDI send")
            original(message)

        self.output.send_message = blocked_send
        closer = threading.Thread(target=lambda: (fire.close(), closed.set()))
        try:
            self.assertTrue(entered.wait(1))
            closer.start()
            self.assertFalse(closed.wait(0.03))
            release.set()
            self.assertTrue(closed.wait(1))
            self.assertFalse(self.output.is_port_open)
            self.assertFalse(fire._oled_thread and fire._oled_thread.is_alive())
        finally:
            release.set()
            if closer.ident:
                closer.join(2)
