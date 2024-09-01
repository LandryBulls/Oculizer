"""
light_control.py

Description: This script provides all the lighting control. It is responsible for controlling the DMX lights and RGB lights, loading profiles, 
setting up the DMX controller, providing functions for sending signals to the DMX controller, and providing functions for controlling the RGB lights.

Author: Landry Bulls
Date: 8/20/24
"""

from PyDMXControl.controllers import OpenDMXController
from PyDMXControl.profiles.Generic import Dimmer, Custom
from oculizer.custom_profiles.RGB import RGB
from oculizer.custom_profiles.ADJ_strobe import Strobe
from oculizer.audio import AudioListener
from oculizer.scenes import SceneManager
from oculizer.light import mapping
import threading
import queue
import os
import json
from pathlib import Path
import numpy as np
import logging

from ..utils import load_json 
import time

logging.basicConfig(filename='oculizer_debug.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_profile(profile_name):
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    profile_path = project_root / 'profiles' / f'{profile_name}.json'
    with open(profile_path, 'r') as f:
        profile = json.load(f)
    
    return profile

def load_controller(profile):
    logger.debug("Starting load_controller function")
    try:
        logger.debug("Initializing OpenDMXController")
        controller = OpenDMXController()
    except Exception as e:
        logger.error(f"Error loading DMX controller: {str(e)}")
        return None, None
    
    control_dict = {}
    curr_channel = 1
    
    for light in profile['lights']:
        logger.debug(f"Processing light: {light['name']} of type {light['type']}")
        try:
            if light['type'] == 'dimmer':
                logger.debug(f"Adding dimmer fixture: {light['name']} at channel {curr_channel}")
                control_dict[light['name']] = controller.add_fixture(Dimmer(name=light['name'], start_channel=curr_channel))
                logger.debug("Flashing dimmer light")
                control_dict[light['name']].dim(255)
                time.sleep(0.5)
                control_dict[light['name']].dim(0)
                curr_channel += 1
            elif light['type'] == 'rgb':
                logger.debug(f"Adding RGB fixture: {light['name']} at channel {curr_channel}")
                control_dict[light['name']] = controller.add_fixture(RGB(name=light['name'], start_channel=curr_channel))
                #control_dict[light['name']] = controller.add_fixture(Custom(name=light['name'], start_channel=curr_channel, channels=6))
                logger.debug("Flashing RGB light")
                control_dict[light['name']].set_channels([255,255,255,255,0,0])
                time.sleep(0.5)
                control_dict[light['name']].set_channels([0,0,0,0,0,0])
                curr_channel += 6
            elif light['type'] == 'strobe':
                logger.debug(f"Adding strobe fixture: {light['name']} at channel {curr_channel}")
                control_dict[light['name']] = controller.add_fixture(Strobe(name=light['name'], start_channel=curr_channel))
                logger.debug("Flashing strobe light")
                control_dict[light['name']].set_channels([255,255])
                time.sleep(0.5)
                control_dict[light['name']].set_channels([0,0])
                curr_channel += 2
            else:
                logger.warning(f"Unknown light type: {light['type']} for light {light['name']}")
        except Exception as e:
            logger.error(f"Error adding fixture {light['name']}: {str(e)}")
    
    logger.debug("Finished load_controller function")
    return controller, control_dict

class LightController(threading.Thread):
    def __init__(self, audio_listener, profile, scene_manager):
        threading.Thread.__init__(self)
        self.audio_listener = audio_listener
        self.profile = profile
        self.light_names = [i['name'] for i in self.profile['lights']]
        logger.debug("Initializing DMX controller")
        try:
            self.dmx_controller, self.controller_dict = load_controller(self.profile)
            if self.dmx_controller is None or self.controller_dict is None:
                raise Exception("Failed to initialize DMX controller")
        except Exception as e:
            logger.error(f"Error initializing DMX controller: {str(e)}")
            raise
        self.scene_manager = scene_manager
        self.running = threading.Event()
        self.fft_data = None
        self.scene_changed = threading.Event()
        logger.debug("LightController initialized")

    def turn_off_all_lights(self):
        logger.debug("Turning off all lights")
        for light in self.profile['lights']:
            if light['type'] == 'dimmer':
                self.controller_dict[light['name']].dim(0)
            elif light['type'] == 'rgb':
                self.controller_dict[light['name']].set_channels([0,0,0,0,0,0])
            elif light['type'] == 'strobe':
                self.controller_dict[light['name']].set_channels([0,0])
        logger.debug("All lights turned off")

    def change_scene(self, scene_name):
        logger.debug(f"Changing scene to {scene_name}")
        self.turn_off_all_lights()
        self.scene_manager.set_scene(scene_name)
        self.scene_changed.set()

    def run(self):
        self.running.set()
        logger.debug("LightController running")
        while self.running.is_set():
            if self.scene_changed.is_set():
                logger.debug("Scene changed, applying new scene")
                self.scene_changed.clear()
            
            if not self.audio_listener.fft_queue.empty():
                try:
                    self.send_dynamic()
                except Exception as e:
                    logger.error(f"Error sending dynamic data: {str(e)}")
            else:
                logger.debug("No FFT data available")
            
            time.sleep(0.01)  # Small delay to prevent busy waiting

    def send_dynamic(self):
        logger.debug("Sending dynamic data")
        try:
            fft_data = self.audio_listener.fft_queue.get_nowait()
            fft_data = np.array(fft_data, dtype=np.float64)
        except queue.Empty:
            logger.debug("No FFT data available")
            return

        current_time = np.float64(time.time())

        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
                continue

            try:
                logger.debug(f"Processing light {light['name']}")
                # this is where it hangs
                light_float64 = {k: (np.float64(v) if isinstance(v, (int, float)) else 
                                     (np.array(v, dtype=np.float64) if isinstance(v, list) else v)) 
                                 for k, v in light.items()}

                logging.debug(f"Light {light['name']} as float64: {light_float64}")
                logging.debug(f"Processing light {light['name']} with FFT data: {fft_data}, time: {current_time}")
                dmx_values = mapping.process_light(light_float64, fft_data, current_time)
                logger.debug(f"DMX values for {light['name']}: {dmx_values}")
                
                if dmx_values is not None:
                    # Convert numpy array to list of integers
                    dmx_values_int = [int(v) for v in dmx_values]
                    logger.debug(f"Setting {light['name']} to {dmx_values_int}")
                    
                    if light['type'] == 'dimmer':
                        self.controller_dict[light['name']].dim(dmx_values_int[0])
                    elif light['type'] == 'rgb':
                        self.controller_dict[light['name']].set_channels(*dmx_values_int)
                    elif light['type'] == 'strobe':
                        self.controller_dict[light['name']].set_channels(*dmx_values_int)
                else:
                    logger.debug(f"No DMX values generated for {light['name']}")
            except Exception as e:
                logger.error(f"Error processing light {light['name']}: {str(e)}")

    def stop(self):
        logger.debug("Stopping LightController")
        self.running.clear()

def main():
    audio_listener = AudioListener()
    scene_manager = SceneManager('scenes')
    profile = load_profile('testing')
    light_controller = LightController(audio_listener, profile, scene_manager)
        
    audio_listener.start()
    light_controller.start()

    print('Running for 10 seconds')
    scene_manager.set_scene('testing')
    time.sleep(10)  

    audio_listener.stop()
    light_controller.stop()
    audio_listener.join()
    light_controller.join()

if __name__ == "__main__":
    main()






