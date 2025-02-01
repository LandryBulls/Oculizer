"""
For testing the Rockville LED panel functionality with the hopper orchestrator.
"""

import time
import numpy as np
from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
import queue

def main():
    # Initialize scene manager and set scene to hopper
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('bass_hopper')
    
    # Initialize Oculizer with rockville profile
    light_controller = Oculizer('rockville', scene_manager)

    print("Starting Rockville panel hopper effect test...")
    print(f"Current scene: {scene_manager.current_scene['name']}")
    print(f"Target lights: {scene_manager.current_scene['orchestrator']['config']['target_lights']}")
    print("\nMonitoring audio and orchestrator state...")
    
    # Start the light controller
    light_controller.start()

    try:
        while True:
            try:
                mfft_data = light_controller.mfft_queue.get_nowait()
                
                # Calculate audio metrics for bass range
                mfft_range = scene_manager.current_scene['orchestrator']['config']['trigger']['mfft_range']
                bass_power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
                
                # Get orchestrator state
                orchestrator = light_controller.current_orchestrator
                if orchestrator:
                    current_light = orchestrator.state['active_light']
                    last_trigger = time.time() - orchestrator.state['last_trigger_time']
                    transition_progress = (time.time() - orchestrator.state['transition_start']) / orchestrator.config['transition']['duration']
                    transition_progress = min(1.0, max(0.0, transition_progress))  # Clamp between 0 and 1
                    
                    # Clear the line and print status
                    print(f"\rBass Power: {bass_power:.3f} | "
                          f"Active Light: {current_light} | "
                          f"Last Trigger: {last_trigger:.2f}s ago | "
                          f"Transition Progress: {transition_progress:.2f}", end='', flush=True)
                else:
                    print("\rWaiting for orchestrator initialization...", end='', flush=True)
                
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