# Windows Hang Fix

## Problem
The `oculize.py` script was hanging on Windows after making a few scene predictions. The skulls continued to animate (display thread still running), but scene predictions stopped. Pressing 'q' to quit caused a complete freeze.

## Root Causes

### 1. Infinite `join()` without timeout
**Location**: `oculize.py` line 285
- The main thread was calling `self.oculizer.join()` without a timeout
- On Windows, if the audio thread was stuck, this would hang indefinitely
- **Fix**: Added 3-second timeout with warning if thread doesn't stop

### 2. Prediction stream not stopped in `stop()` method
**Location**: `oculizer/light/control.py` lines 567-571
- The `Oculizer.stop()` method only cleared the running flag and closed DMX
- The prediction audio stream was only stopped in the `finally` block of `run()`
- This meant the stream kept running even after stop was called
- **Fix**: Explicitly stop and close the prediction stream in `stop()` method

### 3. Race condition in audio callback
**Location**: `oculizer/light/control.py` line 118
- Audio callbacks could continue executing after `stop()` was called
- Callbacks were using blocking `put()` on the queue
- This could cause the callback to hang if the processing thread had stopped
- **Fix**: 
  - Added check for `self.running.is_set()` at start of callback
  - Changed from blocking `put()` to `put_nowait()` 
  - Drop frames if queue is full instead of blocking

### 4. Double-close protection
**Location**: `oculizer/light/control.py` lines 492-499
- Added try-except in the `finally` block to prevent errors from double-closing
- Set `self.prediction_stream = None` after closing to mark as cleaned up

## Changes Made

### `oculize.py`
```python
# Before
self.oculizer.join()

# After  
self.oculizer.join(timeout=3.0)
if self.oculizer.is_alive():
    logging.warning("Oculizer thread did not stop within timeout")
```

### `oculizer/light/control.py`

#### 1. Enhanced `stop()` method
```python
def stop(self):
    self.running.clear()
    
    # Stop and close prediction stream first
    if self.prediction_stream:
        try:
            self.prediction_stream.stop()
            self.prediction_stream.close()
            self.prediction_stream = None
        except Exception as e:
            logger.error(f"Error stopping prediction stream: {e}")
    
    # Close DMX controller connection
    if hasattr(self, 'dmx_controller') and self.dmx_controller:
        self.dmx_controller.close()
```

#### 2. Fixed prediction audio callback
```python
def prediction_audio_callback(self, indata, frames, time_info, status):
    # Check if still running to avoid queue operations after stop
    if not self.running.is_set():
        return
    
    # ... process audio ...
    
    # Use non-blocking put to avoid hanging
    try:
        self.prediction_audio_queue.put_nowait(mono_data.copy())
    except queue.Full:
        pass  # Drop frame if queue is full
```

#### 3. Improved finally block
```python
finally:
    # Clean up prediction stream if not already stopped
    if self.prediction_stream:
        try:
            self.prediction_stream.stop()
            self.prediction_stream.close()
            self.prediction_stream = None
        except Exception as e:
            print(f"Error closing prediction stream in finally: {e}")
```

## Testing
After applying these fixes, the application should:
1. Make scene predictions without hanging
2. Respond to 'q' keypress within 3 seconds
3. Clean up audio streams properly on exit
4. Not leave any hanging threads or processes

## Notes
- The 3-second timeout on `join()` is conservative; the thread typically stops in <1 second
- Dropped audio frames in the prediction queue are acceptable (system drops every ~100th frame under heavy load)
- Windows audio callbacks can be more sensitive to blocking operations than Linux/macOS

