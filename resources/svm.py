# imports
import cv2
from concurrent.futures import ProcessPoolExecutor
import threading
from multiprocessing import cpu_count

import xml.etree.ElementTree as ET
import time
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.utils.class_weight import compute_class_weight
# utils

import mplcursors

import sys
import os
import traceback

from resources import utils, cnn
from resources.features import extract_features, extract_features_from_patches

import joblib
import numpy as np
from multiprocessing import Manager, Queue
from resources.retry import retry_makedirs, read_image_with_retry, write_image_with_retry
from resources.log import LoggerSingleton

def inspect_folder(folder_dir, preset_name, progress_update):
    temp_dir = os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/temp_images/' + os.path.basename(folder_dir)
    try:
        retry_makedirs(temp_dir)
    except Exception as e:
        print(f"Error creating temporary directory: {e}")
        LoggerSingleton().error(f"Error creating temporary directory: {e}")
        return
    
    progress_update.emit(f'Inspecting {folder_dir}...)')
    
    try:
        svm, scaler, pca = joblib.load(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'presets', preset_name))
    except Exception as e:
        print(f"Error loading SVM model: {e}")
        LoggerSingleton().error(f"Error loading SVM model: {e}")
        return
    
    collage_handler = CollageHandler(os.path.basename(folder_dir), temp_dir)

    try:
        n = len(os.listdir(temp_dir))
    except Exception as e:
        print(f"Error listing directory contents: {e}")
        LoggerSingleton().error(f"Error listing directory contents: {e}")
        return
    print('OKAY!!')
    i = 0
    with Manager() as manager:
        queue = manager.Queue()
        thread = threading.Thread(target=monitor_queue, args=(queue, collage_handler))
        thread.start()

        try:
            with ProcessPoolExecutor(max_workers=min(int(os.getenv("INSPECTION_CLIENT_MAX_CORES")), cpu_count())) as executor:
                futures = [executor.submit(process_file, file_name, temp_dir, svm, pca, scaler, queue) for file_name in os.listdir(temp_dir)]

                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        print(f'(Svm-if) Future Exception: {e}')
                        
                    i += 1
                    progress_update.emit(f'{folder_dir} progress: {100 * i / n:.2f}%')
        except Exception as e:
            print(f"Error in process pool execution: {e}")
            LoggerSingleton().error(f"Error in process pool execution: {e}")

        queue.put('DONE')  # Signal that processing is done
        thread.join()  # Wait for the thread to finish

    collage_handler.finish()

def process_file(file_name, temp_dir, svm, pca, scaler, queue):
    if not file_name.endswith('.png'):
        return
    try:
        image_path = os.path.join(temp_dir, file_name)
        labeled_patches = read_divide_classify(image_path, svm, pca, scaler)

        if queue:
            queue.put(labeled_patches)
        else:
            return labeled_patches
    except Exception as e:
        print(f"Error processing file {file_name}: {e}")
        LoggerSingleton().error(f"Error processing file {file_name}: {e}")
        return None

def monitor_queue(queue, collage_handler):
    while True:
        labeled_patches = queue.get()
        if labeled_patches == 'DONE':
            break
        if labeled_patches == None:
            print('none detected in monitor queue')
            continue
        for labeled_patch in labeled_patches:
            collage_handler.add_patch(labeled_patch)

# labeled_patches = [ (patch, image_count, label, distance, patch coords, image_path), ... ]
def read_divide_classify(image_path, svm, pca, scaler):
    attempts = 0
    while attempts < 10:
        try:
            patches, coords = utils.divide_into_patches(read_image_with_retry(image_path, cv2.IMREAD_GRAYSCALE), (int(os.getenv("INSPECTION_CLIENT_GRID_SIZE")), int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))))
            break
        except ZeroDivisionError as e:
            print(f'(Svm-rdf) {e}')
            LoggerSingleton().error('(Svm-rdf) '+ e.__str__())
            return None
        except Exception as e:
            print(f'(Svm-rdf) {e}')
            LoggerSingleton().error('(Svm-rdf) '+ e.__str__())
            attempts += 1
            if attempts >= 10: raise Exception(f'rdc: {e}')
            time.sleep(5)

    patch_features = extract_features_from_patches(patches)

    num_of_patches = len(patches)

    transformed_features = pca.transform(scaler.transform([patch_features[i][1] for i in range(num_of_patches)]))
    labels = svm.predict(transformed_features)
    decision_scores = svm.decision_function(transformed_features)
    
    basename = os.path.basename(image_path)

    image_count = basename[:4]
    labeled_patches = [(patch_features[i][0], image_count, labels[i], float(max(decision_scores[i])), coords[i], basename) for i in range(num_of_patches)]

    return labeled_patches

def train_svm(patches_path):
    # load patches
    patch_loader = PatchLoader(patches_path)
    patches, filenames = patch_loader.load_patches_with_filenames()

    # get features and labels
    features = []
    labels = []
    patch_names = []
    for category, patch_list in patches.items():
        for patch, filename in zip(patch_list, filenames[category]):
            features.append(extract_features(patch))
            labels.append(category)
            patch_names.append(filename)
    
    # convert to numpy arrays
    features = np.array(features)
    labels = np.array(labels)

    # convert empty to blurry
    # for i in range(len(labels)):
    #     if labels[i] == 'empty':
    #         labels[i] = 'blurry'

    # scale
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    # pca
    pca = PCA(n_components=len(features[0]))
    features_reduced = pca.fit_transform(features_scaled)
    
    # compute class weights
    class_weights = compute_class_weight('balanced', classes=np.unique(labels), y=labels)
    print(np.unique(labels))
    
    
    class_weights_dict = {label: class_weights[i] for i, label in zip(range(len(class_weights)), np.unique(labels))}
    
    # adjust the weight of the class you care about
    target_class = 'blurry' 
    class_weights_dict[target_class] *= 1.5  # increase weight, adjust factor as needed

    target_class = 'empty'  # assuming the class you care about is labeled '2'
    class_weights_dict[target_class] *= 0.2  # increase weight, adjust factor as needed

    target_class = 'sharp'  # assuming the class you care about is labeled '2'
    class_weights_dict[target_class] *= 1  # increase weight, adjust factor as needed

    target_class = 'indeterminate'  # assuming the class you care about is labeled '2'
    class_weights_dict[target_class] *= 1  # increase weight, adjust factor as needed

    
# train SVM with class weights
    svm = SVC(kernel='linear', class_weight=class_weights_dict)
    svm.fit(features_reduced, labels)
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.95, random_state=42)
    X_test_scaled = scaler.transform(X_test)
    X_test_reduced = pca.transform(X_test_scaled)
    y_pred = svm.predict(X_test_reduced)

    print(classification_report(y_test, y_pred))

    return svm, scaler, pca, features, labels, patch_names

class CollageHandler:
    def __init__(self, barcode, temp_images_path, live = False):
        from keras.api.models import load_model
        
        self.model = load_model(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"),'blur_detection_model.keras'))
        self.barcode = barcode
        self.blurry_patches = []
        self.blurry_batch_paths = []
        self.indeterminate_patches = []
        self.indeterminate_batch_paths = []
        self.empty_patches = []
        self.lock = threading.Lock()  # Add a lock for thread safety
        self.dimensions = int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))
        self.patch_size =  int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE")) // int(os.getenv("INSPECTION_CLIENT_GRID_SIZE"))
        self.cut_page_coordinates_dict = {}
        self.temp_images_path = temp_images_path
        self.page_paths_to_coord_scales_dict = self.parse_xml_to_dict()
        
        # init cut page coordinates dict from coords_map.xml filein temp_images_path

    def parse_xml_to_dict(self):
        xml_path = os.path.join(self.temp_images_path, 'coord_map.xml')
        tree = ET.parse(xml_path)
        root = tree.getroot()
        image_size = int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE"))
        page_paths_to_coord_scales_dict = {}

        for frame in root.findall('frame'):
            basename = frame.find('basename').text
            coords_text = frame.find('coords').text

            # Extract the coordinates from the coords_text
            coords = eval(coords_text)
            top_left_coords = coords[0]
            bottom_right_coords = coords[1]

            # Calculate the scale_x and scale_y
            scale_x = (bottom_right_coords[0] - top_left_coords[0]) / image_size
            scale_y = (bottom_right_coords[1] - top_left_coords[1]) / image_size

            # Add the data to the dictionary
            page_paths_to_coord_scales_dict[basename] = (top_left_coords, scale_x, scale_y)

        return page_paths_to_coord_scales_dict

    def save_batch_as_image(self, batch: list, patch_class):
        try:
            folder_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'collages', self.barcode, patch_class)
            retry_makedirs(folder_path)

            batch.sort(key=lambda x: x[3], reverse=True)  # Sort by decision score

            collage = self.create_collage(batch)
            file_path = os.path.join(folder_path, f'collage_{patch_class}.png')

            write_image_with_retry(file_path, collage)
            
            metadata_path = file_path.replace(".png", ".metadata")

            with open(metadata_path, 'w') as file:
                buffer = ''
                for patch_touple in batch:
                    buffer += patch_touple[1] + ' '

                file.write(buffer)
            return file_path
        except Exception as e:
            print(f'(Svm-CH-sbai) {e}')
            LoggerSingleton().error('(Svm-CH-sbai) '+ str(e))

    def create_collage(self, batch):
        num_rows = max((len(batch) + self.dimensions - 1) // self.dimensions, 1)
        collage = np.zeros((self.patch_size * num_rows, self.patch_size * self.dimensions), dtype=np.uint8)
        
        max_width = self.patch_size
        max_height = self.patch_size

        for idx, (patch, page_number, label, score, coords, path) in enumerate(batch):
            row = idx // self.dimensions
            col = idx % self.dimensions
            x_offset = col * max_width
            y_offset = row * max_height
            resized_patch = cv2.resize(patch, (max_width, max_height))
            collage[y_offset:y_offset + max_height, x_offset:x_offset + max_width] = resized_patch

        return collage

    def filter_non_blurry(self, target : list):
        new_target = []

        patches = [target[i][0] for i in range(len(target))]
        results = cnn.predict_blur(patches, self.model)
        
        patches.clear()

        for i in range(len(target)):
            if results[i]:
                new_target.append(target[i])

        target.clear()
        target.extend(new_target)

    def finish(self):
        for target, patch_class, target_cache in zip([self.blurry_patches, self.empty_patches, self.indeterminate_patches], ['blurry', 'empty', 'indeterminate'], [self.blurry_batch_paths, None, self.indeterminate_batch_paths]):
            if patch_class == 'empty': continue
            
            # save the svm results
            #self.save_batch_as_image(target, patch_class + f'_svm')
            cnn_results = []
            while True:
                self.filter_non_blurry(target)
                cnn_results.extend(target)

                if len(target_cache) == 0: break

                attempts = 0
                cache = target_cache.pop()
                while attempts < 10:
                    try:
                        target = joblib.load(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_files', self.barcode, cache)) 
                        break
                    except Exception as e:
                        LoggerSingleton().log('joblib ' + str(e))
                        attempts += 1
                        time.sleep(5)

            self.save_batch_as_image(cnn_results, f'{patch_class}_cnn')
            
            self.add_to_cut_page_coordinates_dict(cnn_results)

        self.save_patches_to_xml(self.cut_page_coordinates_dict)

    def add_to_cut_page_coordinates_dict(self, target):
        for labeled_patch in target:
            num_of_page = labeled_patch[1]
            path = labeled_patch[5]

            # add patch to coord dict
            if not num_of_page in self.cut_page_coordinates_dict.keys():
                self.cut_page_coordinates_dict[num_of_page] = []

            xp = labeled_patch[4][0]
            yp = labeled_patch[4][1]
            xa = self.page_paths_to_coord_scales_dict[path][0][0]
            ya = self.page_paths_to_coord_scales_dict[path][0][1]

            scale_x = self.page_paths_to_coord_scales_dict[path][1]
            scale_y = self.page_paths_to_coord_scales_dict[path][2]

            self.cut_page_coordinates_dict[num_of_page].append((int(xa + xp * scale_x), int(ya + yp * scale_y) , int(200 * scale_x), int(200 * scale_y)))

    def finish_old(self):
        for target, patch_class, target_cache in zip([self.blurry_patches, self.empty_patches, self.indeterminate_patches], ['blurry', 'empty', 'indeterminate'], [self.blurry_batch_paths, None, self.indeterminate_batch_paths]):
            if patch_class == 'empty': continue
            
            self.save_batch_as_image(target, patch_class + f'_svm')
            self.filter_non_blurry(target)
            self.save_batch_as_image(target, patch_class + f'_cnn')
            
            # create dict
            for labeled_patch in target:
                num_of_page = labeled_patch[1]
                path = labeled_patch[5]

                # add patch to coord dict
                if not num_of_page in self.cut_page_coordinates_dict.keys():
                    self.cut_page_coordinates_dict[num_of_page] = []

                xp = labeled_patch[4][0]
                yp = labeled_patch[4][1]
                xa = self.page_paths_to_coord_scales_dict[path][0][0]
                ya = self.page_paths_to_coord_scales_dict[path][0][1]

                scale_x = self.page_paths_to_coord_scales_dict[path][1]
                scale_y = self.page_paths_to_coord_scales_dict[path][2]

                self.cut_page_coordinates_dict[num_of_page].append(( int(xa + xp * scale_x), int(ya + yp * scale_y) , int(200 * scale_x), int(200 * scale_y)))
            target.clear()
        
        self.save_patches_to_xml(self.cut_page_coordinates_dict)

    def save_patches_to_xml(self, patches_dict : dict):
        folder_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'collages')
        xml_filename = os.path.join(folder_path, f'{self.barcode}_patches.xml')
        book = ET.Element("book", barcode=str(self.barcode))

        for page_number, patches in patches_dict.items():
            # BAD code!
            for x, y, w, h in patches:
                width = w
                height = h
                break

            page = ET.SubElement(book, "page", number=str(page_number), patch_width=str(width), patch_height=str(height))

            for x, y, width, height in patches:
                #patch = ET.SubElement(page, "patch", x=str(x), y=str(y), label=label)
                patch = ET.SubElement(page, "patch", x=str(x), y=str(y))
        tree = ET.ElementTree(book)
        tree.write(xml_filename, encoding='utf-8', xml_declaration=True)


    def add_patch(self, labeled_patch):
        with self.lock:  # Ensure thread-safe access
            target = None
            patch_class = labeled_patch[2]

            if patch_class == 'blurry':
                target = self.blurry_patches
            elif patch_class == 'empty':
                target = self.empty_patches
            elif patch_class == 'indeterminate':
                target = self.indeterminate_patches

            if target is None:
                return 0  # Didn't add anything
            
            if patch_class == 'empty':
                return 1  # added empty

            target.append(labeled_patch)

            if len(target) >= 10000:
                cache_list = self.blurry_batch_paths if patch_class == 'blurry' else self.indeterminate_batch_paths
                cache_path = os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_files', self.barcode, f'{patch_class}_{len(cache_list)}.pkl')
                retry_makedirs(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'temp_files', self.barcode))
                joblib.dump(target, cache_path)
                cache_list.append(cache_path)
                target.clear()
            
            return 2  # added blurry
       
class PatchLoader:
    def __init__(self, base_folder):
        self.base_folder = base_folder

    def load_patches_with_filenames(self):
        categories = ['blurry', 'sharp', 'empty', 'indeterminate']
        patches = {category: [] for category in categories}
        filenames = {category: [] for category in categories}
        for category in categories:
            category_folder = os.path.join(self.base_folder, category)
            retry_makedirs(category_folder)
            for filename in os.listdir(category_folder):
                try:
                    patch_path = os.path.join(category_folder, filename)
                    patch = read_image_with_retry(patch_path, cv2.IMREAD_GRAYSCALE)
                    patches[category].append(patch)
                    filenames[category].append(filename)
                except Exception as e:
                    print(f'(Svm-pl-lpwf) {e}')
                    LoggerSingleton().error('(Svm-pl-lpwf) ' +  e)
        return patches, filenames