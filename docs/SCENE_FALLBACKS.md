# Scene Fallback System

## Overview

The Oculizer now supports **profile-aware scene fallbacks**, allowing you to use the same scene prediction system across different hardware profiles. When a predicted scene uses fixtures that aren't available in your current profile (e.g., using the `mobile` profile with only 4 Rockvilles), the system automatically falls back to a compatible scene with similar characteristics.

## Problem Statement

The `garage2025` profile contains all possible fixtures (8 RGBs, 4 Rockvilles, lasers, orbs, strobe, pinspot, etc.), while the `mobile` profile only contains 4 Rockvilles. There are 27 scenes that don't use Rockvilles at all, which would result in everything going dark when using the mobile setup.

## Solution

A three-part system:

1. **Scene Analysis** - Identifies which fixtures each scene uses
2. **Fallback Mapping** - Maps incompatible scenes to compatible alternatives with similar characteristics
3. **Runtime Detection** - Automatically applies fallbacks during scene prediction

## File Structure

```
Oculizer/
├── profile_fallbacks.json          # Fallback mappings for each profile
├── analyze_scenes.py                # Tool to analyze scene fixture usage
├── generate_fallbacks.py            # Tool to generate fallback mappings
├── oculizer/scenes/scene_manager.py # Enhanced with fallback support
└── oculize.py                       # Updated to pass profile info
```

## How It Works

### 1. Profile Loading

When Oculizer starts, it:
- Loads the profile JSON to extract available fixture names
- Passes this information to SceneManager
- SceneManager loads `profile_fallbacks.json` for the current profile

### 2. Scene Compatibility Analysis

SceneManager analyzes each scene to determine if it's compatible with the current profile:
- A scene is **compatible** if it uses at least one fixture from the available fixtures
- A scene is **incompatible** if it uses NO fixtures from the profile

### 3. Automatic Fallback Application

When a scene is requested (e.g., from scene prediction):
```python
scene_manager.set_scene('bass_hopper_rainbow')
```

If `bass_hopper_rainbow` is incompatible:
1. Lookup fallback in `profile_fallbacks.json`
2. Find `bass_hopper_rainbow` → `supernova`
3. Apply `supernova` instead
4. Log the fallback for monitoring

## Fallback Mapping Logic

The `generate_fallbacks.py` script creates intelligent mappings based on:

### Color Matching (40 points)
- Scenes with similar color palettes are matched
- Example: `bass_hopper_blue` → `blue_bass_pulse` (both blue)

### Vibe Matching (15 points per vibe)
- Bass-heavy scenes map to bass scenes
- Strobe scenes map to strobe scenes
- Fast/hopper scenes map to similar dynamics

### Characteristic Matching (8-10 points)
- `has_bass` scenes map to other bass-reactive scenes
- `has_strobe` scenes prefer strobe effects
- `is_fast` scenes prefer fast transitions

### Special Pattern Matching (20-25 points)
- Color-specific scenes (red, blue, green, etc.) strongly prefer same color
- Pattern types (hopper, racer, pulse) prefer similar patterns

## Current Fallback Mappings (Mobile Profile)

Total: 27 fallbacks for scenes that don't use Rockvilles

### Color-Matched Examples
```
bass_hopper_blue       → blue_bass_pulse      (blue + bass)
bass_hopper_green      → green_bass_pulse     (green + bass)
bass_hopper_pink       → pink_bass_pulse      (pink + bass)
bass_hopper_white      → white_bass_pulse     (white + bass)
```

### Pattern-Matched Examples
```
bass_hopper_rainbow    → supernova            (hopper + rainbow colors)
blue_speedracer        → bass_racer           (blue + racer + fast)
orb_racer             → bass_racer           (racer + fast)
```

### Vibe-Matched Examples
```
bulb_flicker          → flicker              (strobe vibe)
discobrain            → discodream           (party vibe)
laser_strobe          → pink_strobe_pulse    (strobe vibe)
```

See `profile_fallbacks.json` for the complete mapping.

## Usage

### Running Oculizer with Mobile Profile

```bash
python oculize.py --profile mobile
```

The system will:
1. Load the mobile profile (4 rockvilles only)
2. Detect 27 incompatible scenes
3. Log: "Profile 'mobile' has 27 incompatible scenes (fallbacks will be used)"
4. Automatically apply fallbacks during scene prediction

### Monitoring Fallbacks

Watch the log file for fallback applications:
```bash
tail -f oculizer.log
```

You'll see entries like:
```
Scene 'bass_hopper_rainbow' incompatible with profile 'mobile', using fallback 'supernova'
```

### Display Indicators

The curses UI shows when a fallback is active:
```
Current scene: supernova
  ⚠️  Incompatible scene (using fallback)
```

## Tools

### Analyze Scene Fixture Usage

```bash
python analyze_scenes.py
```

Output:
- Lists all scenes without Rockvilles
- Lists all scenes with only Rockvilles  
- Shows fixture breakdown for each scene
- Saves detailed analysis to `scene_analysis.json`

### Regenerate Fallback Mappings

```bash
python generate_fallbacks.py
```

This will:
1. Analyze all scenes for characteristics (colors, vibes, patterns)
2. Calculate similarity scores between incompatible and compatible scenes
3. Generate new `profile_fallbacks.json` with best matches
4. Show the matching reasoning for each fallback

### Simple Validation Test

```bash
python test_fallbacks_simple.py
```

Validates:
- `profile_fallbacks.json` structure
- Profile fixture extraction
- Scene fixture detection logic

## Customizing Fallbacks

You can manually edit `profile_fallbacks.json` to adjust fallback mappings:

```json
{
  "mobile": {
    "bass_hopper_rainbow": "supernova",
    "bass_hopper_blue": "blue_bass_pulse",
    ...
  }
}
```

After editing:
1. The changes take effect immediately on next Oculizer restart
2. No need to regenerate - manual edits are preserved
3. Run `python test_fallbacks_simple.py` to validate JSON syntax

## Adding New Profiles

To add fallback support for a new profile:

1. Create the profile JSON in `profiles/` directory
2. Run analysis:
   ```bash
   python analyze_scenes.py
   ```
3. Manually add fallbacks to `profile_fallbacks.json`:
   ```json
   {
     "mobile": { ... },
     "my_new_profile": {
       "incompatible_scene1": "fallback_scene1",
       "incompatible_scene2": "fallback_scene2"
     }
   }
   ```
4. Or modify `generate_fallbacks.py` to generate mappings for your profile

## Technical Details

### SceneManager Changes

**New Parameters:**
```python
SceneManager(scenes_directory, 
             profile_name='mobile',
             available_fixtures={'rockville1', 'rockville2', ...})
```

**New Methods:**
- `_load_fallback_mappings()` - Load profile-specific fallbacks
- `_get_scene_fixtures(scene_data)` - Extract fixtures from scene
- `_is_scene_compatible(scene_data)` - Check profile compatibility
- `_analyze_scene_compatibility()` - Analyze all scenes
- `get_fallback_scene(scene_name)` - Get fallback for a scene
- `set_scene(scene_name, apply_fallback=True)` - Apply scene with fallback

**New Attributes:**
- `profile_name` - Current profile name
- `available_fixtures` - Set of available fixture names
- `fallback_mappings` - Dict of scene → fallback mappings
- `scene_compatibility` - Dict of scene → bool compatibility

### Backwards Compatibility

The system is fully backwards compatible:
- If no profile info provided, all scenes are considered compatible
- If no fallback mappings exist, incompatible scenes are used anyway (with warning)
- Existing code without profile awareness continues to work

## Performance

- Fallback lookup: O(1) dictionary lookup
- Compatibility check: O(n) where n = fixtures in scene (typically < 20)
- Analysis runs once at startup
- No performance impact during scene changes or prediction

## Logging

The system logs at various levels:

**INFO:** Scene fallback applications, compatibility summaries
**DEBUG:** Detailed compatibility analysis, fixture detection
**WARNING:** Missing fallbacks, profile loading issues

## Future Enhancements

Possible improvements:
1. **Dynamic fallback generation** - Generate fallbacks at runtime based on available scenes
2. **Multiple fallback chains** - Try fallback1, if incompatible try fallback2, etc.
3. **Partial compatibility** - Score scenes by % of fixtures available
4. **User preferences** - Allow users to customize fallback priorities
5. **Web UI** - Visual fallback editor and scene compatibility viewer

## Troubleshooting

### Scene goes dark even with fallback

Check the log file:
```bash
grep "incompatible" oculizer.log
```

If you see "no fallback found", add an entry to `profile_fallbacks.json`.

### Wrong fallback being used

Edit `profile_fallbacks.json` to change the mapping, or regenerate with `generate_fallbacks.py` and manually adjust.

### Fallback not applying

Verify:
1. Profile name matches key in `profile_fallbacks.json`
2. Scene name matches exactly (case-sensitive)
3. Fallback scene exists in `scenes/` directory

## Credits

Scene fallback system designed for flexible multi-profile operation, enabling the same scene prediction pipeline to work across different hardware configurations.

