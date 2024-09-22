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

# Helper function to convert color name to index
def color_to_index(color_name):
    return COLOR_NAMES.index(color_name) if color_name in COLOR_NAMES else -1

def scale_mfft(mfft_vec, scaling_factor=10.0, scaling_method='log'):
    """
    Scale the MFFT vector to boost higher frequencies.
    
    :param mfft_vec: The input MFFT vector
    :param scaling_factor: Controls the intensity of scaling (higher values = more intense scaling)
    :param scaling_method: The method of scaling ('log', 'exp', or 'linear')
    :return: Scaled MFFT vector
    """
    num_bins = len(mfft_vec)
    
    if scaling_method == 'log':
        # Logarithmic scaling
        scaling = np.log1p(np.arange(num_bins) / num_bins) * scaling_factor + 1

    elif scaling_method == 'exp':
        # Exponential scaling
        scaling = np.exp(np.arange(num_bins) / num_bins * scaling_factor)

    elif scaling_method == 'linear':
        # Linear scaling
        scaling = np.linspace(1, 1 + scaling_factor, num_bins)
    else:
        raise ValueError("Invalid scaling method. Choose 'log', 'exp', or 'linear'.")
    
    # Normalize the scaling factor
    scaling /= scaling.mean()
    
    # Apply scaling
    scaled_mfft = mfft_vec * scaling
    
    return scaled_mfft

def color_to_rgb(color_name):
    # returns the RGB value of the color
    return COLORS[COLOR_NAMES.index(color_name)]

def random_color():
    # choose a random color and returns its rgb value
    return color_to_rgb(COLOR_NAMES[np.random.randint(0, len(COLOR_NAMES))])

# def generate_RGB_signal(brightness=255, color_index=0, strobe=0, colorfade=0):
#     color = COLORS[color_index]
#     return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), int(colorfade)]

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
    mfft_low, mfft_high = int(mfft_range[0]), int(mfft_range[1])
    if mfft_low < 0 or mfft_high > len(mfft_vec):
        raise ValueError(f"MFFT range {mfft_range} is out of bounds for MFFT vector of length {len(mfft_vec)}")
    mfft_mean = np.max(mfft_vec[mfft_low:mfft_high])
    return power_to_brightness(mfft_mean, power_range[0], power_range[1], brightness_range[0], brightness_range[1])

def mfft_to_rgb(mfft_vec, mfft_range, power_range, brightness_range, color, strobe):
    try:
        brightness = mfft_to_brightness(mfft_vec, mfft_range, power_range, brightness_range)
        
        if color == 'random':
            color = color_to_rgb(random_color())
        else:
            color = color_to_rgb(color)
        
        return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), 0]

    except Exception as e:
        print(f"Error in mfft_to_rgb: {str(e)}")
        return [0, 0, 0, 0, 0, 0]  # Return a safe default value

def mfft_to_dimmer(mfft_vec, mfft_range, prange, brange):
    try:
        mfft_low, mfft_high = int(mfft_range[0]), int(mfft_range[1])
        if mfft_low < 0 or mfft_high > len(mfft_vec):
            raise ValueError(f"MFFT range {mfft_range} is out of bounds for MFFT vector of length {len(mfft_vec)}")
        mfft_mean = np.mean(mfft_vec[mfft_low:mfft_high])
        return int(power_to_brightness(mfft_mean, prange[0], prange[1], brange[0], brange[1]))

    except Exception as e:
        print(f"Error in mfft_to_dimmer: {str(e)}")
        return 0  # Return a safe default value

def mfft_to_strobe(mfft_vec, mfft_range, threshold):
    try:
        mfft_low, mfft_high = int(mfft_range[0]), int(mfft_range[1])
        if mfft_low < 0 or mfft_high > len(mfft_vec):
            raise ValueError(f"MFFT range {mfft_range} is out of bounds for MFFT vector of length {len(mfft_vec)}")
        mfft_mean = np.mean(mfft_vec[mfft_low:mfft_high])
        return [255, 255] if mfft_mean >= threshold else [0, 0]
    except Exception as e:
        print(f"Error in mfft_to_strobe: {str(e)}")
        return [0, 0]  # Return a safe default value

def bool_dimmer(brightness):
    brightness = np.random.randint(0, 256) if brightness == 'random' else brightness
    return [int(brightness)]

def bool_rgb(brightness, color, strobe, colorfade):
    # expects color to be DMX value
    brightness = np.random.randint(0, 256) if brightness == 'random' else brightness
    return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), int(colorfade)]

def bool_strobe(speed, brightness):
    speed = np.random.randint(0, 256) if speed == 'random' else speed
    brightness = np.random.randint(0, 256) if brightness == 'random' else brightness
    return [int(speed), int(brightness)]

def bool_laser():
    """
    Function to control the laser in bool mode.
    This simply activates the auto mode of the laser.
    
    Returns:
    list: DMX values for the 10 channels of the laser
    """
    return [
        128,  # Channel 1: Set to Auto program (086-170)
        255,  # Channel 2: Strobe On
        0,    # Channel 3-10: Not used in Auto mode
        0,
        0,
        0,
        0,
        0,
        0,
        0
    ]

def mfft_laserl(mfft_vec, power_range=[0.1, 0.5], speed_range=[0, 255]):
    """
    Function to control the laser based on MFFT data.
    It turns the laser on/off and modulates the speed of auto patterns based on MFFT power.
    
    Args:
    mfft_vec (np.array): MFFT vector
    power_range (list): [min_power, max_power] for mapping
    speed_range (list): [min_speed, max_speed] for mapping
    
    Returns:
    list: DMX values for the 10 channels of the laser
    """
    mfft_power = np.mean(mfft_vec)
    
    if mfft_power <= power_range[0]:
        speed = speed_range[0]
    elif mfft_power >= power_range[1]:
        speed = speed_range[1]
    else:
        # Map the power to speed
        power_ratio = (mfft_power - power_range[0]) / (power_range[1] - power_range[0])
        speed = int(speed_range[0] + power_ratio * (speed_range[1] - speed_range[0]))
    
    return [
        128,    # Channel 1: Set to Auto program (086-170)
        255,    # Channel 2: Strobe On
        0,      # Channel 3-9: Not used
        0,
        0,
        0,
        0,
        0,
        0,
        speed   # Channel 10: Scan Speed (0-255)
    ]

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
    try:
        return int(min_brightness + range_brightness * time_function(t, frequency, function))
    except Exception as e:
        print(f"Error in time_dimmer0: {str(e)}")
        print(f"t: {t}, min_brightness: {min_brightness}, max_brightness: {max_brightness}, frequency: {frequency}, function: {function}")

def time_rgb(t, min_brightness, max_brightness, frequency, function, color, strobe):
    brightness = time_dimmer(t, min_brightness, max_brightness, frequency, function)
    return [int(brightness), int(color[0]), int(color[1]), int(color[2]), int(strobe), 0]

def time_strobe(t, speed_range, brightness_range, frequency, function, target):
    if target == 0:  # speed
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        return [int(speed), int(brightness_range[1])]

    elif target == 1:  # brightness
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return [int(speed_range[1]), int(brightness)]

    else:  # default to both if target is invalid
        speed = time_function(t, frequency, function) * (speed_range[1] - speed_range[0]) + speed_range[0]
        brightness = time_function(t, frequency, function) * (brightness_range[1] - brightness_range[0]) + brightness_range[0]
        return [int(speed), int(brightness)]

# # Non-JIT functions that interface with the JIT functions
# def process_mfft_to_rgb(mfft_vec, light):
#     return mfft_to_rgb(mfft_vec, 
#                        light['mfft_range'], 
#                        light['power_range'], 
#                        light['brightness_range'], 
#                        light.get('color', 'random'), 
#                        light.get('strobe', 0))

def process_bool_dimmer(light): 
    return bool_dimmer(light['brightness'])

def process_bool_strobe(light):
    return bool_strobe(light['speed'], light['brightness'])

def process_bool_rgb(light):
    if 'colorfade' in light:
        colorfade = light['colorfade']
        color = [255,255,255]
        brightness = light['brightness']
        return bool_rgb(brightness, color, 0, colorfade)
    else:
        brightness = np.random.randint(0, 256) if light['brightness'] == 'random' else light['brightness']
        color = random_color() if light['color'] == 'random' else color_to_rgb(light['color'])
        strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
        return bool_rgb(brightness, color, strobe, 0)

def process_time_dimmer(light, t):
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    return time_dimmer(t, light['min_brightness'], light['max_brightness'], light['frequency'], function_index)

def process_time_rgb(light, t):
    color = random_color() if light['color'] == 'random' else color_to_rgb(light['color'])
    strobe = np.random.randint(0, 256) if light.get('strobe') == 'random' else light.get('strobe', 0)
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    return time_rgb(t, light['min_brightness'], light['max_brightness'], 
                    light['frequency'], function_index, color, strobe)

def process_time_strobe(light, t):
    function_index = ['sine', 'square', 'triangle', 'sawtooth_forward', 'sawtooth_backward'].index(light['function'])
    target_index = ['speed', 'brightness', 'both'].index(light['target'])
    return time_strobe(t, light['speed_range'], light['brightness_range'], 
                       light['frequency'], function_index, target_index)

# Main processing function
def process_light(light, mfft_vec, current_time):
    modulator = light['modulator']
    light_type = light['type']

    #print(f"Processing light: {light['name']}, modulator: {modulator}, type: {light_type}")
    #print(f"MFFT vector shape: {mfft_vec.shape}")

    if modulator == 'mfft':
        if light_type == 'dimmer':
            #print(f"MFFT range: {light['mfft_range']}")
            return [mfft_to_dimmer(mfft_vec, light['mfft_range'], light['power_range'], light['brightness_range'])]

        elif light_type == 'rgb':
            #print(f"MFFT range: {light['mfft_range']}")
            return mfft_to_rgb(mfft_vec, light['mfft_range'], light['power_range'], light['brightness_range'], light.get('color', 'random'), light.get('strobe', 0))

        elif light_type == 'strobe':
            #print(f"MFFT range: {light['mfft_range']}")
            return mfft_to_strobe(mfft_vec, light['mfft_range'], light['threshold'])

        elif light_type == 'laser':
            return mfft_laserl(mfft_vec, light['power_range'], light['speed_range'])

    elif modulator == 'bool':
        if light_type == 'dimmer':
            return process_bool_dimmer(light)

        elif light_type == 'rgb':
            return process_bool_rgb(light)

        elif light_type == 'strobe':
            return process_bool_strobe(light)

        elif light_type == 'laser':
            return bool_laser()
            
    elif modulator == 'time':
        if light_type == 'dimmer':
            try:
                return [time_dimmer(current_time, light['min_brightness'], light['max_brightness'], 
                                    light['frequency'], light['function'])]
            except Exception as e:
                print(f"Error in time_dimmer: {str(e)}")
                return [0]
                                
        elif light_type == 'rgb':
            return process_time_rgb(light, current_time)

        elif light_type == 'strobe':
            return process_time_strobe(light, current_time)

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



