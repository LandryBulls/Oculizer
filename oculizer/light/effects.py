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

COLORS = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'purple': (255, 0, 255),
    'orange': (255, 165, 0),
    'pink': (255, 105, 180),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'magenta': (255, 0, 255),
    'cyan': (0, 255, 255),
    'lime': (128, 255, 0),
    'teal': (0, 128, 128),
    'maroon': (128, 0, 0),
    'navy': (0, 0, 128),
    'olive': (128, 128, 0),
    'gray': (128, 128, 128),
    'silver': (192, 192, 192),
    'gold': (255, 215, 0),
    'coral': (255, 127, 80),
    'salmon': (250, 128, 114),
    'peach': (255, 218, 185)
}

palette_keys= {
    'rainbow': ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white'],
    'RGB': ['red', 'green', 'blue'],
    'trip': ['green', 'purple'],
    'electric': ['white', 'teal'],
    'pastel': ['pink', 'yellow', 'blue', 'green'],
    'neon': ['yellow', 'blue', 'green', 'pink'],
    'pastel_neon': ['pink', 'yellow', 'blue', 'green', 'white'],
    'neon_pastel': ['yellow', 'blue', 'green', 'pink', 'white'],
    'pastel_neon_electric': ['pink', 'yellow', 'blue', 'green', 'white', 'teal']
}

PALETTES = {
    'rainbow': [COLORS[color] for color in palette_keys['rainbow']],
    'RGB': [COLORS[color] for color in palette_keys['RGB']],
    'trip': [COLORS[color] for color in palette_keys['trip']],
    'electric': [COLORS[color] for color in palette_keys['electric']],
    'pastel': [COLORS[color] for color in palette_keys['pastel']],
    'neon': [COLORS[color] for color in palette_keys['neon']],
    'pastel_neon': [COLORS[color] for color in palette_keys['pastel_neon']],
    'neon_pastel': [COLORS[color] for color in palette_keys['neon_pastel']],
    'pastel_neon_electric': [COLORS[color] for color in palette_keys['pastel_neon_electric']]
}

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
    """Fade effect for Rockville panel section with independent bar control."""
    state = registry.get_state(light_name, 'rockville_panel_fade')
    current_time = time.time()
    
    # Create a fresh channel array
    channels = [0] * 39

    # Get colors from config and convert from names to RGB values
    colors = config.get('colors', ['white'])
    coverage = float(config.get('coverage', 1))
    if isinstance(colors, list):
        panel_colors = [COLORS[color] if isinstance(color, str) else color for color in colors]
    elif isinstance(colors, str):
        panel_colors = PALETTES[colors]
    else:
        panel_colors = [COLORS[colors]]    

    color_order = config.get('color_order', 'next')
    combo_mode = config.get('combo_mode', 'mix')
    
    # Set up the RGB block indices
    blocks = []
    for i in range(8):
        base_idx = 4 + (i * 3)  # First block starts at channel 4 (Ch5 in manual)
        blocks.append({
            'index': i,
            'channels': (base_idx, base_idx + 1, base_idx + 2)
        })
    
    # Set master dimmer and control channels
    channels[0] = 255  # Master dimmer
    channels[1] = config.get('panel_strobe', 0)  # Panel strobe
    channels[2] = 0    # Panel manual mode
    channels[3] = config.get('mode_speed', 255)  
    
    # Get panel audio power
    panel_mfft_range = config.get('panel_mfft_range', (0, len(mfft_data)))
    panel_power = np.mean(mfft_data[panel_mfft_range[0]:panel_mfft_range[1]])
    print(f"Panel Power: {panel_power}")  # Debug output
    
    # Handle panel section
    # Check if we should trigger
    panel_threshold = config.get('panel_threshold', 0.5)
    if panel_power >= panel_threshold:
        # Only trigger if we're not already active or if the fade has completed
        if not state.is_active or (current_time - state.last_trigger_time) >= config.get('fade_duration', 1.0):
            state.last_trigger_time = current_time
            state.is_active = True
            
            # Increment sequence position for next color if using 'next' order
            if not hasattr(state, 'sequence_position'):
                state.sequence_position = 0
            
            # Store colors for blocks based on combo mode and coverage
            if combo_mode == 'mix':
                # Generate initial block colors
                state.custom_state['block_colors'] = [
                    random.choice(panel_colors) if random.random() <= coverage else (0,0,0) 
                    for _ in range(8)
                ]
                # Ensure at least one block is active by randomly selecting one if none are
                if all(color == (0,0,0) for color in state.custom_state['block_colors']):
                    random_block = random.randint(0, 7)
                    state.custom_state['block_colors'][random_block] = random.choice(panel_colors)
            elif combo_mode == 'pure':
                if color_order == 'next':
                    # Use current sequence position to select color and increment for next time
                    current_color = panel_colors[state.sequence_position % len(panel_colors)]
                    state.custom_state['block_colors'] = [current_color] * 8
                    state.sequence_position += 1
                    print(f"Using color {current_color} (position {state.sequence_position-1})")
                elif color_order == 'random':
                    chosen_color = random.choice(panel_colors)
                    state.custom_state['block_colors'] = [chosen_color] * 8
    
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
        
        # Apply brightness to blocks with their stored colors
        for i, block in enumerate(blocks):
            if 'block_colors' not in state.custom_state:
                state.custom_state['block_colors'] = [random.choice(panel_colors) for _ in range(8)]
            color = state.custom_state['block_colors'][i]
            r_idx, g_idx, b_idx = block['channels']
            channels[r_idx] = int(color[0] * brightness / 255)
            channels[g_idx] = int(color[1] * brightness / 255)
            channels[b_idx] = int(color[2] * brightness / 255)
            
            # Debug output
            print(f"Block {i}: Color RGB{color} at brightness {brightness}")

    # Handle bar section
    if config.get('affect_bar', True):
        bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
        bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
        bar_threshold = config.get('bar_threshold', 0.5)
        bar_mode = config.get('bar_mode', 0)
        print(f"Bar Power: {bar_power}")  # Debug output

        if bar_power >= bar_threshold:
            channels[28] = config.get('bar_strobe', 0)
            channels[29] = 0 if bar_mode == 'random' else bar_mode
            channels[30] = config.get('mode_speed', 255)
        
            if bar_mode == 0:   
                for i in range(31, 39):
                    channels[i] = random.choice(config.get('bar_colors', [255]))
            elif bar_mode == 'random':
                for i in range(31, 39):
                    channels[i] = random.choice([0, 255])
            else:
                for i in range(31, 39):
                    channels[i] = 0
    else:
        # If bar is not affected, ensure all bar channels are off
        for i in range(28, 39):
            channels[i] = 0
    
    return channels

def rockville_sequential_panels(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Sequential activation of panel RGB groups."""
    state = registry.get_state(light_name, 'rockville_sequential_panels')
    current_time = time.time()
    
    # Create a fresh channel array
    channels = [0] * 39

    # Set up the RGB block indices
    blocks = []
    for i in range(8):
        base_idx = 4 + (i * 3)  # First block starts at channel 4 (Ch5 in manual)
        blocks.append({
            'index': i,
            'channels': (base_idx, base_idx + 1, base_idx + 2)
        })
    
    # Set master dimmer and control channels
    channels[0] = 255  # Master dimmer
    channels[1] = config.get('panel_strobe', 0)  # Panel strobe
    channels[2] = 0    # Panel manual mode
    channels[3] = config.get('mode_speed', 255)  # Mode speed
    
    # Initialize bar section to off
    affect_bar = config.get('affect_bar', False)
    if not affect_bar:
        for i in range(28, 39):
            channels[i] = 0
    
    # Get panel audio power
    panel_mfft_range = config.get('panel_mfft_range', (0, len(mfft_data)))
    panel_power = np.mean(mfft_data[panel_mfft_range[0]:panel_mfft_range[1]])
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    if panel_power >= threshold and not state.is_active:
        state.is_active = True
        state.last_trigger_time = current_time
        state.sequence_position = 0
    
    if state.is_active:
        sequence_duration = config.get('sequence_duration', 1.0)
        colors = config.get('colors', [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        
        time_per_step = sequence_duration / len(blocks)
        time_since_trigger = current_time - state.last_trigger_time
        
        # Calculate current position in sequence
        state.sequence_position = int(time_since_trigger / time_per_step)
        
        # Reset if sequence is complete
        if state.sequence_position >= len(blocks):
            state.is_active = False
            return channels
        
        # Set the current block's color
        color = colors[state.sequence_position % len(colors)]
        current_block = blocks[state.sequence_position]
        r_idx, g_idx, b_idx = current_block['channels']
        channels[r_idx] = color[0]
        channels[g_idx] = color[1]
        channels[b_idx] = color[2]
        
        # Debug output
        print(f"Sequence position: {state.sequence_position}, Active block: {current_block['index']}, Color: RGB{color}")
    
    return channels

def rockville_splatter(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Random color patterns for both panel and bar sections."""
    state = registry.get_state(light_name, 'rockville_splatter')
    
    # Create a fresh channel array instead of modifying the input
    channels = [0] * 39
    
    PANEL_COLORS = [COLORS[i] for i in config.get('panel_colors', random.choice(['red', 'green', 'blue']))]
    
    # Set up the RGB block indices
    blocks = []
    for i in range(8):
        base_idx = 4 + (i * 3)  # First block starts at channel 4 (Ch5 in manual)
        blocks.append({
            'index': i,
            'channels': (base_idx, base_idx + 1, base_idx + 2)  # RGB channels as tuple
        })

    # Set master dimmer and control channels
    channels[0] = 255  # Master dimmer
    channels[1] = config.get('panel_strobe', 0)  # Panel strobe
    channels[2] = 0    # Panel manual mode
    channels[3] = config.get('mode_speed', 255)  # Mode speed
    
    # Get audio power in specified range
    panel_mfft_range = config.get('panel_mfft_range', (0, len(mfft_data)))
    panel_power = np.mean(mfft_data[panel_mfft_range[0]:panel_mfft_range[1]])
    panel_threshold = config.get('panel_threshold', 0.5)
    if config.get('affect_panel', True):    
        if panel_power >= panel_threshold:
            # Generate independent random states for each block
            block_states = []
            for _ in range(8):
                is_active = random.random() < 0.5
                #color = PINK if random.random() < 0.5 else GREEN if is_active else OFF
                color = random.choice(PANEL_COLORS)
                block_states.append((is_active, color))
            
            # Apply the states to channels
            for block, (is_active, color) in zip(blocks, block_states):
                r_idx, g_idx, b_idx = block['channels']
                channels[r_idx] = color[0]
                channels[g_idx] = color[1]
                channels[b_idx] = color[2]


    bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
    bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
    bar_threshold = config.get('bar_threshold', 0.5)
    bar_mode = config.get('bar_mode', 0)
    # Handle bar sections
    if config.get('affect_bar', True):
        if bar_power >= bar_threshold:
            channels[28] = config.get('bar_strobe', 0)
            channels[29] = bar_mode
            channels[30] = config.get('mode_speed', 255)
        
            if bar_mode == 0:   
                for i in range(31, 39):
                    channels[i] = random.choice(config.get('bar_colors', [255]))
            else:
                for i in range(31, 39):
                    channels[i] = 0
    
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