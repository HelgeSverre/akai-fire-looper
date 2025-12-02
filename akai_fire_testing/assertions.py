"""
Custom assertion helpers for AKAI Fire testing.

This module provides assertion functions that give clear, helpful
error messages when tests fail.

Functions:
    assert_pad_grid: Assert on pad grid patterns
    assert_button_state: Assert button LED states
    assert_screen_contains: Assert screen content
"""

from typing import List, Tuple, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .mocks import MockAkaiFire, MockCanvas


# =============================================================================
# Pad Assertions
# =============================================================================


def assert_pad_grid(
    fire: "MockAkaiFire",
    expected_lit: Optional[List[int]] = None,
    expected_colors: Optional[dict] = None,
    row: Optional[int] = None,
):
    """
    Assert on pad grid state.

    Args:
        fire: MockAkaiFire instance
        expected_lit: List of pad indices that should be lit (not black)
        expected_colors: Dict of {pad_index: (r, g, b)} expected colors
        row: Only check pads in this row (0-3)

    Raises:
        AssertionError: If assertions fail
    """
    if row is not None:
        # Filter to specific row
        start = row * 16
        end = start + 16
        pads_to_check = range(start, end)
    else:
        pads_to_check = range(64)

    if expected_lit is not None:
        expected_set = set(expected_lit)
        actual_lit = set()
        for i in pads_to_check:
            if fire.pad_colors[i] != (0, 0, 0):
                actual_lit.add(i)

        if expected_set != actual_lit:
            missing = expected_set - actual_lit
            extra = actual_lit - expected_set
            msg = f"Pad grid mismatch."
            if missing:
                msg += f" Missing lit pads: {sorted(missing)}"
            if extra:
                msg += f" Unexpected lit pads: {sorted(extra)}"
            raise AssertionError(msg)

    if expected_colors is not None:
        for pad_index, expected_color in expected_colors.items():
            if pad_index not in pads_to_check:
                continue
            actual = fire.pad_colors[pad_index]
            if actual != expected_color:
                raise AssertionError(
                    f"Pad {pad_index}: expected color {expected_color}, got {actual}"
                )


def assert_row_pattern(
    fire: "MockAkaiFire",
    row: int,
    pattern: List[bool],
):
    """
    Assert a row of pads matches a pattern.

    Args:
        fire: MockAkaiFire instance
        row: Row index (0-3)
        pattern: List of 16 booleans (True = lit, False = off)

    Raises:
        AssertionError: If pattern doesn't match
    """
    if len(pattern) != 16:
        raise ValueError("Pattern must have 16 elements")

    start = row * 16
    for i, should_be_lit in enumerate(pattern):
        pad = start + i
        is_lit = fire.pad_colors[pad] != (0, 0, 0)
        if is_lit != should_be_lit:
            expected = "lit" if should_be_lit else "off"
            actual = "lit" if is_lit else "off"
            raise AssertionError(
                f"Pad {pad} (row {row}, col {i}): expected {expected}, was {actual}"
            )


def assert_column_pattern(
    fire: "MockAkaiFire",
    column: int,
    pattern: List[bool],
):
    """
    Assert a column of pads matches a pattern.

    Args:
        fire: MockAkaiFire instance
        column: Column index (0-15)
        pattern: List of 4 booleans (True = lit, False = off)

    Raises:
        AssertionError: If pattern doesn't match
    """
    if len(pattern) != 4:
        raise ValueError("Pattern must have 4 elements")

    for row, should_be_lit in enumerate(pattern):
        pad = row * 16 + column
        is_lit = fire.pad_colors[pad] != (0, 0, 0)
        if is_lit != should_be_lit:
            expected = "lit" if should_be_lit else "off"
            actual = "lit" if is_lit else "off"
            raise AssertionError(
                f"Pad {pad} (row {row}, col {column}): expected {expected}, was {actual}"
            )


def assert_step_indicator(
    fire: "MockAkaiFire",
    step: int,
    color: Optional[Tuple[int, int, int]] = None,
):
    """
    Assert a step indicator (bottom row) shows correct state.

    Args:
        fire: MockAkaiFire instance
        step: Step index (0-15)
        color: Expected color, or None to just check it's lit

    Raises:
        AssertionError: If assertion fails
    """
    # Bottom row is pads 48-63
    pad = 48 + step

    if color is not None:
        actual = fire.pad_colors[pad]
        if actual != color:
            raise AssertionError(
                f"Step {step} indicator: expected {color}, got {actual}"
            )
    else:
        if fire.pad_colors[pad] == (0, 0, 0):
            raise AssertionError(f"Step {step} indicator should be lit but is off")


# =============================================================================
# Button Assertions
# =============================================================================


def assert_button_state(
    fire: "MockAkaiFire",
    expected_on: Optional[List[int]] = None,
    expected_off: Optional[List[int]] = None,
):
    """
    Assert button LED states.

    Args:
        fire: MockAkaiFire instance
        expected_on: Button IDs that should be on (non-zero)
        expected_off: Button IDs that should be off (zero)

    Raises:
        AssertionError: If assertions fail
    """
    if expected_on is not None:
        for button_id in expected_on:
            value = fire.button_leds.get(button_id, 0)
            if value == 0:
                raise AssertionError(f"Button {button_id} should be on but is off")

    if expected_off is not None:
        for button_id in expected_off:
            value = fire.button_leds.get(button_id, 0)
            if value != 0:
                raise AssertionError(f"Button {button_id} should be off but has value {value}")


def assert_transport_state(
    fire: "MockAkaiFire",
    playing: bool = False,
    recording: bool = False,
):
    """
    Assert transport button states (play, stop, rec).

    Args:
        fire: MockAkaiFire instance
        playing: Whether play should be lit
        recording: Whether rec should be lit

    Raises:
        AssertionError: If states don't match
    """
    from .mocks import MockAkaiFire

    play_value = fire.button_leds.get(MockAkaiFire.BUTTON_PLAY, 0)
    rec_value = fire.button_leds.get(MockAkaiFire.BUTTON_REC, 0)

    if playing and play_value == 0:
        raise AssertionError("Play button should be lit")
    if not playing and play_value != 0:
        raise AssertionError("Play button should be off")

    if recording and rec_value == 0:
        raise AssertionError("Rec button should be lit")
    if not recording and rec_value != 0:
        raise AssertionError("Rec button should be off")


# =============================================================================
# Screen Assertions
# =============================================================================


def assert_screen_contains(canvas: "MockCanvas", text: str):
    """
    Assert screen contains specific text.

    Args:
        canvas: MockCanvas instance
        text: Text to search for

    Raises:
        AssertionError: If text not found
    """
    for drawn_text, x, y in canvas.text_drawn:
        if text in drawn_text:
            return
    raise AssertionError(
        f"Screen does not contain '{text}'. "
        f"Text drawn: {[t[0] for t in canvas.text_drawn]}"
    )


def assert_screen_title(canvas: "MockCanvas", expected_title: str):
    """
    Assert screen has specific title (first text drawn).

    Args:
        canvas: MockCanvas instance
        expected_title: Expected title text

    Raises:
        AssertionError: If title doesn't match
    """
    if not canvas.text_drawn:
        raise AssertionError("No text drawn on screen")

    actual_title = canvas.text_drawn[0][0]
    if actual_title != expected_title:
        raise AssertionError(
            f"Screen title: expected '{expected_title}', got '{actual_title}'"
        )


def assert_screen_empty(canvas: "MockCanvas"):
    """
    Assert screen has no content drawn.

    Args:
        canvas: MockCanvas instance

    Raises:
        AssertionError: If any content was drawn
    """
    if canvas.text_drawn:
        raise AssertionError(f"Screen has text: {[t[0] for t in canvas.text_drawn]}")
    if canvas.rects_drawn:
        raise AssertionError(f"Screen has {len(canvas.rects_drawn)} rectangles")
    if canvas.lines_drawn:
        raise AssertionError(f"Screen has {len(canvas.lines_drawn)} lines")


def assert_menu_selection(canvas: "MockCanvas", selected_item: str):
    """
    Assert menu shows specific item as selected.

    Looks for text prefixed with ">" indicator.

    Args:
        canvas: MockCanvas instance
        selected_item: Text that should be selected

    Raises:
        AssertionError: If item not found as selected
    """
    for text, x, y in canvas.text_drawn:
        if text.startswith(">") and selected_item in text:
            return
    raise AssertionError(
        f"Menu item '{selected_item}' not selected. "
        f"Text drawn: {[t[0] for t in canvas.text_drawn]}"
    )


# =============================================================================
# MIDI Assertions
# =============================================================================


def assert_notes_in_order(midi, expected_notes: List[int], channel: Optional[int] = None):
    """
    Assert notes were played in a specific order.

    Args:
        midi: MockMidiManager instance
        expected_notes: List of note numbers in expected order
        channel: Optional channel filter

    Raises:
        AssertionError: If order doesn't match
    """
    actual_notes = [n for n, v in midi.get_notes_on(channel)]
    if actual_notes != expected_notes:
        raise AssertionError(
            f"Note order mismatch. Expected: {expected_notes}, got: {actual_notes}"
        )


def assert_chord(midi, expected_notes: Set[int], channel: Optional[int] = None):
    """
    Assert a chord (set of notes) was played.

    Order doesn't matter, just that all notes are present.

    Args:
        midi: MockMidiManager instance
        expected_notes: Set of note numbers
        channel: Optional channel filter

    Raises:
        AssertionError: If notes don't match
    """
    actual_notes = set(n for n, v in midi.get_notes_on(channel))
    if actual_notes != expected_notes:
        missing = expected_notes - actual_notes
        extra = actual_notes - expected_notes
        msg = "Chord mismatch."
        if missing:
            msg += f" Missing: {sorted(missing)}"
        if extra:
            msg += f" Extra: {sorted(extra)}"
        raise AssertionError(msg)


# =============================================================================
# State Snapshots
# =============================================================================


def snapshot_pad_state(fire: "MockAkaiFire") -> List[Tuple[int, int, int]]:
    """
    Capture current pad state for later comparison.

    Args:
        fire: MockAkaiFire instance

    Returns:
        Copy of pad colors list
    """
    return list(fire.pad_colors)


def assert_pad_state_changed(
    fire: "MockAkaiFire",
    previous_state: List[Tuple[int, int, int]],
    changed_pads: Optional[List[int]] = None,
):
    """
    Assert pad state changed from snapshot.

    Args:
        fire: MockAkaiFire instance
        previous_state: State from snapshot_pad_state()
        changed_pads: If provided, assert only these pads changed

    Raises:
        AssertionError: If state didn't change as expected
    """
    current = fire.pad_colors
    actually_changed = []

    for i in range(64):
        if current[i] != previous_state[i]:
            actually_changed.append(i)

    if changed_pads is not None:
        expected_set = set(changed_pads)
        actual_set = set(actually_changed)

        if expected_set != actual_set:
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            msg = "Pad changes mismatch."
            if missing:
                msg += f" Expected changes on: {sorted(missing)}"
            if extra:
                msg += f" Unexpected changes on: {sorted(extra)}"
            raise AssertionError(msg)
    else:
        if not actually_changed:
            raise AssertionError("No pads changed")


def assert_pad_state_unchanged(
    fire: "MockAkaiFire",
    previous_state: List[Tuple[int, int, int]],
):
    """
    Assert pad state is unchanged from snapshot.

    Args:
        fire: MockAkaiFire instance
        previous_state: State from snapshot_pad_state()

    Raises:
        AssertionError: If any pads changed
    """
    current = fire.pad_colors
    changed = []

    for i in range(64):
        if current[i] != previous_state[i]:
            changed.append(i)

    if changed:
        raise AssertionError(f"Pads unexpectedly changed: {changed}")
