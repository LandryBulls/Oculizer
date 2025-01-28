"""
effects.py

This module provides stateful effect definitions for the Oculizer lighting system.
Effects can maintain state between processing cycles and create complex temporal patterns.
"""

import time
import random
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class EffectState:
    """Stores the current state of an effect."""
    last_trigger_time: float = 0.0
    is_active: bool = False
    sequence_position: int = 0
    custom_state: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_state is None:
            self.custom_state = {}

class EffectRegistry:
    """Registry of all available effects and their states."""
    def __init__(self):
        self.states: Dict[str, Dict[str, EffectState]] = {}  # {light_name: {effect_name: state}}
        
    def get_state(self, light_name: str, effect_name: str) -> EffectState:
        """Get or create state for a light's effect."""
        if light_name not in self.states:
            self.states[light_name] = {}
        if effect_name not in self.states[light_name]:
            self.states[light_name][effect_name] = EffectState()
        return self.states[light_name][effect_name]

# Global registry instance
registry = EffectRegistry()

def fade_after_trigger(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Effect that fades out after being triggered by audio threshold.
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - fade_duration: seconds to fade out after trigger
    - min_brightness: minimum brightness value
    - max_brightness: maximum brightness value
    """
    state = registry.get_state(light_name, 'fade_after_trigger')
    current_time = time.time()
    
    # Get audio power in specified range
    mfft_range = config.get('mfft_range', (0, len(mfft_data)))
    power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    if power >= threshold:
        state.last_trigger_time = current_time
        state.is_active = True
    
    if state.is_active:
        # Calculate fade
        fade_duration = config.get('fade_duration', 1.0)
        time_since_trigger = current_time - state.last_trigger_time
        
        if time_since_trigger >= fade_duration:
            state.is_active = False
            brightness = config.get('min_brightness', 0)
        else:
            fade_ratio = 1.0 - (time_since_trigger / fade_duration)
            min_bright = config.get('min_brightness', 0)
            max_bright = config.get('max_brightness', 255)
            brightness = int(min_bright + (max_bright - min_bright) * fade_ratio)
        
        # Apply brightness to all RGB channels
        for i in range(0, len(channels), 3):
            if channels[i] > 0:  # Only modify active channels
                channels[i] = brightness
    
    return channels

def sequential_trigger(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Effect that activates lights in sequence after trigger.
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - sequence_duration: seconds for full sequence
    - pattern: list of channel groups to activate in sequence
    """
    state = registry.get_state(light_name, 'sequential_trigger')
    current_time = time.time()
    
    # Get audio power in specified range
    mfft_range = config.get('mfft_range', (0, len(mfft_data)))
    power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    if power >= threshold and not state.is_active:
        state.is_active = True
        state.last_trigger_time = current_time
        state.sequence_position = 0
    
    if state.is_active:
        sequence_duration = config.get('sequence_duration', 1.0)
        pattern = config.get('pattern', [[i] for i in range(0, len(channels), 3)])
        
        time_per_step = sequence_duration / len(pattern)
        time_since_trigger = current_time - state.last_trigger_time
        
        # Calculate current position in sequence
        state.sequence_position = int(time_since_trigger / time_per_step)
        
        # Reset if sequence is complete
        if state.sequence_position >= len(pattern):
            state.is_active = False
            return channels
        
        # Activate current channels in sequence
        active_channels = pattern[state.sequence_position]
        for channel in active_channels:
            if channel < len(channels):
                channels[channel] = 255
    
    return channels

def splatter_effect(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Effect that creates random patterns of specified colors when triggered.
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - colors: list of RGB colors to choose from
    - sections: number of independent sections that can be colored
    """
    state = registry.get_state(light_name, 'splatter_effect')
    
    # Get audio power in specified range
    mfft_range = config.get('mfft_range', (0, len(mfft_data)))
    power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    if power >= threshold:
        # Get configuration
        colors = config.get('colors', [[255, 0, 255], [0, 255, 0]])  # Default pink and green
        sections = config.get('sections', len(channels) // 3)
        
        # Generate new random pattern
        for section in range(sections):
            if random.random() < 0.5:  # 50% chance to activate each section
                color = random.choice(colors)
                base_idx = section * 3
                if base_idx + 2 < len(channels):
                    channels[base_idx:base_idx + 3] = color
            else:
                base_idx = section * 3
                if base_idx + 2 < len(channels):
                    channels[base_idx:base_idx + 3] = [0, 0, 0]
    
    return channels

# Dictionary mapping effect names to their functions
EFFECTS = {
    'fade_after_trigger': fade_after_trigger,
    'sequential_trigger': sequential_trigger,
    'splatter_effect': splatter_effect
}

def apply_effect(effect_name: str, channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Apply a named effect to the channel values."""
    if effect_name in EFFECTS:
        return EFFECTS[effect_name](channels, mfft_data, config, light_name)
    return channels 