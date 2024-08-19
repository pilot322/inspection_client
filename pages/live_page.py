from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QComboBox, QTableWidgetItem, QListWidgetItem, QPushButton, QFileDialog, QListWidget, QMenu
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush, QMouseEvent
from queue import Queue
from time import sleep
import os
import sys
import joblib
from resources.utils import process_and_save_image
from multiprocessing import Manager
import threading
from keras.api.models import load_model
from resources.cnn import predict_blur

class QueueMonitor(QThread):
    def __init__(self, manager_queue):
        super().__init__()
        self.manager_queue = manager_queue
        self._running = True
        self.model = load_model(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"),'blur_detection_model.keras'))


    def run(self):
        while self._running:
            labeled_patches = self.manager_queue.get()
            n = len(labeled_patches)
            if labeled_patches == 'DONE':
                break
            if labeled_patches == None:
                print('none detected in monitor queue')
                continue

            new_labeled_patches = []

            for labeled_patch in labeled_patches:
                if labeled_patch[2] == 'blurry' or labeled_patch[2] == 'indeterminate':
                    new_labeled_patches.append(labeled_patch)
            
            labeled_patches = new_labeled_patches
            patches = [labeled_patches[i][0] for i in range(len(labeled_patches))]
            
            results = predict_blur(patches, self.model)

            count = 0

            for result in results:
                if result:
                    count += 1

            print(f'number of blurries: {count} / {n}')

class FolderWatcher(QThread):
    def __init__(self, folder_to_watch, new_image_signal):
        super().__init__()
        self.folder_to_watch = folder_to_watch
        self.new_image_signal = new_image_signal
        self._running = True
        self.processed_files = set()

        for file_name in sorted(os.listdir(self.folder_to_watch)):
            file_path = os.path.join(self.folder_to_watch, file_name)
            if file_path not in self.processed_files and file_name.endswith(('.tif')):
                self.processed_files.add(file_path)

    def run(self):
        while self._running:
            print('watching')
            for file_name in sorted(os.listdir(self.folder_to_watch)):
                file_path = os.path.join(self.folder_to_watch, file_name)
                if file_path not in self.processed_files and file_name.endswith(('.tif')):
                    sleep(4)
                    self.processed_files.add(file_path)
                    self.new_image_signal.emit(file_path)
            sleep(1)  # Check for new files every second

    def stop(self):
        self._running = False
        self.wait()

class LivePage(QWidget):
    new_image_signal = pyqtSignal(str)

    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.initUI()

        self.watcher_thread = None
        self.watched_folder = ""
        self.selected_preset = ""
        self.new_image_signal.connect(self.process_new_image)

    def initUI(self):
        self.setWindowTitle('Live Mode')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        self.update_label = QLabel('No folder selected')
        self.folder_btn = QPushButton('Select Folder')
        self.preset_combo = QComboBox()
        self.load_presets()
        self.start_btn = QPushButton('Start Watching')
        self.back_btn = QPushButton('Back to main')

        self.folder_btn.clicked.connect(self.select_folder_action)
        self.start_btn.clicked.connect(self.start_watching)
        self.back_btn.clicked.connect(self.back_to_main_page_action)

        layout.addWidget(self.update_label)
        layout.addWidget(self.folder_btn)
        layout.addWidget(QLabel('Select Preset:'))
        layout.addWidget(self.preset_combo)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.back_btn)

        self.setLayout(layout)

    def load_presets(self):
        presets_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets')
        if os.path.exists(presets_folder):
            for file_name in os.listdir(presets_folder):
                if file_name.endswith('.pkl'):
                    self.preset_combo.addItem(file_name)

    def select_folder_action(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.watched_folder = folder
            self.update_label.setText(f'Watching folder: {folder}')
            self.temp_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_images', os.path.basename(folder))

    def start_watching(self):
        if not self.watched_folder or not self.preset_combo.currentText() or self.watcher_thread:
            self.watcher_thread.stop()
            self.monitor_thread.stop()
            self.update_label.setText('Please select a folder and a preset')
            self.start_btn.setText('Start Watching')
            #self.start_btn.setColor('white')
            self.preset_combo.setDisabled(False)
            self.back_btn.setDisabled(False)
            self.folder_btn.setDisabled(False)
            self.watcher_thread = None
            self.monitor_thread = None
            return

        self.selected_preset = self.preset_combo.currentText()
        preset_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets', self.selected_preset)
        
        try:
            self.svm, self.scaler, self.pca = joblib.load(preset_path)
        except Exception as e:
            print(f"Error loading SVM model: {e}")
            return
        
        self.preset_combo.setDisabled(True)
        self.back_btn.setDisabled(True)
        self.folder_btn.setDisabled(True)
        
        self.watcher_thread = FolderWatcher(self.watched_folder, self.new_image_signal)
        self.watcher_thread.start()
        self.update_label.setText(f'Started watching folder: {self.watched_folder}')
        
        self.manager = Manager()
        self.manager_queue = self.manager.Queue()
        self.monitor_thread = QueueMonitor(self.manager_queue)
        self.monitor_thread.start()

    def process_new_image(self, image_path):
        sleep(7)
        self.update_label.setText(f'Processing image: {image_path}')
        
        process_and_save_image(image_path, self.watched_folder, self.temp_folder, None, None, None, None)
        # self.inspect_image(temp_folder)

    def inspect_image(self, temp_folder):

        #utils.inspect_folder(temp_folder, self.selected_preset, lambda x: None)
        self.update_label.setText('Image processed and inspected')

    def back_to_main_page_action(self):
        if self.watcher_thread:
            self.watcher_thread.stop()
        self.stacked_widget.setCurrentIndex(0)