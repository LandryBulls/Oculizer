# Oculizer 🎵 💡

Oculizer is an advanced DMX lighting automation system that creates real-time, music-reactive light shows by combining Spotify metadata with live audio analysis. It uses mel-scaled FFT to analyze audio and maps frequency components to DMX values through configurable scenes.

> ⚠️ **Note**: This project is currently in development and requires some technical setup to get working. Use at your own risk!

## Features

- Real-time audio reactivity using mel-scaled FFT analysis
- Spotify integration for metadata and playback control
- Configurable scene system with JSON-based mapping rules 
- Support for various DMX fixtures:
  - RGB lights
  - Dimmers
  - Strobes
  - Lasers
- Live scene switching through keyboard commands
- MIDI control support
- Audio visualization tools for debugging

## Prerequisites

- Python 3.8+
- USB to DMX adapter (compatible with OpenDMX)
- DMX-controlled lights
- BlackHole virtual audio driver (for macOS) or equivalent
- Spotify Premium account
- DMX control software (to determine your light addresses)

## Required Hardware Configuration

1. DMX lights connected and addressed properly
2. USB to DMX adapter connected and recognized
3. Audio routing to capture Spotify playback (e.g., BlackHole setup on macOS)
4. MIDI controller (optional)

## Installation 

```bash
# Clone the repository
git clone https://github.com/yourusername/oculizer.git
cd oculizer

# Install required packages
pip install -r requirements.txt
```

## Configuration Steps

1. **Spotify Setup**:
   - Create a Spotify Developer account
   - Create a new application
   - Set up proper redirect URIs
   - Create `spotify_credentials.txt` with the following format:
     ```
     client_id YOUR_CLIENT_ID
     client_secret YOUR_CLIENT_SECRET
     redirect_uri YOUR_REDIRECT_URI
     ```

2. **DMX Profile Configuration**:
   - Review `profiles/` directory for example profiles
   - Create/modify profiles to match your DMX setup
   - Update channel numbers and fixture types

3. **Scene Configuration**:
   - Review `scenes/` directory for example scenes
   - Create/modify scenes to match your desired effects
   - Test scenes individually before running full show

## Usage

Main script:
```bash
python oculize.py
```

Alternative interfaces:
```bash
# MIDI control interface
python run_midi.py

# Basic testing interface
python run_tester.py

# Development/debugging interface
python run_dev.py
```

### Key Commands

- `q`: Quit
- `r`: Reload scenes
- Scene-specific hotkeys (defined in scene JSON files)
- Space: Manual trigger (when in appropriate mode)

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

## Development Status

This project is actively being developed. Known areas needing attention:

- Error handling improvements
- Better documentation of scene configuration options
- More robust Spotify token refresh handling
- General code cleanup and optimization
- Additional visualization tools
- Better handling of audio routing setup
- More flexible light modulators in mapping.py
- More audio features 

## Contributing

Feel free to submit issues and pull requests. The project is in active development and welcomes contributions!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Spotipy](https://spotipy.readthedocs.io/) for Spotify API integration
- [PyDMXControl](https://github.com/MattIPv4/PyDMXControl) for DMX control
- Python audio processing libraries (librosa, sounddevice)

## Disclaimer

This project involves controlling lighting equipment and should be used with appropriate caution. Always follow proper safety guidelines when working with DMX equipment.