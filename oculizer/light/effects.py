"""
effects.py

This module provides stateful effect definitions for the Oculizer lighting system.
Effects can maintain state between processing cycles and create complex temporal patterns.

Effect-Modulator Interaction:
----------------------------
Effects in this module can interact with modulator values (from process_mfft, process_bool, process_time)
in two main ways:

1. Override Effects:
   - Completely replace modulator channel values with their own values
   - Useful for effects that need precise control over all channels
   - Example: rockville_splatter completely overwrites channels for distinct patterns

2. Transformative Effects:
   - Modify or enhance existing modulator channel values
   - Preserve some characteristics of the original modulation
   - Example: rockville_panel_fade applies a fade to existing brightness values

Each effect's documentation specifies which type it is and how it handles modulator values.
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
    
    def clear_light_states(self, light_name: str):
        """Clear all effect states for a specific light."""
        if light_name in self.states:
            del self.states[light_name]
    
    def clear_all_states(self):
        """Clear all effect states. Used during scene transitions."""
        self.states.clear()

# Global registry instance
registry = EffectRegistry()

def reset_effect_states():
    """Reset all effect states. Call this during scene transitions."""
    registry.clear_all_states()

def rockville_panel_fade(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Fade effect for Rockville panel section.
    
    Type: Override Effect
    Modulator Interaction: This effect overrides all panel channels (1-28). While it uses
    the audio data for triggering, it does not preserve any modulator channel values.
    Instead, it:
    1. Sets master dimmer and mode channels directly
    2. Applies its own RGB values based on panel_color config
    3. Manages brightness through its own fade logic
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - fade_duration: seconds to fade out after trigger
    - min_brightness: minimum brightness value
    - max_brightness: maximum brightness value
    - panel_color: RGB color for panel background when in manual mode
    
    Channel Control:
    - Channel 1 (Master): Set to 255
    - Channel 2 (Strobe): Unchanged
    - Channel 3 (Mode): Set to 0 (manual mode)
    - Channel 4 (Speed): Set by mode_speed config
    - Channels 5-28: Controlled by fade effect with panel_color
    """
    state = registry.get_state(light_name, 'rockville_panel_fade')
    current_time = time.time()
    
    # Initialize channels if not already set
    if len(channels) < 39:
        channels = [0] * 39
    
    # Set master dimmer to max
    channels[0] = 255
    
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
        
        # Set to manual mode (0) for direct control
        channels[2] = 0  # 3-in-1 mode
        channels[3] = config.get('mode_speed', 255)  # Mode speed
        
        # Set panel color and apply brightness
        color = config.get('panel_color', [255, 255, 255])  # Default to white
        for i in range(8):  # 8 RGB bulb groups
            base_idx = 4 + (i * 3)  # Starting from channel 5 (index 4)
            channels[base_idx:base_idx + 3] = [
                int(c * brightness / 255) for c in color
            ]
    
    return channels

def rockville_sequential_panels(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Sequential activation of panel RGB groups.
    
    Type: Override Effect
    Modulator Interaction: This effect completely overrides panel channels (1-28).
    It does not preserve or use any modulator channel values. Instead, it:
    1. Controls all panel channels directly
    2. Uses audio only for sequence triggering
    3. Manages its own sequence state and timing
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - sequence_duration: seconds for full sequence
    - colors: list of RGB colors to use in sequence
    
    Channel Control:
    - Channel 1 (Master): Set to 255
    - Channel 2 (Strobe): Unchanged
    - Channel 3 (Mode): Set to 0 (manual mode)
    - Channels 5-28: Controlled by sequence pattern
    """
    state = registry.get_state(light_name, 'rockville_sequential_panels')
    current_time = time.time()
    
    # Initialize channels if not already set
    if len(channels) < 39:
        channels = [0] * 39
    
    # Set master dimmer to max and manual mode
    channels[0] = 255  # Master dimmer
    channels[2] = 0    # Manual mode
    
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
        colors = config.get('colors', [[255, 0, 0], [0, 255, 0], [0, 0, 255]])
        
        time_per_step = sequence_duration / 8  # 8 RGB groups
        time_since_trigger = current_time - state.last_trigger_time
        
        # Calculate current position in sequence
        state.sequence_position = int(time_since_trigger / time_per_step)
        
        # Reset if sequence is complete
        if state.sequence_position >= 8:
            state.is_active = False
            return channels
        
        # Set the current panel's color
        color = colors[state.sequence_position % len(colors)]
        base_idx = 4 + (state.sequence_position * 3)
        channels[base_idx:base_idx + 3] = color
    
    return channels

def rockville_splatter(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Random color patterns for both panel and bar sections.
    
    Type: Override Effect
    Modulator Interaction: This effect is a complete override effect that takes full
    control of both panel (1-28) and bar (29-39) sections. It:
    1. Ignores all input channel values from modulators
    2. Sets its own control channels (master, modes)
    3. Generates completely new random patterns
    4. Uses audio only for pattern triggering
    
    Config parameters:
    - mfft_range: (low, high) indices for audio analysis
    - threshold: audio power threshold to trigger effect
    - panel_colors: list of RGB colors for panel sections
    - bar_colors: list of brightness values for bar sections
    - affect_panel: whether to randomize panel sections
    - affect_bar: whether to randomize bar sections
    
    Channel Control:
    Panel Section:
    - Channel 1 (Master): Set to 255
    - Channel 2 (Strobe): Unchanged
    - Channel 3 (Mode): Set to 0 (manual mode)
    - Channels 5-28: Random colors from panel_colors
    
    Bar Section:
    - Channel 29 (Strobe): Set to 0
    - Channel 30 (Mode): Set to 0 (manual mode)
    - Channels 32-39: Random values from bar_colors
    """
    state = registry.get_state(light_name, 'rockville_splatter')
    
    # Initialize channels if not already set
    if len(channels) < 39:
        channels = [0] * 39
    
    # Set master dimmer and manual modes
    channels[0] = 255  # Master dimmer
    channels[2] = 0    # Panel manual mode
    channels[29] = 0   # Bar strobe off
    channels[30] = 0   # Bar manual mode
    
    # Get audio power in specified range
    mfft_range = config.get('mfft_range', (0, len(mfft_data)))
    power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    if power >= threshold:
        # Get configuration
        panel_colors = config.get('panel_colors', [[255, 0, 255], [0, 255, 0]])
        bar_colors = config.get('bar_colors', [0, 255])
        affect_panel = config.get('affect_panel', True)
        affect_bar = config.get('affect_bar', True)
        
        # Randomize panel sections
        if affect_panel:
            for i in range(8):  # 8 RGB groups
                if random.random() < 0.5:  # 50% chance to change each section
                    color = random.choice(panel_colors)
                    base_idx = 4 + (i * 3)
                    channels[base_idx:base_idx + 3] = color
                else:
                    base_idx = 4 + (i * 3)
                    channels[base_idx:base_idx + 3] = [0, 0, 0]
        
        # Randomize bar sections
        if affect_bar:
            for i in range(8):  # 8 bar bulbs
                channels[31 + i] = random.choice(bar_colors)
    
    return channels

# Dictionary mapping effect names to their functions
EFFECTS = {
    'rockville_panel_fade': rockville_panel_fade,
    'rockville_sequential_panels': rockville_sequential_panels,
    'rockville_splatter': rockville_splatter
}

def apply_effect(effect_name: str, channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Apply a named effect to the channel values.
    
    This function is called after the modulator has set initial channel values.
    Each effect may choose to:
    1. Override the modulator values completely
    2. Transform or enhance the modulator values
    3. Selectively modify certain channels while preserving others
    
    See individual effect documentation for specific behavior.
    """
    if effect_name in EFFECTS:
        return EFFECTS[effect_name](channels, mfft_data, config, light_name)
    return channels 