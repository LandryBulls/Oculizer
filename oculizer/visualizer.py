import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from oculizer import Oculizer, SceneManager
from oculizer.config import audio_parameters

nmfft = audio_parameters['NMFFT']

class FeatureVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mfft Feature Visualizer")
        self.setGeometry(100, 100, 1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.coeff_plot = pg.PlotWidget(title='Mel-scaled FFT Coefficients')
        layout.addWidget(self.coeff_plot)

        self.coeff_bars = pg.BarGraphItem(x=range(nmfft), height=[0]*nmfft, width=0.8, brush='b')
        self.coeff_plot.addItem(self.coeff_bars)

        self.coeff_plot.setLabel('left', 'Magnitude')
        self.coeff_plot.setLabel('bottom', 'mfft Coefficient')
        self.coeff_plot.showGrid(y=True)
        self.coeff_plot.setYRange(0, 20)  # Adjust based on your typical coefficient values
        self.coeff_plot.setXRange(-0.5, nmfft+0.5)
        x_axis = self.coeff_plot.getAxis('bottom')
        x_axis.setTicks([[(i, str(i+1)) if (i+1) % 5 == 0 else (i, '') for i in range(nmfft)]])
        x_axis.setStyle(tickTextOffset=10, tickLength=-15)

        # Initialize Oculizer controller
        scene_manager = SceneManager('scenes')
        self.controller = Oculizer('testing', scene_manager)
        self.controller.start()

        # Set up timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(10)  # Update every 10 ms

    def update_plot(self):
        mfft = self.controller.mfft_queue.get()
        if mfft is not None and len(mfft) == nmfft:
            self.coeff_bars.setOpts(height=mfft)

    def closeEvent(self, event):
        self.controller.stop()
        self.controller.join()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = FeatureVisualizer()
    visualizer.show()
    sys.exit(app.exec_())