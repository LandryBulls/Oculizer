import os
import json
import threading
import queue
import numpy as np
import curses
import time
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
from oculizer.config import audio_parameters

nmfft = audio_parameters['NMFFT']

class MFFTVisualizer(QMainWindow):
    def __init__(self, light_controller):
        super().__init__()
        self.setWindowTitle("MFFT Visualizer")
        self.setGeometry(100, 100, 800, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.mfft_plot = pg.PlotWidget(title='Mel-scaled FFT')
        layout.addWidget(self.mfft_plot)

        self.mfft_bars = pg.BarGraphItem(x=range(nmfft), height=[0]*nmfft, width=0.8, brush='b')
        self.mfft_plot.addItem(self.mfft_bars)

        self.mfft_plot.setLabel('left', 'Magnitude')
        self.mfft_plot.setLabel('bottom', 'MFFT Coefficient')
        self.mfft_plot.showGrid(y=True)
        self.mfft_plot.setYRange(0, 20)
        self.mfft_plot.setXRange(-0.5, nmfft+0.5)

        self.light_controller = light_controller

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(10)  # Update every 10 ms

    def update_plot(self):
        try:
            mfft = self.light_controller.mfft_queue.get(block=False)
            if mfft is not None and len(mfft) == nmfft:
                self.mfft_bars.setOpts(height=mfft)
        except queue.Empty:
            pass

def curses_thread(stdscr, scene_manager, light_controller):
    scene_commands = {ord(scene_manager.scenes[scene]['key_command']): scene for scene in scene_manager.scenes}

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}")
        stdscr.addstr(1, 0, "Available scenes:")
        for i, scene in enumerate(scene_manager.scenes):
            stdscr.addstr(i+2, 0, f"{scene} | Commands: {scene_manager.scenes[scene]['key_command']}")

        stdscr.addstr(2+list(scene_manager.scenes.keys()).index(scene_manager.current_scene['name']), 0, f"{scene_manager.current_scene['name']}", curses.A_REVERSE)
        stdscr.addstr(len(scene_manager.scenes)+3, 0, f"Press 'q' to quit. Press 'r' to reload scenes.")
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            light_controller.stop()
            break
        elif key in scene_commands:
            try:
                light_controller.change_scene(scene_commands[key])
            except Exception as e:
                stdscr.addstr(len(scene_manager.scenes)+2, 0, f"Error changing scene: {str(e)}")
        elif key == ord('r'):
            scene_manager.reload_scenes()
            light_controller.change_scene(scene_manager.current_scene['name'])
            stdscr.addstr(len(scene_manager.scenes)+2, 0, "Scenes reloaded.")
            stdscr.refresh()
            time.sleep(1)

        stdscr.refresh()
        time.sleep(0.1)

def main(stdscr):
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('blue')
    light_controller = Oculizer('garage', scene_manager)

    light_controller.start()

    app = QApplication(sys.argv)
    visualizer = MFFTVisualizer(light_controller)
    visualizer.show()

    curses_thread_obj = threading.Thread(target=curses_thread, args=(stdscr, scene_manager, light_controller))
    curses_thread_obj.start()

    app.exec_()

    light_controller.stop()
    light_controller.join()
    curses_thread_obj.join()

if __name__ == '__main__':
    curses.wrapper(main)