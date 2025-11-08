# Scene Fallback System - Quick Summary

## What Was Done

✅ **Created scene analysis tools**
- `analyze_scenes.py` - Identifies which scenes use which fixtures
- `generate_fallbacks.py` - Generates intelligent fallback mappings

✅ **Generated fallback mappings**
- `profile_fallbacks.json` - 27 fallback mappings for mobile profile
- Intelligent matching based on colors, vibes, and patterns

✅ **Enhanced SceneManager**
- Profile awareness (knows which fixtures are available)
- Automatic compatibility detection
- Automatic fallback application

✅ **Updated oculize.py**
- Loads profile fixtures at startup
- Passes profile info to SceneManager
- Displays fallback warnings in UI

✅ **Created documentation**
- `SCENE_FALLBACKS.md` - Comprehensive guide
- `test_fallbacks_simple.py` - Validation tool

## Key Files

```
profile_fallbacks.json      - Fallback mappings (you can edit these!)
analyze_scenes.py           - Run to see scene analysis
generate_fallbacks.py       - Run to regenerate mappings
oculizer/scenes/scene_manager.py - Core fallback logic
oculize.py                  - Integrated with profile loading
```

## How to Use

### With Mobile Profile

```bash
python oculize.py --profile mobile
```

The system automatically:
- Detects 27 incompatible scenes (scenes without rockvilles)
- Applies intelligent fallbacks based on similarity
- Logs fallback applications
- Shows warnings in UI

### Customizing Fallbacks

Edit `profile_fallbacks.json` to adjust mappings:

```json
{
  "mobile": {
    "bass_hopper_rainbow": "supernova",  // Change this to any scene
    "off": "sequence_ice"                // For example
  }
}
```

Save and restart Oculizer - changes apply immediately.

## Example Fallbacks

The system created intelligent mappings:

| Incompatible Scene | Fallback Scene | Reason |
|-------------------|----------------|--------|
| `bass_hopper_blue` | `blue_bass_pulse` | Matched: blue color + bass vibe |
| `bass_hopper_rainbow` | `supernova` | Matched: rainbow colors + hopper pattern |
| `blue_speedracer` | `bass_racer` | Matched: blue + racer + fast |
| `disco` | `discodream` | Matched: party vibe |
| `orb_racer` | `bass_racer` | Matched: racer + fast pattern |

## What Happens

### Scenario 1: Compatible Scene (has rockvilles)
```
Predictor selects: "disco"
→ Scene uses: RGBs + Rockvilles + Pinspot
→ Mobile profile has: Rockvilles ✓
→ Scene is COMPATIBLE
→ Apply "disco" directly
```

### Scenario 2: Incompatible Scene (no rockvilles)
```
Predictor selects: "bass_hopper_rainbow"
→ Scene uses: RGBs only
→ Mobile profile has: Rockvilles only
→ Scene is INCOMPATIBLE
→ Lookup fallback: "bass_hopper_rainbow" → "supernova"
→ Apply "supernova" instead
→ Log: "Scene 'bass_hopper_rainbow' incompatible with profile 'mobile', using fallback 'supernova'"
```

## Monitoring

### In the UI
Look for the warning indicator:
```
Current scene: supernova
  ⚠️  Incompatible scene (using fallback)
```

### In the Logs
```bash
tail -f oculizer.log | grep "incompatible"
```

You'll see:
```
Scene 'bass_hopper_rainbow' incompatible with profile 'mobile', using fallback 'supernova'
```

## Testing

Run the validation tool:
```bash
python test_fallbacks_simple.py
```

Output shows:
- Profile fixture counts
- Fallback mapping validation
- Scene fixture detection

## Statistics

**Mobile Profile:**
- Total scenes: 96
- Rockvilles-only scenes: 9 (fully compatible)
- Mixed scenes (RGBs + Rockvilles): 60 (compatible)
- No-Rockville scenes: 27 (⚠️ need fallbacks)

**Fallback Coverage:**
- All 27 incompatible scenes have fallbacks ✓
- Mappings based on color, vibe, and pattern similarity ✓
- User can customize any mapping ✓

## Next Steps

1. **Test with your mobile setup** - Run oculize.py with `--profile mobile`
2. **Watch the logs** - See which fallbacks are being used
3. **Adjust if needed** - Edit `profile_fallbacks.json` for any scenes you want to change
4. **Regenerate if needed** - Run `generate_fallbacks.py` if you add new scenes

## Notes

- Fallbacks apply only during scene prediction/changes
- You can still manually select any scene (it just might be dark)
- The system is backwards compatible (garage2025 doesn't use fallbacks)
- All original scenes are preserved (fallbacks are non-destructive)

## Recommended Tweaks

You might want to adjust these fallbacks manually:

1. **"off" → "chill_white"** - Maybe change to a very dim scene or leave as is
2. **"lamp" → "sequence_ice"** - Check if this matches your expectations
3. **"vintage" → "sequence_ice"** - Consider if another scene fits better

Edit `profile_fallbacks.json` to change these!

