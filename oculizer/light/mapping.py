import numpy as np
import time
from oculizer.config import audio_parameters

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']

# Define colors as a numpy array for faster operations
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

def random_color():
    return np.random.randint(0, len(COLORS))

def generate_RGB_signal(brightness=255, color_index=0, strobe=0, colorfade=0):
    color = COLORS[color_index]
    return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), int(colorfade)]

def freq_to_index(freq):
    return int(freq * BLOCKSIZE / SAMPLERATE)

def power_to_brightness(power, power_low, power_high, brightness_low, brightness_high):
    if power < power_low:
        return brightness_low
    elif power > power_high:
        return brightness_high
    else:
        return int((power - power_low) / (power_high - power_low) * (brightness_high - brightness_low) + brightness_low)

def mfft_to_brightness(mfft_vec, mfft_range, power_range, brightness_range):
    mfft_low, mfft_high = mfft_range
    mfft_mean = np.mean(mfft_vec[mfft_low:mfft_high])
    return power_to_brightness(mfft_mean, power_range[0], power_range[1], brightness_range[0], brightness_range[1])

def mfft_to_rgb(mfft_vec, mfft_range, power_range, brightness_range, color, strobe):
    brightness = mfft_to_brightness(mfft_vec, mfft_range, power_range, brightness_range)
    
    if color == 'random':
        color = random_color()
    color = COLORS[color]
    
    return [brightness, color[0], color[1], color[2], strobe, 0]

def mfft_to_dimmer(mfft_vec, mfft_range, prange, brange):
    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    mfft_mean = np.mean(mfft_vec[freq_low:freq_high])
    return int(power_to_brightness(mfft_mean, prange[0], prange[1], brange[0], brange[1]))

def mfft_to_strobe(mfft_vec, mfft_range, threshold):
    mfft_low, mfft_high = mfft_range
    mfft_mean = np.mean(mfft_vec[mfft_low:mfft_high])
    return [255, 255] if mfft_mean >= threshold else [0, 0]

def bool_rgb(brightness, color_index, strobe, colorfade):
    color = COLORS[color_index]
    return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), int(colorfade)]

def bool_strobe(speed, brightness):
    return [int(speed), int(brightness)]

def time_function(t, frequency, function):
    if function == 0:  # sine
        return np.sin(t * frequency * 2 * np.pi) * 0.5 + 0.5
    elif function == 1:  # square
        return np.sign(np.sin(t * frequency * 2 * np.pi)) * 0.5 + 0.5
    elif function == 2:  # triangle
        return np.abs(((t * frequency) % 2) - 1)
    elif function == 3:  # sawtooth_forward
        return (t * frequency) % 1
    elif function == 4:  # sawtooth_backward
        return 1 - (t * frequency % 1)

def time_dimmer(t, min_brightness, max_brightness, frequency, function):
    range_brightness = max_brightness - min_brightness
    return int(min_brightness + range_brightness * time_function(t, frequency, function))

def time_rgb(t, min_brightness, max_brightness, frequency, function, color_index, strobe):
    brightness = time_dimmer(t, min_brightness, max_brightness, frequency, function)
    color = COLORS[color_index]
    return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), 0]

def time_strobe(t, speed_range, brightness_range, frequency, function, target):
    if target == 0:  # speed
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        return [int(speed), int(brightness_range[1])]
    elif target == 1:  # brightness
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return [int(speed_range[1]), int(brightness)]
    else:  # both
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return [int(speed), int(brightness)]

# Helper function to convert color name to index
def color_to_index(color_name):
    return COLOR_NAMES.index(color_name) if color_name in COLOR_NAMES else -1

# Non-JIT functions that interface with the JIT functions
def process_mfft_to_rgb(mfft_vec, light):
    return mfft_to_rgb(mfft_vec, 
                       light['mfft_range'], 
                       light['power_range'], 
                       light['brightness_range'], 
                       light.get('color', 'random'), 
                       light.get('strobe', 0))

def process_bool_rgb(light):
    brightness = np.random.randint(0, 256) if light['brightness'] == 'random' else light['brightness']
    color_index = random_color() if light['color'] == 'random' else color_to_index(light['color'])
    strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
    colorfade = light.get('colorfade', 0)
    return bool_rgb(brightness, color_index, strobe, colorfade)

def process_time_rgb(light, t):
    color_index = random_color() if light['color'] == 'random' else color_to_index(light['color'])
    strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    return time_rgb(t, light['min_brightness'], light['max_brightness'], 
                    light['frequency'], function_index, color_index, strobe)

def process_time_strobe(light, t):
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    target_index = ['speed', 'brightness', 'both'].index(light['target'])
    return time_strobe(t, light['speed_range'], light['brightness_range'], 
                       light['frequency'], function_index, target_index)

# Main processing function
def process_light(light, mfft_vec, current_time):
    modulator = light['modulator']
    light_type = light['type']

    if modulator == 'mfft':
        if light_type == 'dimmer':
            return [mfft_to_brightness(mfft_vec, light['mfft_range'], light['power_range'], light['brightness_range'])]
        elif light_type == 'rgb':
            return mfft_to_rgb(mfft_vec, light['mfft_range'], light['power_range'], light['brightness_range'], light['color'], light['strobe'])
        elif light_type == 'strobe':
            return mfft_to_strobe(mfft_vec, light['mfft_range'], light['threshold'])

    elif modulator == 'bool':
        if light_type == 'dimmer':
            return [int(light['brightness'])]
        elif light_type == 'rgb':
            return process_bool_rgb(light)
        elif light_type == 'strobe':
            return bool_strobe(light['speed'], light['brightness'])
            
    elif modulator == 'time':
        if light_type == 'dimmer':
            return [time_dimmer(t, light['min_brightness'], light['max_brightness'], 
                                light['frequency'], light['function'])]
        elif light_type == 'rgb':
            return process_time_rgb(light, t)
        elif light_type == 'strobe':
            return process_time_strobe(light, t)

    return None  # Return None if no valid combination is found


def main():
    # random 128 length mfft vector
    mfft_data = np.random.rand(128)

    # random light profile
    light = {
        'modulator': 'mfft',
        'type': 'rgb',
        'mfft_range': (0, 128),
        'power_range': (0, 1),
        'brightness_range': (0, 255),
        'color': 'random',
        'strobe': 0
    }

    # process the light
    dmx_values = process_light(light, mfft_data, time.time())
    print(dmx_values)

if __name__ == "__main__":
    main()



