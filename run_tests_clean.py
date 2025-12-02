#!/usr/bin/env python3
"""Run tests with clean output."""

import unittest
import sys
import os
import io
from contextlib import redirect_stdout, redirect_stderr

# Suppress pygame and MIDI output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect stdout/stderr during imports
with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    import akai_fire


def run_tests():
    """Run all tests with clean output."""
    print("Running AKAI Fire Library Test Suite...")
    print("=" * 50)

    # Discover tests
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    # Count tests
    def count_tests(test_suite):
        count = 0
        for test in test_suite:
            if isinstance(test, unittest.TestSuite):
                count += count_tests(test)
            else:
                count += 1
        return count

    total_tests = count_tests(suite)
    print(f"Found {total_tests} tests")
    print()

    # Run tests with minimal output
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=1)

    # Capture all output during test run
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        result = runner.run(suite)

    # Calculate statistics
    passed = result.testsRun - len(result.failures) - len(result.errors)

    # Print results
    print(f"✓ Passed: {passed}")
    if result.failures:
        print(f"✗ Failed: {len(result.failures)}")
    if result.errors:
        print(f"⚠ Errors: {len(result.errors)}")

    print(f"\nTotal: {result.testsRun} tests")

    # Show details of failures and errors
    if result.failures:
        print("\n" + "=" * 50)
        print("FAILURES:")
        for test, _ in result.failures:
            print(f"  - {test.id()}")

    if result.errors:
        print("\n" + "=" * 50)
        print("ERRORS:")
        for test, _ in result.errors:
            test_name = test.id() if hasattr(test, "id") else str(test)
            print(f"  - {test_name}")

    # Summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✓ All tests passed!")
    else:
        print(
            f"✗ Test suite failed: {len(result.failures)} failures, {len(result.errors)} errors"
        )

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
