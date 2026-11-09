"""Circuit frame traffic through the real driver and fake MIDI ports."""

import unittest
from unittest.mock import Mock, patch

from akai_fire import AkaiFire
from examples.apps.circuit.main import CircuitSequencer
from examples.apps.circuit.ui.screen_manager import Mode


def midi_port():
    port = Mock()
    port.messages = []
    port.send_message.side_effect = port.messages.append
    port.get_ports.return_value = ["FL STUDIO FIRE"]
    port.get_message.return_value = None
    port.is_port_open.return_value = False
    return port


class CircuitHardwareOutputTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("rtmidi.MidiIn", side_effect=midi_port).start()
        patch("rtmidi.MidiOut", side_effect=midi_port).start()
        patch.dict(
            "os.environ", {"CIRCUIT_MIDI_INPUT": "", "CIRCUIT_MIDI_OUTPUT": ""}
        ).start()
        self.fire = AkaiFire(async_handlers=False, oled_keepalive=False)
        self.addCleanup(self.fire.close)
        self.app = CircuitSequencer(self.fire)
        self.addCleanup(self.app.shutdown)
        self.app.on_start()

    def test_each_mode_submits_one_complete_pad_frame(self):
        for mode in Mode:
            with self.subTest(mode=mode):
                self.app.mode_manager.set_mode(mode)
                for _ in range(2):
                    self.fire.midi_out.messages.clear()
                    self.app.on_update(1 / 30)
                    self.fire.render_to_display()
                    packets = [
                        m
                        for m in self.fire.midi_out.messages
                        if m[:5] == [240, 71, 127, 67, 101]
                    ]
                    self.assertEqual(
                        len(packets),
                        1,
                        "Frame must not clear and repaint pads on the wire",
                    )
                    payload = packets[0][7:-1]
                    self.assertEqual(len(payload), 64 * 4)
                    actual = [
                        (payload[i], tuple(payload[i + 1 : i + 4]))
                        for i in range(0, len(payload), 4)
                    ]
                    self.assertEqual(
                        actual, list(enumerate(self.app.grid_manager.pad_colors))
                    )

    def test_mode_change_clears_with_one_batch(self):
        self.fire.midi_out.messages.clear()
        self.app.grid_manager.set_mode(Mode.SETTINGS)
        packets = self.fire.midi_out.messages
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][:5], [240, 71, 127, 67, 101])
        self.assertTrue(all(v == 0 for i, v in enumerate(packets[0][7:-1]) if i % 4))
