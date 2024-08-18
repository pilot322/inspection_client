from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QScrollArea
from PyQt5.QtGui import QPixmap

class PatchWindow(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Patch Image')
        self.setGeometry(100, 100, 600, 600)
        
        layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        image_label = QLabel()
        pixmap = QPixmap(self.image_path)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(True)
        
        scroll_area.setWidget(image_label)
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)