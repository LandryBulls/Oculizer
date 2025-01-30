"""
For testing the Rockville LED panel functionality with the sequential pairs effect.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
from oculizer.light.effects import registry  # Import to monitor effect state
import queue

def main():
    # Initialize scene manager and set scene to sequence
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('sequence')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville panel sequence effect test...")
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
                effect_state = registry.get_state('rockville1', 'rockville_sequential_panels')
                
                # Calculate sequence info
                sequence_duration = scene_manager.current_scene['lights'][0]['effect'].get('sequence_duration', 0.5)
                time_elapsed = time.time() - effect_state.last_trigger_time
                time_remaining = max(0, sequence_duration - time_elapsed) if effect_state.is_active else 0
                
                # Get current pair info
                current_pair = effect_state.sequence_position if effect_state.is_active else -1
                direction = scene_manager.current_scene['lights'][0]['effect'].get('direction', 'left_to_right')
                wait = scene_manager.current_scene['lights'][0]['effect'].get('wait', True)
                
                # Clear the line and print status
                print(f"\rBass Power: {bass_power:.3f} | "
                      f"Last Trigger: {time_elapsed:.2f}s ago | "
                      f"Active: {effect_state.is_active} | "
                      f"Sequence Time: {time_remaining:.2f}s | "
                      f"Current Pair: {current_pair} | "
                      f"Direction: {direction} | "
                      f"Wait: {wait}", end='', flush=True)
                
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