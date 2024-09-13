from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QComboBox, QTableWidgetItem, QListWidgetItem, QPushButton, QFileDialog, QListWidget, QMenu
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from queue import Queue
from time import sleep
import os
from pages.point_report_window import PointReportWindow
from resources.live_handler import LiveHandler

next_num_page = '0'
recent_half_paths = []
inspecting = False

class FolderWatcher(QThread):
    def __init__(self, folder_to_watch, new_image_signal):
        super().__init__()
        self.folder_to_watch = folder_to_watch
        self.new_image_signal = new_image_signal
        self._running = True
        self.processed_files = set()

        for file_name in sorted(os.listdir(self.folder_to_watch)):
            file_path = os.path.join(self.folder_to_watch, file_name)
            if file_path not in self.processed_files:
                self.processed_files.add(file_path)

    def run(self):
        global inspecting
        while self._running:
            sleep(0.05)  # Check for new files every second
            if inspecting:
                continue
            #print('watching')
            for file_name in sorted(os.listdir(self.folder_to_watch)):
                file_path = os.path.join(self.folder_to_watch, file_name)
                if file_path not in self.processed_files :
                    print(f'new file detected: {file_name}')
                    self.processed_files.add(file_path)
                    if file_name.endswith(('.tif')):
                        global next_num_page
                        self.new_image_signal.emit(file_path)
                        next_num_page = file_name[:4]
           
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

            if self.live_handler:
                self.live_handler.stop()

            self.live_handler = None
            return
        
        self.selected_preset = self.preset_combo.currentText()
        
        self.live_handler = LiveHandler(self.selected_preset)
    
        self.start_btn.setText('Stop Watching')
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #aa0000;                       
            }
        """)
        
        self.preset_combo.setDisabled(True)
        self.back_btn.setDisabled(True)
        self.folder_btn.setDisabled(True)
        
        self.watcher_thread = FolderWatcher(self.watched_folder, self.new_image_signal)
        self.watcher_thread.start()

        
        self.point_report_map = PointReportWindow()
        
        self.live_handler.result_ready.connect(self.point_report_map.draw_points)
        self.live_handler.start_watching(self.watched_folder, self.temp_folder)
        self.update_label.setText(f'Started watching folder: {self.watched_folder}')
        

    def process_new_image(self, image_path):
        i = 0
        while not os.path.exists(image_path):
            #print('overwrite, probably?')
            i += 1
            sleep(0.1)
            if i == 10:
                return

        self.update_label.setText(f'Processing image: {image_path}')
        self.live_handler.add_image(image_path)
        
    def back_to_main_page_action(self):
        if self.watcher_thread:
            self.watcher_thread.stop()
        self.stacked_widget.setCurrentIndex(0)