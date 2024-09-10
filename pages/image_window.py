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


GRID_DIMENSIONS = (int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")), int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))) # [0] : x-columns
PATCH_DIMENSIONS = (int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE")) / GRID_DIMENSIONS[0], int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE")) / GRID_DIMENSIONS[1])

class ImageWindow(QWidget):
    def __init__(self, image_path, parent, view_only=False, zoom_scale = 1.0, offset_x=100):
        super().__init__()
        self.image_path = image_path
        self.parent = parent
        self.extra_patches_x = 5
        self.extra_patches_y = 5
        self.extra_offset = 20
        self.patch_size = PATCH_DIMENSIONS[0]
        self.view_only = view_only
        self.initUI(zoom_scale, offset_x)

    def initUI(self, zoom_scale, offset_x):
        self.setWindowTitle('Image Window')
        self.setGeometry(offset_x, 100, 1500, 800)
        
        layout = QVBoxLayout()
        
        self.image_label = QLabel()
        self.pixmap = QPixmap(self.image_path)
        self.image_label.setPixmap(self.pixmap)
        self.image_label.setScaledContents(True)
        self.image_label.setFixedSize(1500, 800)
        
        self.scene = QGraphicsScene(self)
        self.pixmap_item = self.scene.addPixmap(self.pixmap)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.zoom_scale = zoom_scale
        self.view.scale(self.zoom_scale, self.zoom_scale)

        layout.addWidget(self.view)
        
        self.setLayout(layout)

        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)

        self.selected_patches = {}
        self.hovered_patch = None

    def eventFilter(self, source, event):
        if event.type() == event.MouseMove and not self.view_only:
            self.handle_mouse_move(event)
        elif event.type() == event.MouseButtonPress  and not self.view_only:
            self.handle_mouse_click(event)
        return super().eventFilter(source, event)

    def handle_mouse_move(self, event):
        pos = self.view.mapToScene(event.pos())
        self.hovered_patch = (int(pos.x()), int(pos.y()))
        self.update_scene()

    def handle_mouse_click(self, event):
        pos = self.view.mapToScene(event.pos())

        for i in range(self.extra_patches_x + 1):
            for j in range(self.extra_patches_y + 1):
                int_x = int(pos.x()) + i * self.extra_offset
                int_y = int(pos.y()) + j * self.extra_offset
                print(int_x, int_y)

                if int_x < 0 or int_x - self.patch_size >= self.size().width() or int_y < 0 or int_y - self.patch_size >= self.size().height(): 
                    continue
                if (int_x, int_y) in self.selected_patches:
                    del self.selected_patches[(int_x, int_y)]
                else:
                    if event.button() == Qt.LeftButton:
                        self.select_patch(int_x, int_y, "blurry")
                    elif event.button() == Qt.RightButton:
                        self.select_patch(int_x, int_y, "sharp")
                    elif event.button() == Qt.MiddleButton:
                        self.select_patch(int_x, int_y, "empty")

        self.update_scene()

    def wheelEvent(self, event):
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.zoom_scale *= zoom_in_factor
            self.view.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.zoom_scale *= zoom_out_factor
            self.view.scale(zoom_out_factor, zoom_out_factor)

    def keyPressEvent(self, event):
        if self.view_only:
            return

        if event.key() == Qt.Key_1:
            self.extra_patches_x += 1
        elif event.key() == Qt.Key_2:
            self.extra_patches_x = max(0, self.extra_patches_x - 1)
        elif event.key() == Qt.Key_3:
            self.extra_patches_y += 1
        elif event.key() == Qt.Key_4:
            self.extra_patches_y = max(0, self.extra_patches_y - 1)
        elif event.key() == Qt.Key_5:
            self.extra_patches_x += 10
        elif event.key() == Qt.Key_6:
            self.extra_patches_y += 10
        self.update_scene()

    def update_scene(self):
        self.scene.clear()
        self.scene.addPixmap(self.pixmap)
        self.highlight_patch()
        for (x, y), category in self.selected_patches.items():
            self.draw_patch(x, y, category)

    def highlight_patch(self):
        if self.hovered_patch:
            x, y = self.hovered_patch
            patch_rect = QRectF(x, y, PATCH_DIMENSIONS[0] + self.extra_patches_x * self.extra_offset, PATCH_DIMENSIONS[1] + self.extra_patches_y * self.extra_offset)
            highlight_item = self.scene.addRect(patch_rect, QPen(Qt.NoPen), QColor(0, 0, 255, 100))

    def draw_patch(self, x, y, category):
        patch_rect = QRectF(x, y, PATCH_DIMENSIONS[0], PATCH_DIMENSIONS[1])
        if category == "blurry":
            color = QColor(255, 0, 0, 10)
        elif category == "empty":
            color = QColor(255, 255, 0, 10)
        else:
            color = QColor(0, 255, 0, 10)

        self.scene.addRect(patch_rect, QPen(Qt.NoPen), color)

    

    def select_patch(self, x, y, category):
        self.selected_patches[(x, y)] = category

    def closeEvent(self, event):
        if self.view_only:
            event.accept()
            return
        self.save_patches()
        event.accept()

    def save_patches(self):
        try:
            base_folder = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'patches')
            retry_makedirs(base_folder)
            for (x, y), category in self.selected_patches.items():
                img = Image.open(self.image_path)
                patch = self.get_patch_image(x, y, img)
                category_folder = os.path.join(base_folder, category)
                retry_makedirs(category_folder)
                patch_filename = f"{os.path.basename(self.image_path).split('.')[0]}_{x}_{y}.png"
                patch_path = os.path.join(category_folder, patch_filename)
                patch.save(patch_path)
        except:
            print('error in save patches for new preset')

    def get_patch_image(self, x, y, img):
        left = x
        top = y
        right = left + PATCH_DIMENSIONS[0]
        bottom = top + PATCH_DIMENSIONS[1]
        return img.crop((left, top, right, bottom))
