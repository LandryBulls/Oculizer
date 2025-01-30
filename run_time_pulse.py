"""
For testing the Rockville LED panel functionality with time-based modulation.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
import queue

def main():
    # Initialize scene manager and set scene
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('time_pulse')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville time pulse test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    print("\nMonitoring time-based modulation...")
    
    # Start the light controller
    light_controller.start()
    start_time = time.time()

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Calculate current phase of the sine wave (for 0.5 Hz frequency)
            phase = (elapsed * 0.5) % 1.0
            brightness = int(127.5 + 127.5 * np.sin(2 * np.pi * phase))  # Convert to 0-255 range
            
            # Clear the line and print status
            print(f"\rElapsed Time: {elapsed:.2f}s | Current Brightness: {brightness}", end='', flush=True)
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping test...")
        light_controller.stop()
        light_controller.join()

if __name__ == '__main__':
    main() 