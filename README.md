# Oculizer 🎵 💡

Oculizer is an advanced DMX lighting automation system that creates real-time, music-reactive light shows using machine learning-based scene prediction and live audio analysis. It uses mel-scaled FFT to analyze audio and maps frequency components to DMX values through configurable scenes.

> ⚠️ **Note**: This project is currently in development and requires some technical setup to get working. Use at your own risk!

## Features

- **Real-time audio scene prediction** using EfficientAT neural network and k-means clustering
- Real-time audio reactivity using mel-scaled FFT analysis
- Automatic scene transitions based on audio characteristics
- Configurable scene system with JSON-based mapping rules 
- Support for various DMX fixtures:
  - RGB lights
  - Dimmers
  - Strobes
  - Lasers
- Configurable light-triggered effects
- Live scene switching through keyboard commands
- MIDI control support
- Audio visualization tools for debugging

## Prerequisites

- Python 3.8+
- USB to DMX adapter (compatible with OpenDMX)
- DMX-controlled lights
- Virtual audio cable (VB-Audio Virtual Cable for Windows, BlackHole for macOS)
- CUDA-capable GPU (recommended for better performance)
- DMX control software (to determine your light addresses)

## Required Hardware Configuration

1. DMX lights connected and addressed properly
2. USB to DMX adapter connected and recognized
3. Virtual audio cable to route system audio (e.g., VB-Audio Virtual Cable on Windows, BlackHole on macOS)
4. MIDI controller (optional)

## Installation 

```bash
# Clone the repository
git clone https://github.com/LandryBulls/Oculizer.git
cd oculizer

# Install required packages
pip install -r requirements.txt
```

## Configuration Steps

1. **Audio Setup**:
   - Install VB-Audio Virtual Cable (Windows) or BlackHole (macOS)
   - Route your music player output to the virtual cable
   - List available audio devices: `python oculize.py --list-devices`
   - Note the device index for the virtual cable input

2. **DMX Profile Configuration**:
   - Review `profiles/` directory for example profiles
   - Create/modify profiles to match your DMX setup
   - Update channel numbers and fixture types

3. **Scene Configuration**:
   - Review `scenes/` directory for example scenes
   - Create/modify scenes to match your desired effects
   - Test scenes individually before running full show

## Usage

### Dual-Stream Mode (Recommended)

For optimal performance, use dual-stream mode with:
- **Scarlett 2i2**: Delayed audio from Ableton for FFT-based DMX control
- **CABLE Output**: Real-time audio for responsive scene prediction

```bash
# Dual-stream setup (default)
python oculize.py --profile garage --input-device scarlett --prediction-device 1

# List devices to find correct indices
python oculize.py --list-devices
```

### Single-Stream Mode

Use the same audio source for both FFT and predictions:

```bash
# Single-stream mode
python oculize.py --profile garage --input-device scarlett --single-stream
```

### Command Line Options

- `-p, --profile`: Lighting profile to use (default: garage)
- `-i, --input-device`: Audio device for FFT/DMX (default: scarlett)
- `--prediction-device`: Device index for scene prediction (default: 1)
- `--single-stream`: Use single audio stream for both FFT and prediction
- `--list-devices`: List available audio devices and exit

### Key Commands (while running)

- `q`: Quit
- `r`: Reload scenes

### Dual-Stream Setup

See [DUAL_STREAM_ARCHITECTURE.md](DUAL_STREAM_ARCHITECTURE.md) for detailed information about the dual-stream audio system.

## Scene Configuration

Scenes are defined in JSON files with the following structure:
```json
{
    "name": "scene_name",
    "description": "Scene description",
    "type": "effect",
    "midi": 60, # MIDI note number (optional)
    "key_command": "1", # Keyboard command (optional)
    "lights": [
        {
            "name": "light_name",
            "type": "rgb",
            "modulator": "mfft",
            "mfft_range": [0, 20],
            "power_range": [0, 2],
            "brightness_range": [0, 255],
            "color": "red", 
            "strobe": 0
        }
    ]
}
```

## How It Works

Oculizer uses a machine learning pipeline to predict appropriate lighting scenes in real-time:

1. **Audio Capture**: Captures system audio via a virtual audio cable
2. **Feature Extraction**: Uses EfficientAT (a neural network trained on AudioSet) to extract audio embeddings
3. **Dimensionality Reduction**: Applies PCA to reduce feature dimensions
4. **Clustering**: Uses k-means clustering to classify audio into scene clusters
5. **Scene Mapping**: Maps clusters to predefined lighting scenes
6. **Light Control**: Updates DMX fixtures based on the current scene and audio features

## Development Status

This project is actively being developed. Known areas needing attention:

- Error handling improvements
- Better documentation of scene configuration options
- General code cleanup and optimization
- Additional visualization tools
- Better handling of audio routing setup
- More flexible light modulators in mapping.py
- More audio features 
- Scene prediction model refinement

## Contributing

Feel free to submit issues and pull requests. The project is in active development and welcomes contributions!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [EfficientAT](https://github.com/fschmid56/EfficientAT) for audio tagging model
- [PyDMXControl](https://github.com/MattIPv4/PyDMXControl) for DMX control
- Python audio processing libraries (librosa, sounddevice, soundfile)
- scikit-learn for machine learning components

## Disclaimer

This project involves controlling lighting equipment and should be used with appropriate caution. Always follow proper safety guidelines when working with DMX equipment.