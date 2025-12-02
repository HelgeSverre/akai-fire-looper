#!/usr/bin/env python3
"""
Simple demo of the screen manager abstraction.
Shows how to create consistent GUI screens easily.
"""

import time
from akai_fire import get_akai_fire
from screen_manager import (
    ScreenManager,
    TextScreen,
    MenuScreen,
    ProgressScreen,
    GridScreen,
    ValueScreen,
    MenuItem,
)


def main():
    # Initialize
    fire = get_akai_fire()
    screen_mgr = ScreenManager(fire)

    # Create screens

    # 1. Simple text screen
    text_screen = TextScreen(
        fire.get_canvas(),
        "Info",
        ["AKAI Fire", "Screen Demo", "Version 1.0", "", "5 screen types"],
    )
    screen_mgr.add_screen("info", text_screen)

    # 2. Menu screen
    menu = MenuScreen(fire.get_canvas(), "Main Menu")
    menu.add_item("Play Mode")
    menu.add_item("Settings")
    menu.add_item("About")
    menu.add_item("Exit")
    screen_mgr.add_screen("menu", menu)

    # 3. Progress screen
    progress = ProgressScreen(fire.get_canvas(), "Loading", 0, 100)
    screen_mgr.add_screen("progress", progress)

    # 4. Grid screen (for pad visualization)
    grid = GridScreen(fire.get_canvas(), "Sequence", 4, 16)
    # Set some example pattern
    for col in range(16):
        if col % 4 == 0:  # Every 4th beat
            grid.set_cell(0, col, True)
        if col % 2 == 0:  # Hi-hats
            grid.set_cell(1, col, True)
    screen_mgr.add_screen("grid", grid)

    # 5. Value screen
    value = ValueScreen(fire.get_canvas(), "BPM", 120, "")
    screen_mgr.add_screen("bpm", value)

    # Demo sequence
    print("Screen Manager Demo")
    print("Showing different screen types...")

    # Show each screen
    screens = [
        ("info", 2),
        ("menu", 3),
        ("progress", 0),  # Will animate
        ("grid", 3),
        ("bpm", 2),
    ]

    try:
        for screen_name, duration in screens:
            print(f"Showing {screen_name} screen...")

            if screen_name == "progress":
                # Animate progress bar
                screen_mgr.show_screen(screen_name)
                for i in range(101):
                    progress.set_progress(i)
                    progress.set_additional_text(f"Processing... {i}%")
                    screen_mgr.render()
                    time.sleep(0.02)

                    # Update display for mock
                    if hasattr(fire, "process_events"):
                        if not fire.process_events():
                            return
            else:
                screen_mgr.show_screen(screen_name)

                # If menu, demonstrate navigation
                if screen_name == "menu":
                    for _ in range(3):
                        time.sleep(0.5)
                        menu.select_next()
                        screen_mgr.render()

                        if hasattr(fire, "process_events"):
                            if not fire.process_events():
                                return

                # Wait
                start = time.time()
                while time.time() - start < duration:
                    if hasattr(fire, "process_events"):
                        if not fire.process_events():
                            return
                    time.sleep(0.01)

        # Quick message demo
        print("Showing message...")
        screen_mgr.show_message("Test Complete!\nThanks!", 2)

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        fire.clear_all()
        fire.close()
        print("Done!")


if __name__ == "__main__":
    main()
