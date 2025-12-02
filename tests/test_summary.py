#!/usr/bin/env python3
"""Run tests and provide a clean summary."""

import unittest
import sys
import os


def run_tests():
    """Run all tests and provide summary."""
    print("AKAI Fire Library - Test Summary")
    print("=" * 50)

    # Test categories
    test_modules = {
        "Screen Manager": "test_screen_manager",
        "Canvas": "test_canvas",
        "Core Library": "test_akai_fire",
    }

    results = {}

    for name, module in test_modules.items():
        try:
            # Load and run tests for this module
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(f"tests.{module}")
            runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w"))
            result = runner.run(suite)

            # Store results
            results[name] = {
                "total": result.testsRun,
                "passed": result.testsRun - len(result.failures) - len(result.errors),
                "failed": len(result.failures),
                "errors": len(result.errors),
            }
        except Exception as e:
            results[name] = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 1,
                "error_msg": str(e),
            }

    # Print results
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0

    for name, res in results.items():
        print(f"\n{name}:")
        if "error_msg" in res:
            print(f"  ⚠️  Failed to load: {res['error_msg'][:50]}...")
        else:
            print(f"  Total: {res['total']}")
            print(f"  ✓ Passed: {res['passed']}")
            if res["failed"] > 0:
                print(f"  ✗ Failed: {res['failed']}")
            if res["errors"] > 0:
                print(f"  ⚠ Errors: {res['errors']}")

        total_tests += res["total"]
        total_passed += res["passed"]
        total_failed += res["failed"]
        total_errors += res["errors"]

    # Overall summary
    print("\n" + "=" * 50)
    print("OVERALL SUMMARY")
    print("=" * 50)
    print(f"Total tests: {total_tests}")
    print(f"✓ Passed: {total_passed}")
    print(f"✗ Failed: {total_failed}")
    print(f"⚠ Errors: {total_errors}")

    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"\nSuccess rate: {success_rate:.1f}%")

    # Recommendations
    print("\n" + "=" * 50)
    print("NOTES:")
    print("- Some tests require external dependencies (rtmidi, PIL)")
    print("- Mock implementations are used for testing")
    print("- Circle drawing tests fail due to incomplete mock")

    return 0 if total_failed == 0 and total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
