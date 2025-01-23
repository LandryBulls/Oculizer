import numpy as np
import time
from oculizer.config import audio_parameters

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
    [255, 255, 255] # white
], dtype=np.int32)

COLOR_NAMES = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white']

PANEL_COLORS = {
    'red': 3,
    'green': 6,
    'blue': 9,
    'yellow': 12,
    'pink': 15,
    'light_blue': 18,
    'white': 21
}

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

    elif light['type'] == 'panel':
        # this needs to use the built-in codes for panel colors, not by generating [R,G,B] values. 
        # actually, not sure about that. 
        # [master_dimmer, panel_strobe_speed, panel_mode, panel_mode_speed, red, green, blue]
        brightness = mfft_to_value(mfft_vec, mfft_range, power_range, value_range)
        color = PANEL_COLORS[light.get('color', 'random')]
        strobe = light.get('strobe', 0)
        return [brightness, strobe, 0, 0, *color]
    
    elif light['type'] == 'bar':
        # channels: [bar_strobe_speed, bar_mode, bar_mode_speed, bar_dimmer]
        threshold = light.get('threshold', 0.5)
        mfft_mean = np.mean(mfft_vec[mfft_range[0]:mfft_range[1]])
        brightness = 255 if mfft_mean >= threshold else 0
        strobe = light.get('strobe', 0)
        mode = light.get('mode', np.random.randint(0, 255))
        mode_speed = light.get('mode_speed', 0)
        return [strobe, mode, mode_speed, brightness]

def process_bool(light):
    if light['type'] == 'dimmer':
        if light['brightness']=='random':
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

def time_function(t, frequency, function):
    functions = {
        'sine': lambda t, f: np.sin(t * f * 2 * np.pi) * 0.5 + 0.5,
        'square': lambda t, f: np.sign(np.sin(t * f * 2 * np.pi)) * 0.5 + 0.5,
        'triangle': lambda t, f: np.abs(((t * f) % 2) - 1),
        'sawtooth_forward': lambda t, f: (t * f) % 1,
        'sawtooth_backward': lambda t, f: 1 - (t * f % 1)
    }
    
    # Convert integer input to corresponding string
    if isinstance(function, int):
        function_names = list(functions.keys())
        if 0 <= function < len(function_names):
            function = function_names[function]
        else:
            function = 'sine'  # Default to sine if integer is out of range
    
    # Use the specified function or default to sine
    return functions.get(function, functions['sine'])(t, frequency)

def process_time(light, current_time):
    t = current_time
    frequency = light.get('frequency', 1)
    function = light.get('function', 'sine')
    min_value = light.get('min_brightness', 0)
    max_value = light.get('max_brightness', 255)
    value = int(min_value + (max_value - min_value) * time_function(t, frequency, function))
    
    if light['type'] == 'dimmer':
        return [value]
    elif light['type'] == 'rgb':
        color = color_to_rgb(light.get('color', 'random'))
        strobe = light.get('strobe', 0)
        return [value, *color, strobe, 0]
    elif light['type'] == 'strobe':
        target = light.get('target', 'both')
        speed_range = light.get('speed_range', [0, 255])
        brightness_range = light.get('brightness_range', [0, 255])
        if target == 'speed':
            return [value, brightness_range[1]]
        elif target == 'brightness':
            return [speed_range[1], value]
        else:
            speed = int(speed_range[0] + (speed_range[1] - speed_range[0]) * time_function(t, frequency, function))
            brightness = int(brightness_range[0] + (brightness_range[1] - brightness_range[0]) * time_function(t, frequency, function))
            return [speed, brightness]

def process_light(light, mfft_vec, current_time):
    modulator = light.get('modulator', 'bool')
    
    if modulator == 'mfft':
        return process_mfft(light, mfft_vec)
    elif modulator == 'bool':
        return process_bool(light)
    elif modulator == 'time':
        return process_time(light, current_time)
    
    return None

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



