# Prediction Override Mode - Enhanced Toggle Mode

## Overview

Toggle mode now features **live prediction visualization** with **manual override capability**. You can watch AI predictions happen in real-time while maintaining the ability to override and manually control scenes at any time.

## How It Works

### Two Operating Modes

#### 1. **Following Predictions Mode** (Default)
- Predictions are **ACTIVE** - scenes change automatically
- Active scene shown in **GREEN** 
- Header: `FOLLOWING PREDICTIONS (Auto: scene_name)`
- Predictions update and change scenes in real-time

#### 2. **Override Mode** (Manual Control)
- Your manual selection is **ACTIVE** - prediction changes are blocked
- Predicted scenes shown in **CYAN** (visible but not active)
- Active override scene shown in **MAGENTA**
- Header: `OVERRIDE ACTIVE (Manual: scene_name)`
- You have full control, predictions continue in background

## Key Bindings

| Key | Action |
|-----|--------|
| `Ctrl+O` | **Toggle Override** - Switch between auto/manual mode |
| `Enter` | Select scene (automatically enables override) |
| `Ctrl+T` | Return to oculizer mode |
| `t` | Return to oculizer mode (alternative) |
| `Ctrl+Q` | Quit application |
| `Ctrl+R` | Reload scenes |
| `↑↓←→` | Navigate scene grid |
| `A-Z` | Search for scene by name |
| **Mouse** | Click to select and override |

## Color Legend

| Color | Meaning | When Visible |
|-------|---------|--------------|
| 🟢 **GREEN** | Active scene (predictions) | Following mode |
| 🟣 **MAGENTA** | Active scene (manual) | Override mode |
| 🔵 **CYAN** | Predicted scene (not active) | Override mode only |
| 🟡 **YELLOW** | Selected (keyboard navigation) | Always |
| 🔵 **BLUE** | Hovered (mouse) | Always |
| ⚫ **BLACK** | Available scenes | Always |

## Workflows

### Workflow 1: Watch Predictions, Override When Needed

```
1. Press 't' in oculizer mode
   → Enter toggle mode
   → FOLLOWING PREDICTIONS mode (GREEN active)
   → Watch scenes change automatically

2. Don't like current prediction?
   → Press Enter on desired scene
   → Automatically switches to OVERRIDE mode (MAGENTA active)
   → Your scene is now locked in

3. Watch predictions continue in background
   → Predicted scenes shown in CYAN
   → Your override scene stays MAGENTA (active)
   → Predictions don't affect lights

4. Ready to resume auto mode?
   → Press Ctrl+O
   → Switches to predicted scene
   → Back to FOLLOWING PREDICTIONS mode
```

### Workflow 2: Quick Manual Override

```
1. In toggle mode, following predictions
2. Type scene name or use arrows
3. Press Enter
   → Instantly overrides with your selection
   → Ctrl+O reminder shown in status

4. Press Ctrl+O when ready
   → Resumes automatic predictions
```

### Workflow 3: Monitor Predictions Without Activating

```
1. Press 't' in oculizer mode
2. Immediately press Ctrl+O
   → Enables override with current scene
3. Watch predictions in CYAN
   → See what AI would choose
   → Your scene stays active (MAGENTA)
4. Evaluate predictions over time
5. Press Ctrl+O to follow when satisfied
```

## Visual Examples

### Following Predictions Mode
```
┌─────────────────────────────────────────────────────────┐
│ TOGGLE MODE - FOLLOWING PREDICTIONS (Auto: party)      │
│ [Ctrl+O] Toggle Override  [Ctrl+T] Exit  [Ctrl+Q] Quit │
│ Current Prediction: party                                │
│ Available scenes:                                        │
│                                                          │
│  🟢 party      ambient     chill       hype             │
│  laser_show   strobe      dimmed      bright            │
│  ⚫ ...        ⚫ ...       ⚫ ...       ⚫ ...           │
│                                                          │
│ 🟢=Active | Ctrl+O: Toggle Override | Enter: Select     │
└─────────────────────────────────────────────────────────┘
```

### Override Mode (Manual Control)
```
┌─────────────────────────────────────────────────────────┐
│ TOGGLE MODE - OVERRIDE ACTIVE (Manual: laser_show)     │
│ [Ctrl+O] Toggle Override  [Ctrl+T] Exit  [Ctrl+Q] Quit │
│ Current Prediction: party                                │
│ Available scenes:                                        │
│                                                          │
│  🔵 party      ambient     chill       hype             │
│  🟣 laser_show strobe      dimmed      bright            │
│  ⚫ ...        ⚫ ...       ⚫ ...       ⚫ ...           │
│                                                          │
│ 🟢=Active 🟣=Override 🔵=Predicted | Ctrl+O: Toggle     │
└─────────────────────────────────────────────────────────┘
```

## Use Cases

### 1. **DJ/Live Performance**
- Watch predictions in CYAN while performing
- Override to specific scenes for key moments
- Resume auto-prediction between manual interventions
- Quick response to audience energy

### 2. **Testing/Evaluation**
- Monitor prediction accuracy in real-time
- Override when predictions are wrong
- Compare manual choices vs AI predictions
- Tune scene predictor based on observations

### 3. **Hybrid Control**
- Let AI handle most transitions automatically
- Override for special moments (drops, breaks, buildups)
- Smooth return to auto mode when ready
- Best of both worlds approach

### 4. **Learning Mode**
- Watch what the AI predicts
- Override to see alternative scenes
- Understand prediction patterns
- Build intuition for scene selection

## Technical Details

### Prediction Continuity
- Scene prediction **ALWAYS continues** in toggle mode
- Predictions visible in real-time via header and CYAN highlighting
- Override blocks scene changes but not predictions
- Predictions immediately resume when override disabled

### State Management
- `override_active`: Boolean flag for mode state
- `override_scene`: Currently overridden scene (if any)
- `predicted_scene`: Latest AI prediction
- `current_scene_name`: Actually active scene

### Scene Change Logic
```python
if override_active:
    # Manual control - ignore predictions
    active_scene = override_scene
    show_prediction_in_cyan = True
else:
    # Auto mode - follow predictions
    active_scene = predicted_scene
    change_to_predicted_scene()
```

### Override Triggers
1. **Manual**: Press Ctrl+O to toggle
2. **Automatic**: Selecting any scene (Enter or mouse click)
3. **Disable**: Press Ctrl+O again to resume predictions

## Tips & Best Practices

1. **Start in Auto Mode**: Enter toggle mode without override to see predictions first
2. **Use Ctrl+O as Safety**: Toggle override quickly when needed
3. **Watch Predictions**: Even in override mode, observe CYAN highlights
4. **Trust the AI**: Give predictions a chance, override sparingly
5. **Quick Return**: Ctrl+T exits to oculizer mode maintaining current scene
6. **Status Awareness**: Header always shows current mode and active scene

## Keyboard Shortcuts Reference

```
Ctrl+O  →  Toggle Override (THE KEY FEATURE!)
Enter   →  Select & Override
Ctrl+T  →  Exit to Oculizer
Ctrl+Q  →  Quit Program
Ctrl+R  →  Reload Scenes
```

## Comparison: Old vs New Toggle Mode

### Old Toggle Mode
- ❌ Predictions stopped when entering toggle
- ❌ No way to see what AI would choose
- ❌ Manual control only
- ❌ Binary choice: auto XOR manual

### New Enhanced Toggle Mode
- ✅ Predictions continue visibly
- ✅ Real-time prediction display (CYAN)
- ✅ Both auto and manual modes available
- ✅ Seamless switching: auto AND manual
- ✅ Override indication (MAGENTA)
- ✅ Status header shows mode clearly
- ✅ Ctrl+O quick toggle

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't see predictions | Check if scene predictor is running (top of terminal) |
| Override won't disable | Press Ctrl+O (not lowercase 'o') |
| Scenes not changing | Check if override mode is active (MAGENTA scene) |
| Wrong scene highlighted | MAGENTA = active override, CYAN = prediction |
| Confused about mode | Read header: "FOLLOWING" or "OVERRIDE ACTIVE" |

## Future Enhancements (Ideas)

- [ ] Show prediction confidence scores
- [ ] History of recent predictions
- [ ] Automatic override timeout (return to auto after N seconds)
- [ ] Override for specific duration
- [ ] Hotkeys for common scenes (1-9)
- [ ] Prediction accuracy statistics
