# Forced Fallback Feature

## Overview

The scene fallback system now supports **forced scene replacement** - any scene listed in `profile_fallbacks.json` will be automatically replaced with its fallback, regardless of whether the original scene is technically compatible with the profile.

## What Changed

### Before (Compatibility-Based Fallbacks)
```
IF scene is incompatible (uses no available fixtures)
  AND fallback exists in mapping
THEN apply fallback
```

### After (Forced Fallbacks)
```
IF fallback exists in mapping
THEN always apply fallback (regardless of compatibility)
```

## Why This Matters

This gives you **full control** over scene substitution via the JSON configuration file. You can now:

1. **Replace compatible scenes** - Even if a scene works on your profile, you can force it to use a different scene
2. **Override predictor choices** - Control which scenes actually play based on your preferences
3. **Profile-specific scene mappings** - Create custom scene experiences for different profiles

## Example Use Cases

### 1. Prefer Sequence Scenes
```json
"bass_hopper_blue": "sequence_cosmic"
```
Even though `bass_hopper_blue` has rockvilles (compatible), you prefer the sequence effect.

### 2. Replace Entire Scene Categories
```json
"bass_hopper": "sequence_ice",
"bass_hopper_blue": "sequence_cosmic",
"bass_hopper_green": "sequence_forest",
"bass_hopper_pink": "sequence_pink",
"bass_hopper_rainbow": "sequence_rainbow",
"bass_hopper_white": "sequence_cosmic"
```
Replace all bass hopper scenes with sequence variants.

### 3. Custom Scene Preferences
```json
"blue_bass_pulse": "sequence_blue"
```
You don't like the bass pulse effect, so replace it with a sequence.

## Logging Behavior

The system now logs different messages based on the reason for fallback:

### Forced Replacement (scene is compatible)
```
INFO - Scene 'blue_bass_pulse' replaced with 'sequence_blue' (forced by profile 'mobile' fallback mapping)
```

### Compatibility Replacement (scene is incompatible)
```
INFO - Scene 'bass_hopper_rainbow' incompatible with profile 'mobile', using fallback 'sequence_rainbow'
```

### No Fallback Warning (scene is incompatible, no fallback defined)
```
WARNING - Scene 'orb_cycle' incompatible with profile 'mobile' and no fallback found - using anyway
```

## How to Use

### 1. Add Any Scene to Fallback Mapping
Edit `profile_fallbacks.json`:
```json
{
  "mobile": {
    "any_scene_name": "replacement_scene_name",
    "blue_bass_pulse": "sequence_blue",
    "party": "disco"
  }
}
```

### 2. Restart Oculizer
```bash
python oculize.py --profile mobile
```

### 3. Monitor Logs
```bash
tail -f oculizer.log | grep "replaced\|fallback"
```

## Current Fallback Mappings (Mobile Profile)

Your current configuration replaces **28 scenes**:

| Original Scene | Replacement | Type |
|---------------|-------------|------|
| `bass_hopper` | `sequence_ice` | Forced |
| `bass_hopper_blue` | `sequence_cosmic` | Forced |
| `bass_hopper_green` | `sequence_forest` | Forced |
| `bass_hopper_orange` | `sequence_fire` | Forced |
| `bass_hopper_pink` | `sequence_pink` | Forced |
| `bass_hopper_rainbow` | `sequence_rainbow` | Forced |
| `bass_hopper_white` | `sequence_cosmic` | Forced |
| `blue_speedracer` | `sequence_blue` | Forced |
| `blue_bass_pulse` | `sequence_blue` | **Forced** (scene is compatible!) |
| `green_speedracer` | `sequence_green` | Forced |
| `pink_speedracer` | `sequence_pink` | Forced |
| `red_speedracer` | `sequence_red` | Forced |
| `vintage` | `chill_halogen` | Forced |
| ... and 15 more | | |

## Benefits

✅ **Full Control** - You decide which scenes play, not the predictor  
✅ **Profile Customization** - Different scene experiences per profile  
✅ **Easy to Adjust** - Just edit JSON, no code changes  
✅ **Transparent** - Logs show when replacements happen  
✅ **Backwards Compatible** - Scenes not in mapping work normally  

## Notes

- Fallbacks are only applied during **scene changes** (prediction or manual)
- You can disable fallbacks by passing `apply_fallback=False` to `set_scene()` (API only)
- The original scene files are never modified
- Fallback chains are not supported (no A→B→C, only A→B)

## Example Workflow

1. **Scene predictor selects:** `blue_bass_pulse`
2. **System checks:** Is `blue_bass_pulse` in fallback mapping?
3. **Result:** Yes! `blue_bass_pulse` → `sequence_blue`
4. **Action:** Apply `sequence_blue` instead
5. **Log:** "Scene 'blue_bass_pulse' replaced with 'sequence_blue' (forced by profile 'mobile' fallback mapping)"
6. **Lights:** Rockville sequence effect plays

Now you have complete control over your scene experience! 🎉

