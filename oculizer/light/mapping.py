import numpy as np
import random
import time
from oculizer.config import audio_parameters
from oculizer.light.effects import apply_effect

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']

COLORS = np.array([
    [255, 0, 0],    # red
    [255, 127, 0],  # orange
    [255, 255, 0],  # yellow
    [0, 255, 0],    # green
    [0, 0, 255],    # blue
    [75, 0, 130],   # purple
    [255, 0, 255],  # pink
    [255, 255, 255], # white
    [0, 0, 0]       # black
], dtype=np.int32)

COLOR_NAMES = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white']

# PANEL_COLORS = {
#     'red': 3,
#     'green': 6,
#     'blue': 9,
#     'yellow': 12,
#     'pink': 15,
#     'light_blue': 18,
#     'white': 21
# }

def scale_mfft(mfft_vec, scaling_factor=10.0, scaling_method='log'):
    num_bins = len(mfft_vec)
    if scaling_method == 'log':
        scaling = np.log1p(np.arange(num_bins) / num_bins) * scaling_factor + 1
    elif scaling_method == 'exp':
        scaling = np.exp(np.arange(num_bins) / num_bins * scaling_factor)
    elif scaling_method == 'linear':
        scaling = np.linspace(1, 1 + scaling_factor, num_bins)
    else:
        raise ValueError("Invalid scaling method. Choose 'log', 'exp', or 'linear'.")
    scaling /= scaling.mean()
    return mfft_vec * scaling

def color_to_rgb(color_name):
    return COLORS[COLOR_NAMES.index(color_name)] if color_name in COLOR_NAMES else COLORS[np.random.randint(0, len(COLOR_NAMES))]

def freq_to_index(freq):
    return int(freq * BLOCKSIZE / SAMPLERATE)

def power_to_brightness(power, power_range, brightness_range):
    power_low, power_high = power_range
    brightness_low, brightness_high = brightness_range
    if power <= power_low:
        return brightness_low
    elif power >= power_high:
        return brightness_high
    else:
        return int((power - power_low) / (power_high - power_low) * (brightness_high - brightness_low) + brightness_low)

def mfft_to_value(mfft_vec, mfft_range, power_range, value_range):
    mfft_low, mfft_high = int(mfft_range[0]), int(mfft_range[1])
    if mfft_low < 0 or mfft_high > len(mfft_vec):
        raise ValueError(f"MFFT range {mfft_range} is out of bounds for MFFT vector of length {len(mfft_vec)}")
    mfft_mean = np.mean(mfft_vec[mfft_low:mfft_high])
    return power_to_brightness(mfft_mean, power_range, value_range)

def time_function(t, frequency, function):
    functions = {
        'sine': lambda t, f: np.sin(t * f * 2 * np.pi) * 0.5 + 0.5,
        'square': lambda t, f: np.sign(np.sin(t * f * 2 * np.pi)) * 0.5 + 0.5,
        'triangle': lambda t, f: np.abs(((t * f) % 2) - 1),
        'sawtooth_forward': lambda t, f: (t * f) % 1,
        'sawtooth_backward': lambda t, f: 1 - (t * f % 1)
    }
    return functions.get(function, functions['sine'])(t, frequency)

def process_mfft(light, mfft_vec):
    mfft_range = light.get('mfft_range', (0, len(mfft_vec)))
    power_range = light.get('power_range', (0, 1))
    value_range = light.get('brightness_range', (0, 255))
    
    if light['type'] == 'dimmer':
        return [mfft_to_value(mfft_vec, mfft_range, power_range, value_range)]
    
    elif light['type'] == 'rgb':
        brightness = mfft_to_value(mfft_vec, mfft_range, power_range, value_range)
        color = color_to_rgb(light.get('color', 'random'))
        strobe = light.get('strobe', 0)
        return [brightness, *color, strobe, 0]
    
    elif light['type'] == 'strobe':
        threshold = light.get('threshold', 0.5)
        mfft_mean = np.mean(mfft_vec[mfft_range[0]:mfft_range[1]])
        return [255, 255] if mfft_mean >= threshold else [0, 0]
    
    elif light['type'] == 'laser':
        zoom_range = light.get('zoom_range', [0, 127])
        speed_range = light.get('speed_range', [0, 255])
        mfft_power = np.mean(mfft_vec)
        channels = [0] * 10
        channels[0] = 0
        if mfft_power <= power_range[0]:
            channels[1], channels[3], channels[9] = 0, zoom_range[0], speed_range[0]
        else:
            channels[1], channels[2] = 255, np.random.randint(0, 256)
            if mfft_power >= power_range[1]:
                channels[3], channels[9] = zoom_range[1], speed_range[1]
            else:
                power_ratio = (mfft_power - power_range[0]) / (power_range[1] - power_range[0])
                channels[3] = int(zoom_range[0] + power_ratio * (zoom_range[1] - zoom_range[0]))
                channels[9] = int(speed_range[0] + power_ratio * (speed_range[1] - speed_range[0]))

    elif light['type'] == 'rockville864':
        try:
            # Handle panel component (8 sets of RGB bulbs)
            panel_config = light.get('panel', {})
            if panel_config.get('affect_panel', True):
                panel_mfft_range = panel_config.get('mfft_range', mfft_range)
                panel_power_range = panel_config.get('power_range', power_range)
                panel_value_range = panel_config.get('brightness_range', value_range)
                
                # Calculate panel brightness from audio
                brightness_magnitude = mfft_to_value(mfft_vec, panel_mfft_range, panel_power_range, panel_value_range)
                
                # Initialize 39 channels
                channels = [0] * 39
                
                # Channels 1-4: Master and panel effects
                channels[0] = 255  # Master dimmer always at max
                channels[1] = np.random.randint(0, 256) if panel_config.get('strobe') == 'random' else panel_config.get('strobe', 0)  # Panel strobe speed
                channels[2] = np.random.randint(126, 255) if panel_config.get('mode') == 'random' else panel_config.get('mode', 0)
                channels[3] = brightness_magnitude if panel_config.get('mode_speed', 255) == 'auto' else panel_config.get('mode_speed', 0)  # Mode speed
                
                # If mode is 0, use direct RGB control, otherwise RGB channels are background
                if channels[2] == 0:
                    color = color_to_rgb(panel_config.get('color', 'random'))
                    scaled_color = [int(c * brightness_magnitude / 255) for c in color]
                    
                    # Set all 8 RGB bulb sets (channels 5-28)
                    for i in range(8):
                        base_idx = 4 + (i * 3)
                        channels[base_idx:base_idx + 3] = scaled_color
                else:
                    # When mode is active, use color as background
                    color = color_to_rgb(panel_config.get('color', 'random'))
                    scaled_color = [int(c * brightness_magnitude / 255) for c in color]
                    # Set background color for all RGB channels
                    for i in range(8):
                        base_idx = 4 + (i * 3)
                        channels[base_idx:base_idx + 3] = scaled_color
            else:
                channels = [0] * 39
            
            bar_config = light.get('bar', {})
            if bar_config.get('affect_bar', True):
                bar_mfft_range = bar_config.get('bar_mfft_range', (0, len(mfft_vec)))
                bar_power = np.mean(mfft_vec[bar_mfft_range[0]:bar_mfft_range[1]])
                bar_threshold = bar_config.get('threshold', 0.5)
                bar_mode = bar_config.get('mode', 0)

                if bar_power >= bar_threshold:
                    channels[28] = bar_config.get('strobe', 0)
                    channels[29] = 0 if bar_mode == 'random' else bar_mode
                    channels[30] = bar_config.get('mode_speed', 255)
            
                    if bar_mode == 0:   
                        for i in range(31, 39):
                            channels[i] = random.choice(bar_config.get('bar_colors', [0, 255]))
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
                    
        except Exception as e:
            print(f"Error processing rockville864 light {light['name']}: {e}")
            return [0] * 39

def process_bool(light):
    if light['type'] == 'rockville864':
        try:
            # Initialize 39 channels
            channels = [0] * 39
            channels[0] = 255  # Master dimmer always at max
            
            # Handle panel section
            panel_config = light.get('panel', {})
            
            # Set panel controls
            channels[1] = np.random.randint(0, 256) if panel_config.get('strobe') == 'random' else panel_config.get('strobe', 0)
            channels[2] = panel_config.get('mode', 0)
            channels[3] = panel_config.get('mode_speed', 255)
            
            # Handle panel brightness
            if panel_config.get('brightness') == 'random':
                min_brightness = panel_config.get('min_brightness', 0)
                max_brightness = panel_config.get('max_brightness', 255)
                brightness = np.random.randint(min_brightness, max_brightness + 1)
            else:
                brightness = panel_config.get('brightness', 255)
            
            # If mode is 0, use direct RGB control
            if channels[2] == 0:
                color = color_to_rgb(panel_config.get('color', 'random'))
                scaled_color = [int(c * brightness / 255) for c in color]
                
                # Set all 8 RGB bulb sets
                for i in range(8):
                    base_idx = 4 + (i * 3)
                    channels[base_idx:base_idx + 3] = scaled_color
            else:
                # When mode is active, use color as background
                color = color_to_rgb(panel_config.get('color', 'random'))
                scaled_color = [int(c * brightness / 255) for c in color]
                # Set background color for all RGB channels
                for i in range(8):
                    base_idx = 4 + (i * 3)
                    channels[base_idx:base_idx + 3] = scaled_color
            
            # Handle bar section
            bar_config = light.get('bar', {})
            if bar_config.get('affect_bar', True):
                channels[28] = bar_config.get('strobe', 0)
                channels[29] = 0 if bar_config.get('mode') == 'random' else bar_config.get('mode', 0)
                channels[30] = bar_config.get('mode_speed', 255)
                brightness = bar_config.get('brightness', 0)  # Default to 0 for bar
                
                if channels[29] == 0:  # Manual mode
                    channels[31:39] = [brightness] * 8
                elif channels[29] == "random":
                    channels[29] = 0  # Set to manual mode
                    # Generate 8 different random values
                    min_brightness = bar_config.get('min_brightness', 0)
                    max_brightness = bar_config.get('max_brightness', 255)
                    channels[31:39] = [np.random.randint(min_brightness, max_brightness + 1) for _ in range(8)]
                else:
                    channels[31:39] = [0] * 8
            else:
                # If affect_bar is False, set all bar channels to 0
                channels[28:39] = [0] * 11  
            
            return channels
            
        except Exception as e:
            print(f"Error processing rockville864 light {light['name']}: {e}")
            return [0] * 39
            
    elif light['type'] == 'dimmer':
        if light.get('brightness', 'random') == 'random':
            brightness = np.random.randint(light.get('min_brightness', 0), light.get('max_brightness', 255) + 1)
        else:
            brightness = light.get('brightness', 255)
        return [brightness]
    elif light['type'] == 'rgb':
        if light.get('brightness', 'random') == 'random':
            min_brightness = light.get('min_brightness', 0)
            max_brightness = light.get('max_brightness', 255)
            brightness = np.random.randint(min_brightness, max_brightness + 1)
        else:
            brightness = light.get('brightness', 255)
        color = color_to_rgb(light.get('color', 'random'))
        strobe = np.random.randint(0, 256) if light.get('strobe', 'random') == 'random' else light.get('strobe', 0)
        colorfade = light.get('colorfade', 0)
        return [brightness, *color, strobe, colorfade]
    elif light['type'] == 'strobe':
        speed = np.random.randint(0, 256) if light.get('speed', 'random') == 'random' else light.get('speed', 255)
        brightness = np.random.randint(0, 256) if light.get('brightness', 'random') == 'random' else light.get('brightness', 255)
        return [speed, brightness]
    elif light['type'] == 'laser':
        return [128, 255] + [0] * 8

def process_time(light, current_time):
    if light['type'] == 'rockville864':
        try:
            frequency = light.get('frequency', 1)
            function = light.get('function', 'sine')
            min_value = light.get('min_brightness', 0)
            max_value = light.get('max_brightness', 255)
            
            # Calculate time-based value
            value = int(min_value + (max_value - min_value) * time_function(current_time, frequency, function))
            
            # Initialize channels
            channels = [0] * 39
            channels[0] = 255  # Master dimmer always at max
            
            # Handle panel section
            panel_config = light.get('panel', {})
            target = panel_config.get('target', 'brightness')  # What the time function affects
            
            channels[1] = panel_config.get('strobe', 0)
            channels[2] = panel_config.get('mode', 0)
            
            if target == 'mode_speed':
                channels[3] = value
            else:
                channels[3] = panel_config.get('mode_speed', 255)
            
            # If mode is 0, use direct RGB control
            if channels[2] == 0:
                color = color_to_rgb(panel_config.get('color', 'random'))
                if target == 'brightness':
                    scaled_color = [int(c * value / 255) for c in color]
                else:
                    scaled_color = color
                    
                # Set all 8 RGB bulb sets
                for i in range(8):
                    base_idx = 4 + (i * 3)
                    channels[base_idx:base_idx + 3] = scaled_color
            else:
                # When mode is active, RGB channels become background
                channels[4:28] = [value if target == 'brightness' else panel_config.get('brightness', 255)] * 24
            
            # Handle bar section
            bar_config = light.get('bar', {})
            if bar_config.get('affect_bar', True):  # Only process bar if affect_bar is True
                bar_target = bar_config.get('target', 'none')
                
                # Set basic bar controls
                channels[28] = bar_config.get('strobe', 0)
                channels[29] = bar_config.get('mode', 0)
                channels[30] = bar_config.get('mode_speed', 255)  # Mode speed
                
                if channels[29] == 0:  # Manual mode
                    if bar_target == 'sections':
                        # Apply time function to all sections
                        channels[31:39] = [value] * 8
                    else:
                        # Use configured sections
                        sections = bar_config.get('sections', [255] * 8)
                        channels[31:39] = sections
                elif channels[29] == "random":
                    channels[29] = 0
                    channels[31:39] = [int(np.random.randint(0, 256) * value / 255) for _ in range(8)]
                else:
                    channels[30] = bar_config.get('mode_speed', 255)  # Set mode speed
                    channels[31:39] = [0] * 8
            else:
                # If affect_bar is False, set all bar channels to 0
                channels[28:] = [0] * 12
            
            return channels
            
        except Exception as e:
            print(f"Error processing rockville864 light {light['name']}: {e}")
            return [0] * 39
            
    elif light['type'] == 'dimmer':
        # get the time function value
        value = int(light.get('min_brightness', 0) + (light.get('max_brightness', 255) - light.get('min_brightness', 0)) * time_function(current_time, light.get('frequency', 1), light.get('function', 'sine')))
        return [value]

    elif light['type'] == 'rgb':
        color = color_to_rgb(light.get('color', 'random'))
        strobe = light.get('strobe', 0)
        # get the time function value
        value = int(light.get('min_brightness', 0) + (light.get('max_brightness', 255) - light.get('min_brightness', 0)) * time_function(current_time, light.get('frequency', 1), light.get('function', 'sine')))
        return [value, *color, strobe, 0]
    
    elif light['type'] == 'strobe':
        target = light.get('target', 'both')
        speed_range = light.get('speed_range', [0, 255])
        brightness_range = light.get('brightness_range', [0, 255])
        if target == 'speed':
            return [light.get('brightness', 255), brightness_range[1]]
        elif target == 'brightness':
            return [speed_range[1], light.get('brightness', 255)]
        else:
            speed = int(speed_range[0] + (speed_range[1] - speed_range[0]) * time_function(current_time, light.get('frequency', 1), light.get('function', 'sine')))
            brightness = int(brightness_range[0] + (brightness_range[1] - brightness_range[0]) * time_function(current_time, light.get('frequency', 1), light.get('function', 'sine')))
            return [speed, brightness]

def process_light(light, mfft_vec, current_time, modifiers=None):
    # First check if there's an effect
    if 'effect' in light:
        effect_config = light['effect']
        
        # Handle time modulation if configured
        if 'time_modulation' in effect_config:
            time_mod = effect_config['time_modulation']
            if not modifiers:
                modifiers = {}
            # Calculate time-based brightness scale
            brightness_scale = time_function(
                current_time,
                time_mod.get('frequency', 1.0),
                time_mod.get('function', 'sine')
            )
            # Scale between min and max
            min_bright = time_mod.get('min_brightness', 0) / 255
            max_bright = time_mod.get('max_brightness', 255) / 255
            brightness_scale = min_bright + (max_bright - min_bright) * brightness_scale
            modifiers['brightness_scale'] = brightness_scale
        
        if isinstance(effect_config, str):
            # Simple case: just effect name
            channels = [0] * 39 if light['type'] == 'rockville864' else [0] * 6  # Initialize channels
            channels = apply_effect(effect_config, channels, mfft_vec, {}, light['name'])
        elif isinstance(effect_config, dict):
            # Advanced case: effect name and config
            effect_name = effect_config.pop('name')
            channels = [0] * 39 if light['type'] == 'rockville864' else [0] * 6  # Initialize channels
            channels = apply_effect(effect_name, channels, mfft_vec, effect_config, light['name'])
            effect_config['name'] = effect_name  # Restore the name key
    else:
        # No effect, use modulator
        modulator = light.get('modulator', 'bool')
        
        # Get initial channel values based on modulator
        if modulator == 'mfft':
            channels = process_mfft(light, mfft_vec)
        elif modulator == 'bool':
            channels = process_bool(light)
        elif modulator == 'time':
            channels = process_time(light, current_time)
        else:
            return None
    
    # Apply modifiers if provided
    if channels and modifiers:
        if 'brightness_scale' in modifiers:
            # Scale brightness channels based on the modifier
            if light['type'] == 'dimmer':
                channels[0] = int(channels[0] * modifiers['brightness_scale'])
            elif light['type'] == 'rgb':
                channels[0] = int(channels[0] * modifiers['brightness_scale'])
            elif light['type'] == 'rockville864':
                # For Rockville, scale all RGB values
                for i in range(4, 28, 3):  # RGB sections
                    for j in range(3):  # R, G, B channels
                        channels[i + j] = int(channels[i + j] * modifiers['brightness_scale'])
    
    return channels

def main():
    mfft_data = np.random.rand(128)
    light = {
        'modulator': 'mfft',
        'type': 'rgb',
        'mfft_range': (0, 128),
        'power_range': (0, 1),
        'brightness_range': (0, 255),
        'color': 'random',
        'strobe': 0
    }
    dmx_values = process_light(light, mfft_data, time.time())
    print(dmx_values)

if __name__ == "__main__":
    main()



