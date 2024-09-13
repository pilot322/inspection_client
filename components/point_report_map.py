from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QColor
import sys

class PointReportMapWidget(QWidget):
    # Signal that takes a list of coordinates (list of tuples)
    update_points_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.indication = 'gray'
        self.points = []  # Initialize an empty list to store the points
        self.update_points_signal.connect(self.update_points)
        self.initUI()


    def initUI(self):
        self.setWindowTitle("Point Drawing Window")
        self.setGeometry(100, 100, 300, 300)
    

    def update_points(self, points):
        """Slot to receive and store the points."""
        print('update points')
        self.points = points
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        """Override paintEvent to draw the points and set the background color."""
        qp = QPainter(self)

        # Set background color based on the indication
        if self.indication == 'red':
            bg_color = QColor("#ff0000")  # Red
        elif self.indication == 'orange':
            bg_color = QColor("#ffa500")  # Orange
        elif self.indication == 'yellow':
            bg_color = QColor("#ffff00")  # Yellow
        elif self.indication == 'gray':
            bg_color = QColor("#808080")  # Gray
        else:  # Default to 'green'
            bg_color = QColor("#00ff00")  # Green

        # Fill the background with the selected color
        qp.fillRect(QRect(0, 0, 178, 178), bg_color)

        # Set pen for points
        qp.setPen(QPen(QColor("#ff00ff"), 4, Qt.SolidLine))

        # # Draw the points
        for point in self.points:
            qp.drawPoint(QPoint(*point))