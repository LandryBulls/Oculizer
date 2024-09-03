import curses
from oculizer import Oculizer
import numpy as np
import sounddevice as sd


def main():
    stdscr = curses.initscr()
    oculizer = Oculizer('testing')
    print('Starting oculizer...')
    oculizer.start()

    try:
        while True:
            mfcc_data = audio_listener.get_mfcc_data()
            errors = audio_listener.get_errors()

            if errors:
                print("Errors occurred:", errors)

            if mfcc_data is not None:
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
