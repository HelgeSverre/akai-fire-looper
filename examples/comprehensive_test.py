#!/usr/bin/env python3
"""
Comprehensive test for AKAI Fire - tests all pads, buttons, rotary encoders, and LEDs.
Also demonstrates the screen manager abstraction.
"""

import time
import math
import threading
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from akai_fire import get_akai_fire
from screen_manager import ScreenManager, MenuScreen, TextScreen, ProgressScreen, GridScreen, ValueScreen

class ComprehensiveTest:
    def __init__(self):
        # Initialize controller (auto-detects hardware vs mock)
        self.fire = get_akai_fire()
        
        # Check if using mock
        self.is_mock = hasattr(self.fire, 'process_events')
        
        # Screen manager
        self.screen_manager = ScreenManager(self.fire)
        
        # Test state
        self.running = True
        self.current_test = None
        self.test_thread = None
        
        # Pattern animation state
        self.pattern_phase = 0
        self.pattern_running = False
        
        # LED flicker state
        self.led_flicker_phase = 0
        
        # Initialize screens
        self._setup_screens()
        
        # Set up event handlers
        self._setup_event_handlers()
        
    def _setup_screens(self):
        """Set up all the screens."""
        # Main menu
        menu = MenuScreen(self.fire.get_canvas(), "AKAI Fire Test")
        menu.add_item("1. Test All Pads", action=self.test_pads)
        menu.add_item("2. Test Buttons", action=self.test_buttons)
        menu.add_item("3. Test Rotaries", action=self.test_rotaries)
        menu.add_item("4. Test LEDs", action=self.test_leds)
        menu.add_item("5. Pattern Demo", action=self.start_pattern)
        menu.add_item("6. Clear All", action=self.clear_all)
        menu.add_item("7. Exit", action=self.exit)
        self.screen_manager.add_screen("menu", menu)
        
        # Info screens
        self.screen_manager.add_screen("pad_test", TextScreen(self.fire.get_canvas(), "Pad Test"))
        self.screen_manager.add_screen("button_test", TextScreen(self.fire.get_canvas(), "Button Test"))
        self.screen_manager.add_screen("rotary_test", TextScreen(self.fire.get_canvas(), "Rotary Test"))
        self.screen_manager.add_screen("led_test", TextScreen(self.fire.get_canvas(), "LED Test"))
        
        # Progress screen
        self.screen_manager.add_screen("progress", ProgressScreen(self.fire.get_canvas(), "Progress"))
        
        # Grid screen for pad visualization
        self.screen_manager.add_screen("pad_grid", GridScreen(self.fire.get_canvas(), "Pad Activity", 4, 16))
        
        # Value screens for rotaries
        self.screen_manager.add_screen("volume", ValueScreen(self.fire.get_canvas(), "Volume", 0, "%"))
        self.screen_manager.add_screen("pan", ValueScreen(self.fire.get_canvas(), "Pan", 0, ""))
        self.screen_manager.add_screen("filter", ValueScreen(self.fire.get_canvas(), "Filter", 0, "Hz"))
        self.screen_manager.add_screen("resonance", ValueScreen(self.fire.get_canvas(), "Resonance", 0, "%"))
        
    def _setup_event_handlers(self):
        """Set up all event handlers."""
        # Pad handler - visualize on grid
        @self.fire.on_pad()
        def handle_pad(pad_idx, velocity):
            row = pad_idx // 16
            col = pad_idx % 16
            
            # Update grid visualization
            if self.current_test == "pads":
                grid = self.screen_manager.screens.get("pad_grid")
                if grid:
                    grid.set_cell(row, col, velocity > 0)
                    self.screen_manager.render()
            
            # Light up pad with velocity-based brightness
            if velocity > 0:
                brightness = velocity
                self.fire.set_pad_color(pad_idx, brightness, brightness // 2, brightness // 4)
            else:
                self.fire.clear_pad(pad_idx)
        
        # Button handlers - each button does something specific
        @self.fire.on_button(self.fire.BUTTON_PLAY)
        def handle_play(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_HIGH_GREEN)
                self.screen_manager.show_message("PLAY pressed")
                self.start_pattern()
            else:
                self.fire.set_button_led(self.fire.BUTTON_PLAY, self.fire.LED_OFF)
        
        @self.fire.on_button(self.fire.BUTTON_STOP)
        def handle_stop(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_HIGH_RED)
                self.screen_manager.show_message("STOP - Clearing")
                self.stop_pattern()
                self.clear_all()
            else:
                self.fire.set_button_led(self.fire.BUTTON_STOP, self.fire.LED_OFF)
        
        @self.fire.on_button(self.fire.BUTTON_REC)
        def handle_rec(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_HIGH_RED)
                self.screen_manager.show_message("RECORDING...")
            else:
                self.fire.set_button_led(self.fire.BUTTON_REC, self.fire.LED_OFF)
        
        # Mode buttons - cycle through different pad colors
        colors = {
            self.fire.BUTTON_STEP: (127, 0, 0),      # Red
            self.fire.BUTTON_NOTE: (0, 127, 0),      # Green  
            self.fire.BUTTON_DRUM: (0, 0, 127),      # Blue
            self.fire.BUTTON_PERFORM: (127, 0, 127), # Purple
        }
        
        for button_id, color in colors.items():
            @self.fire.on_button(button_id)
            def make_handler(bid, clr):
                def handler(event):
                    if event == "press":
                        self.fire.set_button_led(bid, self.fire.LED_DULL_RED)
                        # Set first row to this color
                        for i in range(16):
                            self.fire.set_pad_color(i, *clr)
                    else:
                        self.fire.set_button_led(bid, self.fire.LED_OFF)
                return handler
            self.fire.on_button(button_id)(make_handler(button_id, color))
        
        # Pattern/Browser - navigate menu
        @self.fire.on_button(self.fire.BUTTON_PAT_UP)
        def handle_pat_up(event):
            if event == "press":
                menu = self.screen_manager.screens.get("menu")
                if menu and self.current_test is None:
                    menu.select_previous()
                    self.screen_manager.render()
        
        @self.fire.on_button(self.fire.BUTTON_PAT_DOWN)
        def handle_pat_down(event):
            if event == "press":
                menu = self.screen_manager.screens.get("menu")
                if menu and self.current_test is None:
                    menu.select_next()
                    self.screen_manager.render()
        
        @self.fire.on_button(self.fire.BUTTON_BROWSER)
        def handle_browser(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_DULL_GREEN)
                if self.current_test is None:
                    menu = self.screen_manager.screens.get("menu")
                    if menu:
                        menu.activate_selected()
                else:
                    # Return to menu
                    self.current_test = None
                    self.screen_manager.show_screen("menu")
            else:
                self.fire.set_button_led(self.fire.BUTTON_BROWSER, self.fire.LED_OFF)
        
        # Shift/Alt - modify behavior
        @self.fire.on_button(self.fire.BUTTON_SHIFT)
        def handle_shift(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_SHIFT, self.fire.LED_DULL_RED)
                self.screen_manager.show_message("SHIFT ON")
            else:
                self.fire.set_button_led(self.fire.BUTTON_SHIFT, self.fire.LED_OFF)
        
        @self.fire.on_button(self.fire.BUTTON_ALT)
        def handle_alt(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_ALT, self.fire.LED_DULL_RED)
                self.screen_manager.show_message("ALT ON")
            else:
                self.fire.set_button_led(self.fire.BUTTON_ALT, self.fire.LED_OFF)
        
        # Solo buttons - control track LEDs
        for i in range(4):
            @self.fire.on_button(self.fire.BUTTON_SOLO_1 + i)
            def make_solo_handler(track_num):
                def handler(event):
                    if event == "press":
                        # Toggle track LED
                        self.fire.set_track_led(track_num + 1, 2)
                        self.fire.set_button_led(self.fire.BUTTON_SOLO_1 + track_num, 1)
                    else:
                        self.fire.set_track_led(track_num + 1, 0)
                        self.fire.set_button_led(self.fire.BUTTON_SOLO_1 + track_num, 0)
                return handler
            self.fire.on_solo(i+1)(make_solo_handler(i))
        
        # Rotary encoders - show values on screen
        rotary_values = {
            self.fire.ROTARY_VOLUME: 64,
            self.fire.ROTARY_PAN: 64,
            self.fire.ROTARY_FILTER: 64,
            self.fire.ROTARY_RESONANCE: 64,
            self.fire.ROTARY_SELECT: 64,
        }
        
        @self.fire.on_rotary_turn()
        def handle_rotary(rotary_id, direction, velocity):
            # Update value
            delta = velocity if direction == "clockwise" else -velocity
            rotary_values[rotary_id] = max(0, min(127, rotary_values[rotary_id] + delta))
            value = rotary_values[rotary_id]
            
            # Update screen based on rotary
            if rotary_id == self.fire.ROTARY_VOLUME:
                screen = self.screen_manager.screens["volume"]
                screen.set_value(int(value * 100 / 127))
                self.screen_manager.show_screen("volume")
            elif rotary_id == self.fire.ROTARY_PAN:
                screen = self.screen_manager.screens["pan"]
                pan_val = int((value - 64) * 100 / 64)
                screen.set_value(f"{'L' if pan_val < 0 else 'R'}{abs(pan_val)}")
                self.screen_manager.show_screen("pan")
            elif rotary_id == self.fire.ROTARY_FILTER:
                screen = self.screen_manager.screens["filter"]
                freq = int(20 + (value / 127) * 19980)  # 20Hz to 20kHz
                screen.set_value(freq)
                self.screen_manager.show_screen("filter")
            elif rotary_id == self.fire.ROTARY_RESONANCE:
                screen = self.screen_manager.screens["resonance"]
                screen.set_value(int(value * 100 / 127))
                self.screen_manager.show_screen("resonance")
            
            # Update control bank LEDs based on volume
            if rotary_id == self.fire.ROTARY_VOLUME:
                if value < 32:
                    self.fire.set_control_bank_leds(self.fire.FIELD_CHANNEL)
                elif value < 64:
                    self.fire.set_control_bank_leds(self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER)
                elif value < 96:
                    self.fire.set_control_bank_leds(self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER | self.fire.FIELD_USER1)
                else:
                    self.fire.set_control_bank_leds(self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER | self.fire.FIELD_USER1 | self.fire.FIELD_USER2)
        
        # Bank/Select buttons
        @self.fire.on_button(self.fire.BUTTON_BANK)
        def handle_bank(event):
            if event == "press":
                self.fire.set_button_led(self.fire.BUTTON_BANK, 1)
                # Cycle control bank LEDs
                self.led_flicker_phase = (self.led_flicker_phase + 1) % 4
                states = [
                    self.fire.FIELD_CHANNEL,
                    self.fire.FIELD_MIXER,
                    self.fire.FIELD_USER1,
                    self.fire.FIELD_USER2
                ]
                self.fire.set_control_bank_leds(states[self.led_flicker_phase])
            else:
                self.fire.set_button_led(self.fire.BUTTON_BANK, 0)
    
    def test_pads(self):
        """Test all pads with a sweep pattern."""
        self.current_test = "pads"
        self.screen_manager.show_screen("pad_grid")
        
        def pad_sweep():
            # Clear first
            self.fire.clear_all_pads()
            
            # Sweep through all pads
            for i in range(64):
                if not self.running or self.current_test != "pads":
                    break
                    
                # Calculate color based on position
                row = i // 16
                col = i % 16
                red = int((col / 15) * 127)
                green = int((row / 3) * 127)
                blue = int(((15 - col) / 15) * 127)
                
                self.fire.set_pad_color(i, red, green, blue)
                time.sleep(0.02)
            
            # Flash all pads
            for _ in range(3):
                if not self.running or self.current_test != "pads":
                    break
                self.fire.clear_all_pads()
                time.sleep(0.2)
                for i in range(64):
                    self.fire.set_pad_color(i, 60, 60, 60)
                time.sleep(0.2)
                
        self.test_thread = threading.Thread(target=pad_sweep)
        self.test_thread.start()
    
    def test_buttons(self):
        """Test all buttons by lighting their LEDs."""
        self.current_test = "buttons"
        text_screen = self.screen_manager.screens["button_test"]
        text_screen.set_lines(["Press any button!", "LED will light up", "", "Browser = Menu"])
        self.screen_manager.show_screen("button_test")
        
        # Light all button LEDs briefly
        all_buttons = [
            self.fire.BUTTON_PLAY, self.fire.BUTTON_STOP, self.fire.BUTTON_REC,
            self.fire.BUTTON_SHIFT, self.fire.BUTTON_ALT, self.fire.BUTTON_STEP,
            self.fire.BUTTON_NOTE, self.fire.BUTTON_DRUM, self.fire.BUTTON_PERFORM,
            self.fire.BUTTON_PATTERN, self.fire.BUTTON_BROWSER, 
            self.fire.BUTTON_SOLO_1, self.fire.BUTTON_SOLO_2, 
            self.fire.BUTTON_SOLO_3, self.fire.BUTTON_SOLO_4,
            self.fire.BUTTON_PAT_UP, self.fire.BUTTON_PAT_DOWN,
            self.fire.BUTTON_BANK, self.fire.BUTTON_SELECT
        ]
        
        def button_sweep():
            for button in all_buttons:
                if not self.running or self.current_test != "buttons":
                    break
                self.fire.set_button_led(button, 2)
                time.sleep(0.1)
                self.fire.set_button_led(button, 0)
                
        self.test_thread = threading.Thread(target=button_sweep)
        self.test_thread.start()
    
    def test_rotaries(self):
        """Test rotary encoders."""
        self.current_test = "rotaries"
        text_screen = self.screen_manager.screens["rotary_test"]
        text_screen.set_lines(["Turn any knob!", "Values shown", "on screen"])
        self.screen_manager.show_screen("rotary_test")
    
    def test_leds(self):
        """Test track LEDs and control bank LEDs."""
        self.current_test = "leds"
        text_screen = self.screen_manager.screens["led_test"]
        text_screen.set_lines(["Testing LEDs...", "Track: 1-4", "Control Bank"])
        self.screen_manager.show_screen("led_test")
        
        def led_test():
            # Track LEDs
            for i in range(3):
                for track in range(1, 5):
                    if not self.running or self.current_test != "leds":
                        return
                    self.fire.set_track_led(track, 2)
                    time.sleep(0.1)
                    self.fire.set_track_led(track, 0)
            
            # Control bank LEDs
            patterns = [
                self.fire.FIELD_CHANNEL,
                self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER,
                self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER | self.fire.FIELD_USER1,
                self.fire.FIELD_CHANNEL | self.fire.FIELD_MIXER | self.fire.FIELD_USER1 | self.fire.FIELD_USER2,
                0
            ]
            
            for pattern in patterns:
                if not self.running or self.current_test != "leds":
                    return
                self.fire.set_control_bank_leds(pattern)
                time.sleep(0.3)
                
        self.test_thread = threading.Thread(target=led_test)
        self.test_thread.start()
    
    def start_pattern(self):
        """Start animated pattern on pads."""
        self.pattern_running = True
        
        def pattern_animation():
            while self.pattern_running and self.running:
                # Create wave pattern
                for col in range(16):
                    for row in range(4):
                        if not self.pattern_running:
                            return
                            
                        pad = row * 16 + col
                        
                        # Calculate wave
                        phase = self.pattern_phase + col * 0.4
                        brightness = int((math.sin(phase) + 1) * 63)
                        
                        # Different color per row
                        if row == 0:
                            self.fire.set_pad_color(pad, brightness, 0, 0)
                        elif row == 1:
                            self.fire.set_pad_color(pad, 0, brightness, 0)
                        elif row == 2:
                            self.fire.set_pad_color(pad, 0, 0, brightness)
                        else:
                            self.fire.set_pad_color(pad, brightness, brightness, 0)
                
                self.pattern_phase += 0.1
                time.sleep(0.03)
                
        self.test_thread = threading.Thread(target=pattern_animation)
        self.test_thread.start()
    
    def stop_pattern(self):
        """Stop pattern animation."""
        self.pattern_running = False
        if self.test_thread:
            self.test_thread.join(timeout=1)
    
    def clear_all(self):
        """Clear everything."""
        self.stop_pattern()
        self.current_test = None
        self.fire.clear_all()
        self.screen_manager.show_screen("menu")
    
    def exit(self):
        """Exit the test."""
        self.running = False
        self.stop_pattern()
        self.fire.clear_all()
        self.screen_manager.show_message("Goodbye!", 1)
    
    def run(self):
        """Main run loop."""
        # Initial setup
        self.fire.clear_all()
        self.screen_manager.show_screen("menu")
        
        print("\n=== AKAI Fire Comprehensive Test ===")
        print("Use Pattern Up/Down to navigate menu")
        print("Press Browser to select")
        print("Press buttons, turn knobs, tap pads!")
        print("Close window or Ctrl+C to exit\n")
        
        try:
            while self.running:
                if self.is_mock:
                    if not self.fire.process_events():
                        break
                else:
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.exit()
            self.fire.close()


if __name__ == "__main__":
    test = ComprehensiveTest()
    test.run()