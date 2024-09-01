"""
This script contains the functions for converting input signals into DMX values based on the input parameters. Also stores colors and functions for converting colors to RGB values.

Author: Landry Bulls
Date: 8/24/24
"""

import numpy as np
import time
from numba import jit
from oculizer.config import audio_parameters
import logging

logging.basicConfig(filename='oculizer_debug.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
], dtype=np.float64)

COLOR_NAMES = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'white']

@jit(nopython=True)
def random_color():
    return np.random.randint(0, len(COLORS))

@jit(nopython=True)
def generate_RGB_signal(brightness=255.0, color_index=0, strobe=0.0, colorfade=0.0):
    color = COLORS[color_index]
    return np.array([brightness, color[0], color[1], color[2], strobe, colorfade])

@jit(nopython=True)
def freq_to_index(freq):
    return int(freq * BLOCKSIZE / SAMPLERATE)

@jit(nopython=True)
def power_to_brightness(power, lower_threshold, upper_threshold, min_brightness=0.0, max_brightness=255.0):
    if power < lower_threshold:
        return min_brightness
    elif power > upper_threshold:
        return max_brightness
    else:
        return (power - lower_threshold) / (upper_threshold - lower_threshold) * (max_brightness - min_brightness) + min_brightness

@jit(nopython=True)
def _fft_to_rgb(fft_vec, frange, prange, brange, color_index, strobe):
    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    brightness = power_to_brightness(fft_mean, prange[0], prange[1], brange[0], brange[1])
    
    color = COLORS[color_index]
    
    return np.array([brightness, color[0], color[1], color[2], strobe, 0.0])

def fft_to_rgb(fft_vec, frange, prange, brange, color, strobe):
    if color == 'random':
        color_index = random_color()
    else:
        color_index = color_to_index(color)
    
    return _fft_to_rgb(fft_vec, np.array(frange, dtype=np.float64), 
                       np.array(prange, dtype=np.float64), 
                       np.array(brange, dtype=np.float64), 
                       color_index, float(strobe))

@jit(nopython=True)
def fft_to_dimmer(fft_vec, frange, prange, brange):
    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    return power_to_brightness(fft_mean, prange[0], prange[1], brange[0], brange[1])

@jit(nopython=True)
def fft_to_strobe(fft_vec, frange, lower_threshold=0.5):
    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    return np.array([255.0, 255.0]) if fft_mean >= lower_threshold else np.array([0.0, 0.0])

def bool_rgb(brightness, color_index, strobe, colorfade):
    color = COLORS[color_index]
    return np.array([brightness, color[0], color[1], color[2], strobe, colorfade])

def bool_strobe(speed, brightness):
    return np.array([speed, brightness])

@jit(nopython=True)
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

@jit(nopython=True)
def time_dimmer(t, min_brightness, max_brightness, frequency, function):
    range_brightness = max_brightness - min_brightness
    return min_brightness + range_brightness * time_function(t, frequency, function)

@jit(nopython=True)
def time_rgb(t, min_brightness, max_brightness, frequency, function, color_index, strobe):
    brightness = time_dimmer(t, min_brightness, max_brightness, frequency, function)
    color = COLORS[color_index]
    return np.array([brightness, color[0], color[1], color[2], strobe, 0.0])

@jit(nopython=True)
def time_strobe(t, speed_range, brightness_range, frequency, function, target):
    if target == 0:  # speed
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        return np.array([speed, brightness_range[1]])
    elif target == 1:  # brightness
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return np.array([speed_range[1], brightness])
    else:  # both
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return np.array([speed, brightness])

# Helper function to convert color name to index
def color_to_index(color_name):
    return COLOR_NAMES.index(color_name) if color_name in COLOR_NAMES else -1

# Non-JIT functions that interface with the JIT functions
def process_fft_to_rgb(fft_vec, light):
    return fft_to_rgb(fft_vec, 
                      light['frequency_range'], 
                      light['power_range'], 
                      light['brightness_range'], 
                      light.get('color', 'random'), 
                      light.get('strobe', 0))

def process_bool_rgb(light):
    logging.debug(f"Processing bool RGB light: {light}")
    try:
        brightness = np.random.randint(0, 256) if light['brightness'] == 'random' else light['brightness']
        color_index = random_color() if light['color'] == 'random' else color_to_index(light['color'])
        strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
        colorfade = light.get('colorfade', 0)
        logging.debug(f"Generated brightness: {brightness}, color index: {color_index}, strobe: {strobe}, colorfade: {colorfade}")
        return bool_rgb(float(brightness), color_index, float(strobe), float(colorfade))
    except Exception as e:
        logging.error(f"Error processing bool RGB light: {str(e)}")
        return np.array([0, 0, 0, 0, 0, 0])
    return bool_rgb(float(brightness), color_index, float(strobe), float(colorfade))

def process_time_rgb(light, t):
    color_index = random_color() if light['color'] == 'random' else color_to_index(light['color'])
    strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    return time_rgb(t, float(light['min_brightness']), float(light['max_brightness']), 
                    float(light['frequency']), function_index, color_index, float(strobe))

def process_time_strobe(light, t):
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    target_index = ['speed', 'brightness', 'both'].index(light['target'])
    return time_strobe(t, np.array(light['speed_range'], dtype=np.float64), 
                       np.array(light['brightness_range'], dtype=np.float64), 
                       float(light['frequency']), function_index, target_index)

# Main processing function
def process_light(light, fft_vec=None, t=None):

    modulator = light['modulator']
    logging.debug(f"Processing light {light['name']} with modulator {modulator}")
    light_type = light['type']
    logging.debug(f"Light type: {light_type}")

    result = None

    if modulator == 'fft':
        if light_type == 'dimmer':
            result = fft_to_dimmer(fft_vec, np.array(light['frequency_range'], dtype=np.float64), 
                                   np.array(light['power_range'], dtype=np.float64), 
                                   np.array(light['brightness_range'], dtype=np.float64))
        elif light_type == 'rgb':
            result = process_fft_to_rgb(fft_vec, light)
        elif light_type == 'strobe':
            result = fft_to_strobe(fft_vec, np.array(light['frequency_range'], dtype=np.float64), 
                                   float(light['power_range'][0]))
    elif modulator == 'bool':
        if light_type == 'dimmer':
            result = float(light['brightness'])
        elif light_type == 'rgb':
            result = process_bool_rgb(light)
        elif light_type == 'strobe':
            result = bool_strobe(float(light['speed']), float(light['brightness']))

    elif modulator == 'time':
        if light_type == 'dimmer':
            result = time_dimmer(t, float(light['min_brightness']), float(light['max_brightness']), 
                                 float(light['frequency']), light['function'])
        elif light_type == 'rgb':
            result = process_time_rgb(light, t)
        elif light_type == 'strobe':
            result = process_time_strobe(light, t)

    # Convert result to list of integers
    if result is not None:
        if isinstance(result, (int, float)):
            return [int(result)]
        else:
            return [int(v) for v in result]
    logging.debug(f"No DMX values generated for {light['name']}")
    return None  # Return None if no valid combination is found

