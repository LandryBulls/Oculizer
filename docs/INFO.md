# Oculizer Light Control Documentation

## Modulators

Modulators are the base control systems that determine how lights respond to input (audio, time, or boolean states). Here are the available modulators:

### 1. MFFT Modulator 
Processes audio frequency data to control light behavior.
*mfft stands for mel-scaled fast fourier transform*


**Common Parameters:**
- `mfft_range`: Tuple (start, end) defining which frequency bins to analyze
- `power_range`: Tuple (min, max) for power scaling
- `brightness_range`: Tuple (min, max) for output brightness
- `threshold`: Float value for triggering effects (default: 0.5)

### 2. Boolean Modulator
Generates random patterns based on probability and configuration.

**Common Parameters:**
- `min_brightness`: Minimum brightness value (default: 0)
- `max_brightness`: Maximum brightness value (default: 255)
- `brightness`: Either a fixed value or "random"
- `strobe`: Either a fixed value or "random"

### 3. Time Modulator
Creates time-based patterns using various waveforms.

**Common Parameters:**
- `frequency`: Oscillation frequency (default: 1)
- `function`: Wave type ("sine", "square", "triangle", "sawtooth_forward", "sawtooth_backward")
- `min_brightness`: Minimum brightness value
- `max_brightness`: Maximum brightness value

## Effects

### 1. Rockville Panel Fade (`rockville_panel_fade`)
Fades panel colors in and out based on audio triggers.

**Parameters:**
- `colors`: List of color names or palette name
- `coverage`: Float (0-1) determining percentage of panels active
- `color_order`: "next" or "random"
- `combo_mode`: "mix" or "pure"
- `wait`: Boolean to wait for fade completion
- `fade_duration`: Duration of fade in seconds
- `panel_threshold`: Audio threshold for triggering
- `panel_strobe`: Strobe speed (0-255)
- `mode_speed`: Speed of mode changes
- `affect_bar`: Boolean to include bar section
- `bar_sustain`: Duration for bar section to stay active
- `bar_threshold`: Audio threshold for bar
- `bar_mode`: Bar pattern mode (0 or "random")
- `bar_colors`: List of possible bar brightness values

### 2. Rockville Sequential Panels (`rockville_sequential_panels`)
Activates pairs of panels in sequence.

**Parameters:**
- `colors`: List of color names or palette name
- `color_order`: "next" or "random"
- `combo_mode`: "mix" or "pure"
- `direction`: "left_to_right", "right_to_left", or "alternating"
- `sequence_duration`: Duration of full sequence
- `threshold`: Audio threshold for triggering
- `wait`: Boolean to wait for sequence completion
- `affect_bar`: Boolean to include bar section
- `bar_sustain`: Duration for bar section
- `bar_threshold`: Audio threshold for bar
- `bar_mode`: Bar pattern mode

### 3. Rockville Splatter (`rockville_splatter`)
Creates random color patterns across panels.

**Parameters:**
- `panel_colors`: List of color names
- `panel_threshold`: Audio threshold for panel
- `affect_panel`: Boolean to include panel section
- `affect_bar`: Boolean to include bar section
- `bar_sustain`: Duration for bar section
- `bar_threshold`: Audio threshold for bar
- `bar_mode`: Bar pattern mode
- `bar_colors`: List of possible bar brightness values

### 4. Rockville Panel Sustain (`rockville_panel_sustain`)
Similar to panel fade but maintains full brightness for a duration.

**Parameters:**
- `colors`: List of color names or palette name
- `coverage`: Float (0-1) determining percentage of panels active
- `color_order`: "next" or "random"
- `combo_mode`: "mix" or "pure"
- `wait`: Boolean to wait for sustain completion
- `sustain_duration`: Duration to maintain full brightness
- `panel_threshold`: Audio threshold for triggering
- `panel_strobe`: Strobe speed (0-255)
- `mode_speed`: Speed of mode changes
- `affect_bar`: Boolean to include bar section
- `bar_sustain`: Duration for bar section
- `bar_threshold`: Audio threshold for bar
- `bar_mode`: Bar pattern mode
- `bar_colors`: List of possible bar brightness values

## Available Colors and Palettes

### Individual Colors
- red
- green
- blue
- yellow
- purple
- orange
- pink
- white
- black
- magenta
- cyan
- lime
- teal
- maroon
- navy
- olive
- gray
- silver
- gold
- coral
- salmon
- peach

### Color Palettes
- `rainbow`: red, orange, yellow, green, blue, purple, pink, white
- `RGB`: red, green, blue
- `trip`: green, purple
- `electric`: white, teal
- `pastel`: pink, yellow, blue, green
- `neon`: yellow, blue, green, pink
- `pastel_neon`: pink, yellow, blue, green, white
- `neon_pastel`: yellow, blue, green, pink, white
- `pastel_neon_electric`: pink, yellow, blue, green, white, teal

## Light Types

The system supports several types of lights, each with different channel configurations:

1. `dimmer`: Single channel brightness control
2. `rgb`: RGB color control with strobe
3. `strobe`: Dedicated strobe light control
4. `laser`: 10-channel laser control
5. `rockville864`: 39-channel LED panel with bar section

Each light type has specific channel mappings and supported features depending on the modulator and effect being used.
