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
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create plots for each feature
        self.plots = {
            'mel_spectrogram': pg.PlotWidget(title="Mel Spectrogram"),
            'spectral_centroid': pg.PlotWidget(title="Spectral Centroid"),
            'spectral_contrast': pg.PlotWidget(title="Spectral Contrast"),
            'onset_strength': pg.PlotWidget(title="Onset Strength")
        }

        for plot in self.plots.values():
            layout.addWidget(plot)

        # Initialize AudioListener
        self.audio_listener = AudioListener()
        self.audio_listener.start()

        # Set up timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # Update every 50 ms

    def update_plots(self):
        features = self.audio_listener.get_features()
        if features is not None:
            self.plots['mel_spectrogram'].clear()
            self.plots['mel_spectrogram'].plot(features['mel_spectrogram'].mean(axis=1))

            self.plots['spectral_centroid'].clear()
            self.plots['spectral_centroid'].plot(features['spectral_centroid'][0])

            self.plots['spectral_contrast'].clear()
            self.plots['spectral_contrast'].plot(features['spectral_contrast'].mean(axis=1))

            self.plots['onset_strength'].clear()
            self.plots['onset_strength'].plot(features['onset_strength'])

    def closeEvent(self, event):
        self.audio_listener.stop()
        self.audio_listener.join()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = FeatureVisualizer()
    visualizer.show()
    sys.exit(app.exec_())
