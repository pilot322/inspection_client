import os
import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QToolTip
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRectF, QTimer
import cv2
import numpy as np
from resources.retry import read_image_with_retry, write_image_with_retry

class CollageCutterWindow(QWidget):
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.barcode = os.path.basename(folder_path)
        self.marked_patches = set()  # Store marked patches
        self.initUI()
        self.dimensions = (int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")), int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")))
        self.patch_size = (int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE"))) // int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))

        QTimer.singleShot(10, lambda: self.activateWindow())
        QTimer.singleShot(15, lambda: self.showMaximized())
        

    def initUI(self):
        self.setWindowTitle(f'{self.barcode} Collage Inspector')
        self.setGeometry(100, 100, 1200, 800)
        
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        self.tab_paths = []
        for subdir in os.listdir(self.folder_path):
            subdir_path = os.path.join(self.folder_path, subdir)
            if not os.path.exists(subdir_path):
                continue
            
            for file_name in os.listdir(subdir_path):
                if file_name.endswith('.png'):
                    tab = QWidget()
                    self.tab_paths.append((subdir, file_name))
                    self.tabs.addTab(tab, f'{subdir}/{file_name}')
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        self.tabs.currentChanged.connect(self.load_tab)
        self.tabs.setFocusPolicy(Qt.StrongFocus)
        self.tabs.keyPressEvent = self.handle_key_press_event

        self.load_tab(0)

        save_button = QPushButton("Save Marked Patches")
        save_button.clicked.connect(self.save_marked_patches)
        layout.addWidget(save_button)

    def load_tab(self, index):
        tab = self.tabs.widget(index)
        if tab.layout():
            return  # Already loaded
        
        subdir, file_name = self.tab_paths[index]
        file_path = os.path.join(self.folder_path, subdir, file_name)
        metadata_path = file_path.replace('.png', '.metadata')
        
        tab_layout = QVBoxLayout()
        graphics_view = ZoomableGraphicsView(self)
        graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        graphics_view.setRenderHint(QPainter.Antialiasing)
        graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        graphics_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        scene = QGraphicsScene()
        pixmap = QPixmap(file_path)
        pixmap_item = QGraphicsPixmapItem(pixmap)
        scene.addItem(pixmap_item)
        graphics_view.setScene(scene)

        tab_layout.addWidget(graphics_view)
        tab.setLayout(tab_layout)

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as file:
                metadata = file.read().strip().split()
            graphics_view.metadata = metadata
            graphics_view.mouseMoveEvent = lambda event: self.show_tooltip(event, metadata, graphics_view)
            graphics_view.mousePressEvent = lambda event: self.mark_patch(event, metadata, graphics_view)
        
        QTimer.singleShot(0, lambda: self.reset_scrollbars(graphics_view))

    def reset_scrollbars(self, graphics_view):
        graphics_view.verticalScrollBar().setValue(0)
        graphics_view.horizontalScrollBar().setValue(0)

    def show_tooltip(self, event, metadata, graphics_view):
        pos = graphics_view.mapToScene(event.pos())
        x = pos.x()
        y = pos.y()
        
        row = int(y // self.patch_size)
        col = int(x // self.patch_size)
        index = row * self.dimensions[1] + col

        if index >= 0 and index < len(metadata):
            page_number = metadata[index]
            QToolTip.showText(event.globalPos(), f'Page: {page_number}', graphics_view)
        
        event.ignore()

    def mark_patch(self, event, metadata, graphics_view):
        if event.button() == Qt.LeftButton:
            pos = graphics_view.mapToScene(event.pos())
            x = pos.x()
            y = pos.y()
            
            row = int(y // self.patch_size)
            col = int(x // self.patch_size)
            index = row * self.dimensions[1] + col

            if index >= 0 and index < len(metadata):
                patch_key = (graphics_view, row, col)
                if patch_key in self.marked_patches:
                    self.marked_patches.remove(patch_key)
                    self.paint_patch(graphics_view.scene(), row, col, QColor(0, 0, 0, 0), repaint=True)  # Unmark and repaint original
                else:
                    self.marked_patches.add(patch_key)
                    self.paint_patch(graphics_view.scene(), row, col, QColor(255, 0, 0, 100))  # Mark as blurry

    def paint_patch(self, scene, row, col, color, repaint=False):
        if repaint:
            items = scene.items(QRectF(col * self.patch_size, row * self.patch_size, self.patch_size, self.patch_size))
            for item in items:
                if isinstance(item, QGraphicsPixmapItem):
                    scene.removeItem(item)

            pixmap_item = QGraphicsPixmapItem(QPixmap(self.tabs.tabText(self.tabs.currentIndex())))
            pixmap_item.setOffset(col * self.patch_size, row * self.patch_size)
            scene.addItem(pixmap_item)
        else:
            pen = QPen(color, 2)
            brush = color
            x = col * self.patch_size
            y = row * self.patch_size
            patch_rect = QRectF(x, y, self.patch_size, self.patch_size)
            scene.addRect(patch_rect, pen, brush)

    def save_marked_patches(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_images', self.barcode + '_' + str(timestamp))
        blurry_path = os.path.join(save_path, 'blurry')
        indeterminate_path = os.path.join(save_path, 'indeterminate')

        os.makedirs(blurry_path, exist_ok=True)
        os.makedirs(indeterminate_path, exist_ok=True)

        patch_counter = 1
        tab_index = self.tabs.currentIndex()
        self.load_tab(tab_index)
        tab = self.tabs.widget(tab_index)
        if not tab:
            return

        tab_layout = tab.layout()
        if tab_layout is None:
            return

        graphics_view = None
        for i in range(tab_layout.count()):
            widget = tab_layout.itemAt(i).widget()
            if isinstance(widget, ZoomableGraphicsView):
                graphics_view = widget
                break

        if graphics_view is None:
            return

        subdir, file_name = self.tab_paths[tab_index]
        file_path = os.path.join(self.folder_path, subdir, file_name)
        metadata_path = file_path.replace('.png', '.metadata')

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as file:
                metadata = file.read().strip().split()
            graphics_view.metadata = metadata

        image_np = read_image_with_retry(file_path, cv2.IMREAD_GRAYSCALE)
        
        rows, cols = image_np.shape[:2]
        rows //= self.dimensions[0]
        for row in range(rows):
            for col in range(self.dimensions[0]):
                index = row * self.dimensions[1] + col
                if index >= len(metadata):
                    continue

                x = col * self.patch_size
                y = row * self.patch_size
                patch = image_np[y:y + self.patch_size, x:x + self.patch_size]

                # Check if patch is not a placeholder (not entirely black)
                if np.all(patch == 0):
                    continue

                # Save the patch
                patch_file_name = f'{self.barcode}_{timestamp}_{patch_counter}.png'
                patch_counter += 1
                if (graphics_view, row, col) in self.marked_patches:
                    cv2.imwrite(os.path.join(blurry_path, patch_file_name), patch)
                else:
                    cv2.imwrite(os.path.join(indeterminate_path, patch_file_name), patch)

        print(f"Saved {patch_counter-1} patches to {save_path}")

    def qimage_to_numpy(self, image):
        """Convert QImage to numpy array for grayscale images."""
        image = image.convertToFormat(4)  # Convert to 8-bit grayscale format
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        arr = np.array(ptr).reshape(height, width, 4)  # Copy the data into an array
        return arr[:, :, 0]  # Return only the grayscale channel

    def handle_key_press_event(self, event):
        if event.key() == Qt.Key_Right:
            current_index = self.tabs.currentIndex()
            next_index = (current_index + 1) % self.tabs.count()
            self.tabs.setCurrentIndex(next_index)
        elif event.key() == Qt.Key_Left:
            current_index = self.tabs.currentIndex()
            prev_index = (current_index - 1 + self.tabs.count()) % self.tabs.count()
            self.tabs.setCurrentIndex(prev_index)
        else:
            super().keyPressEvent(event)

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor

            if event.angleDelta().y() > 0:
                factor = zoom_in_factor
            else:
                factor = zoom_out_factor

            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor

            if event.angleDelta().y() > 0:
                factor = zoom_in_factor
            else:
                factor = zoom_out_factor

            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)