"""Keep the walkthrough's code excerpts and runnable examples executable."""

import ast
import contextlib
import io
import re
import unittest
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "docs/BUILDING_AN_APP.md"


class TutorialDocsTests(unittest.TestCase):
    def test_source_excerpts_match_the_maintained_app(self):
        blocks = re.findall(
            r"<!-- source: ([^:]+):([^ ]+) -->\n```python\n(.*?)\n```",
            TUTORIAL.read_text(),
            re.DOTALL,
        )
        self.assertEqual(len(blocks), 10)
        for filename, symbol, snippet in blocks:
            with self.subTest(source=f"{filename}:{symbol}"):
                source = (ROOT / filename).read_text()
                if symbol != "*":
                    node = ast.parse(source)
                    for name in symbol.split("."):
                        node = next(
                            item
                            for item in node.body
                            if getattr(item, "name", None) == name
                        )
                    source = dedent(
                        "\n".join(
                            source.splitlines()[
                                min(
                                    [
                                        node.lineno,
                                        *[
                                            d.lineno
                                            for d in getattr(node, "decorator_list", [])
                                        ],
                                    ]
                                )
                                - 1 : node.end_lineno
                            ]
                        )
                    )
                self.assertEqual(
                    ast.dump(ast.parse(snippet)), ast.dump(ast.parse(source))
                )

    def test_headless_walkthrough_runs_without_opening_midi(self):
        match = re.search(
            r"<!-- runnable: pixel-editor-headless -->\n```python\n(.*?)\n```",
            TUTORIAL.read_text(),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        output = io.StringIO()
        with (
            patch("rtmidi.MidiIn", side_effect=AssertionError("Unexpected MIDI input")),
            patch(
                "rtmidi.MidiOut", side_effect=AssertionError("Unexpected MIDI output")
            ),
            contextlib.redirect_stdout(output),
        ):
            exec(  # noqa: S102 - execute this checked-in tutorial as a regression fixture
                compile(match.group(1), str(TUTORIAL), "exec"),
                {"__name__": "tutorial_check"},
            )
        self.assertIn("Pixel editor checks passed", output.getvalue())
