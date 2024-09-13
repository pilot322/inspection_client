from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QPoint, pyqtSlot
from PyQt5.QtGui import QPainter, QPen, QColor
import sys
from components.point_report_map import PointReportMapWidget
import os
from time import sleep
from pages.image_window import ImageWindow

class PointReportWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.image_paths = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Report')
        self.d = 200
        self.setGeometry(100, 100, self.d, self.d)

        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

         # Make the window background transparent
        #self.setAttribute(Qt.WA_TranslucentBackground)

        # Set the window opacity (0.0 is fully transparent, 1.0 is fully opaque)
        #self.setWindowOpacity(0.7)

        layout = QVBoxLayout()
        
        # Create an instance of the custom PointDrawingWidget
        self.point_drawing_widget = PointReportMapWidget()
        
        # Add the drawing widget to the layout
        layout.addWidget(self.point_drawing_widget)
        
        self.setLayout(layout)

        #self.draw_points([(0,0), (100, 100), (200, 200), (250, 250), (300, 300)])

        self.show()

    @pyqtSlot(list)
    def draw_points(self, labeled_patches : list):
        num_of_page = labeled_patches.pop()
        self.image_paths = labeled_patches.pop()
        self.setWindowTitle(num_of_page)
        grid_size = int(os.getenv('INSPECTION_CLIENT_GRID_SIZE'))
        image_size = int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE'))
        patch_height = image_size // grid_size
        # for labeled_patch in labeled_patches:
        #     print(labeled_patch)
        map_to_ij = lambda x : (self.d // (grid_size + 1)*(1 + (x - patch_height // 2) // patch_height))

        temp = ""
        for labeled_patch in labeled_patches:
            temp += str(labeled_patch[4]) + " "
        print(temp)

        points = [(map_to_ij(labeled_patch[4][0]) // 2, map_to_ij(labeled_patch[4][1])) for labeled_patch in labeled_patches]
        
        h = grid_size
        w = grid_size * 2
        #print(points)
        og = [[False for j in range(w)] for i in range(h)]
        #print('h, w:',h, w)
        for labeled_patch in labeled_patches:
            j = labeled_patch[6][0]
            i = labeled_patch[6][1]
            #print(i, j)
            og[i][j] = True
        try:
            indication = self.calculate_indication(og, h * w)
            print('indication:', indication)
        except Exception as e:
            print(f'FUCK: {e}')
        
        self.point_drawing_widget.indication = indication
        print('points:', points)
        
        sleep(0.1)
        print('emit!')
        self.point_drawing_widget.update_points_signal.emit(points)
    
    def set_image_paths(self, paths):
        self.image_paths = []

    def calculate_indication(self, og, n):
        # Step 1: Count total number of True values
        total_true_count = sum(item for row in og for item in row)
        print(og)
        if total_true_count == 0:
            return 'green'  # No True values at all

        def bfs(og, visited, i, j):
            # Perform BFS to find the size of the connected chunk of True values
            print('bfs', i, j)
            queue = [(i, j)]
            visited[i][j] = True
            chunk_size = 0
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Up, Down, Left, Right

            while len(queue) > 0:
                print('lol')
                x, y = queue.pop(0)
                chunk_size += 1

                # Explore neighbors (up, down, left, right)
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < len(og) and 0 <= ny < len(og[0]) and not visited[nx][ny] and og[nx][ny]:
                        visited[nx][ny] = True
                        queue.append((nx, ny))
            
            return chunk_size

        # Step 2: Find all chunks of connected True values
        visited = [[False for _ in row] for row in og]
        chunks = []

        for i in range(len(og)):
            for j in range(len(og[i])):
                if og[i][j] and not visited[i][j]:
                    chunk_size = bfs(og, visited, i, j)
                    print('chunk', chunk_size)
                    chunks.append(chunk_size)

        print('ok')
        # Step 3: Check chunk conditions
        for chunk_size in sorted(chunks):
            if chunk_size >= 0.1 * n:
                return 'red'
            elif chunk_size >= 0.04 * n:
                return 'orange'

        # Step 4: Check overall True percentage
        true_percentage = total_true_count / n

        if true_percentage > 0.1:
            return 'yellow'
        elif true_percentage > 0.05:
            return 'gray'
        
        # Step 5: Default to 'green' if none of the above
        return 'green'
    
    def mousePressEvent(self, event):
        """Override mousePressEvent to open a new window on click."""
        if event.button() == Qt.LeftButton:
            print("Opening new window...")

            if not self.image_paths: return

            self.new_window_1 = ImageWindow(self.image_paths[0], self, view_only=True, zoom_scale=0.4, offset_x=500)  # Create the new window
            self.new_window_2 = ImageWindow(self.image_paths[1], self, view_only=True, zoom_scale=0.4, offset_x=800)
            self.new_window_1.show()  # Show the new window
            self.new_window_2.show()  # Show the new window