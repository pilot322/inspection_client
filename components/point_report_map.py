from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor
import sys

class PointReportMapWidget(QWidget):
    # Signal that takes a list of coordinates (list of tuples)
    update_points_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.points = []  # Initialize an empty list to store the points
        self.update_points_signal.connect(self.update_points)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Point Drawing Window")
        self.setGeometry(100, 100, 300, 300)

    def update_points(self, points):
        """Slot to receive and store the points."""
        self.points = points
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        """Override paintEvent to draw the points."""
        qp = QPainter(self)
        qp.setPen(QPen(QColor("#ff00ff"), 4, Qt.SolidLine))

        for point in self.points:
            qp.drawPoint(QPoint(*point))
