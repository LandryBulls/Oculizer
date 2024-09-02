import threading
import queue
import numpy as np
from scipy.fftpack import rfft
import librosa
import time
import curses
import sounddevice as sd
from oculizer.config import audio_parameters

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']
HOP_LENGTH = audio_parameters['HOP_LENGTH']

def get_blackhole_device_idx():
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'BlackHole' in device['name']:
            return i, device['name']
    return None, None

class AudioListener(threading.Thread):
    def __init__(self, sample_rate=SAMPLERATE, block_size=BLOCKSIZE, hop_length=HOP_LENGTH, channels=1):
        threading.Thread.__init__(self)
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.hop_length = hop_length
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.feature_queue = queue.Queue()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        self.device_idx, self.device_name = get_blackhole_device_idx()
        self.stream = None

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.error_queue.put(f"Audio callback error: {status}")
        try:
            audio_data = indata.copy().flatten()
            self.audio_queue.put(audio_data)
            
            # Extract features using librosa
            features = self.extract_features(audio_data)
            self.feature_queue.put(features)
        except Exception as e:
            self.error_queue.put(f"Error processing audio data: {str(e)}")

    def extract_features(self, audio_data):
        # Compute the Short-time Fourier Transform (STFT)
        stft = librosa.stft(audio_data, n_fft=self.block_size, hop_length=self.hop_length)
        
        # Compute the magnitude spectrogram
        magnitude = np.abs(stft)
        
        # Compute mel spectrogram
        mel_spectrogram = librosa.feature.melspectrogram(S=magnitude, sr=self.sample_rate, hop_length=self.hop_length)
        
        # Compute spectral centroid
        spectral_centroid = librosa.feature.spectral_centroid(S=magnitude, sr=self.sample_rate, hop_length=self.hop_length)
        
        # Compute spectral contrast
        spectral_contrast = librosa.feature.spectral_contrast(S=magnitude, sr=self.sample_rate, hop_length=self.hop_length)
        
        # Compute onset strength
        onset_strength = librosa.onset.onset_strength(S=magnitude, sr=self.sample_rate, hop_length=self.hop_length)
        
        return {
            'mel_spectrogram': mel_spectrogram,
            'spectral_centroid': spectral_centroid,
            'spectral_contrast': spectral_contrast,
            'onset_strength': onset_strength
        }

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
                    sd.sleep(100)
        except Exception as e:
            self.error_queue.put(f"Error in audio stream: {str(e)}")

    def stop(self):
        self.running.clear()

    def get_audio_data(self):
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None

    def get_features(self, timeout=0.08):
        try:
            return self.feature_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_errors(self):
        errors = []
        while not self.error_queue.empty():
            errors.append(self.error_queue.get_nowait())
        return errors

def main():
    stdscr = curses.initscr()

    audio_listener = AudioListener()
    audio_listener.start()
    print('Listening to audio...')

    try:
        while True:
            audio_data = audio_listener.get_audio_data()
            audio_features = audio_listener.get_features()
            errors = audio_listener.get_errors()
            
            stdscr.clear()
            if audio_features is not None:
                stdscr.addstr(0, 1, f"Mel spectrogram shape: {audio_features['mel_spectrogram'].shape}")
                stdscr.addstr(1, 1, f"Spectral centroid: {audio_features['spectral_centroid'][0]}")
                stdscr.addstr(2, 1, f"Spectral contrast shape: {audio_features['spectral_contrast'].shape}")
                stdscr.addstr(3, 1, f"Onset strength shape: {audio_features['onset_strength'].shape}")
            stdscr.addstr(3, 1, f"Block size: {audio_listener.block_size}")
            stdscr.refresh()

            if errors:
                print("Errors occurred:", errors)

            time.sleep(0.01)  # Small delay to prevent busy-waiting
    except KeyboardInterrupt:
        print("Stopping audio listener...")
    finally:
        audio_listener.stop()
        audio_listener.join()
        curses.endwin()

if __name__ == "__main__":
    main()