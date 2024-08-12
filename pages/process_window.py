from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog, QListWidget, QListWidgetItem, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resources import utils, database

class ProcessThread(QThread):
    progress_update = pyqtSignal(str)
    processing_done = pyqtSignal()

    def __init__(self, selected_folders, list_widget : QListWidget):
        super().__init__()
        self.selected_folders = selected_folders
        self.list_widget = list_widget

    def run(self):
        for folder in self.selected_folders:
            utils.process_images(folder, os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/temp_images/' + os.path.basename(folder))
            self.progress_update.emit(f'Cut {folder}')
            items = self.list_widget.findItems(folder, Qt.MatchExactly)
            if items:
                item = items[0]
                item.setForeground(Qt.red)
            database.update_folder_state(os.path.basename(folder), 'processed')

        self.processing_done.emit()

class ProcessWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_folders = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Cut Folders')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        self.select_folders_btn = QPushButton('Cut Folders')
        self.folders_list_widget = QListWidget()
        self.start_processing_btn = QPushButton('Start Cutting')
        self.update_label = QLabel('Ready to cut folders...')

        layout.addWidget(self.select_folders_btn)
        layout.addWidget(self.folders_list_widget)
        layout.addWidget(self.start_processing_btn)
        layout.addWidget(self.update_label)

        self.setLayout(layout)

        self.select_folders_btn.clicked.connect(self.select_folders)
        self.start_processing_btn.clicked.connect(self.start_processing)

    def select_folders(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        parent_folder = QFileDialog.getExistingDirectory(self, "Select Parent Directory", options=options)
        if parent_folder:
            for folder_name in os.listdir(parent_folder):
                folder_path = os.path.join(parent_folder, folder_name)
                if os.path.isdir(folder_path) and folder_path not in self.selected_folders:
                    self.add_folder_to_list(folder_path, database.get_folder_state(os.path.basename(folder_path)))
                    
    def add_folder_to_list(self, folder, state):
        item = QListWidgetItem(folder)
        if state == 'processed':
            item.setForeground(Qt.red)
        elif state == 'inspected':
            item.setForeground(QColor("#008080"))
        elif state == 'opened':
            item.setForeground(Qt.purple)
        elif state == 'passed':
            item.setForeground(Qt.green)
        else:
            item.setForeground(Qt.gray)
        self.folders_list_widget.addItem(item)
        self.selected_folders.append(folder)

    def start_processing(self):
        if not self.selected_folders:
            self.update_label.setText("No folders selected for cutting.")
            return

        self.thread = ProcessThread(self.selected_folders, self.folders_list_widget)
        self.thread.progress_update.connect(self.update_label.setText)
        self.thread.processing_done.connect(self.processing_done)
        self.thread.start()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            item = self.folders_list_widget.currentItem()
            if item:
                folder_path = item.text()
                self.selected_folders.remove(folder_path)
                self.folders_list_widget.takeItem(self.folders_list_widget.row(item))
        else:
            super().keyPressEvent(event)

    def processing_done(self):
        self.update_label.setText("Cutting completed.")
