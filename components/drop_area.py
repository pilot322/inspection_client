import os
from resources.database import get_folder_state


from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QComboBox, QListWidget, QListWidgetItem, QFileDialog
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QColor

class DropArea(QWidget):
    def __init__(self, main_page):
        super().__init__()
        self.setAcceptDrops(True)
        self.main_page = main_page
        self.label = QLabel("Drag and drop folders here", self)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        print('event')
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            for url in urls:
                print(url.toLocalFile())
                folder_path = url.toLocalFile()
                if os.path.isdir(folder_path) and folder_path not in self.main_page.selected_folders:
                    print('ok')
                    self.main_page.add_folder_to_list(folder_path, get_folder_state(folder_path))
        self.updateTotalFolders()

    def updateTotalFolders(self):
        self.label.setText(f"Selected folders: {len(self.main_page.selected_folders)}. Drag and drop folders here")
