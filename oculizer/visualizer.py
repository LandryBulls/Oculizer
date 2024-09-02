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
            'mel_spectrogram': pg.PlotWidget(title="Mel Spectrogram"),
            'spectral_centroid': pg.PlotWidget(title="Spectral Centroid"),
            'spectral_contrast': pg.PlotWidget(title="Spectral Contrast"),
            'onset_strength': pg.PlotWidget(title="Onset Strength")
        }

        # Set up bar graphs and lock y-axis
        self.bars = {}
        for name, plot in self.plots.items():
            layout.addWidget(plot)
            if name == 'spectral_centroid':
                self.bars[name] = pg.BarGraphItem(x=[], height=[], width=0.6, brush='b')
                plot.addItem(self.bars[name])
                plot.setYRange(0, 4000)  # Lock y-axis from 0 to 4000
            elif name == 'spectral_contrast':
                self.bars[name] = pg.BarGraphItem(x=[], height=[], width=0.6, brush='r')
                plot.addItem(self.bars[name])
                plot.setYRange(0, 50)
            elif name == 'mel_spectrogram': 
                plot.setYRange(0, 3)  # Lock y-axis for mel spectrogram as well
            elif name == 'onset_strength':
                self.bars[name] = pg.BarGraphItem(x=[], height=[], width=0.6, brush='g')
                plot.addItem(self.bars[name])
                plot.setYRange(0, 1)

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
            # Update mel spectrogram (line plot)
            self.plots['mel_spectrogram'].clear()
            mel_data = features['mel_spectrogram'].mean(axis=1)
            self.plots['mel_spectrogram'].plot(mel_data)

            # Update spectral centroid (bar plot)
            centroid_data = features['spectral_centroid'][0]
            self.bars['spectral_centroid'].setOpts(x=range(len(centroid_data)), height=centroid_data)

            # Update spectral contrast (bar plot)
            contrast_data = features['spectral_contrast'].mean(axis=1)
            self.bars['spectral_contrast'].setOpts(x=range(len(contrast_data)), height=contrast_data)

            # Update onset strength (bar plot)
            onset_data = features['onset_strength']
            self.bars['onset_strength'].setOpts(x=range(len(onset_data)), height=onset_data)

    def closeEvent(self, event):
        self.audio_listener.stop()
        self.audio_listener.join()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = FeatureVisualizer()
    visualizer.show()
    sys.exit(app.exec_())
