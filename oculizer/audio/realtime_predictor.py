"""Real-time audio scene prediction using audio input device."""
import time
import numpy as np
import threading
import queue
from collections import deque
from statistics import mode
import sounddevice as sd
import librosa
import logging

logger = logging.getLogger(__name__)


class RealTimeScenePredictor:
    """Predicts scenes in real-time from audio input device."""
    
    def __init__(self, predictor, device_index, sample_rate=48000, 
                 cache_duration=4, update_interval=0.1, 
                 prediction_interval=0.1, scene_cache_length=50):
        """
        Initialize real-time scene predictor.
        
        Args:
            predictor: ScenePredictor instance for making predictions
            device_index: Audio input device index
            sample_rate: Sample rate for audio capture (Hz)
            cache_duration: Duration of audio cache (seconds)
            update_interval: How often to output updates (seconds)
            prediction_interval: How often to make predictions (seconds)
            scene_cache_length: Number of recent scene predictions to cache
        """
        self.predictor = predictor
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.cache_duration = cache_duration
        self.update_interval = update_interval
        self.prediction_interval = prediction_interval
        self.scene_cache_length = scene_cache_length
        
        # Audio cache - stores cache_duration seconds of audio data
        self.cache_size = int(sample_rate * cache_duration)
        self.audio_cache = deque(maxlen=self.cache_size)
        
        # Scene prediction cache for mode calculation
        self.scene_cache = deque(maxlen=scene_cache_length)
        
        # Prediction timing
        self.last_prediction_time = 0
        self.last_update_time = 0
        self.prediction_count = 0
        
        # Current scene state
        self.current_scene = None
        self.current_cluster = None
        
        # Audio stream
        self.audio_queue = queue.Queue()
        self.stream = None
        self.running = False
        
    def audio_callback(self, indata, frames, time, status):
        """Callback function for audio stream."""
        if status:
            logger.warning(f"Audio status: {status}")
        
        # Convert stereo to mono by averaging channels
        if len(indata.shape) > 1:
            mono_data = np.mean(indata, axis=1)
        else:
            mono_data = indata
        
        # Add to queue for processing
        self.audio_queue.put(mono_data.copy())
    
    def get_current_scene(self):
        """Get the mode of recent scenes or most recent if no mode exists."""
        if not self.scene_cache:
            return None
        try:
            return mode(self.scene_cache)
        except:
            return self.scene_cache[-1]
    
    def process_audio(self):
        """Process audio data from queue."""
        while self.running:
            try:
                # Get audio data from queue (non-blocking)
                audio_chunk = self.audio_queue.get(timeout=0.1)
                
                # Add to cache
                self.audio_cache.extend(audio_chunk)
                
                current_time = time.time()
                
                # Check if we have enough data and it's time for prediction
                if (len(self.audio_cache) >= self.cache_size and 
                    current_time - self.last_prediction_time >= self.prediction_interval):
                    
                    # Convert cache to numpy array
                    audio_data = np.array(self.audio_cache)
                    
                    # Resample to 32kHz if needed for the predictor
                    if self.sample_rate != 32000:
                        audio_data = librosa.resample(
                            audio_data, 
                            orig_sr=self.sample_rate, 
                            target_sr=32000
                        )
                    
                    # Make prediction and add to scene cache
                    scene, cluster = self.predictor.predict(audio_data, return_cluster=True)
                    self.scene_cache.append(scene)
                    
                    # Update current scene
                    self.current_scene = self.get_current_scene()
                    self.current_cluster = cluster
                    
                    # Update prediction timing
                    self.last_prediction_time = current_time
                    
                    # Check if it's time for an update output
                    if current_time - self.last_update_time >= self.update_interval:
                        elapsed_time = current_time - self.last_update_time
                        logger.info(
                            f"[{self.prediction_count:04d}] Scene: {self.current_scene}, "
                            f"Cluster: {cluster}, Interval: {elapsed_time:.2f}s"
                        )
                        
                        # Update timing
                        self.last_update_time = current_time
                        self.prediction_count += 1
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
    
    def start(self):
        """Start the real-time prediction."""
        # Get device info for display
        device_info = sd.query_devices(self.device_index)
        device_name = device_info['name']
        
        logger.info(f"Starting real-time scene prediction...")
        logger.info(f"Device: {self.device_index} ({device_name}), Sample Rate: {self.sample_rate}Hz")
        logger.info(f"Cache Duration: {self.cache_duration}s, Update Interval: {self.update_interval}s")
        logger.info(f"Prediction Interval: {self.prediction_interval}s, Scene Cache Length: {self.scene_cache_length}")
        
        self.running = True
        
        # Determine number of channels based on device
        device_name = sd.query_devices(self.device_index)['name']
        channels = 2 if "Scarlett" in device_name or "CABLE" in device_name else 1
        
        # Start audio stream
        self.stream = sd.InputStream(
            device=self.device_index,
            channels=channels,
            samplerate=self.sample_rate,
            callback=self.audio_callback,
            blocksize=1024
        )
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self.process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        # Start audio stream
        self.stream.start()
        logger.info("Real-time scene prediction started")
    
    def stop(self):
        """Stop the real-time prediction."""
        logger.info("Stopping real-time prediction...")
        self.running = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        if hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=1.0)
        
        logger.info("Real-time scene prediction stopped")

