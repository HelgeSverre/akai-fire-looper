"""
Animation utilities for AKAI Fire pad animations.

This module provides common animation patterns and utilities extracted from
the experimental batching examples.
"""

import math
import colorsys
from typing import List, Tuple, Callable
from dataclasses import dataclass


@dataclass
class AnimationState:
    """State container for animations."""
    frame: int = 0
    time: float = 0.0
    

def hsv_to_rgb_127(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """
    Convert HSV to RGB with 0-127 range (AKAI Fire range).
    
    Args:
        h: Hue (0.0-1.0)
        s: Saturation (0.0-1.0)
        v: Value (0.0-1.0)
        
    Returns:
        Tuple of (red, green, blue) in 0-127 range
    """
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 127), int(g * 127), int(b * 127))


def angle_to_rgb_127(angle: float) -> Tuple[int, int, int]:
    """
    Convert angle (degrees) to RGB color.
    
    Args:
        angle: Angle in degrees (0-360)
        
    Returns:
        Tuple of (red, green, blue) in 0-127 range
    """
    # Simplified HSV to RGB conversion
    h = (angle % 360) / 60
    x = int(127 * (1 - abs(h % 2 - 1)))
    
    if h < 1:
        return (127, x, 0)
    elif h < 2:
        return (x, 127, 0)
    elif h < 3:
        return (0, 127, x)
    elif h < 4:
        return (0, x, 127)
    elif h < 5:
        return (x, 0, 127)
    else:
        return (127, 0, x)


def pad_index_to_xy(index: int) -> Tuple[int, int]:
    """Convert pad index (0-63) to x,y coordinates."""
    return (index % 16, index // 16)


def xy_to_pad_index(x: int, y: int) -> int:
    """Convert x,y coordinates to pad index (0-63)."""
    return y * 16 + x


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


class AnimationPattern:
    """Base class for animation patterns."""
    
    def __init__(self):
        self.state = AnimationState()
        
    def update(self, delta_time: float = 0.033):
        """Update animation state."""
        self.state.frame += 1
        self.state.time += delta_time
        
    def render(self) -> List[Tuple[int, int, int, int]]:
        """
        Render the animation frame.
        
        Returns:
            List of (pad_index, red, green, blue) tuples
        """
        raise NotImplementedError


class RainbowWavePattern(AnimationPattern):
    """Rotating rainbow wave pattern."""
    
    def __init__(self, speed: float = 2.0, wave_length: float = 64.0):
        super().__init__()
        self.speed = speed
        self.wave_length = wave_length
        
    def render(self) -> List[Tuple[int, int, int, int]]:
        pad_colors = []
        
        for i in range(64):
            x, y = pad_index_to_xy(i)
            angle = (self.state.frame * self.speed + i * (360 / self.wave_length)) % 360
            r, g, b = angle_to_rgb_127(angle)
            pad_colors.append((i, r, g, b))
            
        return pad_colors


class CircularPulsePattern(AnimationPattern):
    """Expanding/contracting circular pulses."""
    
    def __init__(self, center_x: float = 7.5, center_y: float = 1.5, 
                 frequency: float = 0.1, max_radius: float = 4.0):
        super().__init__()
        self.center_x = center_x
        self.center_y = center_y
        self.frequency = frequency
        self.max_radius = max_radius
        
    def render(self) -> List[Tuple[int, int, int, int]]:
        pad_colors = []
        radius = (math.sin(self.state.time * self.frequency * 2 * math.pi) + 1) * self.max_radius
        
        for i in range(64):
            x, y = pad_index_to_xy(i)
            dist = distance(x, y, self.center_x, self.center_y)
            intensity = max(0, min(127, int(127 * (1 - abs(dist - radius) / 2))))
            
            # Blue-cyan gradient
            pad_colors.append((i, 0, intensity // 2, intensity))
            
        return pad_colors


class MatrixRainPattern(AnimationPattern):
    """Matrix-style rain effect."""
    
    def __init__(self, drop_speed: float = 2.0, color: Tuple[int, int, int] = (0, 127, 0)):
        super().__init__()
        self.drop_speed = drop_speed
        self.color = color
        
    def render(self) -> List[Tuple[int, int, int, int]]:
        pad_colors = []
        
        for i in range(64):
            x, y = pad_index_to_xy(i)
            
            # Different drop speeds for each column
            drop_pos = (x * 7 + self.state.frame * self.drop_speed) % 80
            
            if drop_pos < 64:
                # Calculate intensity based on position
                row_pos = y * 16
                intensity = max(0, min(127, int(127 * (1 - abs(row_pos - drop_pos) / 16))))
                
                r = int(self.color[0] * intensity / 127)
                g = int(self.color[1] * intensity / 127)
                b = int(self.color[2] * intensity / 127)
                pad_colors.append((i, r, g, b))
            else:
                pad_colors.append((i, 0, 0, 0))
                
        return pad_colors


class WavePattern(AnimationPattern):
    """Sinusoidal wave pattern."""
    
    def __init__(self, frequency: float = 0.1, wave_speed: float = 0.1,
                 direction: str = "horizontal"):
        super().__init__()
        self.frequency = frequency
        self.wave_speed = wave_speed
        self.direction = direction
        
    def render(self) -> List[Tuple[int, int, int, int]]:
        pad_colors = []
        
        for i in range(64):
            x, y = pad_index_to_xy(i)
            
            if self.direction == "horizontal":
                pos = x
            elif self.direction == "vertical":
                pos = y
            else:  # diagonal
                pos = x + y
                
            wave = math.sin(self.state.time * self.wave_speed * 2 * math.pi + pos * self.frequency * 2 * math.pi)
            intensity = int((wave + 1) * 63.5)
            
            # Create color gradient
            red = max(0, min(127, intensity))
            green = max(0, min(127, int(intensity * 0.5)))
            blue = max(0, min(127, 127 - intensity))
            
            pad_colors.append((i, red, green, blue))
            
        return pad_colors


class AnimationComposer:
    """Compose multiple animation patterns together."""
    
    def __init__(self):
        self.patterns: List[Tuple[AnimationPattern, float]] = []
        
    def add_pattern(self, pattern: AnimationPattern, blend_weight: float = 1.0):
        """Add a pattern with a blend weight."""
        self.patterns.append((pattern, blend_weight))
        
    def update(self, delta_time: float = 0.033):
        """Update all patterns."""
        for pattern, _ in self.patterns:
            pattern.update(delta_time)
            
    def render(self) -> List[Tuple[int, int, int, int]]:
        """Render composite of all patterns."""
        if not self.patterns:
            return [(i, 0, 0, 0) for i in range(64)]
            
        # Initialize accumulator
        accumulator = [[0.0, 0.0, 0.0] for _ in range(64)]
        total_weight = sum(weight for _, weight in self.patterns)
        
        # Blend all patterns
        for pattern, weight in self.patterns:
            frame = pattern.render()
            for index, r, g, b in frame:
                accumulator[index][0] += r * weight / total_weight
                accumulator[index][1] += g * weight / total_weight
                accumulator[index][2] += b * weight / total_weight
                
        # Convert to integer values
        pad_colors = []
        for i in range(64):
            r = int(min(127, accumulator[i][0]))
            g = int(min(127, accumulator[i][1]))
            b = int(min(127, accumulator[i][2]))
            pad_colors.append((i, r, g, b))
            
        return pad_colors


class SmoothedValue:
    """Smoothly interpolate between values over time."""
    
    def __init__(self, initial_value: float, smoothing: float = 0.15):
        self.current = initial_value
        self.target = initial_value
        self.smoothing = smoothing
        
    def update(self) -> float:
        """Update and return current value."""
        if abs(self.current - self.target) > 0.0001:
            self.current += (self.target - self.current) * self.smoothing
        return self.current
        
    def set_target(self, value: float):
        """Set target value to smoothly move towards."""
        self.target = value
        
    def set_immediate(self, value: float):
        """Set value immediately without smoothing."""
        self.current = value
        self.target = value