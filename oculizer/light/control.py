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
from oculizer.light.mapping import process_light, color_to_index
from oculizer.config import audio_parameters
import threading
import queue
import os
import json
from pathlib import Path
import sounddevice as sd
import numpy as np
from scipy.fftpack import rfft
from librosa.feature import mfcc

from oculizer.utils import load_json 
import time

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']

def get_blackhole_device_idx():
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'BlackHole' in device['name']:
            return i, device['name']
    return None, None

def get_features(audio_data):
    return np.abs(rfft(audio_data))

def load_profile(profile_name):
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    profile_path = project_root / 'profiles' / f'{profile_name}.json'
    with open(profile_path, 'r') as f:
        profile = json.load(f)
    
    return profile

def get_features(audio_data, sr, n_mfcc=13):

    try:
        mfcc_features = mfcc(y=audio_data, sr=sr, n_mfcc=n_mfcc)
    except Exception as e:
        return None
    mfcc_mean = np.mean(np.abs(mfcc_features), axis=1)
    #mfcc_std = np.std(mfcc_features, axis=1)
    
    # Concatenate mean and std to get a feature vector
    feature_vector = np.concatenate([mfcc_mean])#, mfcc_std])
    
    return feature_vector

def load_controller(profile):
    try:
        controller = OpenDMXController()
    except Exception as e:
        print(f"Error loading DMX controller: {str(e)}")
        return None, None
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

class Oculizer(threading.Thread):
    def __init__(self, profile_name, sample_rate=SAMPLERATE, block_size=BLOCKSIZE, channels=1, n_mfcc=13):
        threading.Thread.__init__(self)
        self.profile_name = profile_name
        self.sample_rate = audio_parameters['SAMPLERATE']
        self.block_size = audio_parameters['BLOCKSIZE']
        self.n_mfcc = n_mfcc
        self.channels = channels
        #self.fft_queue = queue.Queue(maxsize=1)  # Only keep the most recent FFT data
        self.mfcc_queue = queue.Queue(maxsize=1)  # Only keep the most recent MFCC data
        self.device_idx, self.device_name = get_blackhole_device_idx()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        
        # Light controller initialization
        self.profile = load_profile(self.profile_name)
        self.light_names = [i['name'] for i in self.profile['lights']]
        self.dmx_controller, self.controller_dict = load_controller(self.profile)
        self.scene_manager = SceneManager('scenes')
        self.scene_changed = threading.Event()

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.error_queue.put(f"Audio callback error: {status}")
        try:
            audio_data = indata.copy().flatten()
            mfcc_data = get_features(audio_data, self.sample_rate, self.n_mfcc)
            if self.mfcc_queue.full():
                try:
                    self.mfcc_queue.get_nowait()  # Discard old data
                except queue.Empty:
                    pass  # Queue was emptied by another thread, which is fine
            self.mfcc_queue.put(mfcc_data)
        except Exception as e:
            self.error_queue.put(f"Error processing audio data: {str(e)}")

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
                    time.sleep(0.001)  # Small delay to prevent busy-waiting
        except Exception as e:
            self.error_queue.put(f"Error in audio stream: {str(e)}")

    def process_audio_and_lights(self):
        if self.scene_changed.is_set():
            self.scene_changed.clear()
            self.turn_off_all_lights()

        try:
            mfcc_data = self.mfcc_queue.get(block=False)
        except queue.Empty:
            return  # No new data, skip this iteration

        current_time = time.time()

        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
                continue

            dmx_values = process_light(light, mfcc_data, current_time)
            
            if dmx_values is not None:
                if light['type'] == 'dimmer':
                    self.controller_dict[light['name']].dim(dmx_values[0])
                elif light['type'] in ['rgb', 'strobe']:
                    self.controller_dict[light['name']].set_channels(dmx_values)

    def change_scene(self, scene_name):
        self.scene_manager.set_scene(scene_name)
        self.scene_changed.set()

    def turn_off_all_lights(self):
        for light in self.profile['lights']:
            if light['type'] == 'dimmer':
                self.controller_dict[light['name']].dim(0)
            elif light['type'] == 'rgb':
                self.controller_dict[light['name']].set_channels([0,0,0,0,0,0])
            elif light['type'] == 'strobe':
                self.controller_dict[light['name']].set_channels([0,0])

    def stop(self):
        self.running.clear()

    def get_errors(self):
        errors = []
        while not self.error_queue.empty():
            errors.append(self.error_queue.get_nowait())
        return errors

def main():
    controller = Oculizer('testing', scene_manager)
    controller.scene_manager.set_scene('hell')
    print("Starting Oculizer...")
    controller.start()
    try:
        while True:
            try:
                mfcc_data = controller.mfcc_queue.get(timeout=0.1)
                print(mfcc_data)
                time.sleep(0.1)

            except queue.Empty:
                pass

            except KeyboardInterrupt:
                print("Stopping Oculizer...")
                controller.stop()
                controller.join()
                break

    except KeyboardInterrupt:
        print("Stopping Oculizer...")
        controller.stop()
        controller.join()

if __name__ == "__main__":
    main()






