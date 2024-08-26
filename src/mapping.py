"""
This script contains the functions for converting input signals into DMX values based on the input parameters. Also stores colors and functions for converting colors to RGB values.

Author: Landry Bulls
Date: 8/24/24
"""

import numpy as np
import json
from config import audio_parameters
import numpy as np
import time
from math import sin, pi

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']

# these are DMX colors
colors = {
    'red': [255, 0, 0],
    'orange': [255, 127, 0],
    'yellow': [255, 255, 0],
    'green': [0, 255, 0],
    'blue': [0, 0, 255],
    'purple': [75, 0, 130],
    'pink': [255, 0, 255],
    'white': [255, 255, 255]
}

def random_color():
    """
    Returns a random color from the color wheel
    """
    return np.random.choice(list(colors.keys()))

def generate_RGB_signal(brightness=255, color='pink', strobe=0, colorfade=0):
    """
    Returns the list of 7 DMX values for the RGB light
    """
    if strobe=='random':
        strobe_val = np.random.randint(0, 255)
    if color == 'random':
        color = random_color()
    else:
        color = colors[color]
    return [brightness, color[0], color[1], color[2], strobe_val, 0]

def freq_to_index(freq):
    if freq > SAMPLERATE / 2:
        raise ValueError(f"Frequency {freq} Hz is above the Nyquist frequency {SAMPLERATE/2} Hz")
    return int(freq * BLOCKSIZE / SAMPLERATE)

def power_to_brightness(power, lower_threshold, upper_threshold, min_brightness=0, max_brightness=255):
    """
    Converts a power value to a brightness value based on the input thresholds.

    Parameters:
    power (float): The power value to convert to a brightness value.
    lower_threshold (float): The lower threshold for the power value under which the minimum brightness is used.
    upper_threshold (float): The upper threshold for the power value over which the maximum brightness is used.
    min_brightness (int): The minimum brightness value to use.
    max_brightness (int): The maximum brightness value to use.

    Returns:
    int: The brightness value to use. 
    """
    if power < lower_threshold:
        return min_brightness
    elif power > upper_threshold:
        return max_brightness
    else:
        return int((power - lower_threshold) / (upper_threshold - lower_threshold) * (max_brightness - min_brightness) + min_brightness)

def fft_to_rgb(fft_vec, frange=[0,2000], prange=[1.0, 15.0], brange=[0,255], color='random', strobe=0):
    """
    Converts an FFT vector to a set of DMX values to activate an RGB fixture. 

    Parameters:
    fft_vec (np.array): The FFT vector to convert to a DMX value.
    range (int): The range of the FFT vector to consider.
    lower_threshold (int): The lower threshold for the FFT sum under which the minimum brightness is used.
    upper_threshold (int): The upper threshold for the FFT sum over which the maximum brightness is used.
    min_brightness (int): The minimum brightness value to use.
    max_brightness (int): The maximum brightness value to use.
    strobe (int): The strobe value to use.

    Returns:
    int: The DMX value(s) to be sent to a given fixture. 
    """

    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    brightness = power_to_brightness(fft_mean, prange[0], prange[1], brange[0], brange[1])

    if color == 'random':
        color = random_color()
    color = colors[color]
    
    return [brightness, color[0], color[1], color[2], strobe, 0]

def fft_to_dimmer(fft_vec, frange, prange=[0.5,1.0], brange=[0,255]):
    """
    Converts an FFT vector to a dimmer value based on the sum of the FFT vector in a given range.

    Parameters:
    fft_vec (np.array): The FFT vector to convert to a DMX value.
    range (int): The range of the FFT vector to consider.
    lower_threshold (int): The lower threshold for the FFT sum under which the minimum brightness is used.
    upper_threshold (int): The upper threshold for the FFT sum over which the maximum brightness is used.
    min_brightness (int): The minimum brightness value to use.
    max_brightness (int): The maximum brightness value to use.

    Returns:
    int: The DMX value to be sent to a given dimmer. 
    """

    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    brightness = power_to_brightness(fft_mean, prange[0], prange[1], brange[0], brange[1])

    return brightness   

def fft_to_strobe(fft_vec, frange, lower_threshold=0.5):
    """
    Converts an FFT vector to a strobe value based on the sum of the FFT vector in a given range.
    For now, just returns the brightness value and whether to turn it on or off (255 or 0)

    Parameters:
    fft_vec (np.array): The FFT vector to convert to a DMX value.
    range (int): The range of the FFT vector to consider.
    lower_threshold (int): The lower threshold for the FFT sum under which the minimum brightness is used.
    upper_threshold (int): The upper threshold for the FFT sum over which the maximum brightness is used.
    min_brightness (int): The minimum brightness value to use.
    max_brightness (int): The maximum brightness value to use.

    Returns:
    int: The DMX value to be sent to a given dimmer. 
    """

    freq_low, freq_high = freq_to_index(frange[0]), freq_to_index(frange[1])
    fft_mean = np.mean(fft_vec[freq_low:freq_high])
    if fft_mean >= lower_threshold:
        return (255, 255)
    else:
        return (0, 0)

def bool_rgb(light):
    """
    Returns the DMX value for a static dimmer light
    """
    if 'colorfade' in light:
        color = [0, 0, 0]
        colorfade = light['colorfade']
    else:
        if light['color']=='random':
            color = colors[random_color()]
        else:
            color = colors[light['color']]
        colorfade = 0

    if 'strobe' in light:
        strobe = light['strobe']
        if strobe=='random':
            strobe = np.random.randint(0, 255)
    else:
        strobe = 0

    brightness = light['brightness']
    if light['brightness']=='random':
        brightness = np.random.randint(0, 255)
    
    return [brightness, color[0], color[1], color[2], strobe, colorfade]

def bool_strobe(light):
    """
    Returns the DMX value for a static strobe light
    """
    if light['speed'] == 'random':
        speed = np.random.randint(0, 255)

    if light['brightness'] == 'random':
        brightness = np.random.randint(0, 255)

    return [speed, brightness]

def time_dimmer(light):
    """
    Returns the DMX value for a time-based dimmer light based on the current time in seconds. 
    """
    amplitude = (light['max_brightness'] - light['min_brightness']) / 2
    midpoint = (light['max_brightness'] + light['min_brightness']) / 2
    if light['function'] == 'sine':
        return int(np.sin(time.time() * light['frequency']) * amplitude + midpoint)
    elif light['function'] == 'square':
        return int(np.sign(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
    elif light['function'] == 'triangle':
        return int(np.abs(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
    elif light['function'] == 'sawtooth_forward':
        return int((time.time() * light['frequency'] % 1) * amplitude + midpoint)
    elif light['function'] == 'sawtooth_backward':
        return int((1 - time.time() * light['frequency'] % 1) * amplitude + midpoint)

def time_rgb(light):
    """
    Returns the DMX value for a time-based RGB light based on the current time in seconds. 
    """
    min_brightness = light['min_brightness']
    max_brightness = light['max_brightness']
    range_brightness = max_brightness - min_brightness
    
    if light['function'] == 'sine':
        brightness = int(min_brightness + range_brightness * (np.sin(time.time() * light['frequency']*2*pi) * 0.5 + 0.5))
    elif light['function'] == 'square':
        brightness = int(min_brightness + range_brightness * (np.sign(np.sin(time.time() * light['frequency']*2*pi)) * 0.5 + 0.5))
    elif light['function'] == 'triangle':
        brightness = int(min_brightness + range_brightness * np.abs(((time.time() * light['frequency']) % 2) - 1))
    elif light['function'] == 'sawtooth_forward':
        brightness = int(min_brightness + range_brightness * ((time.time() * light['frequency']) % 1))
    elif light['function'] == 'sawtooth_backward':
        brightness = int(min_brightness + range_brightness * (1 - (time.time() * light['frequency'] % 1)))

    if light['color'] == 'random':
        color = colors[random_color()]
    else:
        color = colors[light['color']]

    strobe = light.get('strobe', 0)
    if strobe == 'random':
        strobe = np.random.randint(0, 255)

    return [brightness, color[0], color[1], color[2], strobe, 0]

def time_strobe(light):
    """
    Returns the DMX value for a time-based strobe light based on the current time in seconds. 
    """
    speed_range = light['speed_range'][1] - light['speed_range'][0]
    brightness_range = light['brightness_range'][1] - light['brightness_range'][0]
    if light['target'] == 'speed':
        amplitude = speed_range / 2
        midpoint = (light['speed_range'][1] + light['speed_range'][0]) / 2
        if light['function'] == 'sine':
            speed = int(np.sin(time.time() * light['frequency']) * amplitude + midpoint)
        elif light['function'] == 'square':
            speed = int(np.sign(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
        elif light['function'] == 'triangle':
            speed = int(np.abs(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
        elif light['function'] == 'sawtooth_forward':
            speed = int((time.time() * light['frequency'] % 1) * amplitude + midpoint)
        elif light['function'] == 'sawtooth_backward':
            speed = int((1 - time.time() * light['frequency'] % 1) * amplitude + midpoint)
        return [speed, light['brightness']]

    elif light['target'] == 'brightness':
        amplitude = brightness_range / 2
        midpoint = (light['brightness_range'][1] + light['brightness_range'][0]) / 2
        if light['function'] == 'sine':
            brightness = int(np.sin(time.time() * light['frequency']) * amplitude + midpoint)
        elif light['function'] == 'square':
            brightness = int(np.sign(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
        elif light['function'] == 'triangle':
            brightness = int(np.abs(np.sin(time.time() * light['frequency'])) * amplitude + midpoint)
        elif light['function'] == 'sawtooth_forward':
            brightness = int((time.time() * light['frequency'] % 1) * amplitude + midpoint)
        elif light['function'] == 'sawtooth_backward':
            brightness = int((1 - time.time() * light['frequency'] % 1) * amplitude + midpoint)
        return [light['speed'], brightness]

    elif light['target'] == 'both':
        speed_amplitude = speed_range / 2
        speed_midpoint = (light['speed_range'][1] + light['speed_range'][0]) / 2
        brightness_amplitude = brightness_range / 2
        brightness_midpoint = (light['brightness_range'][1] + light['brightness_range'][0]) / 2
        if light['function'] == 'sine':
            speed = int(np.sin(time.time() * light['frequency']) * speed_amplitude + speed_midpoint)
            brightness = int(np.sin(time.time() * light['frequency']) * brightness_amplitude + brightness_midpoint)
        elif light['function'] == 'square':
            speed = int(np.sign(np.sin(time.time() * light['frequency'])) * speed_amplitude + speed_midpoint)
            brightness = int(np.sign(np.sin(time.time() * light['frequency'])) * brightness_amplitude + brightness_midpoint)
        elif light['function'] == 'triangle':
            speed = int(np.abs(np.sin(time.time() * light['frequency'])) * speed_amplitude + speed_midpoint)
            brightness = int(np.abs(np.sin(time.time() * light['frequency'])) * brightness_amplitude + brightness_midpoint)
        elif light['function'] == 'sawtooth_forward':
            speed = int((time.time() * light['frequency'] % 1) * speed_amplitude + speed_midpoint)
            brightness = int((time.time() * light['frequency'] % 1) * brightness_amplitude + brightness_midpoint)
        elif light['function'] == 'sawtooth_backward':
            speed = int((1 - time.time() * light['frequency'] % 1) * speed_amplitude + speed_midpoint)
            brightness = int((1 - time.time() * light['frequency'] % 1) * brightness_amplitude + brightness_midpoint)
        return [speed, brightness]

if __name__ == '__main__':
    # Test the functions
    print('fft vec:')
    fft_vec = np.random.rand(BLOCKSIZE)
    print(fft_vec)
    print('fft to dimmer:')
    print(fft_to_dimmer(fft_vec, [0, 2000]))
    print('fft to rgb:')
    print(fft_to_rgb(fft_vec, [0, 2000]))
    print('fft to strobe:')
    print(fft_to_strobe(fft_vec, [0, 2000]))
    print('bool rgb:')
    print(bool_rgb({'brightness': 255, 'color': 'red', 'strobe': False}))
    print('bool strobe:')
    print(bool_strobe({'speed': 255, 'brightness': 255}))
    print('time dimmer:')
    print(time_dimmer({'min_brightness': 0, 'max_brightness': 255, 'frequency': 0.1, 'function': 'sine'}))
    print('time rgb:')
    print(time_rgb({'min_brightness': 0, 'max_brightness': 255, 'frequency': 0.1, 'function': 'sine', 'color': 'red', 'strobe': False}))
    print('time strobe:')
    print(time_strobe({'speed_range': [0, 255], 'brightness_range': [0, 255], 'frequency': 1, 'function': 'sine', 'target': 'both'}))


