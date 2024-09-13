import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
from multiprocessing import Process, Queue, Value, Lock, cpu_count
from resources.utils import process_and_save_image
from resources.svm import read_divide_classify
import joblib

def temp_image_worker_process(path_queue, image_queue, folder_path, temp_images_path):
    #print('PLEASE')
    while True:
        try:
            image_name = path_queue.get()  # Blocking until new image arrives
            # print(f'new image {image_name}')
            # print('wtf')
            if image_name is None:  # Stop signal
                break
            # print('wtf!')
            halfs, paths, num = process_and_save_image(os.path.basename(image_name), folder_path, temp_images_path, return_images=True)
            # print('done')
            image_queue.put((halfs, paths, num))
        except Exception as e:
            print(f'exeption {e}')

def inspect_worker_process(image_queue, labeled_patches_queue, svm, pca, scaler):
    """Process each image in the queue: generate temp images, run SVM, and filter with Keras model."""
    while True:
        item = image_queue.get()  # Blocking until new image arrives
        if item is None:  # Stop signal
            break
        halfs, paths, num = item
        #print(f'new halfs')
        total_labeled_patches = []

        for half, i in zip(halfs, range(2)):
            labeled_patches = read_divide_classify(num, svm, pca, scaler, image=half)
            
            if i == 1:
                for labeled_patch in labeled_patches:
                    labeled_patch.insert(4, (labeled_patch[4][0] + int(os.getenv('INSPECTION_CLIENT_TEMP_IMAGE_SIZE')),labeled_patch[4][1]))
                    labeled_patch.pop(5)
                    labeled_patch.insert(6, (labeled_patch[6][0] + int(os.getenv('INSPECTION_CLIENT_GRID_SIZE')), labeled_patch[6][1]))
                    labeled_patch.pop(7)

            total_labeled_patches.extend(labeled_patches)

        labeled_patches_queue.put((total_labeled_patches, paths, num))

def classify_patches_worker_process(labeled_patches_queue, results_queue, model):
    from resources.cnn import predict_blur
    while True:
        item = labeled_patches_queue.get()  # Blocking until new image arrives
        if item is None:  # Stop signal
            break
        labeled_patches, half_paths, num = item
        #print(f'new labeled_patches')
        n = len(labeled_patches)
        patches = [labeled_patches[i][0] for i in range(len(labeled_patches))]
        
        results = predict_blur(patches, model)

        count = sum(results)

        print(f'number of blurries: {count} / {n}')

        new_labeled_patches = []
        
        for i in range(len(labeled_patches)):
            if results[i]:
                new_labeled_patches.append(labeled_patches[i])
        
        new_labeled_patches.append(half_paths)
        new_labeled_patches.append(num)
        
        results_queue.put(new_labeled_patches)

class LiveHandler(QObject):
    # Signal to emit results back to the main PyQt application
    result_ready = pyqtSignal(list)  # str: image path, dict: filtered results

    def __init__(self, selected_preset):
        from keras.api.preprocessing.image import img_to_array
        from keras.api.models import load_model

        super().__init__()
        self.model = load_model(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'blur_detection_model.keras'))
        self.image_queue = Queue()
        self.path_queue = Queue()
        self.labeled_patches_queue = Queue()
        self.results_queue = Queue()
        self.temp_image_worker = None
        self.inspect_worker = None
        self.classify_patches_worker = None

        self.folder_path = None
        self.temp_folder_path = None

        preset_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets', selected_preset)
        self.svm, self.scaler, self.pca = joblib.load(preset_path)
        
        # Set up a timer to regularly check the results queue
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_results_queue)

    def check_results_queue(self):
        """Check the results queue and emit signals from the main thread."""
        while not self.results_queue.empty():
            results = self.results_queue.get()
            self.result_ready.emit(results)  # Emit the signal from the main thread


    def start_watching(self, folder_path, temp_folder_path):
        self.folder_path = folder_path
        self.temp_folder_path = temp_folder_path
        self.temp_image_worker = Process(target=temp_image_worker_process, args=(self.path_queue, self.image_queue, self.folder_path, self.temp_folder_path,))
        self.temp_image_worker.start()
        
        self.inspect_worker = Process(target=inspect_worker_process, args=(self.image_queue, self.labeled_patches_queue, self.svm, self.pca, self.scaler,))
        self.inspect_worker.start()
        
        self.classify_patches_worker = Process(target=classify_patches_worker_process, args=(self.labeled_patches_queue, self.results_queue, self.model,))
        self.classify_patches_worker.start()

        self.worker_processes = [self.temp_image_worker, self.inspect_worker, self.classify_patches_worker]
        self.timer.start(100)  # Check every 100ms

    def stop_watching(self):
        """Stop all worker processes."""
        for process in self.worker_processes:
            process.terminate()
            process.join()
        self.worker_processes = []

        self.timer.stop()

    @pyqtSlot(str)
    def add_image(self, image_path):
        """Add a new image path to the queue for processing."""
        #print(f'new image {image_path}')
        self.path_queue.put(image_path)

    @pyqtSlot()
    def stop(self):
        """Stop all processes and clean up."""
        self.path_queue.put(None)
        self.image_queue.put(None)
        self.labeled_patches_queue.put(None)
        self.stop_watching()