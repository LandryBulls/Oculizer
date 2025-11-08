"""
light_control.py

Description: This script provides all the lighting control. It is responsible for controlling the DMX lights and RGB lights, loading profiles, 
setting up the DMX controller, providing functions for sending signals to the DMX controller, and providing functions for controlling the RGB lights.

Author: Landry Bulls
Date: 8/20/24
"""

import numpy as np
import sounddevice as sd
import librosa
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
                 scene_prediction_enabled=False, scene_prediction_device=None, predictor_version='v1',
                 average_dual_channels=False, scene_cache_size=25, prediction_channels=None):
        threading.Thread.__init__(self)
        self.profile_name = profile_name
        self.input_device = input_device.lower()
        self.sample_rate = audio_parameters['SAMPLERATE']
        self.block_size = audio_parameters['BLOCKSIZE']
        self.hop_length = audio_parameters['HOP_LENGTH']
        self.channels = 1
        self.average_dual_channels = average_dual_channels
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
        # Resolve prediction device (can be string name or integer index)
        self.scene_prediction_device = self._get_prediction_device_idx(scene_prediction_device) if scene_prediction_enabled else None
        self.predictor_version = predictor_version
        self.scene_cache_size = scene_cache_size
        self.prediction_channels_spec = prediction_channels  # Store the user specification
        self.prediction_channel_indices = None  # Will be parsed later
        self.scene_predictor = None
        self.prediction_stream = None
        self.prediction_audio_queue = queue.Queue(maxsize=100)  # Limit queue size
        self.prediction_audio_cache = None  # Will be initialized if needed
        self.scene_cache = None
        self.current_predicted_scene = None
        self.latest_prediction = None  # Store the latest raw prediction
        self.current_cluster = None
        self.last_prediction_time = 0
        self.prediction_interval = 0.1
        self.prediction_count = 0
        self.prediction_thread = None  # Separate thread for prediction processing
        self.prediction_lock = threading.Lock()  # Lock for thread-safe access
        
        # Audio quality monitoring
        self.audio_quality_check_interval = 100  # Check every N callbacks
        self.audio_callback_count = 0
        self.last_audio_rms = None
        self.audio_underrun_count = 0
        self.max_queue_depth_seen = 0  # Track maximum queue buildup
        
        if scene_prediction_enabled:
            self._init_scene_prediction()

    def _get_audio_device_idx(self):
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if self.input_device == 'blackhole' and 'BlackHole' in device['name']:
                return i
            elif self.input_device == 'scarlett' and ('Scarlett' in device['name'] or 'Focusrite' in device['name']) and device['max_input_channels'] > 0:
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

    def _parse_channel_spec(self, channel_spec, max_channels):
        """
        Parse channel specification string into list of 0-based indices.
        
        Examples:
            "1" -> [0] (channel 1)
            "1,2" -> [0, 1] (channels 1-2)
            "1-4" -> [0, 1, 2, 3] (channels 1-4)
            "1-16" -> [0, 1, ..., 15] (all 16 channels)
        
        Args:
            channel_spec: String specification of channels (1-based)
            max_channels: Maximum number of channels available
            
        Returns:
            List of 0-based channel indices
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            indices = []
            
            # Handle range notation (e.g., "1-16")
            if '-' in channel_spec:
                start, end = channel_spec.split('-')
                start_idx = int(start) - 1  # Convert to 0-based
                end_idx = int(end) - 1
                
                if start_idx < 0 or end_idx >= max_channels:
                    logger.warning(f"Channel range {channel_spec} out of bounds (1-{max_channels})")
                    return None
                
                indices = list(range(start_idx, end_idx + 1))
                
            # Handle comma-separated list (e.g., "1,2,3")
            elif ',' in channel_spec:
                for ch in channel_spec.split(','):
                    ch_idx = int(ch.strip()) - 1  # Convert to 0-based
                    if ch_idx < 0 or ch_idx >= max_channels:
                        logger.warning(f"Channel {int(ch.strip())} out of bounds (1-{max_channels})")
                        return None
                    indices.append(ch_idx)
                    
            # Handle single channel (e.g., "1")
            else:
                ch_idx = int(channel_spec) - 1  # Convert to 0-based
                if ch_idx < 0 or ch_idx >= max_channels:
                    logger.warning(f"Channel {channel_spec} out of bounds (1-{max_channels})")
                    return None
                indices = [ch_idx]
            
            logger.info(f"Using prediction channels: {[i+1 for i in indices]} (user-specified)")
            return indices
            
        except Exception as e:
            logger.error(f"Error parsing channel specification '{channel_spec}': {e}")
            return None
    
    def _get_prediction_device_idx(self, device_spec):
        """Get device index for prediction, handling both string names and integer indices."""
        if device_spec is None:
            return None
        
        # If it's already an integer, try to use it directly but validate
        if isinstance(device_spec, int):
            devices = sd.query_devices()
            if 0 <= device_spec < len(devices):
                return device_spec
            else:
                print(f"\nWarning: Device index {device_spec} is out of range.")
                # Fall back to searching for cable_output
                device_spec = 'cable_output'
        
        # If it's a string, search for matching device
        if isinstance(device_spec, str):
            device_name = device_spec.lower()
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device_name == 'blackhole' and 'BlackHole' in device['name'] and device['max_input_channels'] > 0:
                    return i
                elif device_name == 'scarlett' and ('Scarlett' in device['name'] or 'Focusrite' in device['name']) and device['max_input_channels'] > 0:
                    return i
                elif device_name == 'cable' and 'CABLE' in device['name'] and device['max_input_channels'] > 0:
                    return i
                elif device_name == 'cable_input' and 'CABLE Input' in device['name'] and device['max_input_channels'] > 0:
                    return i
                elif device_name == 'cable_output' and 'CABLE Output' in device['name'] and device['max_input_channels'] > 0:
                    return i
            
            # If device not found, print available devices and raise error
            print("\nAvailable audio input devices:")
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    print(f"{i}: {device['name']}")
            
            raise ValueError(f"Prediction audio device '{device_spec}' not found. Please check available devices above.")
        
        return device_spec

    def _init_scene_prediction(self):
        """Initialize scene prediction components."""
        from oculizer.scene_predictors import get_predictor
        from collections import deque
        import librosa
        
        # Get the ScenePredictor class for the specified version
        ScenePredictor = get_predictor(self.predictor_version)
        
        # Different predictor versions use different sample rates
        # v1, v3: 32kHz | v4, v5: 48kHz (trained at these rates, must match!)
        if self.predictor_version in ['v4', 'v5']:
            self.prediction_sr = 48000
        else:
            self.prediction_sr = 32000
        
        # Initialize scene predictor with correct sample rate
        self.scene_predictor = ScenePredictor(sr=self.prediction_sr)
        
        # Initialize audio cache for 4 seconds at predictor sample rate
        self.prediction_audio_cache = deque(maxlen=self.prediction_sr * 4)
        
        # Initialize scene cache with configurable size
        self.scene_cache = deque(maxlen=self.scene_cache_size)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Scene prediction initialized with {self.predictor_version} predictor at {self.prediction_sr}Hz (device: {self.scene_prediction_device})")
        logger.info(f"Scene cache size: {self.scene_cache_size} ({'instant response' if self.scene_cache_size == 1 else f'~{self.scene_cache_size * 0.1:.1f}s smoothing'})")
        
        # Validate device sample rate if we have a prediction device
        if self.scene_prediction_device is not None:
            try:
                device_info = sd.query_devices(self.scene_prediction_device)
                device_sr = device_info.get('default_samplerate', 48000)
                device_name = device_info.get('name', 'Unknown')
                logger.info(f"Prediction device '{device_name}' native sample rate: {device_sr}Hz")
                
                # Warn if device sample rate doesn't match what we expect
                if abs(device_sr - 48000) > 100:  # Allow small tolerance
                    logger.warning(f"⚠️  Prediction device sample rate ({device_sr}Hz) differs from expected 48000Hz!")
                    logger.warning("    This may cause audio quality issues. Consider configuring the device to 48kHz.")
            except Exception as e:
                logger.warning(f"Could not validate prediction device sample rate: {e}")

    def prediction_audio_callback(self, indata, frames, time_info, status):
        """Callback for scene prediction audio stream."""
        # Check if still running to avoid queue operations after stop
        if not self.running.is_set():
            return
            
        if status:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️  Prediction audio status: {status}")
            self.audio_underrun_count += 1
        
        # Extract specified channels and convert to mono
        if len(indata.shape) > 1 and self.prediction_channel_indices is not None:
            # Select specified channels and average them
            selected_channels = indata[:, self.prediction_channel_indices]
            if len(self.prediction_channel_indices) > 1:
                mono_data = np.mean(selected_channels, axis=1)
            else:
                mono_data = selected_channels.flatten()
        elif len(indata.shape) > 1:
            # Default: average all channels
            mono_data = np.mean(indata, axis=1)
        else:
            mono_data = indata.flatten()
        
        # Periodic audio quality monitoring
        self.audio_callback_count += 1
        if self.audio_callback_count % self.audio_quality_check_interval == 0:
            import logging
            logger = logging.getLogger(__name__)
            
            # Check RMS energy
            rms = np.sqrt(np.mean(mono_data ** 2))
            
            # Log if RMS is suspiciously low (possible silence/disconnection)
            if rms < 0.001:
                logger.warning(f"⚠️  Very low audio level detected (RMS: {rms:.6f}) - check audio routing")
            
            # Log if RMS changed dramatically (possible sample rate issues)
            if self.last_audio_rms is not None:
                rms_change = abs(rms - self.last_audio_rms) / (self.last_audio_rms + 1e-10)
                if rms_change > 10.0 and rms > 0.001:  # More than 10x change
                    logger.warning(f"⚠️  Large audio level change detected - possible audio quality issue")
            
            self.last_audio_rms = rms
            
            # Report underruns if any occurred
            if self.audio_underrun_count > 0:
                logger.warning(f"⚠️  {self.audio_underrun_count} audio buffer underruns detected in last {self.audio_quality_check_interval} callbacks")
                self.audio_underrun_count = 0
        
        # Add to queue for processing (non-blocking to avoid hanging)
        try:
            self.prediction_audio_queue.put_nowait(mono_data.copy())
        except queue.Full:
            pass  # Drop frame if queue is full to avoid blocking

    def prediction_processing_thread(self):
        """Separate thread for processing scene predictions (heavy CPU work)."""
        import librosa
        import logging
        from statistics import mode
        from collections import Counter
        
        logger = logging.getLogger(__name__)
        logger.info("Prediction processing thread started")
        
        while self.running.is_set():
            try:
                # Check queue depth before processing
                queue_depth = self.prediction_audio_queue.qsize()
                if queue_depth > self.max_queue_depth_seen:
                    self.max_queue_depth_seen = queue_depth
                    if queue_depth > 10:
                        logger.warning(f"⚠️  Audio queue depth: {queue_depth} (predictions may be lagging behind real-time)")
                
                # Process any queued audio data (with timeout to check running flag)
                try:
                    audio_chunk = self.prediction_audio_queue.get(timeout=0.5)
                    with self.prediction_lock:
                        self.prediction_audio_cache.extend(audio_chunk)
                except queue.Empty:
                    continue
                
                # Check if we have enough cached audio (4 seconds at predictor sample rate)
                with self.prediction_lock:
                    cache_length = len(self.prediction_audio_cache)
                
                if cache_length < self.prediction_sr * 4:
                    continue
                
                # Check if it's time for prediction
                current_time = time.time()
                if current_time - self.last_prediction_time < self.prediction_interval:
                    continue
                
                # FLUSH QUEUE: Drain any accumulated audio to get freshest data
                # This prevents predicting on stale audio if predictions are slow
                chunks_flushed = 0
                while not self.prediction_audio_queue.empty():
                    try:
                        audio_chunk = self.prediction_audio_queue.get_nowait()
                        with self.prediction_lock:
                            self.prediction_audio_cache.extend(audio_chunk)
                        chunks_flushed += 1
                    except queue.Empty:
                        break
                
                # Copy audio data for processing (release lock quickly)
                with self.prediction_lock:
                    audio_data = np.array(self.prediction_audio_cache)
                
                # Log if we flushed a lot of chunks (indicates lag)
                if chunks_flushed > 5:
                    logger.debug(f"Flushed {chunks_flushed} queued audio chunks before prediction")
                
                # Resample if needed (audio stream is at 48kHz, predictor expects self.prediction_sr)
                # Note: In dual-stream mode, prediction device might have different sample rate
                audio_stream_sample_rate = 48000  # From InputStream configuration
                if audio_stream_sample_rate != self.prediction_sr:
                    audio_data = librosa.resample(
                        audio_data,
                        orig_sr=audio_stream_sample_rate,
                        target_sr=self.prediction_sr
                    )
                
                # Make prediction (heavy CPU work happens here) - measure time
                prediction_start_time = time.time()
                scene, cluster = self.scene_predictor.predict(audio_data, return_cluster=True)
                prediction_duration = time.time() - prediction_start_time
                
                # Update state with lock
                with self.prediction_lock:
                    self.latest_prediction = scene  # Store the raw prediction
                    self.scene_cache.append(scene)
                    
                    # Update current scene using mode of recent predictions
                    if self.scene_cache:
                        try:
                            self.current_predicted_scene = mode(self.scene_cache)
                        except:
                            # If no unique mode (tie), use the most recent
                            self.current_predicted_scene = self.scene_cache[-1]
                    
                    self.current_cluster = cluster
                    self.last_prediction_time = current_time
                    self.prediction_count += 1
                    
                    # Log prediction periodically with cache info and timing
                    if self.prediction_count % 10 == 0:
                        # Get distribution of scenes in cache for debugging
                        scene_counts = Counter(self.scene_cache)
                        cache_info = f"Cache({len(self.scene_cache)}): {dict(scene_counts)}"
                        
                        # Get current queue depth
                        current_queue_depth = self.prediction_audio_queue.qsize()
                        queue_info = f"Q:{current_queue_depth}"
                        if self.max_queue_depth_seen > 10:
                            queue_info += f"(max:{self.max_queue_depth_seen})"
                        
                        logger.info(
                            f"[{self.prediction_count:04d}] Prediction: {scene}, "
                            f"Mode: {self.current_predicted_scene}, Cluster: {cluster} | "
                            f"Time: {prediction_duration*1000:.1f}ms | {queue_info} | {cache_info}"
                        )
                    
                    # Warn if predictions are taking too long
                    if prediction_duration > 0.5:  # More than 500ms
                        logger.warning(f"⚠️  Slow prediction: {prediction_duration*1000:.1f}ms - may cause lag")
                    
            except Exception as e:
                logger.error(f"Error in prediction processing thread: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.5)  # Avoid tight loop on repeated errors
        
        logger.info("Prediction processing thread stopped")
    
    def update_scene_prediction(self):
        """Lightweight method called from main thread - just checks thread health."""
        if not self.scene_prediction_enabled:
            return
        
        # Check if prediction thread is still alive
        if self.prediction_thread and not self.prediction_thread.is_alive():
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Prediction thread died, attempting to restart...")
            self.prediction_thread = threading.Thread(target=self.prediction_processing_thread, daemon=True)
            self.prediction_thread.start()

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
                """Set channel values (batched update to avoid multiple DMX sends)."""
                # Update all channels in controller's buffer without sending
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        channel = self.start_channel + i
                        if 1 <= channel <= 512:
                            self.controller.dmx_data[channel] = max(0, min(255, int(value)))
                # Send all updates at once
                self.controller._send_dmx_packet()
        
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
                """Set RGB channel values (batched update to avoid multiple DMX sends)."""
                # Update all channels in controller's buffer without sending
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        channel = self.start_channel + i
                        if 1 <= channel <= 512:
                            self.controller.dmx_data[channel] = max(0, min(255, int(value)))
                # Send all updates at once
                self.controller._send_dmx_packet()
        
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
                """Set strobe channel values (batched update to avoid multiple DMX sends)."""
                # Update all channels in controller's buffer without sending
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        channel = self.start_channel + i
                        if 1 <= channel <= 512:
                            self.controller.dmx_data[channel] = max(0, min(255, int(value)))
                # Send all updates at once
                self.controller._send_dmx_packet()
        
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
                """Set laser channel values (batched update to avoid multiple DMX sends)."""
                # Update all channels in controller's buffer without sending
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        channel = self.start_channel + i
                        if 1 <= channel <= 512:
                            self.controller.dmx_data[channel] = max(0, min(255, int(value)))
                # Send all updates at once
                self.controller._send_dmx_packet()
        
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
                """Set Rockville channel values (batched update to avoid multiple DMX sends)."""
                # Update all channels in controller's buffer without sending
                for i, value in enumerate(values):
                    if i < self.n_channels:
                        channel = self.start_channel + i
                        if 1 <= channel <= 512:
                            self.controller.dmx_data[channel] = max(0, min(255, int(value)))
                # Send all updates at once
                self.controller._send_dmx_packet()
        
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
                else:
                    print("🔌 Connecting to DMX controller...")
                
                # Use EnttecProController for DMXKing ultraDMX MAX
                # On retry attempts, skip cache and do full port scan
                skip_cache = (attempt > 0)
                dmx_config = get_dmx_config(skip_cache=skip_cache)
                controller = EnttecProController(
                    port=dmx_config['port'],
                    baudrate=dmx_config['baudrate'],
                    timeout=dmx_config['timeout']
                )
                print(f"✓ DMX controller connected on {dmx_config['port']}")
                control_dict = {}
                curr_channel = 1
                sleeptime = 0.1

                # Access the global n_channels dictionary
                global n_channels
                
                print(f"💡 Initializing {len(self.profile['lights'])} light fixtures...")
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

                print(f"✓ All {len(control_dict)} light fixtures initialized\n")
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
        
        # Check if still running to avoid operations after stop
        if not self.running.is_set():
            return
        
        # Handle stereo input - average channels 1 and 2 if dual channel mode is enabled
        if self.average_dual_channels and len(indata.shape) > 1 and indata.shape[1] >= 2:
            # Average the first two channels (0 and 1, which are channels 1 and 2)
            audio_data = np.mean(indata[:, :2], axis=1)
        else:
            audio_data = indata.copy().flatten()
        
        # In single-stream mode, also feed prediction queue
        if self.scene_prediction_enabled and self.scene_prediction_device is None:
            try:
                self.prediction_audio_queue.put_nowait(audio_data.copy())
            except queue.Full:
                pass  # Drop frame if queue is full to avoid blocking
        
        mfft_data = np.mean(librosa.feature.melspectrogram(y=audio_data, sr=self.sample_rate, n_fft=self.block_size, hop_length=self.hop_length), axis=1)
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
        # Use 2 channels if average_dual_channels is enabled, otherwise use default
        device_info = sd.query_devices(self.device_idx)
        main_channels = 2 if self.average_dual_channels else self.channels
        
        # Log FFT/reactivity stream configuration
        import logging
        logger = logging.getLogger(__name__)
        fft_device_name = device_info['name']
        if self.average_dual_channels:
            logger.info(f"🎚️  FFT/Reactivity: '{fft_device_name}' - averaging channels 1-2 at {self.sample_rate}Hz")
        else:
            logger.info(f"🎚️  FFT/Reactivity: '{fft_device_name}' - using channel 1 (mono) at {self.sample_rate}Hz")
        
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
                    max_input_channels = pred_device_info['max_input_channels']
                    
                    # Parse channel specification
                    if self.prediction_channels_spec:
                        self.prediction_channel_indices = self._parse_channel_spec(
                            self.prediction_channels_spec, max_input_channels
                        )
                        pred_channels = max(self.prediction_channel_indices) + 1  # Open enough channels
                    else:
                        # Auto-detect: for multi-channel devices, open all channels
                        if 'BlackHole' in pred_device_info['name'] and max_input_channels > 2:
                            pred_channels = max_input_channels  # Open all channels
                            self.prediction_channel_indices = None  # Average all
                        elif 'Scarlett' in pred_device_info['name'] or 'CABLE' in pred_device_info['name']:
                            pred_channels = 2
                            self.prediction_channel_indices = None  # Average all
                        else:
                            pred_channels = 1
                            self.prediction_channel_indices = None
                    
                    self.prediction_stream = sd.InputStream(
                        device=self.scene_prediction_device,
                        channels=pred_channels,
                        samplerate=48000,  # Typical for CABLE Output
                        blocksize=1024,
                        callback=self.prediction_audio_callback
                    )
                    self.prediction_stream.start()
                    
                    # Start prediction processing thread
                    self.prediction_thread = threading.Thread(target=self.prediction_processing_thread, daemon=True)
                    self.prediction_thread.start()
                    
                    import logging
                    logger = logging.getLogger(__name__)
                    pred_device_name = pred_device_info['name']
                    if self.prediction_channel_indices:
                        channels_desc = f"channels {[i+1 for i in self.prediction_channel_indices]} (averaged)"
                    else:
                        channels_desc = f"all {pred_channels} channels (averaged)"
                    logger.info(f"🎵 Scene Prediction: '{pred_device_name}' - using {channels_desc} at 48000Hz")
                
                # Start prediction thread for single-stream mode if enabled
                if self.scene_prediction_enabled and self.scene_prediction_device is None:
                    self.prediction_thread = threading.Thread(target=self.prediction_processing_thread, daemon=True)
                    self.prediction_thread.start()
                    
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"🎵 Scene Prediction: Single-stream mode (sharing FFT device)")
                
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
        scene_just_changed = False
        if self.scene_changed.is_set():
            self.scene_changed.clear()
            scene_just_changed = True
            self.turn_off_all_lights()
            # Initialize orchestrator if configured in new scene
            if 'orchestrator' in self.scene_manager.current_scene:
                orch_config = self.scene_manager.current_scene['orchestrator']
                orch_type = orch_config['type']
                if orch_type in ORCHESTRATORS:
                    self.current_orchestrator = ORCHESTRATORS[orch_type](orch_config['config'])
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Orchestrator type {orch_type} not found")

        try:
            mfft_data = self.mfft_queue.get(block=False)
        except queue.Empty:
            # If scene just changed, use zeros to initialize lights
            # Otherwise return and wait for audio data
            if scene_just_changed:
                mfft_data = np.zeros(128)  # Default MFFT size
            else:
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

        # Track which lights are in the current scene
        scene_light_names = {light['name'] for light in self.scene_manager.current_scene['lights']}
        
        # Process all lights in profile
        for light_name in self.light_names:
            # Find the light config in the scene (if it exists)
            light_config = None
            for light in self.scene_manager.current_scene['lights']:
                if light['name'] == light_name:
                    light_config = light
                    break
            
            # If light is not in the scene, turn it off and continue
            if light_config is None:
                self.controller_dict[light_name].set_channels([0] * self.controller_dict[light_name].n_channels)
                continue

            try:
                # Check if light is active according to orchestrator
                light_mods = modifications.get(light_name, {'active': True, 'modifiers': {}})
                
                if not light_mods['active']:
                    # Light is disabled by orchestrator - turn it off
                    self.controller_dict[light_name].set_channels([0] * self.controller_dict[light_name].n_channels)
                    continue

                # Process light based on configuration
                dmx_values = process_light(light_config, mfft_data, current_time, modifiers=light_mods['modifiers'])
                if dmx_values is not None:
                    self.controller_dict[light_name].set_channels(dmx_values)

            except Exception as e:
                print(f"Error processing light {light_name}: {str(e)} (Error type: {type(e).__name__})")

    def change_scene(self, scene_name):
        # Reset all effect states before changing scene
        reset_effect_states()
        self.scene_manager.set_scene(scene_name)
        # Reset orchestrator when changing scenes
        self.current_orchestrator = None
        # Set flag for main loop to handle the transition
        self.scene_changed.set()
        # Main loop will turn off lights and apply new scene

    def get_light_type(self, light_name):
        """Helper function to get light type from profile."""
        for light in self.profile['lights']:
            if light['name'] == light_name:
                return light['type']
        return None

    def turn_off_all_lights(self):
        # Batch all light updates together to send a single DMX packet
        for light_name, light_fixture in self.controller_dict.items():
            # Update channels in DMX buffer without sending
            for i in range(light_fixture.n_channels):
                channel = light_fixture.start_channel + i
                if 1 <= channel <= 512:
                    self.dmx_controller.dmx_data[channel] = 0
        
        # Send all updates at once
        self.dmx_controller._send_dmx_packet()
        time.sleep(0.05)  # Small delay to ensure DMX signal is processed

    def stop(self):
        import logging
        logger = logging.getLogger(__name__)
        
        self.running.clear()
        
        # Stop prediction thread if running
        if self.prediction_thread and self.prediction_thread.is_alive():
            logger.info("Waiting for prediction thread to stop...")
            self.prediction_thread.join(timeout=2.0)
            if self.prediction_thread.is_alive():
                logger.warning("Prediction thread did not stop within timeout")
        
        # Stop and close prediction stream
        if self.prediction_stream:
            try:
                self.prediction_stream.stop()
                self.prediction_stream.close()
                self.prediction_stream = None
            except Exception as e:
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





