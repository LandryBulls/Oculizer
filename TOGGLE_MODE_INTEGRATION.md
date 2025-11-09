# Toggle Mode Integration

## Overview
Added seamless switching between **Oculizer Mode** (automatic scene prediction) and **Toggle Mode** (manual scene selection) within the same session.

## How to Use

### From Oculizer Mode → Toggle Mode
While running `oculize.py`, press **`t`** to enter toggle mode.

### From Toggle Mode → Oculizer Mode
While in toggle mode, press **`Ctrl+T`** to return to oculizer mode.

### Exiting
Press **`Ctrl+Q`** from either mode to quit the application entirely.

## Features

### Oculizer Mode (Default)
- Automatic scene prediction based on audio analysis
- Real-time FFT-based light reactivity
- Displays current scene, predictions, clusters, and logs
- **Controls**:
  - `q` - Quit application
  - `t` - Enter toggle mode
  - `r` - Reload scenes

### Toggle Mode
- Interactive grid-based scene selector
- Mouse support (click to select, hover to highlight)
- Keyboard navigation (arrow keys)
- Type-to-search scene names
- Visual indicators:
  - **Green background** - Currently active scene
  - **Yellow background** - Selected scene (keyboard navigation)
  - **Blue background** - Hovered scene (mouse)
  - **Black background** - Normal scenes
- **Controls**:
  - `Ctrl+T` or `t` - Return to oculizer mode
  - `Ctrl+Q` - Quit application
  - `Ctrl+R` - Reload scenes
  - Arrow keys - Navigate grid
  - Enter - Activate selected scene
  - Type letters - Search for scenes
  - Mouse click - Select and activate scene

## Implementation Details

### Changes to `oculize.py`

1. **Added Toggle Mode Infrastructure**:
   - Imported helper functions from toggle.py logic
   - Added toggle mode color pairs
   - Added helper functions: `sort_scenes_alphabetically()`, `find_scene_by_prefix()`, `calculate_grid_dimensions()`, etc.

2. **New Method**: `AudioOculizerController.run_toggle_mode()`
   - Implements the full toggle mode UI
   - Handles mouse events and keyboard navigation
   - Allows scene switching while maintaining the running light controller
   - Returns to oculizer mode when exited

3. **Updated Key Handler**:
   - Added 't' key to enter toggle mode
   - Toggle mode has its own event loop
   - Returns control to oculizer mode when user presses Ctrl+T

4. **Updated Display**:
   - Added toggle mode instructions to controls

### Changes to `toggle.py`

1. **Refactored Main Function**:
   - Created `run_toggle_mode()` function that accepts existing scene_manager and light_controller
   - Returns `True` to exit program, `False` to return to caller
   - Preserves standalone functionality through separate `main()` wrapper

2. **Added Return Key**:
   - Ctrl+T (key code 20) returns to oculizer mode
   - Ctrl+Q (key code 17) exits program entirely
   - Lowercase 't' also returns to oculizer mode (for convenience)

3. **Mouse Cleanup**:
   - Properly disables mouse tracking when exiting toggle mode
   - Prevents mouse events from affecting oculizer mode

## Usage Examples

### Standard Workflow
```bash
# Start oculizer with automatic scene prediction
python oculize.py --profile mobile

# While running:
# - Press 't' to manually select a specific scene
# - Use mouse or keyboard to select scene in toggle mode
# - Press Ctrl+T to return to automatic predictions
# - Automatic predictions resume from where they left off
```

### Standalone Toggle Mode
```bash
# Run toggle mode directly (as before)
python toggle.py --profile mobile

# This works independently without scene prediction
```

## Benefits

1. **Best of Both Worlds**: Combine automatic scene prediction with manual override
2. **No Restart Required**: Switch modes instantly without stopping the application
3. **Preserved State**: Light controller and scene manager remain active during mode switch
4. **Flexible Control**: Choose between hands-off automation or precise manual control
5. **Backward Compatible**: toggle.py still works as a standalone script

## Technical Notes

- Both modes share the same `Oculizer` instance and `SceneManager`
- Scene prediction continues running in the background during toggle mode
- DMX controller remains connected throughout mode switches
- Mouse tracking is only enabled during toggle mode to avoid interference
- Scene changes in toggle mode are reflected immediately in the light system
- Returning to oculizer mode resumes automatic scene prediction
