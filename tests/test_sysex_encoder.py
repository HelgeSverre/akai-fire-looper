"""Golden-vector tests for the OLED SysEx bitmap encoder.

``AkaiFire._deliver_display`` packs the 128x64 monochrome canvas into
AKAI Fire's quirky 7-bit interleave (see ``bitmap_pixel_mapping``). A
wrong index draws garbage on real hardware and nothing else in the
suite would catch it, so the expected byte positions below were derived
by hand from the mapping table — independent of the implementation.

Layout model: pixel (x, y) → x_mapped = x + 128*(y//8);
rb = bitmap_pixel_mapping[x_mapped % 7][y % 8];
byte = (x_mapped // 7) * 8 + rb // 7; bit = rb % 7.

Derived spot checks:
    (0, 0):  rb=13 → byte 1, bit 6 → 0x40
    (0, 1):  rb=0  → byte 0, bit 0 → 0x01
    (1, 0):  rb=19 → byte 2, bit 5 → 0x20
    (127,63): x_mapped=1023, rb=12 → byte 1169, bit 5 → 0x20
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import AkaiFire, Canvas
from akai_fire.errors import MIDISendError


class MockMidiPort:
    def __init__(self):
        self.messages = []
        self.port_name = None
        self.is_port_open = False

    def send_message(self, message):
        self.messages.append(message)

    def get_message(self):
        return None

    def open_port(self, port):
        self.is_port_open = True
        self.port_name = port

    def close_port(self):
        self.is_port_open = False

    def get_ports(self):
        return ["FL STUDIO FIRE", "Other"]


def _make_fire():
    with (
        patch("rtmidi.MidiIn", return_value=MockMidiPort()),
        patch("rtmidi.MidiOut", return_value=MockMidiPort()),
    ):
        return AkaiFire(async_handlers=False)


def _last_display_message(fire):
    """Return the payload bitmap of the most recent display SysEx."""
    message = fire.mock_midi_out.messages[-1]
    assert message[0] == 0xF0 and message[-1] == 0xF7, "not a SysEx message"
    return message


class TestDisplaySysexEncoder(unittest.TestCase):
    def setUp(self):
        self.fire = _make_fire()
        self.fire.mock_midi_out = self.fire.midi_out

    def tearDown(self):
        self.fire.close()

    def test_message_framing(self):
        """Header, 7-bit length fields, and EOX match the AKAI protocol."""
        self.fire.render_to_display()
        message = _last_display_message(self.fire)
        # 11 header bytes + 1171 bitmap bytes + EOX
        self.assertEqual(len(message), 1183)
        self.assertEqual(
            message[:11],
            [0xF0, 0x47, 0x7F, 0x43, 0x0E, 9, 23, 0, 0x07, 0, 0x7F],
            "(1171+4) splits into 7-bit length bytes 9 / 23",
        )
        self.assertEqual(message[-1], 0xF7)
        self.assertTrue(all(b <= 0x7F for b in message[11:-1]))

    def test_all_unlit_canvas_sends_zero_bitmap(self):
        """A fresh canvas (all 1 = unlit) must light nothing on hardware."""
        self.fire.render_to_display()
        message = _last_display_message(self.fire)
        bitmap = message[11:-1]
        self.assertEqual(len(bitmap), 1171)
        self.assertEqual(set(bitmap), {0})

    def test_single_pixel_golden_positions(self):
        """Hand-derived byte/bit positions for four probe pixels."""
        cases = [
            ((0, 0), 1, 0x40),
            ((0, 1), 0, 0x01),
            ((1, 0), 2, 0x20),
            ((127, 63), 1169, 0x20),
        ]
        for (x, y), byte_index, expected_byte in cases:
            with self.subTest(pixel=(x, y)):
                canvas = Canvas()
                canvas.set_pixel(x, y, 0)  # 0 = lit
                self.fire.render_to_display(canvas)
                bitmap = _last_display_message(self.fire)[11:-1]
                lit = [(i, b) for i, b in enumerate(bitmap) if b]
                self.assertEqual(
                    lit,
                    [(byte_index, expected_byte)],
                    f"pixel ({x},{y}) lit unexpected bytes",
                )

    def test_full_lit_canvas_popcount_and_tail(self):
        """All 8192 pixels map to distinct bits; complete blocks are 0x7F.

        Blocks 0-145 cover bytes 0-1167 fully; the tail block leaves
        byte 1170 with only bits 5-6 set (0x60).
        """
        canvas = Canvas()
        canvas.clear(0)  # every pixel lit
        self.fire.render_to_display(canvas)
        bitmap = _last_display_message(self.fire)[11:-1]
        popcount = sum(bin(b).count("1") for b in bitmap)
        self.assertEqual(popcount, 128 * 64)
        self.assertEqual(set(bitmap[:1168]), {0x7F}, "complete blocks must be all-lit")
        self.assertEqual(bitmap[1170], 0x60)

    def test_send_failure_raises_midisend_error(self):
        """A failing midi_out surfaces as MIDISendError, not a raw rtmidi error."""

        def broken_send(message):
            raise RuntimeError("rtmidi exploded")

        self.fire.midi_out.send_message = broken_send
        with self.assertRaises(MIDISendError):
            self.fire.render_to_display()


if __name__ == "__main__":
    unittest.main()
