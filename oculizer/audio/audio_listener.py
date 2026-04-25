import threading
import queue
import numpy as np
from scipy.fftpack import rfft
import time
import curses
import sounddevice as sd
from oculizer.config import audio_parameters

SAMPLERATE = audio_parameters['SAMPLERATE']
BLOCKSIZE = audio_parameters['BLOCKSIZE']


class AdaptiveNormalizer:
    """
    Adaptive gain normalization for audio feature signals (e.g. mel spectrogram).

    Tracks a slow exponential moving average (EMA) of the signal's RMS level and
    applies a constant gain factor to bring it toward a configurable target. This
    makes the system robust to different input sources that may have different
    effective gain levels (e.g. BlackHole virtual device vs. a Scarlett 2i2 with
    a hardware gain knob).

    Uses asymmetric time constants:
    - Faster adaptation (attack) when the signal level increases, to avoid
      saturation and over-brightening.
    - Slower adaptation (release) when the signal level drops, to avoid amplifying
      silence or noise.

    Short-term musical dynamics are preserved because both time constants are much
    longer than a typical note or beat duration.
    """

    def __init__(self, target_rms=1.0, attack_time=20.0, release_time=60.0,
                 sample_rate=SAMPLERATE, block_size=BLOCKSIZE,
                 min_gain=0.2, max_gain=20.0, silence_threshold=1e-4):
        """
        Args:
            target_rms:          Desired long-term RMS level for the normalised output.
            attack_time:         Seconds to adapt when the signal gets louder (gain falls).
            release_time:        Seconds to adapt when the signal gets quieter (gain rises).
            sample_rate:         Audio sample rate (Hz).
            block_size:          Audio block/frame size (samples); used to compute the
                                 number of callbacks per second.
            min_gain:            Floor gain to apply (prevents division by near-zero EMA).
            max_gain:            Ceiling gain to apply (prevents runaway amplification
                                 during extended silence).
            silence_threshold:   RMS values below this threshold are treated as silence;
                                 the EMA is not updated so gain doesn't creep up.
        """
        callbacks_per_sec = sample_rate / block_size
        self.alpha_attack = 1.0 / (attack_time * callbacks_per_sec)
        self.alpha_release = 1.0 / (release_time * callbacks_per_sec)
        self.target_rms = target_rms
        self.min_gain = min_gain
        self.max_gain = max_gain
        self.silence_threshold = silence_threshold
        self.ema_rms = None   # Lazily initialised on first non-silent frame.
        self.current_gain = 1.0

    def process(self, data):
        """
        Normalise *data* and return the scaled array.

        The internal EMA and gain are updated in place every call, so repeated
        calls with frames of audio will cause the gain to converge toward the
        target level over the configured time window.

        Args:
            data: 1-D numpy array (e.g. mel spectrogram frame or FFT magnitudes).

        Returns:
            Scaled numpy array of the same shape as *data*.
        """
        rms = float(np.sqrt(np.mean(data ** 2)))

        # Skip EMA update during silence to prevent gain runaway.
        if rms >= self.silence_threshold:
            if self.ema_rms is None:
                self.ema_rms = rms
            else:
                alpha = self.alpha_attack if rms > self.ema_rms else self.alpha_release
                self.ema_rms = alpha * rms + (1.0 - alpha) * self.ema_rms

            self.current_gain = float(np.clip(
                self.target_rms / (self.ema_rms + 1e-10),
                self.min_gain, self.max_gain
            ))

        return data * self.current_gain

def get_blackhole_device_idx():
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'BlackHole' in device['name']:
            return i, device['name']
    return None, None

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
            fft_data = np.abs(rfft(audio_data))
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