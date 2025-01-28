"""
For testing the Rockville LED panel functionality with effects.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
from oculizer.light.effects import registry  # Import to monitor effect state
import queue

def main():
    # Initialize scene manager and set scene to splatter
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('splatter')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville splatter effect test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    # print("Effect configuration:")
    # for light in scene_manager.current_scene['lights']:
    #     if 'effect' in light:
    #         print(f"  Light: {light['name']}")
    #         print(f"  Effect: {light['effect']['name']}")
    #         print(f"  Threshold: {light['effect'].get('threshold', 'default')}")
    #         print(f"  Panel Colors: {light['effect'].get('panel_colors', 'default')}")
    #         print(f"  Bar Colors: {light['effect'].get('bar_colors', 'default')}")
    print("\nMonitoring audio and effect state...")
    
    # Start the light controller
    light_controller.start()

    try:
        while True:
            try:
                mfft_data = light_controller.mfft_queue.get_nowait()
                
                # Calculate audio metrics for both frequency ranges
                bass_power = np.mean(mfft_data[0:20])  # Bass range
                treble_power = np.mean(mfft_data[115:127])  # Treble range
                
                # Get effect state
                effect_state = registry.get_state('rockville1', 'rockville_splatter')
                
                # Clear the line and print status
                print(f"\rBass: {bass_power:.3f} | Treble: {treble_power:.3f} | "
                      f"Last Trigger: {time.time() - effect_state.last_trigger_time:.2f}s ago | "
                      f"Active: {effect_state.is_active}", end='', flush=True)
                
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
