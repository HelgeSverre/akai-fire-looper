"""
Runner script for the Circuit Tracks-inspired MIDI sequencer.
Handles imports and module paths correctly.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the circuit sequencer
if __name__ == "__main__":
    try:
        # Change to examples/circuit directory
        circuit_dir = os.path.join(os.path.dirname(__file__), "examples", "circuit")
        os.chdir(circuit_dir)

        # Now import and run
        from main import main

        main()

    except Exception as e:
        print(f"Error starting Circuit sequencer: {e}")
        import traceback

        traceback.print_exc()
