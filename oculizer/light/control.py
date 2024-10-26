"""
light_control.py

Description: This script provides all the lighting control. It is responsible for controlling the DMX lights and RGB lights, loading profiles, 
setting up the DMX controller, providing functions for sending signals to the DMX controller, and providing functions for controlling the RGB lights.

Author: Landry Bulls
Date: 8/20/24
"""

import numpy as np
import sounddevice as sd
from librosa.feature import melspectrogram
from PyDMXControl.controllers import OpenDMXController
from PyDMXControl.profiles.Generic import Dimmer, Custom
from oculizer.custom_profiles.RGB import RGB
from oculizer.custom_profiles.ADJ_strobe import Strobe
from oculizer.scenes import SceneManager
from oculizer.light.mapping import process_light, scale_mfft
from oculizer.config import audio_parameters
from oculizer.utils import load_json
import threading
import queue
import time
from pathlib import Path

class Oculizer(threading.Thread):
    def __init__(self, profile_name, scene_manager):
        threading.Thread.__init__(self)
        self.profile_name = profile_name
        self.sample_rate = audio_parameters['SAMPLERATE']
        self.block_size = audio_parameters['BLOCKSIZE']
        self.hop_length = audio_parameters['HOP_LENGTH']
        self.channels = 1
        self.mfft_queue = queue.Queue(maxsize=1)
        self.device_idx = self._get_blackhole_device_idx()
        self.running = threading.Event()
        self.scene_manager = scene_manager
        self.profile = self._load_profile()
        self.light_names = [i['name'] for i in self.profile['lights']]
        self.dmx_controller, self.controller_dict = self._load_controller()
        self.scene_changed = threading.Event()

    def _get_blackhole_device_idx(self):
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if 'BlackHole' in device['name']:
                return i
        return None

    def _load_profile(self):
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent.parent
        profile_path = project_root / 'profiles' / f'{self.profile_name}.json'
        return load_json(profile_path)

    def _load_controller(self):
        controller = OpenDMXController()
        control_dict = {}
        curr_channel = 1
        sleeptime = 0.1

        for light in self.profile['lights']:
            if light['type'] == 'dimmer':
                control_dict[light['name']] = controller.add_fixture(Dimmer(name=light['name'], start_channel=curr_channel))
                curr_channel += 1
                control_dict[light['name']].dim(255)
                time.sleep(sleeptime)
                control_dict[light['name']].dim(0)

            elif light['type'] == 'rgb':
                control_dict[light['name']] = controller.add_fixture(RGB(name=light['name'], start_channel=curr_channel))
                curr_channel += 6
                control_dict[light['name']].set_channels([255, 255, 255, 255, 255, 0])
                time.sleep(sleeptime)
                control_dict[light['name']].set_channels([0, 0, 0, 0, 0, 0])

            elif light['type'] == 'strobe':
                control_dict[light['name']] = controller.add_fixture(Strobe(name=light['name'], start_channel=curr_channel))
                curr_channel += 2
                control_dict[light['name']].set_channels([255, 255])
                time.sleep(sleeptime)
                control_dict[light['name']].set_channels([0, 0])

            elif light['type'] == 'laser':
                # Create a custom fixture with 10 channels for laser
                laser_fixture = controller.add_fixture(Custom(name=light['name'], start_channel=curr_channel, channels=10))
                control_dict[light['name']] = laser_fixture
                curr_channel += 10
                
                # Initialize with standby mode
                laser_fixture.set_channels([0] * 10)
                time.sleep(sleeptime)
                # Test pattern
                laser_fixture.set_channels([128, 255] + [0] * 8)
                time.sleep(sleeptime)
                # Back to standby
                laser_fixture.set_channels([0] * 10)

        return controller, control_dict

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio callback error: {status}")
            return
        
        audio_data = indata.copy().flatten()
        mfft_data = np.mean(melspectrogram(y=audio_data, sr=self.sample_rate, n_fft=self.block_size, hop_length=self.hop_length), axis=1)
        mfft_data = scale_mfft(mfft_data)
        
        if self.mfft_queue.full():
            try:
                self.mfft_queue.get_nowait()
            except queue.Empty:
                pass
        self.mfft_queue.put(mfft_data)

    def run(self):
        self.running.set()
        try:
            with sd.InputStream(
                device=self.device_idx,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self.audio_callback
            ):
                while self.running.is_set():
                    self.process_audio_and_lights()
                    time.sleep(0.001)
        except Exception as e:
            print(f"Error in audio stream: {str(e)}")
            print(f"Origin script: {e.__traceback__.tb_frame.f_globals['__file__']}")    

    def process_audio_and_lights(self):
        if self.scene_changed.is_set():
            self.scene_changed.clear()
            self.turn_off_all_lights()

        try:
            mfft_data = self.mfft_queue.get(block=False)
        except queue.Empty:
            return

        current_time = time.time()

        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
                # Skip lights that aren't in the profile instead of trying to turn them off
                continue

            try:
                dmx_values = process_light(light, mfft_data, current_time)
                if dmx_values is not None:
                    if light['type'] == 'dimmer':
                        self.controller_dict[light['name']].dim(dmx_values[0])
                    elif light['type'] == 'rgb':
                        self.controller_dict[light['name']].set_channels(dmx_values[:6])
                    elif light['type'] == 'strobe':
                        self.controller_dict[light['name']].set_channels(dmx_values[:2])
                    elif light['type'] == 'laser':
                        # Ensure we're sending all 10 channels for laser
                        channels = dmx_values[:10]
                        # Pad with zeros if needed
                        if len(channels) < 10:
                            channels.extend([0] * (10 - len(channels)))
                        self.controller_dict[light['name']].set_channels(channels)

            except Exception as e:
                print(f"Error processing light {light['name']}: {str(e)}")


    def change_scene(self, scene_name):
        self.turn_off_all_lights()
        self.scene_manager.set_scene(scene_name)
        self.scene_changed.set()
        self.process_audio_and_lights()  # Apply the new scene immediately
        #self.dmx_controller.update()  # Ensure new scene DMX signals are sent

    def get_light_type(self, light_name):
        """Helper function to get light type from profile."""
        for light in self.profile['lights']:
            if light['name'] == light_name:
                return light['type']
        return None

    def turn_off_all_lights(self):
        for light_name, light_fixture in self.controller_dict.items():
            # Get the light type from the profile
            light_type = next((light['type'] for light in self.profile['lights'] if light['name'] == light_name), None)
            
            if light_type == 'laser':
                # Special handling for laser - set all channels to 0
                light_fixture.set_channels([0] * 10)
            elif hasattr(light_fixture, 'dim'):
                light_fixture.dim(0)
            elif hasattr(light_fixture, 'set_channels'):
                light_fixture.set_channels([0] * light_fixture.channels)
        
        time.sleep(0.1)  # Small delay to ensure DMX signals are processed

    def stop(self):
        self.running.clear()

def main():
    # init scene manager
    scene_manager = SceneManager('scenes')
    # set the initial scene to the test scene
    scene_manager.set_scene('testing')  
    # init the light controller with the name of the profile and the scene manager
    controller = Oculizer('testing', scene_manager)
    print("Starting Oculizer...")
    controller.start()
    
    try:
        while True:
            time.sleep(1)  # Main thread does nothing but keep the program alive
    except KeyboardInterrupt:
        print("Stopping Oculizer...")
        controller.stop()
        controller.join()

if __name__ == "__main__":
    main()






