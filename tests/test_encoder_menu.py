"""Navigate/edit behavior shared by encoder-driven applications."""

import unittest
from unittest.mock import Mock

from akai_fire_framework import EncoderMenu, MenuItem


class EncoderMenuTests(unittest.TestCase):
    def test_press_turn_press_edits_without_moving_selection(self):
        adjust = Mock()
        action = Mock()
        menu = EncoderMenu(
            [MenuItem("BPM", adjust=adjust), MenuItem("Save", activate=action)]
        )
        menu.press()
        self.assertTrue(menu.editing)
        menu.turn(-3)
        adjust.assert_called_once_with(-3)
        self.assertEqual(menu.selected_index, 0)
        menu.press()
        self.assertFalse(menu.editing)
        menu.turn(1)
        menu.press()
        action.assert_called_once_with()
        self.assertFalse(menu.editing)

    def test_navigation_respects_magnitude_and_bounds(self):
        menu = EncoderMenu([MenuItem(str(i)) for i in range(8)])
        menu.turn(5)
        self.assertEqual(menu.selected_index, 5)
        menu.turn(-3)
        self.assertEqual(menu.selected_index, 2)
        menu.turn(-10)
        self.assertEqual(menu.selected_index, 0)
        menu.turn(20)
        self.assertEqual(menu.selected_index, 7)

    def test_selecting_another_item_finishes_editing(self):
        menu = EncoderMenu(
            [MenuItem("BPM", adjust=Mock()), MenuItem("Swing", adjust=Mock())]
        )
        menu.press()
        menu.select(1)
        self.assertFalse(menu.editing)
        menu.press()
        menu.finish_editing()
        self.assertFalse(menu.editing)

    def test_wrap_is_opt_in_and_read_only_items_do_not_edit(self):
        menu = EncoderMenu([MenuItem("A"), MenuItem("B")], wrap=True)
        menu.turn(-1)
        self.assertEqual(menu.selected_index, 1)
        menu.press()
        self.assertFalse(menu.editing)
        menu.turn(1)
        self.assertEqual(menu.selected_index, 0)

    def test_navigation_can_keep_editing_without_activating_actions(self):
        first, second, action = Mock(), Mock(), Mock()
        menu = EncoderMenu(
            [
                MenuItem("A", adjust=first),
                MenuItem("B", adjust=second),
                MenuItem("Save", activate=action),
                MenuItem("Info"),
            ]
        )
        menu.move(1, keep_editing=True)
        self.assertFalse(menu.editing)  # The option preserves, never starts an edit.
        menu.press()
        menu.move(-1, keep_editing=True)
        menu.turn(2)
        first.assert_called_once_with(2)
        second.assert_not_called()
        menu.select(1, keep_editing=True)
        menu.turn(-3)
        second.assert_called_once_with(-3)
        menu.move(1, keep_editing=True)
        self.assertFalse(menu.editing)
        action.assert_not_called()
        menu.select(0)
        menu.press()
        menu.select(3, keep_editing=True)
        self.assertFalse(menu.editing)

    def test_preserved_edit_stays_active_at_navigation_boundary(self):
        menu = EncoderMenu([MenuItem("A", adjust=Mock())])
        menu.press()
        menu.move(-1, keep_editing=True)
        self.assertTrue(menu.editing)
        menu.move(1)
        self.assertFalse(menu.editing)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            EncoderMenu([])
        with self.assertRaises(ValueError):
            MenuItem("Ambiguous", adjust=Mock(), activate=Mock())
