#!/usr/bin/env python3
"""Simple test runner that doesn't import akai_fire."""

import unittest
import sys
import os


def run_tests():
    """Run all tests."""
    print("Running tests...")
    print("=" * 50)

    # Discover tests
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

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
