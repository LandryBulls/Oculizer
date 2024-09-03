import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from oculizer import Oculizer, SceneManager

class FeatureVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MFCC Feature Visualizer")
        self.setGeometry(100, 100, 1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create two plots: one for energy, one for other coefficients
        self.energy_plot = pg.PlotWidget(title='MFCC Energy Term (Coefficient 0)')
        self.coeff_plot = pg.PlotWidget(title='MFCC Coefficients 1-12')
        layout.addWidget(self.energy_plot)
        layout.addWidget(self.coeff_plot)

        # Set up bar graphs
        self.energy_bar = pg.BarGraphItem(x=[0], height=[0], width=0.8, brush='r')
        self.coeff_bars = pg.BarGraphItem(x=range(12), height=[0]*12, width=0.8, brush='b')
        self.energy_plot.addItem(self.energy_bar)
        self.coeff_plot.addItem(self.coeff_bars)

        # Customize the plots
        self.energy_plot.setLabel('left', 'Magnitude')
        self.energy_plot.showGrid(y=True)
        self.energy_plot.setYRange(0, 100)  # Adjust based on your typical energy values
        self.energy_plot.setXRange(-0.5, 0.5)
        self.energy_plot.getAxis('bottom').setTicks([[(0, 'Energy')]])

        self.coeff_plot.setLabel('left', 'Magnitude')
        self.coeff_plot.setLabel('bottom', 'MFCC Coefficient')
        self.coeff_plot.showGrid(y=True)
        self.coeff_plot.setYRange(0, 20)  # Adjust based on your typical coefficient values
        self.coeff_plot.setXRange(-0.5, 11.5)
        x_axis = self.coeff_plot.getAxis('bottom')
        x_axis.setTicks([[(i, str(i+1)) for i in range(12)]])

        # Initialize Oculizer controller
        scene_manager = SceneManager('scenes')
        self.controller = Oculizer('testing', scene_manager)
        self.controller.control_lights = False
        self.controller.start()

        # Set up timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # Update every 50 ms

    def update_plot(self):
        mfcc = self.controller.get_features()
        if mfcc is not None and len(mfcc) == 13:
            # Update energy term (first coefficient)
            self.energy_bar.setOpts(height=[mfcc[0]])
            
            # Update other MFCC coefficients
            self.coeff_bars.setOpts(height=mfcc[1:])

    def closeEvent(self, event):
        self.controller.stop()
        self.controller.join()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = FeatureVisualizer()
    visualizer.show()
    sys.exit(app.exec_())