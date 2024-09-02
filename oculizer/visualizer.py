import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from oculizer.audio import AudioListener

class FeatureVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Feature Visualizer")
        self.setGeometry(100, 100, 1200, 800)  # Increased size for better visibility

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create plots for each feature
        self.plots = {
            'Spectrogram': pg.PlotWidget(title='Spectrogram'),
        }

        # Set up bar graphs and lock y-axis
        self.bars = {}
        for name, plot in self.plots.items():
            layout.addWidget(plot)
            plot.setYRange(0, 20)
            self.bars[name] = plot.plot(pen=None, symbol='o', symbolPen=None, symbolBrush='r')

        # Initialize AudioListener
        self.audio_listener = AudioListener()
        self.audio_listener.start()

        # Set up timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # Update every 50 ms

    def update_plots(self):
        fft = self.audio_listener.get_fft_data()
        if fft is not None:
            # Update mel spectrogram (line plot)
            self.plots['Spectrogram'].clear()
            self.plots['Spectrogram'].plot(fft)

    def closeEvent(self, event):
        self.audio_listener.stop()
        self.audio_listener.join()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = FeatureVisualizer()
    visualizer.show()
    sys.exit(app.exec_())
