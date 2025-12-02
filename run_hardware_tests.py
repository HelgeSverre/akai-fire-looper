#!/usr/bin/env python3
"""Run tests with actual hardware and provide detailed summary."""

import subprocess
import sys
import re


def run_test_module(module_name, python_path):
    """Run a specific test module and return results."""
    cmd = [python_path, "-m", "unittest", f"tests.{module_name}", "-v"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse output
    output = result.stderr
    tests_run = 0
    failures = 0
    errors = 0

    # Find test count
    match = re.search(r"Ran (\d+) test", output)
    if match:
        tests_run = int(match.group(1))

    # Count failures and errors
    if "FAILED" in output:
        match = re.search(r"failures=(\d+)", output)
        if match:
            failures = int(match.group(1))
        match = re.search(r"errors=(\d+)", output)
        if match:
            errors = int(match.group(1))

    passed = tests_run - failures - errors
    return {
        "total": tests_run,
        "passed": passed,
        "failed": failures,
        "errors": errors,
        "output": output,
    }


def main():
    python_path = "/Users/helge/code/akai-fire-looper/.venv/bin/python"

    print("AKAI Fire Library - Hardware Test Results")
    print("=" * 60)
    print("Using Python:", python_path)
    print()

    # Test modules
    modules = {
        "Screen Manager Tests": "test_screen_manager",
        "Canvas Tests": "test_canvas",
        "Core Library Tests": "test_akai_fire",
    }

    total_stats = {"total": 0, "passed": 0, "failed": 0, "errors": 0}

    for name, module in modules.items():
        print(f"\n{name}:")
        print("-" * 40)

        results = run_test_module(module, python_path)

        print(f"Total: {results['total']}")
        print(f"✓ Passed: {results['passed']}")
        if results["failed"]:
            print(f"✗ Failed: {results['failed']}")
        if results["errors"]:
            print(f"⚠ Errors: {results['errors']}")

        # Update totals
        for key in total_stats:
            total_stats[key] += results[key]

        # Show specific failures/errors
        if results["failed"] or results["errors"]:
            lines = results["output"].split("\n")
            for i, line in enumerate(lines):
                if "FAIL:" in line or "ERROR:" in line:
                    print(f"  - {line.strip()}")
                    # Try to get the assertion error
                    if i + 1 < len(lines) and "AssertionError" in lines[i + 1]:
                        print(f"    {lines[i+1].strip()}")

    # Overall summary
    print("\n" + "=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    print(f"Total tests: {total_stats['total']}")
    print(f"✓ Passed: {total_stats['passed']}")
    print(f"✗ Failed: {total_stats['failed']}")
    print(f"⚠ Errors: {total_stats['errors']}")

    success_rate = (
        (total_stats["passed"] / total_stats["total"] * 100)
        if total_stats["total"] > 0
        else 0
    )
    print(f"\nSuccess rate: {success_rate:.1f}%")

    # Check if hardware is connected
    print("\n" + "=" * 60)
    print("HARDWARE STATUS")
    print("=" * 60)

    # Try to detect if AKAI Fire is connected
    try:
        import rtmidi

        midi_in = rtmidi.MidiIn()
        ports = midi_in.get_ports()
        fire_found = any("FL STUDIO FIRE" in port for port in ports)
        print(f"AKAI Fire hardware: {'✓ Connected' if fire_found else '✗ Not found'}")
        if ports:
            print("\nAvailable MIDI ports:")
            for port in ports:
                print(f"  - {port}")
    except Exception as e:
        print(f"Could not check MIDI ports: {e}")

    return 0 if total_stats["failed"] == 0 and total_stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
