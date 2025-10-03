"""
Dual Audio Stream Controller for Oculizer

This module extends the Oculizer class to handle two audio streams:
1. Real-time stream: Used for scene prediction (4-second lookahead)
2. Delayed stream: Used for real-time lighting control (synchronized with speakers)

Author: Landry Bulls
Date: 12/19/24
"""

import numpy as np
import sounddevice as sd
import threading
import time
import queue
from collections import deque
from pathlib import Path
import logging

from oculizer.light.control import Oculizer
from mappings.v1.predictor import ScenePredictor

logger = logging.getLogger(__name__)

class DualStreamOculizer(Oculizer):
    def __init__(self, profile_name, scene_manager, 
                 realtime_device='cable_input', delayed_device='cable_output',
                 prediction_interval=0.5, buffer_duration=4.0):
        """
        Initialize dual stream Oculizer.
        
        Args:
            profile_name: Lighting profile name
            scene_manager: Scene manager instance
            realtime_device: Audio device for real-time stream (scene prediction)
            delayed_device: Audio device for delayed stream (lighting control)
            prediction_interval: How often to run scene prediction (seconds)
            buffer_duration: Duration of audio buffer for prediction (seconds)
        """
        # Initialize base class with delayed device (for lighting control)
        super().__init__(profile_name, scene_manager, input_device=delayed_device)
        
        # Dual stream configuration
        self.realtime_device = realtime_device.lower()
        self.delayed_device = delayed_device.lower()
        self.prediction_interval = prediction_interval
        self.buffer_duration = buffer_duration
        
        # Audio buffers
        self.buffer_samples = int(self.sample_rate * self.buffer_duration)
        self.realtime_buffer = deque(maxlen=self.buffer_samples)
        self.prediction_queue = queue.Queue(maxsize=1)
        
        # Scene prediction
        self.scene_predictor = ScenePredictor()
        self.predicted_scenes = deque(maxlen=100)  # Store recent predictions
        self.current_predicted_scene = 'party'  # Default scene
        
        # Threading
        self.realtime_running = threading.Event()
        self.prediction_running = threading.Event()
        
        # Get real-time audio device index
        self.realtime_device_idx = self._get_realtime_device_idx()
        
        logger.info(f"Dual stream Oculizer initialized:")
        logger.info(f"  Real-time device: {realtime_device} (index: {self.realtime_device_idx})")
        logger.info(f"  Delayed device: {delayed_device} (index: {self.device_idx})")
    
    def _get_realtime_device_idx(self):
        """Get audio device index for real-time stream."""
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if self.realtime_device == 'blackhole' and 'BlackHole' in device['name']:
                return i
            elif self.realtime_device == 'scarlett' and 'Scarlett' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.realtime_device == 'cable_input' and 'CABLE Input' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.realtime_device == 'cable_output' and 'CABLE Output' in device['name'] and device['max_input_channels'] > 0:
                return i
            elif self.realtime_device == 'cable' and 'CABLE' in device['name'] and device['max_input_channels'] > 0:
                return i
        
        # If device not found, print available devices and raise error
        logger.error(f"Real-time audio device '{self.realtime_device}' not found.")
        logger.info("Available audio input devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                logger.info(f"  {i}: {device['name']}")
        
        raise ValueError(f"Real-time audio device '{self.realtime_device}' not found.")
    
    def realtime_audio_callback(self, indata, frames, time, status):
        """Callback for real-time audio stream (scene prediction)."""
        if status:
            logger.warning(f"Real-time audio callback error: {status}")
            return
        
        # Add audio data to rolling buffer
        audio_data = indata.copy().flatten()
        self.realtime_buffer.extend(audio_data)
        
        # Signal that we have enough data for prediction
        if len(self.realtime_buffer) >= self.buffer_samples:
            if not self.prediction_queue.full():
                # Convert buffer to numpy array for prediction
                buffer_array = np.array(list(self.realtime_buffer))
                self.prediction_queue.put(buffer_array)
    
    def prediction_worker(self):
        """Worker thread for scene prediction."""
        self.prediction_running.set()
        last_prediction_time = 0
        
        while self.prediction_running.is_set():
            try:
                # Check if it's time for a new prediction
                current_time = time.time()
                if current_time - last_prediction_time >= self.prediction_interval:
                    try:
                        # Get audio buffer for prediction
                        audio_buffer = self.prediction_queue.get(timeout=0.1)
                        
                        # Run scene prediction
                        predicted_scene = self.scene_predictor.predict(audio_buffer)
                        
                        # Store prediction with timestamp
                        prediction_data = {
                            'scene': predicted_scene,
                            'timestamp': current_time,
                            'audio_timestamp': current_time + self.buffer_duration  # When this audio will play
                        }
                        
                        self.predicted_scenes.append(prediction_data)
                        self.current_predicted_scene = predicted_scene
                        
                        logger.info(f"Scene prediction: {predicted_scene} (will play at {prediction_data['audio_timestamp']:.2f})")
                        
                        last_prediction_time = current_time
                        
                    except queue.Empty:
                        pass  # No new audio data available
                
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in prediction worker: {e}")
                time.sleep(1)  # Wait before retrying
    
    def get_scene_for_time(self, target_time):
        """Get the predicted scene for a specific time."""
        if not self.predicted_scenes:
            return self.current_predicted_scene
        
        # Find the prediction closest to the target time
        best_prediction = None
        best_diff = float('inf')
        
        for prediction in self.predicted_scenes:
            diff = abs(prediction['audio_timestamp'] - target_time)
            if diff < best_diff:
                best_diff = diff
                best_prediction = prediction
        
        # If prediction is too old (> 10 seconds), use current prediction
        if best_prediction and best_diff < 10.0:
            return best_prediction['scene']
        else:
            return self.current_predicted_scene
    
    def start(self):
        """Start both audio streams and prediction."""
        # Start base class audio stream (delayed)
        super().start()
        
        # Start real-time audio stream
        self.realtime_running.set()
        self.realtime_stream = sd.InputStream(
            device=self.realtime_device_idx,
            channels=self.channels,
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            callback=self.realtime_audio_callback
        )
        self.realtime_stream.start()
        
        # Start prediction worker thread
        self.prediction_thread = threading.Thread(target=self.prediction_worker)
        self.prediction_thread.daemon = True
        self.prediction_thread.start()
        
        logger.info("Dual stream Oculizer started")
    
    def stop(self):
        """Stop both audio streams and prediction."""
        # Stop prediction
        self.prediction_running.clear()
        if hasattr(self, 'prediction_thread'):
            self.prediction_thread.join(timeout=2)
        
        # Stop real-time stream
        self.realtime_running.clear()
        if hasattr(self, 'realtime_stream'):
            self.realtime_stream.stop()
            self.realtime_stream.close()
        
        # Stop base class (delayed stream)
        super().stop()
        
        logger.info("Dual stream Oculizer stopped")
    
    def process_audio_and_lights(self):
        """Override base class method to use predicted scenes."""
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
                    logger.warning(f"Orchestrator type {orch_type} not found")
            else:
                logger.debug("No orchestrator configured in scene")

        try:
            mfft_data = self.mfft_queue.get(block=False)
        except queue.Empty:
            return

        current_time = time.time()
        
        # Get the predicted scene for the current audio time
        predicted_scene = self.get_scene_for_time(current_time)
        
        # If the predicted scene is different from current scene, change it
        if predicted_scene != self.scene_manager.current_scene['name']:
            logger.info(f"Changing scene from {self.scene_manager.current_scene['name']} to {predicted_scene}")
            self.change_scene(predicted_scene)
            return  # Let the scene change complete before processing lights

        # Get orchestrator modifications if orchestrator exists
        modifications = {}
        if self.current_orchestrator:
            modifications = self.current_orchestrator.process(
                self.light_names,
                mfft_data,
                current_time
            )

        # Process lights with the current scene
        for light in self.scene_manager.current_scene['lights']:
            if light['name'] not in self.light_names:
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
                logger.error(f"Error processing light {light['name']}: {str(e)}")

# Import required modules for the override
from oculizer.light.orchestrators import ORCHESTRATORS
from oculizer.light.mapping import process_light
