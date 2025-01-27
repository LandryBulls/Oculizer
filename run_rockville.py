"""
For testing the Rockville LED panel functionality.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def main():
    # Initialize scene manager and set scene to rockville
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('rockville_example')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville panel test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    
    # Start the light controller
    light_controller.start()

    try:
        while True:
            # Try to get the latest MFFT data from the queue
            try:
                mfft_data = light_controller.mfft_queue.get_nowait()
                # Calculate some useful metrics
                mfft_mean = np.mean(mfft_data)
                mfft_max = np.max(mfft_data)
                mfft_min = np.min(mfft_data)
                
                # Print the metrics with clear formatting
                print(f"\rMFFT - Mean: {mfft_mean:.4f} | Max: {mfft_max:.4f} | Min: {mfft_min:.4f}", end='', flush=True)
            except:
                pass
            
            time.sleep(0.1)  # Slight delay to prevent overwhelming the console

    except KeyboardInterrupt:
        print("\nStopping test...")
        light_controller.stop()
        light_controller.join()

if __name__ == '__main__':
    main()
