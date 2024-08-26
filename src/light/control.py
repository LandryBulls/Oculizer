"""
light_control.py

Description: This script provides all the lighting control. It is responsible for controlling the DMX lights and RGB lights, loading profiles, 
setting up the DMX controller, providing functions for sending signals to the DMX controller, and providing functions for controlling the RGB lights.

Author: Landry Bulls
Date: 8/20/24
"""

from PyDMXControl.controllers import OpenDMXController
from PyDMXControl.profiles.Generic import Dimmer, Custom
from custom_profiles.RGB import RGB
from custom_profiles.ADJ_strobe import Strobe
import threading
import queue
import os
import json
from mapping import fft_to_rgb, fft_to_strobe, fft_to_dimmer, generate_RGB_signal, bool_rgb, time_dimmer, time_rgb, time_strobe
from audio_listener import AudioListener
from scene_manager import SceneManager
from utils import load_json 
import time

def load_profile(profile_name):
    with open(f'profiles/{profile_name}.json', 'r') as f:
        profile = json.load(f)
    return profile

def load_controller(profile):
    controller = OpenDMXController()
    control_dict = {}
    curr_channel = 1
    for light in profile['lights']:
        if light['type'] == 'dimmer':
            control_dict[light['name']] = controller.add_fixture(Dimmer(name=light['name'], start_channel=curr_channel))
            # flash the light to make sure it's working
            control_dict[light['name']].dim(255)
            time.sleep(0.5)
            control_dict[light['name']].dim(0)
            curr_channel += 1
        elif light['type'] == 'rgb':
            control_dict[light['name']] = controller.add_fixture(RGB(name=light['name'], start_channel=curr_channel))
            # flash the light to make sure it's working
            control_dict[light['name']].set_channels([255,255,255,255,0,0])
            time.sleep(0.5)
            control_dict[light['name']].set_channels([0,0,0,0,0,0])
            curr_channel += 6
        elif light['type'] == 'strobe':
            control_dict[light['name']] = controller.add_fixture(Strobe(name=light['name'], start_channel=curr_channel))
            # flash the light to make sure it's working
            control_dict[light['name']].set_channels([255,255])
            time.sleep(0.5)
            control_dict[light['name']].set_channels([0,0])
            curr_channel += 2

    return controller, control_dict

class LightController(threading.Thread):
    def __init__(self, audio_listener, profile_name, scene_manager):
        threading.Thread.__init__(self)
        self.audio_listener = audio_listener
        self.profile = load_profile(profile_name)
        self.light_names = [i['name'] for i in self.profile['lights']]
        self.dmx_controller, self.controller_dict = load_controller(self.profile)
        self.scene_manager = scene_manager
        self.running = threading.Event()
        self.fft_data = None
        self.scene_changed = threading.Event()

    def turn_off_all_lights(self):
        for light in self.profile['lights']:
            if light['type'] == 'dimmer':
                self.controller_dict[light['name']].dim(0)
            elif light['type'] == 'rgb':
                self.controller_dict[light['name']].set_channels([0,0,0,0,0,0])
            elif light['type'] == 'strobe':
                self.controller_dict[light['name']].set_channels([0,0])

    def change_scene(self, scene_name):
        # first turn off all the lights
        self.turn_off_all_lights()
        self.scene_manager.set_scene(scene_name)
        self.scene_changed.set()

    def run(self):
        self.running.set()
        while self.running.is_set():
            if self.scene_changed.is_set():
                #print(f"Changing to scene: {self.scene_manager.current_scene['name']}")
                self.scene_changed.clear()
                
                # # Apply the new scene immediately
                # if self.scene_manager.current_scene['type'] == 'static':
                #     self.send_static()
            
            # if self.scene_manager.current_scene['type'] == 'dynamic':
            if not self.audio_listener.fft_queue.empty():
                try:
                    self.send_dynamic()
                except Exception as e:
                    print(f"Error sending dynamic data: {str(e)}")
            # elif self.scene_manager.current_scene['type'] == 'static':
            #     # For static scenes, we only need to update occasionally
            #     time.sleep(0.1)  # Adjust this value as needed
            
    def send_dynamic(self):
        # Fetch FFT data once for all lights
        try:
            # get the most recent FFT data
            fft_data = self.audio_listener.fft_queue.get_nowait()
        except queue.Empty:
            print("No FFT data available")
            return

        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
                continue  # Skip lights not in the profile

            if light['modulator'] == 'fft':
                if light['type'] == 'dimmer':
                    dmx_value = fft_to_dimmer(fft_data, light['frequency_range'], light['power_range'], light['brightness_range'])
                    self.controller_dict[light['name']].dim(dmx_value)
                elif light['type'] == 'rgb':
                    dmx_values = fft_to_rgb(fft_data, frange=light['frequency_range'], prange=light['power_range'], brange=light['brightness_range'], color=light['color'], strobe=light['strobe'])
                    self.controller_dict[light['name']].set_channels(dmx_values)
                elif light['type'] == 'strobe':
                    dmx_values = fft_to_strobe(fft_data, light['frequency_range'], light['power_range'][0])
                    self.controller_dict[light['name']].set_channels(dmx_values)

            elif light['modulator'] == 'bool':
                if light['type'] == 'dimmer':
                    self.controller_dict[light['name']].dim(light['brightness'])
                elif light['type'] == 'rgb':
                    self.controller_dict[light['name']].set_channels(bool_rgb(light))
                elif light['type'] == 'strobe':
                    self.controller_dict[light['name']].set_channels(light['speed'], light['brightness'])

            elif light['modulator'] == 'time':
                try:
                    if light['type'] == 'dimmer':
                        self.controller_dict[light['name']].dim(time_dimmer(light))
                    elif light['type'] == 'rgb':
                        self.controller_dict[light['name']].set_channels(time_rgb(light))
                    elif light['type'] == 'strobe':
                        self.controller_dict[light['name']].set_channels(time_strobe(light))
                except Exception as e:
                    print(f"Error sending time data: {str(e)}")

    def stop(self):
        self.running.clear()

def main():
    audio_listener = AudioListener()  # Make sure this is imported or defined
    scene_manager = SceneManager('scenes')
    light_controller = LightController(audio_listener, 'testing', scene_manager)
    
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






