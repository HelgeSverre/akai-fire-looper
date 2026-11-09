"""Launch the Eight Track control prototype with generated preview audio."""

import argparse

from akai_fire import get_akai_fire

from .app import EightTrackApp
from .audio import PreviewSound


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Eight Track: eight-track performance prototype"
    )
    parser.add_argument(
        "--hardware", action="store_true", help="Use the connected Fire"
    )
    parser.add_argument(
        "--silent", action="store_true", help="Disable computer preview sound"
    )
    parser.add_argument("--duration", type=float, help="Exit after this many seconds")
    args = parser.parse_args(argv)
    with get_akai_fire(
        use_mock=False if args.hardware else "pygame", max_workers=1
    ) as fire:
        sound = PreviewSound(enabled=not args.silent)
        try:
            with EightTrackApp(fire, output=sound) as app:
                app.run(duration=args.duration)
        finally:
            sound.close()


if __name__ == "__main__":
    main()
