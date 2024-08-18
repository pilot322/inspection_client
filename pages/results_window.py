import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QToolTip, QHBoxLayout, QLabel, QFileDialog
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRectF, QTimer
from pages.image_window import ImageWindow

class ResultsWindow(QWidget):
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.barcode = os.path.basename(folder_path)
        self.processed_images_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_images', self.barcode)
        self.initUI()
        self.dimensions = (int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")), int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")))
        self.patch_size = (int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE"))) // int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))
        self.colors = [(255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0), (0,0,255), (75, 0, 130), (148, 0, 211)]
        self.next_color_index = 0
        QTimer.singleShot(10, lambda: self.activateWindow())
        QTimer.singleShot(15, lambda: self.showMaximized())
        

    def initUI(self):
        self.setWindowTitle(f'{self.barcode} Results')
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

    def load_tab(self, index):
        tab = self.tabs.widget(index)
        if tab.layout():
            return  # Already loaded
        
        subdir, file_name = self.tab_paths[index]
        file_path = os.path.join(self.folder_path, subdir, file_name)
        metadata_path = file_path.replace('.png', '.metadata')
        
        tab_layout = QVBoxLayout()
        graphics_view = ZoomableGraphicsView()
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
            graphics_view.mousePressEvent = lambda event: self.open_page_image(event, metadata, graphics_view)
        
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

    def open_page_image(self, event, metadata, graphics_view):
        if event.button() == Qt.LeftButton:
            pos = graphics_view.mapToScene(event.pos())
            x = pos.x()
            y = pos.y()
            
            row = int(y // self.patch_size)
            col = int(x // self.patch_size)
            index = row * self.dimensions[1] + col

            if index >= 0 and index < len(metadata):
                page_number = metadata[index]
                self.show_page_images(page_number)

                # Paint all patches of the page black
                self.paint_patches_black(graphics_view.scene(), metadata, page_number)

    def paint_patches_black(self, scene, metadata, page_number):
        pen = QPen(QColor(255, 255, 255, 255), 2)
        brush = QColor(self.colors[self.next_color_index][0],self.colors[self.next_color_index][1],self.colors[self.next_color_index][2], 100)
        self.next_color_index += 1
        self.next_color_index %= len(self.colors)
        for idx, page in enumerate(metadata):
            if page == page_number:
                row = idx // self.dimensions[0]
                col = idx % self.dimensions[1]
                x = col * self.patch_size
                y = row * self.patch_size
                patch_rect = QRectF(x, y, self.patch_size, self.patch_size)
                scene.addRect(patch_rect, pen, brush)

    def show_page_images(self, page_number):
        left_image_path = os.path.join(self.processed_images_path, f'{page_number}_Main_frame_left.png')
        right_image_path = os.path.join(self.processed_images_path, f'{page_number}_Main_frame_right.png')

        if not os.path.exists(left_image_path) or not os.path.exists(right_image_path):
            return

        self.image_window_left = ImageWindow(left_image_path, self)
        self.image_window_right = ImageWindow(right_image_path, self)
        self.image_window_left.show()
        self.image_window_right.show()

    def show_page_images_old(self, page_number):
        left_image_path = os.path.join(self.processed_images_path, f'{page_number}_Main_frame_left.png')
        right_image_path = os.path.join(self.processed_images_path, f'{page_number}_Main_frame_right.png')

        if not os.path.exists(left_image_path) or not os.path.exists(right_image_path):
            return

        page_window = QWidget()
        page_window.setWindowTitle(f'Page {page_number}')
        page_window.setGeometry(100, 100, 1200, 600)
        
        layout = QHBoxLayout()
        
        left_view = ZoomableGraphicsView()
        right_view = ZoomableGraphicsView()

        left_scene = QGraphicsScene()
        right_scene = QGraphicsScene()

        left_pixmap = QPixmap(left_image_path)
        right_pixmap = QPixmap(right_image_path)

        left_item = QGraphicsPixmapItem(left_pixmap)
        right_item = QGraphicsPixmapItem(right_pixmap)

        left_scene.addItem(left_item)
        right_scene.addItem(right_item)

        left_view.setScene(left_scene)
        right_view.setScene(right_scene)

        left_view.setDragMode(QGraphicsView.ScrollHandDrag)
        right_view.setDragMode(QGraphicsView.ScrollHandDrag)

        left_view.setRenderHint(QPainter.Antialiasing)
        left_view.setRenderHint(QPainter.SmoothPixmapTransform)
        right_view.setRenderHint(QPainter.Antialiasing)
        right_view.setRenderHint(QPainter.SmoothPixmapTransform)

        left_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        left_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        right_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        right_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Initial zoom out
        left_view.scale(0.8, 0.8)
        right_view.scale(0.8, 0.8)

        layout.addWidget(left_view)
        layout.addWidget(right_view)
        
        page_window.setLayout(layout)
        page_window.show()

        self.page_window = page_window

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
