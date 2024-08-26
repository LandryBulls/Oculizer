"""
Provides the AudioListener class, which listens to audio input and provides audio and FFT data using threading and queues.

Author: Landry Bulls
Date: 8/23/24
"""

import threading
import queue
import sounddevice as sd
import numpy as np
from scipy.fftpack import rfft
import time
from config import audio_parameters
import curses

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']

# get blackhole audio device
def get_blackhole_device_idx():
    devices = sd.query_devices()
    for device in devices:
        if 'BlackHole' in device['name']:
            return device['index']
    return None

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
        self.device_idx = get_blackhole_device_idx()

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.error_queue.put(f"Audio callback error: {status}")
        try:
            audio_data = np.copy(indata[:, 0])
            fft_data = np.abs(np.fft.rfft(np.sum(indata, axis=1), n=None))
            self.audio_queue.put(audio_data)
            self.fft_queue.put(fft_data)
        except Exception as e:
            self.error_queue.put(f"Error processing audio data: {str(e)}")

    def run(self):
        self.running.set()
        try:
            with sd.InputStream(callback=self.audio_callback, channels=self.channels, 
                                samplerate=self.sample_rate, blocksize=self.block_size, device=self.device_idx):
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
            # put the sum with curses
            stdscr.clear()
            stdscr.addstr(0, 1, f"FFT Sum: {np.sum(fft_data)}")
            if fft_data is not None:
                stdscr.addstr(1, 1, f'FFT Shape: {len(fft_data)}')
            stdscr.addstr(2, 1, "Sample rate: {}".format(audio_listener.sample_rate))
            stdscr.addstr(3, 1, "Block size: {}".format(audio_listener.block_size))
            stdscr.refresh()

            if errors:
                print("Errors occurred:", errors)

            if audio_data is not None and fft_data is not None:
                # Process data here
                pass

            sd.sleep(10)  # Small delay to prevent busy-waiting (this is 10 milliseconds)
    except KeyboardInterrupt:
        print("Stopping audio listener...")
    finally:
        audio_listener.stop()
        audio_listener.join()

if __name__ == "__main__":
    main()