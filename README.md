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

Oculizer provides two main scripts for controlling your light show:

### 1. `oculize.py` - Automatic Scene Prediction

The main script that uses machine learning to automatically predict and switch between scenes based on audio content.

#### Dual-Stream Mode (Recommended for Windows)

For optimal performance, use dual-stream mode with separate audio sources:
- **FFT Stream**: Delayed audio from your audio interface (e.g., Scarlett) for DMX modulation
- **Prediction Stream**: Real-time audio (e.g., CABLE Output/VB Cable) for scene prediction

```bash
# Dual-stream with predictor version 4 (default)
python oculize.py --profile garage2025 --input-device scarlett --prediction-device cable_output

# Using predictor v5 (latest)
python oculize.py --profile garage2025 --predictor-version v5

# List available audio devices
python oculize.py --list-devices
```

#### Single-Stream Mode (Default for macOS)

Use the same audio source for both FFT and predictions (better for simpler setups):

```bash
# Single-stream mode (recommended for macOS with BlackHole)
python oculize.py --profile garage2025 --input-device blackhole --single-stream
```

#### Dual-Channel Averaging

If you have a multi-input audio interface (e.g., Scarlett 18i20) and want to average channels 1 and 2 for FFT:

```bash
# Average first two input channels for FFT
python oculize.py --profile garage2025 --input-device scarlett --average-dual-channels

# Can combine with dual-stream for predictions
python oculize.py --profile garage2025 --input-device scarlett --average-dual-channels --prediction-device cable_output
```

#### Command Line Options

- `-p, --profile`: Lighting profile to use (default: `garage2025`)
- `-i, --input-device`: Audio device for FFT/DMX modulation. Can be device name (`scarlett`, `blackhole`, `cable_output`) or device index number (default: `scarlett` on Windows, `blackhole` on macOS)
- `--prediction-device`: Device for scene prediction in dual-stream mode. Can be device name or index (default: `cable_output`)
- `--single-stream`: Use single audio stream for both FFT and prediction (default on macOS)
- `--predictor-version`, `--predictor`: Scene predictor version (`v1`, `v3`, `v4`, `v5`) (default: `v4`)
- `--average-dual-channels`: Average first two input channels together for FFT (useful for Scarlett 18i20)
- `--list-devices`: List available audio devices and exit

#### Interactive Controls

While running `oculize.py`:
- **q**: Quit the application
- **r**: Reload all scenes from disk

#### Display Information

The interface shows:
- Current audio devices for FFT and prediction
- Active lighting profile
- Predictor version in use
- Current scene name
- Latest scene prediction
- Prediction cluster ID
- Real-time log messages

### 2. `toggle.py` - Manual Scene Control

An interactive grid-based scene browser for manual control and testing.

```bash
# Launch with default profile
python toggle.py --profile bbgv --input scarlett

# With dual-channel averaging
python toggle.py --profile garage2025 --input scarlett --average-dual-channels
```

#### Command Line Options

- `-p, --profile`: Lighting profile to use (default: `bbgv`)
- `-i, --input`: Audio device for FFT/DMX. Can be device name (`scarlett`, `blackhole`, `cable`) or device index (default: `scarlett` on Windows, `blackhole` on macOS)
- `--average-dual-channels`: Average first two input channels together for FFT

#### Interactive Controls

- **Arrow Keys**: Navigate between scenes in the grid
- **Enter**: Activate the selected scene
- **Mouse Click**: Click on a scene to select and activate it
- **Type to Search**: Start typing a scene name to jump to it (e.g., type "par" to jump to "party")
- **Backspace**: Delete last character in search
- **ESC**: Clear search
- **Ctrl+R**: Reload all scenes from disk
- **Ctrl+Q**: Quit the application

#### Display Features

- **Grid Layout**: Scenes displayed in a multi-column grid that adapts to terminal size
- **Color Coding**:
  - **Green**: Currently active scene
  - **Yellow**: Selected scene (keyboard navigation)
  - **Blue**: Hovered scene (mouse)
  - **White**: Inactive scenes
- **Live Search**: Type-to-find functionality with visual feedback
- **Alphabetical Sorting**: Scenes are automatically sorted alphabetically

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
2. **Feature Extraction**: Uses **[EfficientAT](https://github.com/fschmid56/EfficientAT)** - a state-of-the-art audio tagging neural network developed by Florian Schmid, Khaled Koutini, and Gerhard Widmer at Johannes Kepler University Linz. EfficientAT is trained on AudioSet and provides high-quality audio embeddings that capture semantic content of music.
3. **Dimensionality Reduction**: Applies PCA to reduce feature dimensions
4. **Clustering**: Uses k-means clustering to classify audio into scene clusters
5. **Scene Mapping**: Maps clusters to predefined lighting scenes
6. **Light Control**: Updates DMX fixtures based on the current scene and audio features

### Audio Scene Prediction

The scene prediction system leverages **EfficientAT** neural network embeddings combined with spectral audio features (MFCCs, spectral centroid, RMS energy, etc.) to understand both the semantic content and acoustic properties of music. This allows Oculizer to intelligently match musical moments to appropriate lighting scenes.

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

### EfficientAT - Audio Tagging Neural Network

This project relies heavily on **[EfficientAT](https://github.com/fschmid56/EfficientAT)**, a state-of-the-art audio tagging model developed by:
- **Florian Schmid** ([@fschmid56](https://github.com/fschmid56))
- **Khaled Koutini**
- **Gerhard Widmer**

From the LIT AI Lab and Institute of Computational Perception at Johannes Kepler University Linz, Austria.

**Citation:**
```
@inproceedings{Schmid2023efficient,
  title={Efficient Large-Scale Audio Tagging Via Transformer-To-CNN Knowledge Distillation},
  author={Schmid, Florian and Koutini, Khaled and Widmer, Gerhard},
  booktitle={IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  year={2023}
}
```

EfficientAT provides the foundational audio understanding capabilities that make Oculizer's intelligent scene prediction possible.

### Other Dependencies

- [PyDMXControl](https://github.com/MattIPv4/PyDMXControl) for DMX control
- [librosa](https://librosa.org/) for audio feature extraction
- [sounddevice](https://python-sounddevice.readthedocs.io/) for real-time audio capture
- [scikit-learn](https://scikit-learn.org/) for machine learning components (PCA, k-means clustering)

## Disclaimer

This project involves controlling lighting equipment and should be used with appropriate caution. Always follow proper safety guidelines when working with DMX equipment.