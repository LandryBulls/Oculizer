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
from oculizer.light.enttec_controller import EnttecProController
from oculizer.light.dmx_config import get_dmx_config
from oculizer.scenes import SceneManager
from oculizer.light.mapping import process_light, scale_mfft
from oculizer.config import audio_parameters
from oculizer.utils import load_json
import threading
import queue
import time
from pathlib import Path
from oculizer.light.effects import reset_effect_states
from oculizer.light.orchestrators import ORCHESTRATORS

global n_channels
n_channels = {
    'dimmer': 1,
    'rgb': 6,
    'strobe': 2,
    'laser': 10,
    'rockville864': 39,
    'pinspot': 6
}

class Oculizer(threading.Thread):
    def __init__(self, profile_name, scene_manager, input_device='cable', 
                 scene_prediction_enabled=False, scene_prediction_device=None, predictor_version='v1'):
        threading.Thread.__init__(self)
        self.profile_name = profile_name
        self.input_device = input_device.lower()
        self.sample_rate = audio_parameters['SAMPLERATE']
        self.block_size = audio_parameters['BLOCKSIZE']
        self.hop_length = audio_parameters['HOP_LENGTH']
        self.channels = 1
        self.mfft_queue = queue.Queue(maxsize=1)
        self.device_idx = self._get_audio_device_idx()
        self.running = threading.Event()
        self.scene_manager = scene_manager
        self.profile = self._load_profile()
        self.light_names = [i['name'] for i in self.profile['lights']]
        self.dmx_controller, self.controller_dict = self._load_controller()
        self.scene_changed = threading.Event()
        self.current_orchestrator = None
        # Set scene_changed event to trigger initial orchestrator setup
        self.scene_changed.set()
        
        # Scene prediction setup
        self.scene_prediction_enabled = scene_prediction_enabled
        self.scene_prediction_device = scene_prediction_device
        self.predictor_version = predictor_version
        self.scene_predictor = None
        self.prediction_stream = None
        self.prediction_audio_queue = queue.Queue()
        self.prediction_audio_cache = None  # Will be initialized if needed
        self.scene_cache = None
        self.current_predicted_scene = None
        self.latest_prediction = None  # Store the latest raw prediction
        self.current_cluster = None
        self.last_prediction_time = 0
        self.prediction_interval = 0.1
        self.prediction_count = 0
        
        if scene_prediction_enabled:
            self._init_scene_prediction()

    def _get_audio_device_idx(self):
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if self.input_device == 'blackhole' and 'BlackHole' in device['name']:
                return i
            elif self.input_device == 'scarlett' and 'Scarlett' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.input_device == 'cable' and 'CABLE' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.input_device == 'cable_input' and 'CABLE Input' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.input_device == 'cable_output' and 'CABLE Output' in device['name'] and device['max_input_channels'] > 0:
                return i
        
        # If device not found, print available devices and raise error
        print("\nAvailable audio input devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # Only show input devices
                print(f"{i}: {device['name']}")
        
        raise ValueError(f"Audio input device '{self.input_device}' not found. Please check available devices above.")

    def _init_scene_prediction(self):
        """Initialize scene prediction components."""
        from oculizer.scene_predictors import get_predictor
        from collections import deque
        import librosa
        
        # Get the ScenePredictor class for the specified version
        ScenePredictor = get_predictor(self.predictor_version)
        
        # Initialize scene predictor (32kHz for EfficientAT model)
        self.scene_predictor = ScenePredictor(sr=32000)
        
        # Initialize audio cache for 4 seconds at 32kHz
        self.prediction_audio_cache = deque(maxlen=32000 * 4)
        
        # Initialize scene cache for mode calculation (50 predictions ~5 seconds)
        self.scene_cache = deque(maxlen=50)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Scene prediction initialized with {self.predictor_version} predictor (device: {self.scene_prediction_device})")

    def prediction_audio_callback(self, indata, frames, time_info, status):
        """Callback for scene prediction audio stream."""
        # Check if still running to avoid queue operations after stop
        if not self.running.is_set():
            return
            
        if status:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Prediction audio status: {status}")
        
        # Convert stereo to mono by averaging channels
        if len(indata.shape) > 1:
            mono_data = np.mean(indata, axis=1)
        else:
            mono_data = indata.flatten()
        
        # Add to queue for processing (non-blocking to avoid hanging)
        try:
            self.prediction_audio_queue.put_nowait(mono_data.copy())
        except queue.Full:
            pass  # Drop frame if queue is full to avoid blocking

    def update_scene_prediction(self):
        """Process scene prediction from audio cache."""
        if not self.scene_prediction_enabled:
            return
        
        current_time = time.time()
        
        # Check if it's time for prediction
        if current_time - self.last_prediction_time < self.prediction_interval:
            return
        
        # Process any queued audio data
        while not self.prediction_audio_queue.empty():
            try:
                audio_chunk = self.prediction_audio_queue.get_nowait()
                self.prediction_audio_cache.extend(audio_chunk)
            except queue.Empty:
                break
        
        # Check if we have enough cached audio (4 seconds at 32kHz)
        if len(self.prediction_audio_cache) < 32000 * 4:
            return
        
        try:
            # Convert cache to numpy array
            audio_data = np.array(self.prediction_audio_cache)
            
            # Resample if needed (prediction cache is at system sample rate, need 32kHz)
            # Note: In dual-stream mode, prediction device might have different sample rate
            prediction_sample_rate = 48000  # Typical for CABLE Output
            if prediction_sample_rate != 32000:
                import librosa
                audio_data = librosa.resample(
                    audio_data,
                    orig_sr=prediction_sample_rate,
                    target_sr=32000
                )
            
            # Make prediction
            scene, cluster = self.scene_predictor.predict(audio_data, return_cluster=True)
            self.latest_prediction = scene  # Store the raw prediction
            self.scene_cache.append(scene)
            
            # Update current scene using mode of recent predictions
            if self.scene_cache:
                try:
                    from statistics import mode
                    self.current_predicted_scene = mode(self.scene_cache)
                except:
                    # If no unique mode (tie), use the most recent
                    self.current_predicted_scene = self.scene_cache[-1]
            
            self.current_cluster = cluster
            self.last_prediction_time = current_time
            self.prediction_count += 1
            
            # Log prediction periodically with cache info
            if self.prediction_count % 10 == 0:
                import logging
                from collections import Counter
                logger = logging.getLogger(__name__)
                
                # Get distribution of scenes in cache for debugging
                scene_counts = Counter(self.scene_cache)
                cache_info = f"Cache({len(self.scene_cache)}): {dict(scene_counts)}"
                
                logger.info(
                    f"[{self.prediction_count:04d}] Prediction: {scene}, "
                    f"Mode: {self.current_predicted_scene}, Cluster: {cluster} | {cache_info}"
                )
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in scene prediction: {e}")

    def _create_dimmer_fixture(self, name, start_channel, channels, controller):
        """Create a dimmer fixture for EnttecProController."""
        class DimmerFixture:
            def __init__(self, name, start_channel, channels, controller):
                self.name = name
                self.start_channel = start_channel
                self.n_channels = channels
                self.controller = controller
            
            def dim(self, value):
                """Set dimmer value."""
                self.controller.set_channel(self.start_channel, value)
            
            def set_channels(self, values):
                """Set channel values."""
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        self.controller.set_channel(self.start_channel + i, value)
        
        return DimmerFixture(name, start_channel, channels, controller)

    def _create_rgb_fixture(self, name, start_channel, channels, controller):
        """Create an RGB fixture for EnttecProController."""
        class RGBFixture:
            def __init__(self, name, start_channel, channels, controller):
                self.name = name
                self.start_channel = start_channel
                self.n_channels = channels
                self.controller = controller
            
            def set_channels(self, values):
                """Set RGB channel values."""
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        self.controller.set_channel(self.start_channel + i, value)
        
        return RGBFixture(name, start_channel, channels, controller)

    def _create_strobe_fixture(self, name, start_channel, channels, controller):
        """Create a strobe fixture for EnttecProController."""
        class StrobeFixture:
            def __init__(self, name, start_channel, channels, controller):
                self.name = name
                self.start_channel = start_channel
                self.n_channels = channels
                self.controller = controller
            
            def set_channels(self, values):
                """Set strobe channel values."""
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        self.controller.set_channel(self.start_channel + i, value)
        
        return StrobeFixture(name, start_channel, channels, controller)

    def _create_laser_fixture(self, name, start_channel, channels, controller):
        """Create a laser fixture for EnttecProController."""
        class LaserFixture:
            def __init__(self, name, start_channel, channels, controller):
                self.name = name
                self.start_channel = start_channel
                self.n_channels = channels
                self.controller = controller
            
            def set_channels(self, values):
                """Set laser channel values."""
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        self.controller.set_channel(self.start_channel + i, value)
        
        return LaserFixture(name, start_channel, channels, controller)

    def _create_rockville_fixture(self, name, start_channel, channels, controller):
        """Create a Rockville fixture for EnttecProController."""
        class RockvilleFixture:
            def __init__(self, name, start_channel, channels, controller):
                self.name = name
                self.start_channel = start_channel
                self.n_channels = channels
                self.controller = controller
            
            def set_channels(self, values):
                """Set Rockville channel values."""
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        self.controller.set_channel(self.start_channel + i, value)
        
        return RockvilleFixture(name, start_channel, channels, controller)

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
                
                # Use EnttecProController for DMXKing ultraDMX MAX
                dmx_config = get_dmx_config()
                controller = EnttecProController(
                    port=dmx_config['port'],
                    baudrate=dmx_config['baudrate'],
                    timeout=dmx_config['timeout']
                )
                control_dict = {}
                curr_channel = 1
                sleeptime = 0.1

                # Access the global n_channels dictionary
                global n_channels
                
                # Create custom fixture objects for EnttecProController
                for light in self.profile['lights']:
                    if light['type'] == 'dimmer':
                        channels = n_channels['dimmer']
                        fixture = self._create_dimmer_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.dim(255)
                        time.sleep(sleeptime)
                        fixture.dim(0)

                    elif light['type'] == 'rgb':
                        channels = n_channels['rgb']
                        fixture = self._create_rgb_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.set_channels([255] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([0] * channels)

                    elif light['type'] == 'strobe':
                        channels = n_channels['strobe']
                        fixture = self._create_strobe_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.set_channels([255] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([0] * channels)

                    elif light['type'] == 'laser':
                        channels = n_channels['laser']
                        fixture = self._create_laser_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.set_channels([0] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([128, 255] + [0] * (channels - 2))
                        time.sleep(sleeptime)
                        fixture.set_channels([0] * channels)

                    elif light['type'] == 'rockville864':
                        channels = n_channels['rockville864']
                        fixture = self._create_rockville_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.set_channels([0] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([255] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([0] * channels)

                    elif light['type'] == 'pinspot':
                        channels = n_channels['pinspot']
                        fixture = self._create_rgb_fixture(light['name'], curr_channel, channels, controller)
                        control_dict[light['name']] = fixture
                        curr_channel += channels
                        fixture.set_channels([0] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([255] * channels)
                        time.sleep(sleeptime)
                        fixture.set_channels([0] * channels)

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
        
        # Handle stereo input - average channels 1 and 2 for Scarlett loopback
        if len(indata.shape) > 1 and indata.shape[1] >= 2:
            # Average the first two channels (0 and 1, which are channels 1 and 2)
            audio_data = np.mean(indata[:, :2], axis=1)
        else:
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
        
        # Determine channels for main FFT stream
        # Use 2 channels for Scarlett to capture loopback on channels 1&2
        device_info = sd.query_devices(self.device_idx)
        main_channels = 2 if 'Scarlett' in device_info['name'] else self.channels
        
        try:
            # Start main audio stream for FFT/DMX control
            with sd.InputStream(
                device=self.device_idx,
                channels=main_channels,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self.audio_callback
            ):
                # Start scene prediction stream if enabled and separate device specified
                if self.scene_prediction_enabled and self.scene_prediction_device is not None:
                    pred_device_info = sd.query_devices(self.scene_prediction_device)
                    pred_channels = 2 if ('Scarlett' in pred_device_info['name'] or 
                                         'CABLE' in pred_device_info['name']) else 1
                    
                    self.prediction_stream = sd.InputStream(
                        device=self.scene_prediction_device,
                        channels=pred_channels,
                        samplerate=48000,  # Typical for CABLE Output
                        blocksize=1024,
                        callback=self.prediction_audio_callback
                    )
                    self.prediction_stream.start()
                    
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Started prediction stream on device {self.scene_prediction_device}")
                
                # Main processing loop
                while self.running.is_set():
                    self.process_audio_and_lights()
                    
                    # Update scene prediction periodically
                    if self.scene_prediction_enabled:
                        self.update_scene_prediction()
                    
                    time.sleep(0.001)
                    
        except Exception as e:
            print(f"Error in audio stream: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up prediction stream if not already stopped
            if self.prediction_stream:
                try:
                    self.prediction_stream.stop()
                    self.prediction_stream.close()
                    self.prediction_stream = None
                except Exception as e:
                    print(f"Error closing prediction stream in finally: {e}")    

    def process_audio_and_lights(self):
        if self.scene_changed.is_set():
            self.scene_changed.clear()
            self.turn_off_all_lights()
            # Initialize orchestrator if configured in new scene
            if 'orchestrator' in self.scene_manager.current_scene:
                orch_config = self.scene_manager.current_scene['orchestrator']
                orch_type = orch_config['type']
                if orch_type in ORCHESTRATORS:
                    self.current_orchestrator = ORCHESTRATORS[orch_type](orch_config['config'])
                else:
                    print(f"Orchestrator type {orch_type} not found")
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
            # All fixture types now use set_channels method
            light_fixture.set_channels([0] * light_fixture.n_channels)
        
        time.sleep(0.1)  # Small delay to ensure DMX signals are processed

    def stop(self):
        self.running.clear()
        
        # Stop and close prediction stream first
        if self.prediction_stream:
            try:
                self.prediction_stream.stop()
                self.prediction_stream.close()
                self.prediction_stream = None
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error stopping prediction stream: {e}")
        
        # Close DMX controller connection
        if hasattr(self, 'dmx_controller') and self.dmx_controller:
            self.dmx_controller.close()

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





