# Oculizer Diagnostic Scripts

## test_audio_levels.py

Audio level testing tool for diagnosing clipping and distortion issues.

### Usage

```bash
# Test all available input devices
python scripts/test_audio_levels.py

# Test a specific device by index
python scripts/test_audio_levels.py 2
```

### What It Tests

- Peak audio levels (max/min)
- RMS (average) levels
- Clipping detection (samples at ±1.0)
- Real-time level meters

### Output Example

```
=== Testing Device: BlackHole 2ch ===
Sample Rate: 48000Hz, Channels: 2, Duration: 10s

Monitoring audio levels...
RMS: 0.1234 | Peak: +0.8543 | ██████████████░░░░░░░░░░░░░░░░░░░░░░

=== Test Summary ===
Peak Max: +0.8543
Peak Min: -0.8234
Average RMS: 0.1156
Max RMS: 0.1834
Clipping: 0/480000 samples (0.00%)

=== Diagnosis ===
✓ Audio levels look good!
```

### When To Use

- Before running Oculizer for the first time on Mac
- When scene predictions are wrong
- After changing hardware setup
- To dial in the optimal `--prediction-gain` value

### macOS Physical Loopback

If you're using Scarlett 2i2 with TRS loopback:

1. Run this script with music playing
2. Watch for clipping warnings
3. Adjust Scarlett monitor output knob
4. Adjust `--prediction-gain` if needed
5. Re-test until clipping <0.1%

See [MAC_AUDIO_SETUP.md](../MAC_AUDIO_SETUP.md) for details.
