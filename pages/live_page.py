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
from resources.svm import read_divide_classify
from pages.point_report_window import PointReportWindow

class QueueMonitor(QThread):
    def __init__(self, manager_queue, send_labeled_patches_callback):
        super().__init__()
        self.manager_queue = manager_queue
        self._running = True
        self.model = load_model(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"),'blur_detection_model.keras'))
        self.send_labeled_patches_callback = send_labeled_patches_callback
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

            new_labeled_patches = []
            for i in range(len(labeled_patches)):
                if results[i]:
                    new_labeled_patches.append(labeled_patches[i])

            self.send_labeled_patches_callback(new_labeled_patches)
            

    def stop(self):
        self._running = False
        self.manager_queue.put('DONE')
        self.wait()

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
            #print('watching')
            for file_name in sorted(os.listdir(self.folder_to_watch)):
                file_path = os.path.join(self.folder_to_watch, file_name)
                if file_path not in self.processed_files :
                    print(f'new file detected: {file_name}')
                    self.processed_files.add(file_path)
                    if file_name.endswith(('.tif')):
                        sleep(1)
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
        self.monitor_thread = None
        self.watched_folder = ""
        self.selected_preset = ""
        self.point_report_map = None
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
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #fafafa;                       
            }
            """
        )
        
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
            self.update_label.setText(f'Selected folder: {folder}')
            self.temp_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_images', os.path.basename(folder))

    def start_watching(self):
        if not self.watched_folder or not self.preset_combo.currentText() or self.watcher_thread is not None:
            if self.watcher_thread:
                self.watcher_thread.stop()
            if self.monitor_thread:
                self.monitor_thread.stop()
            if self.point_report_map:
                self.point_report_map.close()
                self.point_report_map = None
            self.update_label.setText('Please select a folder and a preset' if not self.watched_folder else f'Folder selected: {self.watched_folder}')
            self.start_btn.setText('Start Watching')
            self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #fafafa;                       
            }
            """)
            #self.start_btn.setColor('white')
            self.preset_combo.setDisabled(False)
            self.back_btn.setDisabled(False)
            self.folder_btn.setDisabled(False)
            self.watcher_thread = None
            self.monitor_thread = None
            return
        
        self.point_report_map = PointReportWindow()
        self.start_btn.setText('Stop Watching')
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #aa0000;                       
            }
        """)
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
        self.monitor_thread = QueueMonitor(self.manager_queue, self.point_report_map.draw_points)
        self.monitor_thread.start()

    def process_new_image(self, image_path):
        self.update_label.setText(f'Processing image: {image_path}')
        print(f'paths: {os.path.basename(image_path)} {self.watched_folder} {self.temp_folder}')        
        paths = process_and_save_image(os.path.basename(image_path), self.watched_folder, self.temp_folder, None, None, None, None)
        
        total_labeled_patches = []

        i = 0
        for path in paths:
            labeled_patches = read_divide_classify(path, self.svm, self.pca, self.scaler)

            if i == 1:
                for labeled_patch in labeled_patches:
                    labeled_patch.insert(4, (labeled_patch[4][0] + int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE')),labeled_patch[4][1]))
                    labeled_patch.pop(5)
                    #labeled_patch[4] = (labeled_patch[4][0] + int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE')),labeled_patch[4][1] + int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE')) )
            total_labeled_patches.extend(labeled_patches)
            i += 1
        self.manager_queue.put(total_labeled_patches)
        
    def back_to_main_page_action(self):
        if self.watcher_thread:
            self.watcher_thread.stop()
        self.stacked_widget.setCurrentIndex(0)