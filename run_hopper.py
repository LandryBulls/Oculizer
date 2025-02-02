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
    
    print("\nInitializing scene manager...")
    print(f"Available scenes: {list(scene_manager.scenes.keys())}")
    
    # Set scene to bass_hopper
    try:
        scene_manager.set_scene('bass_hopper')
        print(f"\nLoaded scene: {scene_manager.current_scene['name']}")
        print(f"Scene configuration:")
        print(f"- Orchestrator type: {scene_manager.current_scene['orchestrator']['type']}")
        print(f"- Target lights: {scene_manager.current_scene['orchestrator']['config']['target_lights']}")
        print(f"- Trigger config: {scene_manager.current_scene['orchestrator']['config']['trigger']}")
    except Exception as e:
        print(f"Error loading scene: {str(e)}")
        return
    
    # Initialize Oculizer with rockville profile
    print("\nInitializing Oculizer...")
    light_controller = Oculizer('rockville', scene_manager)
    print(f"Available lights: {light_controller.light_names}")
    
    # Start the light controller
    print("\nStarting light controller...")
    light_controller.start()
    
    print("\nMonitoring audio and orchestrator state...")
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
                    current_light = orchestrator.state.get('active_light', 'None')
                    last_trigger = time.time() - orchestrator.state.get('last_trigger_time', time.time())
                    transition_progress = (time.time() - orchestrator.state.get('transition_start', time.time())) / orchestrator.config['transition']['duration']
                    transition_progress = min(1.0, max(0.0, transition_progress))  # Clamp between 0 and 1
                    
                    # Clear the line and print status
                    print(f"\rBass Power: {bass_power:.3f} | "
                          f"Active Light: {current_light} | "
                          f"Last Trigger: {last_trigger:.2f}s ago | "
                          f"Transition Progress: {transition_progress:.2f}", end='', flush=True)
                else:
                    print(f"\rWaiting for orchestrator initialization... (Current orchestrator: {type(orchestrator)})", end='', flush=True)
                
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                print(f"\nError in main loop: {str(e)}")
                if hasattr(e, '__traceback__'):
                    print(f"Error location: {e.__traceback__.tb_frame.f_code.co_filename}:{e.__traceback__.tb_lineno}")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping test...")
        light_controller.stop()
        light_controller.join()

if __name__ == '__main__':
    main() 