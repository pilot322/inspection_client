from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor
import sys
from components.point_report_map import PointReportMapWidget
import os

class PointReportWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Point Drawing Example')
        self.d = 200
        self.setGeometry(100, 100, self.d, self.d)

        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

         # Make the window background transparent
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Set the window opacity (0.0 is fully transparent, 1.0 is fully opaque)
        self.setWindowOpacity(0.7)

        layout = QVBoxLayout()
        
        # Create an instance of the custom PointDrawingWidget
        self.point_drawing_widget = PointReportMapWidget()
        
        # Add the drawing widget to the layout
        layout.addWidget(self.point_drawing_widget)
        
        self.setLayout(layout)

        #self.draw_points([(0,0), (100, 100), (200, 200), (250, 250), (300, 300)])

        self.show()

    def draw_points(self, labeled_patches):
        grid_size = int(os.getenv('INSPECTION_CLIENT_GRID_SIZE'))
        image_size = int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE'))
        patch_height = image_size // grid_size
        # for labeled_patch in labeled_patches:
        #     print(labeled_patch)
        map_to_ij = lambda x : (self.d // (grid_size + 1)*(1 + (x - patch_height // 2) // patch_height))

        temp = ""
        for labeled_patch in labeled_patches:
            temp += str(labeled_patch[4]) + " "
        print(temp)
        points = [(map_to_ij(labeled_patch[4][0]) // 2, map_to_ij(labeled_patch[4][1])) for labeled_patch in labeled_patches]

        """Method to emit the signal with the list of points."""
        self.point_drawing_widget.update_points_signal.emit(points)