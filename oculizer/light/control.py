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
from PyDMXControl.controllers import OpenDMXController # type: ignore
from PyDMXControl.profiles.Generic import Dimmer, Custom # type: ignore
from oculizer.custom_profiles.RGB import RGB
from oculizer.custom_profiles.ADJ_strobe import Strobe
from oculizer.scenes import SceneManager
from oculizer.light.mapping import process_light, scale_mfft, color_to_rgb
from oculizer.config import audio_parameters
from oculizer.utils import load_json
import threading
import queue
import time
from pathlib import Path
from oculizer.light.effects import reset_effect_states
from oculizer.light.orchestrators import ORCHESTRATORS

n_channels = {
    'dimmer': 1,
    'rgb': 6,
    'strobe': 2,
    'laser': 10,
    'rockville864': 39
}

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
        self.current_orchestrator = None
        # Set scene_changed event to trigger initial orchestrator setup
        self.scene_changed.set()

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
        max_retries = 3
        retry_delay = 1.0  # seconds
        last_error = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Retrying DMX connection (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                
                controller = OpenDMXController()
                control_dict = {}
                curr_channel = 1
                sleeptime = 0.1

                # this will flash each light as it loads it into the controller
                # this is useful for debugging to ensure that each light is being loaded correctly
                
                for light in self.profile['lights']:
                    if light['type'] == 'dimmer':
                        control_dict[light['name']] = controller.add_fixture(Dimmer(name=light['name'], start_channel=curr_channel))
                        n_channels = n_channels['dimmer']
                        control_dict[light['name']].n_channels = n_channels
                        curr_channel += n_channels
                        control_dict[light['name']].dim(255)
                        time.sleep(sleeptime)
                        control_dict[light['name']].dim(0)

                    elif light['type'] == 'rgb':
                        control_dict[light['name']] = controller.add_fixture(RGB(name=light['name'], start_channel=curr_channel))
                        n_channels = n_channels['rgb']
                        control_dict[light['name']].n_channels = n_channels
                        curr_channel += n_channels
                        control_dict[light['name']].set_channels([255] * n_channels)
                        time.sleep(sleeptime)
                        control_dict[light['name']].set_channels([0] * n_channels)

                    elif light['type'] == 'strobe':
                        control_dict[light['name']] = controller.add_fixture(Strobe(name=light['name'], start_channel=curr_channel))
                        n_channels = n_channels['strobe']
                        control_dict[light['name']].n_channels = n_channels
                        curr_channel += n_channels
                        control_dict[light['name']].set_channels([255] * n_channels)
                        time.sleep(sleeptime)
                        control_dict[light['name']].set_channels([0] * n_channels)

                    elif light['type'] == 'laser':
                        laser_fixture = controller.add_fixture(Custom(name=light['name'], start_channel=curr_channel, channels=10))
                        control_dict[light['name']] = laser_fixture
                        n_channels = n_channels['laser']
                        control_dict[light['name']].n_channels = n_channels
                        curr_channel += n_channels
                        laser_fixture.set_channels([0] * n_channels)
                        time.sleep(sleeptime)
                        laser_fixture.set_channels([128, 255] + [0] * (n_channels - 2))
                        time.sleep(sleeptime)
                        laser_fixture.set_channels([0] * n_channels)

                    elif light['type'] == 'rockville864':
                        control_dict[light['name']] = controller.add_fixture(Custom(name=light['name'], start_channel=curr_channel, channels=39))
                        n_channels = n_channels['rockville864']
                        control_dict[light['name']].n_channels = n_channels
                        curr_channel += n_channels
                        control_dict[light['name']].set_channels([0] * n_channels)
                        time.sleep(sleeptime)
                        control_dict[light['name']].set_channels([255] * n_channels)
                        time.sleep(sleeptime)
                        control_dict[light['name']].set_channels([0] * n_channels)

                return controller, control_dict

            except IOError as e:
                last_error = e
                print(f"Failed to connect to DMX interface: {str(e)}")
                if attempt < max_retries - 1:
                    print("Will retry after unplugging and replugging the device...")
                    continue
                
                print("\nTroubleshooting steps:")
                print("1. Unplug and replug your DMX interface")
                print("2. Check if the device shows up in 'System Information > USB'")
                print("3. Try a different USB port")
                print("4. If using a USB hub, try connecting directly to the computer")
                raise RuntimeError("Failed to connect to DMX interface after multiple attempts") from last_error
            
            except Exception as e:
                print(f"Unexpected error while setting up DMX controller: {str(e)}")
                raise

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
            print("\nScene change detected, initializing orchestrator...")
            self.scene_changed.clear()
            self.turn_off_all_lights()
            # Initialize orchestrator if configured in new scene
            if 'orchestrator' in self.scene_manager.current_scene:
                print(f"Found orchestrator config: {self.scene_manager.current_scene['orchestrator']}")
                orch_config = self.scene_manager.current_scene['orchestrator']
                orch_type = orch_config['type']
                if orch_type in ORCHESTRATORS:
                    print(f"Creating orchestrator of type: {orch_type}")
                    self.current_orchestrator = ORCHESTRATORS[orch_type](orch_config['config'])
                    print(f"Orchestrator initialized: {self.current_orchestrator}")
                else:
                    print(f"Error: Unknown orchestrator type '{orch_type}'")
            else:
                print("No orchestrator configured in scene")

        try:
            mfft_data = self.mfft_queue.get(block=False)
        except queue.Empty:
            return

        current_time = time.time()

        # Get orchestrator modifications if orchestrator exists
        modifications = {}
        if self.current_orchestrator:
            modifications = self.current_orchestrator.process(
                self.light_names,
                mfft_data,
                current_time
            )

        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
                # Skip lights that aren't in the profile
                continue

            try:
                # Check if light is active according to orchestrator
                light_mods = modifications.get(light['name'], {'active': True, 'modifiers': {}})
                
                if not light_mods['active']:
                    # Light is disabled by orchestrator - turn it off
                    self.controller_dict[light['name']].set_channels([0] * self.controller_dict[light['name']].n_channels)
                    continue

                # Process light based on configuration
                dmx_values = process_light(light, mfft_data, current_time, modifiers=light_mods['modifiers'])
                if dmx_values is not None:
                    self.controller_dict[light['name']].set_channels(dmx_values)

            except Exception as e:
                print(f"Error processing light {light['name']}: {str(e)} (Error type: {type(e).__name__})")

    def change_scene(self, scene_name):
        self.turn_off_all_lights()
        # Reset all effect states before changing scene
        reset_effect_states()
        self.scene_manager.set_scene(scene_name)
        # Reset orchestrator when changing scenes
        self.current_orchestrator = None
        self.scene_changed.set()
        self.process_audio_and_lights()  # Apply the new scene immediately

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
            
            if light_type == 'rockville864':
                # Special handling for rockville - set all 39 channels to 0
                light_fixture.set_channels([0] * light_fixture.n_channels)
            elif light_type == 'laser':
                # Special handling for laser - set all channels to 0
                light_fixture.set_channels([0] * light_fixture.n_channels)
            elif light_type == 'rgb':
                # RGB fixtures use 6 channels
                light_fixture.set_channels([0] * light_fixture.n_channels)
            elif light_type == 'strobe':
                # Strobe fixtures use 2 channels
                light_fixture.set_channels([0] * light_fixture.n_channels)
            elif hasattr(light_fixture, 'dim'):
                # Only use dim for actual dimmer fixtures
                light_fixture.dim(0)
            else:
                # Fallback - get number of channels from fixture
                light_fixture.set_channels([0] * light_fixture.n_channels)
        
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





