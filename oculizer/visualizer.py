import curses
from audio_listener import AudioListener
import numpy as np
import sounddevice as sd


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

            if errors:
                print("Errors occurred:", errors)

            if fft_data is not None:
                # uses curses to display the audio data
                stdscr.clear()
                stdscr.addstr(0, 0, f"Audio data: {np.sum(fft_data)}")
                stdscr.refresh()
            else:
                stdscr.addstr(0, 0, "No audio data available")
                stdscr.refresh()


            sd.sleep(10)  # Small delay to prevent busy-waiting (this is 10 milliseconds)
    except KeyboardInterrupt:
        print("Stopping audio listener...")
    finally:
        audio_listener.stop()
        audio_listener.join()

if __name__ == '__main__':
    main()
    curses.endwin()
