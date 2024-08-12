# ImageInspector/pages/new_preset_page.py

import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import sys
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resources import utils
from resources.features import extract_features
from resources.svm import PatchLoader, train_svm
from pages.image_window import ImageWindow
from sklearn.preprocessing import LabelEncoder

import mplcursors
import os
from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen

from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import joblib
import numpy as np
import cv2
import matplotlib.pyplot as plt 
from resources.retry import *
from components.patch_window import PatchWindow

class NewPresetPage(QWidget):
    # constructor
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget

        self.selected_folder = ""
        self.opened_images = set()
        self.initUI()

    # add widgets
    def initUI(self):
        self.setWindowTitle('New Preset Page')
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        
        self.select_folder_btn = QPushButton('Select Folder')
        self.selected_folder_label = QLabel('No folder selected')
        self.image_list_widget = QListWidget()
        self.preset_name_field = QLineEdit()
        self.preset_name_field.setPlaceholderText('Enter preset name')
        self.train_btn = QPushButton('Train')
        #self.train_btn.setEnabled(False)  # Initially disabled
        back_btn = QPushButton('Back to Main Page')

        layout.addWidget(self.select_folder_btn)
        layout.addWidget(self.selected_folder_label)
        layout.addWidget(self.image_list_widget)
        layout.addWidget(self.preset_name_field)
        layout.addWidget(self.train_btn)
        layout.addWidget(back_btn)

        self.setLayout(layout)

        self.select_folder_btn.clicked.connect(self.select_folder_action)
        self.image_list_widget.itemClicked.connect(self.open_image_action)
        self.train_btn.clicked.connect(self.train_svm_action)
        back_btn.clicked.connect(self.back_to_main_page_action)

    # -----------------
    # button callbacks
    # -----------------
    
    def select_folder_action(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", options=options)
        if folder:
            self.selected_folder = folder
            self.selected_folder_label.setText(f'Selected folder: {folder}')
            
            temp_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"),'temp_images', 'temp_preset_images')
            print(temp_folder)
            utils.read_images(folder, temp_folder)
            self.populate_image_list(temp_folder)

    def open_image_action(self, item):
        image_path = item.data(Qt.UserRole)
        print(f"Current opened images set: {self.opened_images}")
        if image_path not in self.opened_images:
            print(f"Trying to open image at: {image_path}")
            if os.path.exists(image_path):
                print(f"Image exists at: {image_path}")
                self.image_window = ImageWindow(image_path, self)
                self.image_window.show()
                self.opened_images.add(image_path)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)  # Disable the item
                print(f"Opened images: {self.opened_images}")
            else:
                print(f"Image does not exist at: {image_path}")
        else:
            print(f"Image already opened: {image_path}")

    # trains the svm from the patches directory, stores relevant objects in appropriate presets folder
    def train_svm_action(self):
        # get preset name
        preset_name = self.preset_name_field.text().strip()
        if not preset_name:
            print("Preset name cannot be empty")
            return
        
        svm, scaler, pca, features, labels, patch_names = train_svm(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'patches'))
        
        # Save the SVM, scaler, and PCA model
        presets_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets')
        
        retry_makedirs(presets_folder)

        joblib.dump((svm, scaler, pca), os.path.join(presets_folder, f'{preset_name}.pkl'))

        for i in range(len(features[0]) - 1):
            self.plot_pca(features, labels, scaler, pca, patch_names, i + 1)

    def back_to_main_page_action(self):
        self.stacked_widget.setCurrentIndex(0)
        self.stacked_widget.currentWidget().load_presets_action()

    # ----------------
    # other functions
    # ----------------

    # plots pca on the new preset's data
    def plot_pca(self, features, labels, scaler, pca, patch_names, starting_pc=1):
        # Encode labels as numeric values
        label_encoder = LabelEncoder()
        numeric_labels = label_encoder.fit_transform(labels)
        print('what', numeric_labels)

        # Define custom colors for each label
        colors = {
            'blurry': 'red',
            'sharp': 'green',
            'empty': 'yellow',
            'indeterminate': 'purple'
        }
        color_list = [colors[label_encoder.inverse_transform([label])[0]] for label in numeric_labels]

        features_scaled = scaler.transform(features)
        features_reduced = pca.transform(features_scaled)

        plt.figure(figsize=(10, 7))
        scatter = plt.scatter(features_reduced[:, starting_pc - 1], features_reduced[:, starting_pc], c=color_list, cmap='viridis')

        cursor = mplcursors.cursor(scatter, hover=True)
        
        @cursor.connect("add")
        def on_add(sel):
            index = sel.index
            sel.annotation.set_text(patch_names[index])
            sel.annotation.get_bbox_patch().set_alpha(0.6)


        @cursor.connect("add")
        def on_click(sel):
            index = sel.index
            category = labels[index]
            file_name = patch_names[index]
            image_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'patches', category, file_name)
            
            # Open the patch image in a new window
            self.show_patch_window(image_path)

        plt.title('PCA of Image Patches')
        plt.xlabel(f'Principal Component {starting_pc} {pca.components_[starting_pc-1]}')
        plt.ylabel(f'Principal Component {starting_pc + 1} {pca.components_[starting_pc]}')
        
        # Create legend
        handles, _ = scatter.legend_elements()
        unique_labels = label_encoder.inverse_transform(np.unique(numeric_labels))
        plt.legend(handles, unique_labels, title="Classes")

        plt.show()

    def show_patch_window(self, image_path):
        self.patch_window = PatchWindow(image_path)
        self.patch_window.show()


    
    def check_all_items_disabled(self):
        all_disabled = all(not item.flags() & Qt.ItemIsEnabled for item in self.image_list_widget.findItems("*", Qt.MatchWildcard))
        if all_disabled:
            self.train_btn.setEnabled(True)

    # reads dir
    def populate_image_list(self, folder):
        self.image_list_widget.clear()
        for filename in os.listdir(folder):
            item = QListWidgetItem(filename)
            item.setData(Qt.UserRole, os.path.join(folder, filename))
            self.image_list_widget.addItem(item)
        
