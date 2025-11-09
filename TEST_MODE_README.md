# Test Mode Feature

## Overview
Added a `--test` flag to `oculize.py` that enables scene prediction testing without requiring FFT processing or DMX hardware connection.

## What Test Mode Does

When you run `python oculize.py --test`, the following changes occur:

1. **Skips DMX Controller Initialization**: No need to have the DMX interface connected
2. **Skips FFT Audio Processing**: No FFT calculation or light reactivity
3. **Uses Virtual Cable for Predictions**: Automatically selects the appropriate virtual audio device:
   - **macOS**: BlackHole (channel 1)
   - **Windows**: Cable Output (all channels)
4. **Scene Predictions Only**: Runs scene prediction in real-time based on the virtual cable audio stream

## Usage

### Basic Test Mode
```bash
# macOS
python oculize.py --test

# Windows
python oculize.py --test
```

### Test Mode with Custom Profile
```bash
python oculize.py --test --profile mobile
```

### Test Mode with Custom Predictor Version
```bash
python oculize.py --test --predictor-version v4
```

### Test Mode with Custom Scene Cache Size
```bash
# Instant response (no smoothing)
python oculize.py --test --scene-cache-size 1

# Heavy smoothing
python oculize.py --test --scene-cache-size 25
```

## How It Works

### OS-Specific Defaults

**macOS**:
- Prediction Device: BlackHole
- Prediction Channels: Channel 1
- Scene Cache Size: 1 (instant response)

**Windows/Linux**:
- Prediction Device: Cable Output
- Prediction Channels: Auto-detect (all channels)
- Scene Cache Size: 25 (heavy smoothing)

### Technical Implementation

1. **oculize.py Changes**:
   - Added `--test` flag to argument parser
   - Added `test_mode` parameter to `AudioOculizerController` and `main()` function
   - Modified argument parsing to automatically configure virtual cable when `--test` is used
   - Updated display to show "TEST (prediction only, no FFT/DMX)" mode indicator
   - Modified `turn_off_all_lights()` to skip in test mode
   - Updated audio device display to only show prediction device in test mode

2. **oculizer/light/control.py Changes**:
   - Added `test_mode` parameter to `Oculizer.__init__()`
   - Skips `_get_audio_device_idx()` call in test mode (sets to `None`)
   - Skips DMX controller initialization in test mode
   - Modified `run()` method to:
     - Skip FFT audio stream setup in test mode
     - Only run prediction stream in test mode
     - Use simplified main loop that only handles predictions
   - Modified `process_audio_and_lights()` to return early in test mode
   - Modified `turn_off_all_lights()` to skip in test mode
   - Modified `stop()` to skip DMX controller cleanup in test mode

## Use Cases

1. **Testing Scene Predictions**: Verify that scene predictions are working correctly without needing the full lighting setup
2. **Development**: Develop and test scene prediction models without hardware
3. **Debugging**: Isolate scene prediction issues from FFT/DMX issues
4. **Remote Testing**: Test on a machine without DMX hardware

## Display Output

In test mode, the curses display shows:
- `Prediction: [device_name] [channels]` - The audio device used for predictions
- `Stream Mode: TEST (prediction only, no FFT/DMX)` - Indicates test mode is active
- All normal scene prediction information (current scene, predicted scene, cluster, etc.)

## Notes

- Test mode requires scene prediction to be enabled (it's enabled by default)
- The system will still load the profile and scene files normally
- No DMX commands are sent in test mode
- FFT processing is completely skipped to reduce CPU usage
