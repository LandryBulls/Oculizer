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
    'purple': (200, 0, 255),
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
    direction: int = 1  # 1 for left to right, -1 for right to left
    color_position: int = 0
    current_sweep_color: tuple = None
    custom_state: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_state is None:
            self.custom_state = {}
        if self.current_sweep_color is None:
            self.current_sweep_color = COLORS['white']

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
    """Fade effect for Rockville panel section with independent bar control.
    
    The bar section can now also have a sustain duration via the bar_sustain parameter.
    When bar_sustain is specified, the bar will stay on for that duration after being triggered,
    allowing patterns like left-to-right movement to complete their cycle."""
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
    wait = config.get('wait', True)  # Get wait parameter
    
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
    
    # Handle panel section
    # Check if we should trigger based on wait parameter
    panel_threshold = config.get('panel_threshold', 0.5)
    fade_duration = config.get('fade_duration', 1.0)
    time_since_trigger = current_time - state.last_trigger_time
    
    can_trigger = (
        panel_power >= panel_threshold and (
            not state.is_active or  # Not currently active
            not wait or  # Wait is disabled, allowing interruption
            time_since_trigger >= fade_duration  # Current fade has completed
        )
    )
    
    if can_trigger:
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
                state.custom_state['block_colors'] = [
                    current_color if random.random() <= coverage else (0,0,0)
                    for _ in range(8)
                ]
                # Ensure at least one block is active
                if all(color == (0,0,0) for color in state.custom_state['block_colors']):
                    random_block = random.randint(0, 7)
                    state.custom_state['block_colors'][random_block] = current_color
                state.sequence_position += 1
            elif color_order == 'random':
                chosen_color = random.choice(panel_colors)
                state.custom_state['block_colors'] = [
                    chosen_color if random.random() <= coverage else (0,0,0)
                    for _ in range(8)
                ]
                # Ensure at least one block is active
                if all(color == (0,0,0) for color in state.custom_state['block_colors']):
                    random_block = random.randint(0, 7)
                    state.custom_state['block_colors'][random_block] = chosen_color
    
    if state.is_active:
        # Calculate fade
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
            

    # Handle bar section
    if config.get('affect_bar', True):
        bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
        bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
        bar_threshold = config.get('bar_threshold', 0.5)
        bar_mode = config.get('bar_mode', 0)

        # Check if bar_sustain is configured
        bar_sustain = config.get('bar_sustain', None)
        
        if bar_sustain is not None:
            # Use sustain behavior for bar
            if not hasattr(state, 'bar_last_trigger'):
                state.bar_last_trigger = 0
                state.bar_active = False
            
            bar_time_since_trigger = current_time - state.bar_last_trigger
            
            # Check if we should trigger the bar
            if bar_power >= bar_threshold and (
                not state.bar_active or  # Not currently active
                bar_time_since_trigger >= bar_sustain  # Current sustain has completed
            ):
                state.bar_last_trigger = current_time
                state.bar_active = True
            
            # Update bar state based on sustain duration
            if state.bar_active:
                if bar_time_since_trigger >= bar_sustain:
                    state.bar_active = False
                else:
                    # Bar is active, set channels
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
            # Use original behavior (no sustain)
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
    """Sequential activation of panel RGB groups in pairs.
    
    Activates pairs of panels in sequence:
    - Blocks 1 & 5
    - Blocks 2 & 6
    - Blocks 3 & 7
    - Blocks 4 & 8
    
    Direction can be 'left_to_right', 'right_to_left', or 'alternating'.
    Colors follow pure/mix and next/random rules for consistent behavior with other effects.
    """
    state = registry.get_state(light_name, 'rockville_sequential_panels')
    current_time = time.time()
    
    # Get colors from config and convert from names to RGB values
    colors = config.get('colors', ['white'])
    if isinstance(colors, list):
        panel_colors = [COLORS[color] if isinstance(color, str) else color for color in colors]
    elif isinstance(colors, str):
        panel_colors = PALETTES[colors]
    else:
        panel_colors = [COLORS[colors]]
    
    # Create a fresh channel array
    channels = [0] * 39

    # Set up the RGB block indices in pairs
    block_pairs = [
        # (left_block, right_block)
        (0, 4),  # blocks 1 & 5
        (1, 5),  # blocks 2 & 6
        (2, 6),  # blocks 3 & 7
        (3, 7),  # blocks 4 & 8
    ]
    
    # Map block indices to their RGB channels
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
    
    color_order = config.get('color_order', 'next')
    combo_mode = config.get('combo_mode', 'mix')
    
    # Check if we should trigger
    threshold = config.get('threshold', 0.5)
    wait = config.get('wait', True)  # Get wait parameter
    direction_mode = config.get('direction', 'left_to_right')
    
    # Check if we can trigger based on wait parameter
    can_trigger = (
        panel_power >= threshold and (
            not state.is_active or  # Not currently active
            not wait  # Wait is disabled, allowing interruption
        )
    )
    
    if can_trigger:
        state.is_active = True
        state.last_trigger_time = current_time
        state.sequence_position = 0
        if not hasattr(state, 'direction'):
            state.direction = 1  # 1 for left to right, -1 for right to left
        
        # Set new sweep color in pure mode with next ordering
        if combo_mode == 'pure' and color_order == 'next':
            if not hasattr(state, 'color_position'):
                state.color_position = 0
            if not hasattr(state, 'current_sweep_color'):
                state.current_sweep_color = panel_colors[state.color_position % len(panel_colors)]
            else:
                # Update color for new sweep
                state.color_position += 1
                state.current_sweep_color = panel_colors[state.color_position % len(panel_colors)]
        elif combo_mode == 'pure' and color_order == 'random':
            # Set new random color for this sweep
            state.current_sweep_color = random.choice(panel_colors)
    
    if state.is_active:
        sequence_duration = config.get('sequence_duration', 1.0)
        
        time_per_step = sequence_duration / len(block_pairs)
        time_since_trigger = current_time - state.last_trigger_time
        
        # Calculate current position in sequence
        raw_position = int(time_since_trigger / time_per_step)
        
        # Handle direction modes
        if direction_mode == 'right_to_left':
            state.sequence_position = len(block_pairs) - 1 - raw_position
        elif direction_mode == 'alternating':
            if not hasattr(state, 'direction'):
                state.direction = 1
            if raw_position >= len(block_pairs):
                state.direction *= -1  # Reverse direction for next sequence
            state.sequence_position = raw_position if state.direction == 1 else (len(block_pairs) - 1 - raw_position)
        else:  # left_to_right (default)
            state.sequence_position = raw_position
        
        # Reset if sequence is complete
        if raw_position >= len(block_pairs):
            state.is_active = False
            return channels
        
        # Get the current pair of blocks
        if 0 <= state.sequence_position < len(block_pairs):
            left_idx, right_idx = block_pairs[state.sequence_position]
            
            # Determine colors based on mode
            if combo_mode == 'pure':
                # Use the current sweep color
                left_color = right_color = state.current_sweep_color
            else:  # mix mode
                # Each block gets its own random color
                left_color = random.choice(panel_colors)
                right_color = random.choice(panel_colors)
            
            # Set the colors for both blocks
            for block_idx, color in [(left_idx, left_color), (right_idx, right_color)]:
                r_idx, g_idx, b_idx = blocks[block_idx]['channels']
                channels[r_idx] = color[0]
                channels[g_idx] = color[1]
                channels[b_idx] = color[2]
            
    
    # Handle bar section
    if affect_bar:
        bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
        bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
        bar_threshold = config.get('bar_threshold', 0.5)
        bar_mode = config.get('bar_mode', 0)

        # Check if bar_sustain is configured
        bar_sustain = config.get('bar_sustain', None)
        
        if bar_sustain is not None:
            # Use sustain behavior for bar
            if not hasattr(state, 'bar_last_trigger'):
                state.bar_last_trigger = 0
                state.bar_active = False
            
            bar_time_since_trigger = current_time - state.bar_last_trigger
            
            # Check if we should trigger the bar
            if bar_power >= bar_threshold and (
                not state.bar_active or  # Not currently active
                bar_time_since_trigger >= bar_sustain  # Current sustain has completed
            ):
                state.bar_last_trigger = current_time
                state.bar_active = True
            
            # Update bar state based on sustain duration
            if state.bar_active:
                if bar_time_since_trigger >= bar_sustain:
                    state.bar_active = False
                else:
                    # Bar is active, set channels
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
            # Use original behavior (no sustain)
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
    
    return channels

def rockville_splatter(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Random color patterns for both panel and bar sections.
    
    The bar section can now also have a sustain duration via the bar_sustain parameter.
    When bar_sustain is specified, the bar will stay on for that duration after being triggered,
    allowing patterns like left-to-right movement to complete their cycle."""
    state = registry.get_state(light_name, 'rockville_splatter')
    current_time = time.time()
    
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
    channels[1] = np.random.randint(0, 256) if config.get('panel_strobe') == 'random' else config.get('panel_strobe', 0)  # Panel strobe
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
                color = random.choice(PANEL_COLORS)
                block_states.append((is_active, color))
            
            # Apply the states to channels
            for block, (is_active, color) in zip(blocks, block_states):
                r_idx, g_idx, b_idx = block['channels']
                channels[r_idx] = color[0]
                channels[g_idx] = color[1]
                channels[b_idx] = color[2]

    # Handle bar section
    if config.get('affect_bar', True):
        bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
        bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
        bar_threshold = config.get('bar_threshold', 0.5)
        bar_mode = config.get('bar_mode', 0)

        # Check if bar_sustain is configured
        bar_sustain = config.get('bar_sustain', None)
        
        if bar_sustain is not None:
            # Use sustain behavior for bar
            if not hasattr(state, 'bar_last_trigger'):
                state.bar_last_trigger = 0
                state.bar_active = False
            
            bar_time_since_trigger = current_time - state.bar_last_trigger
            
            # Check if we should trigger the bar
            if bar_power >= bar_threshold and (
                not state.bar_active or  # Not currently active
                bar_time_since_trigger >= bar_sustain  # Current sustain has completed
            ):
                state.bar_last_trigger = current_time
                state.bar_active = True
            
            # Update bar state based on sustain duration
            if state.bar_active:
                if bar_time_since_trigger >= bar_sustain:
                    state.bar_active = False
                else:
                    # Bar is active, set channels
                    channels[28] = config.get('bar_strobe', 0)
                    channels[29] = bar_mode
                    channels[30] = config.get('mode_speed', 255)
                    
                    if bar_mode == 0:   
                        for i in range(31, 39):
                            channels[i] = random.choice(config.get('bar_colors', [255]))
                    else:
                        for i in range(31, 39):
                            channels[i] = 0
        else:
            # Use original behavior (no sustain)
            if bar_power >= bar_threshold:
                channels[28] = np.random.randint(0, 256) if config.get('bar_strobe') == 'random' else config.get('bar_strobe', 0)
                channels[29] = bar_mode
                channels[30] = config.get('mode_speed', 255)
            
                if bar_mode == 0:   
                    for i in range(31, 39):
                        channels[i] = random.choice(config.get('bar_colors', [255]))
                else:
                    for i in range(31, 39):
                        channels[i] = 0
    else:
        # If bar is not affected, ensure all bar channels are off
        for i in range(28, 39):
            channels[i] = 0
    
    return channels

def rockville_panel_sustain(channels: List[int], mfft_data: np.ndarray, config: dict, light_name: str) -> List[int]:
    """Sustain effect for Rockville panel section with independent bar control.
    Similar to panel_fade but maintains full brightness for a set duration instead of fading.
    
    The bar section can now also have a sustain duration via the bar_sustain parameter.
    When bar_sustain is specified, the bar will stay on for that duration after being triggered,
    allowing patterns like left-to-right movement to complete their cycle."""
    state = registry.get_state(light_name, 'rockville_panel_sustain')
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
    wait = config.get('wait', True)  # Get wait parameter
    
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
    
    # Handle panel section
    panel_threshold = config.get('panel_threshold', 0.5)
    sustain_duration = config.get('sustain_duration', 1.0)
    time_since_trigger = current_time - state.last_trigger_time
    
    can_trigger = (
        panel_power >= panel_threshold and (
            not state.is_active or  # Not currently active
            not wait or  # Wait is disabled, allowing interruption
            time_since_trigger >= sustain_duration  # Current sustain has completed
        )
    )
    
    if can_trigger:
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
                state.custom_state['block_colors'] = [
                    current_color if random.random() <= coverage else (0,0,0)
                    for _ in range(8)
                ]
                # Ensure at least one block is active
                if all(color == (0,0,0) for color in state.custom_state['block_colors']):
                    random_block = random.randint(0, 7)
                    state.custom_state['block_colors'][random_block] = current_color
                state.sequence_position += 1
            elif color_order == 'random':
                chosen_color = random.choice(panel_colors)
                state.custom_state['block_colors'] = [
                    chosen_color if random.random() <= coverage else (0,0,0)
                    for _ in range(8)
                ]
                # Ensure at least one block is active
                if all(color == (0,0,0) for color in state.custom_state['block_colors']):
                    random_block = random.randint(0, 7)
                    state.custom_state['block_colors'][random_block] = chosen_color
    
    if state.is_active:
        # Check if we're still within the sustain duration
        if time_since_trigger >= sustain_duration:
            state.is_active = False
            brightness = config.get('min_brightness', 0)
        else:
            # Maintain full brightness during sustain period
            brightness = config.get('max_brightness', 255)
        
        # Apply brightness to blocks with their stored colors
        for i, block in enumerate(blocks):
            if 'block_colors' not in state.custom_state:
                state.custom_state['block_colors'] = [random.choice(panel_colors) for _ in range(8)]
            color = state.custom_state['block_colors'][i]
            r_idx, g_idx, b_idx = block['channels']
            channels[r_idx] = int(color[0] * brightness / 255)
            channels[g_idx] = int(color[1] * brightness / 255)
            channels[b_idx] = int(color[2] * brightness / 255)
            

    # Handle bar section
    if config.get('affect_bar', True):
        bar_mfft_range = config.get('bar_mfft_range', (0, len(mfft_data)))
        bar_power = np.mean(mfft_data[bar_mfft_range[0]:bar_mfft_range[1]])
        bar_threshold = config.get('bar_threshold', 0.5)
        bar_mode = config.get('bar_mode', 0)

        # Check if bar_sustain is configured
        bar_sustain = config.get('bar_sustain', None)
        
        if bar_sustain is not None:
            # Use sustain behavior for bar
            if not hasattr(state, 'bar_last_trigger'):
                state.bar_last_trigger = 0
                state.bar_active = False
            
            bar_time_since_trigger = current_time - state.bar_last_trigger
            
            # Check if we should trigger the bar
            if bar_power >= bar_threshold and (
                not state.bar_active or  # Not currently active
                bar_time_since_trigger >= bar_sustain  # Current sustain has completed
            ):
                state.bar_last_trigger = current_time
                state.bar_active = True
            
            # Update bar state based on sustain duration
            if state.bar_active:
                if bar_time_since_trigger >= bar_sustain:
                    state.bar_active = False
                else:
                    # Bar is active, set channels
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
            # Use original behavior (no sustain)
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

# Dictionary mapping effect names to their functions
EFFECTS = {
    'rockville_panel_fade': rockville_panel_fade,
    'rockville_sequential_panels': rockville_sequential_panels,
    'rockville_splatter': rockville_splatter,
    'rockville_panel_sustain': rockville_panel_sustain
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