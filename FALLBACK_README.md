# Scene Fallback System - Quick Start

## What Was Delivered

✅ **Automatic scene fallbacks for mobile profile** - 27 incompatible scenes now map to compatible alternatives  
✅ **Intelligent matching** - Fallbacks chosen by color, vibe, and pattern similarity  
✅ **Easy customization** - Edit `profile_fallbacks.json` to change any mapping  
✅ **Full integration** - Works automatically with scene prediction  
✅ **Backwards compatible** - garage2025 profile unaffected  

## Usage

### Run with Mobile Profile
```bash
python oculize.py --profile mobile
```

The system automatically:
1. Detects 27 scenes without rockvilles
2. Applies intelligent fallbacks
3. Keeps lights active (no dark periods)
4. Logs fallback applications

### Customize Fallbacks

Edit `profile_fallbacks.json`:
```json
{
  "mobile": {
    "bass_hopper_rainbow": "supernova",  // ← Change to any scene you prefer
    "off": "sequence_ice"
  }
}
```

Save and restart - done!

## Key Files

| File | Purpose |
|------|---------|
| `profile_fallbacks.json` | Fallback mappings (edit me!) |
| `analyze_scenes.py` | Run to see scene analysis |
| `generate_fallbacks.py` | Run to regenerate all mappings |
| `test_fallbacks_simple.py` | Run to validate system |
| `SCENE_FALLBACKS.md` | Full technical docs |

## Example Fallbacks

| Predicted Scene | Fallback Scene | Why |
|----------------|----------------|-----|
| `bass_hopper_blue` | `blue_bass_pulse` | Blue + bass |
| `bass_hopper_rainbow` | `supernova` | Rainbow + hopper |
| `blue_speedracer` | `bass_racer` | Blue + racer |
| `laser_strobe` | `pink_strobe_pulse` | Strobe effect |

## Monitoring

### In the UI
```
Current scene: supernova
  ⚠️  Incompatible scene (using fallback)
```

### In the Logs
```bash
tail -f oculizer.log | grep incompatible
```

## Need Help?

- **Full docs:** See `SCENE_FALLBACKS.md`
- **Summary:** See `FALLBACK_SUMMARY.md`  
- **Implementation details:** See `IMPLEMENTATION_SUMMARY.md`

## What's Next?

1. Test with your mobile setup
2. Watch the logs to see which fallbacks are used
3. Edit `profile_fallbacks.json` to adjust any scenes
4. Enjoy seamless scene prediction across profiles! 🎉

