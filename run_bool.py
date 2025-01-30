"""
For testing the Rockville LED panel functionality with bool-based modulation.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
import queue

def main():
    # Initialize scene manager and set scene
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('bool')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville random patterns test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    print("\nMonitoring random pattern generation...")
    
    # Start the light controller
    light_controller.start()
    pattern_count = 0
    start_time = time.time()

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            pattern_count += 1
            
            # Clear the line and print status
            print(f"\rElapsed Time: {elapsed:.2f}s | Patterns Generated: {pattern_count}", end='', flush=True)
            
            time.sleep(0.5)  # Slower update rate to make patterns more visible

    except KeyboardInterrupt:
        print("\nStopping test...")
        light_controller.stop()
        light_controller.join()

if __name__ == '__main__':
    main() 