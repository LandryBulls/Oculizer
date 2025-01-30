"""
For testing the Rockville LED panel functionality with the sustain effect.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
from oculizer.light.effects import registry  # Import to monitor effect state
import queue

def main():
    # Initialize scene manager and set scene to sustain
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('sustain')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville panel sustain effect test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    print("\nMonitoring audio and effect state...")
    
    # Start the light controller
    light_controller.start()

    try:
        while True:
            try:
                mfft_data = light_controller.mfft_queue.get_nowait()
                
                # Calculate audio metrics for bass range
                bass_power = np.mean(mfft_data[0:20])  # Bass range
                
                # Get effect state
                effect_state = registry.get_state('rockville1', 'rockville_panel_sustain')
                
                # Calculate time remaining in sustain if active
                time_remaining = 0
                if effect_state.is_active:
                    sustain_duration = scene_manager.current_scene['lights'][0]['effect'].get('sustain_duration', 0.4)
                    time_elapsed = time.time() - effect_state.last_trigger_time
                    time_remaining = max(0, sustain_duration - time_elapsed)
                
                # Clear the line and print status
                print(f"\rBass Power: {bass_power:.3f} | "
                      f"Last Trigger: {time.time() - effect_state.last_trigger_time:.2f}s ago | "
                      f"Active: {effect_state.is_active} | "
                      f"Sustain Remaining: {time_remaining:.2f}s | "
                      f"Blocks Active: {len(effect_state.custom_state.get('block_colors', []))}", end='', flush=True)
                
            except Exception as e:
                if not isinstance(e, queue.Empty):
                    print(f"\nError: {str(e)}")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping test...")
        light_controller.stop()
        light_controller.join()

if __name__ == '__main__':
    main() 