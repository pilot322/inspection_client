import sys
import os
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QComboBox, QTableWidgetItem, QListWidgetItem, QPushButton, QFileDialog, QListWidget, QMenu, QApplication
from PyQt5.QtCore import QThread, pyqtSignal, Qt, pyqtSlot
from PyQt5.QtGui import QColor

from queue import Queue

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resources import utils
from resources.features import extract_features
from resources import svm
from pages.collage_cutter import CollageCutterWindow
from pages.results_window import ResultsWindow
from pages.process_window import ProcessWindow
from resources.database import initialize_db, update_folder_state, get_all_folders, get_folder_state
from resources.retry import retry_makedirs
from components.drop_area import DropArea
from components.selection_table import SelectionTable
from time import sleep

class InspectionThread(QThread):
    progress_update = pyqtSignal(str)
    inspection_done = pyqtSignal()
    state_update = pyqtSignal(dict)

    def __init__(self, folder_dir, preset_name, cutFlag, inspectFlag):
        super().__init__()
        self.folder_dir = folder_dir
        self.preset_name = preset_name
        self.folder_queue = Queue()
        self.cutFlag = cutFlag
        self.inspectFlag = inspectFlag
        
        self._running = True

    def run(self):
        if self.cutFlag:
            self.progress_update.emit(f'Cutting {os.path.basename(self.folder_dir)}, please wait...')
            utils.process_images(self.folder_dir, os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_images', os.path.basename(self.folder_dir)))
            print('d1')
            sleep(1)
            self.progress_update.emit(f'Cut {os.path.basename(self.folder_dir)}.')
            print('d2')
            print('d3')
            self.state_update.emit({'dir': self.folder_dir, 'state': 'cut'})
            print('d7')
            update_folder_state(self.folder_dir, 'processed')
            print('d8')
            sleep(1)
        if self.inspectFlag:
            print('d9')
            self.progress_update.emit('Inspection started')
            sleep(1)
            print('d10')
            svm.inspect_folder(self.folder_dir, self.preset_name, self.progress_update)
            print('d11')
            update_folder_state(self.folder_dir, 'inspected')
            print('d12')
            self.state_update.emit({'dir': self.folder_dir, 'state': 'inspected'})
            sleep(1)

        self.inspection_done.emit()

    @pyqtSlot()
    def stop(self):
        self._running = False
        self.wait()


class MainPage(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.folder_queue = Queue()
        self.selected_folders = []
        self.worker_thread = None
        self.advanced = False
        self.initUI()
        self.load_presets_action()
        self.setFocusPolicy(Qt.StrongFocus)

    def initUI(self):
        self.setWindowTitle('Main Page')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        self.live_btn = QPushButton('Live')
        self.drop_area = DropArea(self)
        self.folder_table = SelectionTable(self)
        self.new_preset_btn = QPushButton('Create new preset')
        self.preset_combo = QComboBox()
        self.start_inspection_action_btn = QPushButton('Start Inspection')
        self.view_results_action_btn = QPushButton('View Results')
        self.cut_collage_button = QPushButton("Open Collage Inspector")
        self.update_label = QLabel('. . .')

        self.live_btn.setDisabled(True)

        layout.addWidget(self.live_btn)
        layout.addWidget(self.drop_area)
        layout.addWidget(self.folder_table)
        layout.addWidget(self.preset_combo)
        layout.addWidget(self.start_inspection_action_btn)
        layout.addWidget(self.view_results_action_btn)
        layout.addWidget(self.update_label)

        self.setLayout(layout)

        self.live_btn.clicked.connect(self.open_live_action)
        self.start_inspection_action_btn.clicked.connect(self.start_inspection_action)
        self.view_results_action_btn.clicked.connect(self.view_results_action)
        self.new_preset_btn.clicked.connect(self.create_new_preset_action)
        self.cut_collage_button.clicked.connect(self.cut_collage_action_btn)

    def open_live_action(self):
        self.stacked_widget.setCurrentIndex(2)

    def create_new_preset_action(self):
        self.stacked_widget.setCurrentIndex(1)

    def load_presets_action(self):
        self.preset_combo.clear()
        presets_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets')
        retry_makedirs(presets_folder)
        for filename in os.listdir(presets_folder):
            if filename.endswith('.pkl'):
                self.preset_combo.addItem(filename)

    def open_process_window_action(self):
        self.process_window = ProcessWindow()
        self.process_window.show()

    def select_processed_folders_action(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        parent_folder = QFileDialog.getExistingDirectory(self, "Select Parent Directory", options=options)
        if parent_folder:
            for folder_name in os.listdir(parent_folder):
                folder_path = os.path.join(parent_folder, folder_name)
                if os.path.isdir(folder_path) and folder_name not in self.selected_folders:
                    self.add_folder_to_list(folder_name, get_folder_state(folder_name))

    def cut_collage_action_btn(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'collages'), options=options)
        if folder_path:
            self.collage_inspector_window = CollageCutterWindow(folder_path)
            self.collage_inspector_window.show()

    def start_inspection_action(self):
        self.start_inspection_action_btn.setDisabled(True)
        self.folder_table.setDisabled(True)
        self.folder_table.clearSelection()

        if not self.selected_folders:
            self.update_label.setText("No folder selected for inspection.")
            self.start_inspection_action_btn.setDisabled(False)
            self.folder_table.setDisabled(False)
            return

        for folder in self.selected_folders:
            self.folder_queue.put(folder)

        self.process_next_folder()

    def view_results_action(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'collages'), options=options)
        if folder_path:
            self.results_window = ResultsWindow(folder_path)
            self.results_window.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_CapsLock:
            if self.advanced:
                self.layout().removeWidget(self.new_preset_btn)
                self.new_preset_btn.setVisible(False)
                self.layout().removeWidget(self.cut_collage_button)
                self.cut_collage_button.setVisible(False)
            else:
                self.layout().addWidget(self.new_preset_btn)
                self.new_preset_btn.setVisible(True)
                self.layout().addWidget(self.cut_collage_button)
                self.cut_collage_button.setVisible(True)
            self.advanced = not self.advanced

        if event.key() == Qt.Key_Delete:
            selected_rows = self.folder_table.selectionModel().selectedRows()
            indexes = [row.row() for row in selected_rows]
            for index in sorted(indexes, reverse=True):
                folder_path = self.folder_table.item(index, 0).text()
                self.selected_folders.remove(folder_path)
                self.folder_table.removeRow(index)
            self.drop_area.updateTotalFolders()
        else:
            super().keyPressEvent(event)

    def process_next_folder(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()

        if self.folder_queue.empty():
            self.update_label.setText("Inspection completed.")
            self.start_inspection_action_btn.setDisabled(False)
            self.folder_table.setDisabled(False)
            return

        folder_dir = self.folder_queue.get()
        preset_name = self.preset_combo.currentText()

        table_index = self.folder_table.findItems(folder_dir, Qt.MatchExactly)[0].row()
        cutFlag =self.folder_table.cellWidget(table_index, 1).isChecked()
        inspectFlag = self.folder_table.cellWidget(table_index, 2).isChecked()

        self.worker_thread = InspectionThread(folder_dir, preset_name, cutFlag, inspectFlag)
        self.worker_thread.progress_update.connect(self.update_label.setText)
        self.worker_thread.inspection_done.connect(self.process_next_folder)
        self.worker_thread.state_update.connect(self.update_state)
        self.worker_thread.start()

    def update_state(self, d):
        state = d['state']
        folder_dir = d['dir']

        items = self.folder_table.findItems(folder_dir, Qt.MatchExactly)
        if items:
            item = items[0]
            
            if state == 'cut':
                item.setForeground(QColor("#FF0000"))
            else:
                item.setForeground(QColor("#008080"))
       
        

    def add_folder_to_list(self, folder, state):
        self.folder_table.addFolder(folder)
        self.selected_folders.append(folder)
        self.selected_folders.sort()

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
        event.accept()