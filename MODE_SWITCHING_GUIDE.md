# Mode Switching Quick Guide

## Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      OCULIZER MODE                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  🤖 Automatic Scene Prediction                        │  │
│  │  🎵 Audio Analysis & FFT Reactivity                   │  │
│  │  📊 Real-time Logs & Predictions                      │  │
│  │                                                        │  │
│  │  Controls:                                            │  │
│  │    q - Quit                                           │  │
│  │    t - Toggle Mode  ◄──────────────────────┐         │  │
│  │    r - Reload Scenes                        │         │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────│─────────────┘
                                                 │
                                        Press 't' │
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      TOGGLE MODE                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  🎯 Manual Scene Selection                            │  │
│  │  🖱️  Mouse & Keyboard Navigation                     │  │
│  │  🔍 Type-to-Search                                    │  │
│  │                                                        │  │
│  │  ┌────────┬────────┬────────┬────────┐              │  │
│  │  │ party  │ chill  │ hype   │ ambient│              │  │
│  │  ├────────┼────────┼────────┼────────┤              │  │
│  │  │ strobe │ laser  │ dimmed │ bright │              │  │
│  │  └────────┴────────┴────────┴────────┘              │  │
│  │                                                        │  │
│  │  Controls:                                            │  │
│  │    Ctrl+T - Back to Oculizer  ◄─────────┐            │  │
│  │    Ctrl+Q - Quit                         │            │  │
│  │    Ctrl+R - Reload Scenes                │            │  │
│  │    Enter  - Activate Scene               │            │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────│─────────────┘
                                                 │
                                    Press Ctrl+T │
                                                 │
                                                 ▼
                                    (Return to Oculizer Mode)
```

## Quick Reference

### Starting the Application

```bash
# Start with automatic mode
python oculize.py --profile mobile

# Or start standalone toggle mode
python toggle.py --profile mobile
```

### Key Bindings

| Key       | Context       | Action                          |
|-----------|---------------|---------------------------------|
| `t`       | Oculizer      | Enter toggle mode               |
| `Ctrl+T`  | Toggle        | Return to oculizer mode         |
| `Ctrl+Q`  | Both          | Quit application                |
| `r`       | Oculizer      | Reload scenes                   |
| `Ctrl+R`  | Toggle        | Reload scenes                   |
| `↑↓←→`    | Toggle        | Navigate scene grid             |
| `Enter`   | Toggle        | Activate selected scene         |
| `A-Z`     | Toggle        | Search for scene by name        |
| `Backspace`| Toggle       | Delete search character         |
| `Esc`     | Toggle        | Clear search                    |

### Mouse Controls (Toggle Mode Only)

- **Hover**: Blue highlight over scene
- **Click**: Select and activate scene
- **Move**: Real-time hover highlighting

## Example Workflow

1. **Start Oculizer**: `python oculize.py --profile mobile`
   - Automatic scene prediction starts
   - Audio reactivity is active
   - Lights respond to music

2. **Need Manual Control?**: Press `t`
   - Grid of all available scenes appears
   - Current scene is highlighted in green
   - Navigate with arrow keys or mouse

3. **Select a Scene**:
   - Use arrow keys to navigate
   - Or click with mouse
   - Press Enter to activate
   - Scene changes immediately

4. **Back to Automatic**: Press `Ctrl+T`
   - Returns to prediction mode
   - Automatic scene changes resume
   - All state preserved

5. **Done**: Press `Ctrl+Q` from either mode
   - Clean shutdown
   - DMX controller disconnected
   - Audio streams stopped

## Color Legend (Toggle Mode)

- 🟢 **Green Background** - Currently active scene
- 🟡 **Yellow Background** - Selected (keyboard navigation)
- 🔵 **Blue Background** - Hovered (mouse position)
- ⚫ **Black Background** - Available scenes

## Tips

- Search in toggle mode by typing: start typing "par" and it jumps to "party"
- Search times out after 1 second of no typing
- Scenes are alphabetically sorted in toggle mode
- Changes in toggle mode are reflected immediately
- Oculizer mode remembers your manual changes
- You can press 't' multiple times to quickly check/change scenes
