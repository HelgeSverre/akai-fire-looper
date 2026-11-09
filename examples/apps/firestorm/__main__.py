"""Run Firestorm in pygame or on an explicitly selected Fire."""

import argparse

from akai_fire import get_akai_fire

from .app import FirestormApp
from .audio import Sound


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Firestorm: an interactive particle instrument"
    )
    parser.add_argument(
        "--hardware", action="store_true", help="Use the connected Fire"
    )
    parser.add_argument("--silent", action="store_true", help="Disable computer audio")
    parser.add_argument("--duration", type=float, help="Exit after this many seconds")
    parser.add_argument(
        "--seed", type=int, help="Seed the visual simulation for repeatable runs"
    )
    args = parser.parse_args(argv)
    options = {"max_workers": 1} if args.hardware else {}
    with get_akai_fire(
        use_mock=False if args.hardware else "pygame", **options
    ) as fire:
        sound = Sound(enabled=not args.silent)
        try:
            with FirestormApp(fire, sound=sound, seed=args.seed) as app:
                app.run(duration=args.duration)
        finally:
            sound.close()


if __name__ == "__main__":
    main()
