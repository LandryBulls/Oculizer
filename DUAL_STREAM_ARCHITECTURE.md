# Dual-Stream Audio Architecture

## Overview

This document describes the dual-stream audio architecture implemented in Oculizer for optimal performance with delayed audio processing (e.g., through Ableton).

## Architecture

### Dual-Stream Mode (Default)

**Stream 1: FFT/DMX Modulation Stream**
- **Device**: Scarlett 2i2 USB Audio Interface (inputs 1 & 2)
- **Purpose**: Moment-by-moment DMX control based on audio features
- **Audio Source**: Delayed audio from Ableton (loopback from monitor output)
- **Processing**: 
  - Captures stereo audio (channels 1 & 2)
  - Averages both channels to create mono signal
  - Performs mel-spectrogram FFT analysis
  - Maps frequency bands to DMX channel values in real-time
  - Updates lights continuously based on audio features

**Stream 2: Scene Prediction Stream**
- **Device**: VB-Audio CABLE Output (or similar virtual audio device)
- **Purpose**: ML-based scene classification for automatic scene transitions  
- **Audio Source**: Real-time, non-delayed audio from system
- **Processing**:
  - Captures real-time audio (before Ableton delay)
  - Maintains 4-second rolling audio buffer
  - Runs EfficientAT neural network for feature extraction
  - Performs k-means clustering to classify audio
  - Maps clusters to scene names
  - Uses mode of recent predictions for stability

### Single-Stream Mode (Optional)

**Single Stream for Both**
- **Device**: User-specified (e.g., Scarlett or CABLE)
- **Purpose**: Both FFT modulation and scene prediction
- **Audio Source**: Same audio for both purposes
- **Processing**:
  - FFT processing as in dual-stream mode
  - Scene prediction also uses the same audio
  - Simpler setup but all audio has same delay characteristics

## Benefits of Dual-Stream

1. **Optimal Timing**: Scene predictions use non-delayed audio for responsive transitions
2. **Synchronized Effects**: FFT-based modulation uses Ableton-processed audio, allowing for:
   - Time-aligned effects processing
   - Audio manipulation (EQ, compression, etc.)
   - Delay compensation for visual alignment
3. **Independent Control**: Each stream can be optimized for its specific purpose
4. **Flexibility**: Can route different audio sources based on needs

## Signal Flow

### Your Setup (Dual-Stream)

```
Music Source (Spotify, etc.)
    ↓
VB-Audio CABLE Input ← System audio routed here
    ↓
    ├─→ CABLE Output → [Scene Prediction Stream] → Cluster → Scene Name
    │                       (real-time, no delay)
    └─→ Ableton Live (Audio Input)
            ↓ (processing/delay)
        Monitor Output (3.5mm jack)
            ↓ (hardware loopback)
        Scarlett 2i2 Inputs 1&2 → [FFT Stream] → DMX Values → Lights
                                    (delayed, processed)
```

### Single-Stream Alternative

```
Music Source
    ↓
Audio Device (Scarlett or CABLE)
    ↓
    ├─→ [FFT Stream] → DMX → Lights
    └─→ [Scene Prediction] → Scene Name
        (both use same audio with same characteristics)
```

## Implementation Details

### Modified Files

**`oculizer/light/control.py`:**
- Added scene prediction to `Oculizer` class
- New parameters:
  - `scene_prediction_enabled`: Enable/disable scene prediction
  - `scene_prediction_device`: Device index for prediction stream (optional)
- New methods:
  - `_init_scene_prediction()`: Initialize predictor and caches
  - `prediction_audio_callback()`: Callback for prediction stream
  - `update_scene_prediction()`: Process predictions from cached audio
- Modified `audio_callback()`: Average channels 1 & 2 for Scarlett stereo
- Modified `run()`: Start dual streams if configured
- New properties:
  - `current_predicted_scene`: Latest scene prediction
  - `current_cluster`: Latest cluster number
  - `prediction_count`: Number of predictions made

**`oculize.py`:**
- Removed standalone `RealTimeScenePredictor`
- Updated `AudioOculizerController` to use integrated prediction
- New parameters:
  - `input_device`: Device name for FFT stream (e.g., 'scarlett')
  - `dual_stream`: Enable dual-stream mode (default: True)
  - `prediction_device`: Device index for prediction (required for dual-stream)
- Updated display to show both devices when in dual-stream mode
- Reads predictions from `oculizer.current_predicted_scene`

### Command-Line Usage

```bash
# Dual-stream mode (default)
# FFT from Scarlett, predictions from CABLE Output (device 1)
python oculize.py --profile garage --input-device scarlett --prediction-device 1

# Single-stream mode
# Both FFT and predictions from same device
python oculize.py --profile garage --input-device scarlett --single-stream

# List available audio devices
python oculize.py --list-devices
```

### Configuration Parameters

**Dual-Stream (Default):**
- `--input-device scarlett`: Scarlett for FFT
- `--prediction-device 1`: CABLE Output for predictions
- Scene prediction runs on separate stream

**Single-Stream:**
- `--input-device scarlett` (or other device)
- `--single-stream`: Reuse FFT stream for predictions
- Both use same audio

## Performance Characteristics

### Dual-Stream
- **CPU Load**: Moderate (two audio callbacks + FFT + ML inference)
- **Latency**: 
  - Scene predictions: ~100ms (real-time audio + prediction time)
  - DMX control: Follows Ableton delay
- **Accuracy**: Optimal (each stream optimized for its purpose)
- **Scene Transition Responsiveness**: Excellent (real-time audio)
- **Visual Sync**: Excellent (Ableton-processed audio)

### Single-Stream
- **CPU Load**: Lower (one audio callback + FFT + ML inference)
- **Latency**: Same for both scene and DMX
- **Accuracy**: Good (but predictions and DMX have same delay)
- **Scene Transition Responsiveness**: Depends on audio delay
- **Visual Sync**: Good (but scene changes may lag)

## Audio Device Configuration

### Finding Device Indices

```bash
python oculize.py --list-devices
```

Example output:
```
=== Input Devices ===
0: Built-in Microphone (2 channels)
1: CABLE Output (VB-Audio Virtual Cable) (2 channels)
2: Scarlett 2i2 USB (2 channels)
```

### Typical Configuration

- **Scarlett**: Usually auto-detected by name 'Scarlett'
- **CABLE Output**: Find index with `--list-devices`, typically device 1
- **BlackHole** (macOS): Similar to CABLE Output

## Troubleshooting

### Scene predictions not working
- Check `--prediction-device` index with `--list-devices`
- Verify audio is routed to CABLE Input (system output)
- Check logs for prediction errors

### FFT/lights not responding to audio
- Verify Scarlett loopback is connected (monitor output → inputs 1&2)
- Check Ableton is outputting to Scarlett
- Ensure `--input-device scarlett` is set

### High CPU usage
- Try `--single-stream` mode if dual-stream is too intensive
- Check if GPU is being used for neural network inference
- Reduce scene prediction frequency if needed (requires code change)

### Audio device not found
- Run `--list-devices` to see available devices
- Check device is connected and recognized by OS
- Verify device name matches expected pattern ('Scarlett', 'CABLE', etc.)

## Future Enhancements

Possible improvements to the dual-stream system:

1. **Configurable sample rates**: Allow different rates for each stream
2. **Dynamic stream switching**: Toggle between dual/single at runtime
3. **Latency compensation**: Automatic delay detection and compensation
4. **Stream monitoring**: Display audio levels for each stream in UI
5. **Scene prediction tuning**: Adjustable prediction interval and cache size
6. **Multi-device support**: More than two audio streams for complex setups
7. **Scene override**: Manual scene control that overrides predictions

## Credits

This architecture was designed to leverage:
- **EfficientAT** neural network for audio feature extraction
- **scikit-learn** for clustering and scene classification  
- **librosa** for audio processing and resampling
- **sounddevice** for low-latency audio capture
- **Ableton Live** for audio effects and delay

