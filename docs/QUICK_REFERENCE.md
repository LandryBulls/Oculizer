# Oculizer Quick Reference Card

## Starting the Application

```bash
# Automatic mode (default)
python oculize.py --profile mobile

# Test mode (no DMX/FFT)
python oculize.py --test

# Standalone toggle mode
python toggle.py --profile mobile
```

## Key Bindings

### Oculizer Mode (Automatic)
| Key | Action |
|-----|--------|
| `t` | Enter toggle mode (manual selection) |
| `q` | Quit application |
| `r` | Reload scenes |

### Toggle Mode (Hybrid Auto/Manual)
| Key | Action |
|-----|--------|
| `Ctrl+O` | **Toggle Override** (auto ↔ manual) |
| `Enter` | Select scene (enables override) |
| `Ctrl+T` | Return to oculizer mode |
| `t` | Return to oculizer mode (alternative) |
| `Ctrl+Q` | Quit application |
| `Ctrl+R` | Reload scenes |
| `↑↓←→` | Navigate scene grid |
| `A-Z` | Search for scene by name |
| `Backspace` | Delete search character |
| `Esc` | Clear search |
| **Mouse** | Click to select and override |

## Visual Indicators (Toggle Mode)

| Color | Meaning | Mode |
|-------|---------|------|
| 🟢 **Green** | Active scene (auto) | Following predictions |
| 🟣 **Magenta** | Active scene (manual) | Override mode |
| 🔵 **Cyan** | Predicted (not active) | Override mode |
| 🟡 **Yellow** | Selected (keyboard) | Always |
| 🔵 **Blue** | Hovered (mouse) | Always |
| ⚫ **Black** | Available scenes | Always |

## Common Workflows

### Quick Scene Override
```
1. Running in oculizer mode
2. Press 't' → Toggle mode (predictions visible)
3. Click scene or use arrows + Enter → Override enabled
4. Press Ctrl+O → Resume predictions
   OR Press Ctrl+T → Back to oculizer mode
```

### Browse and Test Scenes
```
1. Press 't' → Enter toggle mode
2. Use arrow keys to navigate through scenes
3. Press Enter on each to see effect
4. Type scene name to jump to it
5. Press Ctrl+T when done → Return to auto mode
```

### Manual Control Session
```
1. Press 't' → Enter toggle mode
2. Select scenes manually as needed
3. Stay in toggle mode for duration
4. Press Ctrl+Q to exit when done
```

## Tips & Tricks

- **Fast Scene Switch**: Press 't', type first letters, press Enter, press Ctrl+T
- **Preview Mode**: Enter toggle mode to see all available scenes at once
- **Search Smart**: Type "par" to jump to "party", "las" to "laser_show", etc.
- **Mouse Quick**: Single click in toggle mode activates scene instantly
- **Stay Manual**: Remain in toggle mode if you want full manual control
- **Auto Resume**: Predictions resume instantly when you return from toggle mode

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Toggle mode not responding | Press Ctrl+C and restart |
| Mouse not working | Use keyboard arrows instead |
| Can't return to oculizer | Press Ctrl+T or lowercase 't' |
| Scene won't change | Check if DMX controller is connected |
| Display garbled | Resize terminal, press 't' then Ctrl+T |

## Default Configurations

### macOS
- Input Device: Scarlett
- Prediction Device: BlackHole (channel 1)
- Profile: mobile
- Cache Size: 1 (instant response)

### Windows/Linux
- Input Device: Scarlett
- Prediction Device: Cable Output
- Profile: garage2025
- Cache Size: 25 (smoothed)

## Advanced Options

```bash
# Custom predictor version
python oculize.py --predictor-version v4

# Single stream mode
python oculize.py --single-stream

# Custom scene cache (smoothing)
python oculize.py --scene-cache-size 5

# Average dual channels
python oculize.py --average-dual-channels

# List audio devices
python oculize.py --list-devices
```

---

**Legend**: `Ctrl+X` = Control key + X | `↑↓←→` = Arrow keys | `A-Z` = Any letter
