"""Verify the testing package works without rtmidi / Pillow installed.

``akai_fire_testing.MockAkaiFire`` is marketed as zero-dependency headless
testing. That means importing it must not pull in ``rtmidi`` or ``PIL``.
The approach: spawn a subprocess with a meta-path finder that raises
``ImportError`` for both modules, then run the import + construction in
that subprocess. If anything along the import chain still reaches for
rtmidi / PIL the subprocess exits with a non-zero status.
"""

import os
import subprocess
import sys
import textwrap
import unittest


class TestHeadlessImport(unittest.TestCase):
    def _run_guarded(
        self, blocked: tuple[str, ...], code: str
    ) -> subprocess.CompletedProcess:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        blocked_repr = repr(list(blocked))
        script = textwrap.dedent(f"""
            import sys

            class _Block:
                def __init__(self, blocked):
                    self.blocked = set(blocked)
                def find_spec(self, name, path=None, target=None):
                    root = name.split('.', 1)[0]
                    if root in self.blocked:
                        raise ImportError(f"blocked: {{name}}")
                    return None

            sys.meta_path.insert(0, _Block({blocked_repr}))

            {textwrap.indent(code, '            ').lstrip()}
            """)
        env = {**os.environ, "PYTHONPATH": project_root}
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_akai_fire_package_imports_without_hardware_deps(self):
        result = self._run_guarded(
            ("rtmidi", "PIL"),
            "import akai_fire\n"
            "from akai_fire.device import AkaiFireDevice\n"
            "assert AkaiFireDevice is not None\n",
        )
        self.assertEqual(
            result.returncode,
            0,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_mock_akai_fire_constructable_without_hardware_deps(self):
        result = self._run_guarded(
            ("rtmidi", "PIL"),
            "from akai_fire_testing import MockAkaiFire\n"
            "fire = MockAkaiFire()\n"
            "assert fire is not None\n",
        )
        self.assertEqual(
            result.returncode,
            0,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_accessing_akai_fire_hardware_class_needs_rtmidi(self):
        # Sanity check that our guard actually blocks: reaching for AkaiFire
        # (the hardware class) must fail when rtmidi is unavailable.
        result = self._run_guarded(
            ("rtmidi",),
            "import akai_fire\n"
            "try:\n"
            "    akai_fire.AkaiFire\n"
            "except ImportError:\n"
            "    print('blocked-as-expected')\n"
            "else:\n"
            "    print('UNEXPECTED: resolved without rtmidi')\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("blocked-as-expected", result.stdout)


if __name__ == "__main__":
    unittest.main()
