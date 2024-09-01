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

def get_blackhole_device_idx():
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'BlackHole' in device['name']:
            return i, device['name']
    return None, None

def get_fft_vector(audio_data):
    # using librosa
    return np.abs(librosa.stft(audio_data))

class AudioListener(threading.Thread):
    def __init__(self, sample_rate=SAMPLERATE, block_size=BLOCKSIZE, channels=1):
        threading.Thread.__init__(self)
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.fft_queue = queue.Queue()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        self.device_idx, self.device_name = get_blackhole_device_idx()
        self.stream = None

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.error_queue.put(f"Audio callback error: {status}")
        try:
            audio_data = indata.copy().flatten()
            fft_data = np.abs(librosa.stft(audio_data))
            self.audio_queue.put(audio_data)
            self.fft_queue.put(fft_data)
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

    def get_fft_data(self, timeout=0.08):
        try:
            return self.fft_queue.get(timeout=timeout)
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
            fft_data = audio_listener.get_fft_data()
            errors = audio_listener.get_errors()
            
            stdscr.clear()
            if fft_data is not None:
                stdscr.addstr(0, 1, f"FFT Sum: {np.sum(fft_data)}")
                stdscr.addstr(1, 1, f'FFT Shape: {len(fft_data)}')
                stdscr.addstr(2, 1, f'FFT Data: {fft_data}')
            stdscr.addstr(2, 1, f"Sample rate: {audio_listener.sample_rate}")
            stdscr.addstr(3, 1, f"Block size: {audio_listener.block_size}")
            stdscr.refresh()

            if errors:
                print("Errors occurred:", errors)

            if audio_data is not None and fft_data is not None:
                # Process data here
                pass

            time.sleep(0.01)  # Small delay to prevent busy-waiting
    except KeyboardInterrupt:
        print("Stopping audio listener...")
    finally:
        audio_listener.stop()
        audio_listener.join()
        curses.endwin()

if __name__ == "__main__":
    main()