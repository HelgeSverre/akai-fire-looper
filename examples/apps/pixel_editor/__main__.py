"""Run the tutorial app in pygame by default; hardware is explicit."""

import argparse
from pathlib import Path

from akai_fire import get_akai_fire

from .app import PixelEditorApp


def main(argv=None):
    parser = argparse.ArgumentParser(description="Paint a 16×4 picture on the Fire.")
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Use the connected Fire instead of the pygame mock",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("pixel-art.json"),
        help="Save/load path (default: ./pixel-art.json)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Exit after this many seconds; useful for smoke tests",
    )
    args = parser.parse_args(argv)
    # The factory forwards kwargs to the chosen backend. max_workers belongs
    # only to hardware, whose single worker preserves callback order.
    options = {"max_workers": 1} if args.hardware else {}
    with (
        get_akai_fire(use_mock=False if args.hardware else "pygame", **options) as fire,
        PixelEditorApp(fire, path=args.file) as app,
    ):
        app.run(duration=args.duration)


if __name__ == "__main__":
    main()
