import cv2
import os
import numpy as np
from multiprocessing import cpu_count, Manager
from concurrent.futures import ProcessPoolExecutor
from resources.retry import *
from resources.log import LoggerSingleton, debug
import xml.etree.ElementTree as ET

test = True

SMOOTH_CONSTANT = 95
THRESHOLD_FOR_GLOSS = 250

# function that splits the image, returns the lafs
def process_image(img):
    halfs = split_image(img)

    processed_halfs = []
    coords = []

    for i, half in zip(range(2), halfs):
        processed_half, upper_left_coords, lower_right_coords = remove_surrounding_non_pages(half)
        processed_halfs.append(processed_half)
        
        if i == 1:
            _, cols = img.shape[:2]
            cols = cols // 2
            upper_left_coords[0] += cols
            lower_right_coords[0] += cols
            
        coords.append((upper_left_coords, lower_right_coords))
    
    return processed_halfs, coords

def read_images(images_path, temp_images_path):
    images = []
    
    retry_makedirs(temp_images_path)
    
    for filename in os.listdir(temp_images_path):
        if filename.endswith('.png'):
            os.remove(temp_images_path + '/' + filename)

    for filename in os.listdir(images_path):
        image = read_image_with_retry(os.path.join(images_path, filename), cv2.IMREAD_GRAYSCALE)
        halfs, coords = process_image(image)
        
        labels = ['left', 'right']
        for half, label in zip(halfs, labels):
            images.append(half)
            write_image_with_retry(os.path.join(temp_images_path, f"{filename.split('.')[0]}_{label}.png"), half)

    return images

def process_and_save_image(filename, images_path, temp_images_path, counter=None, total_files=None, lock=None, results=None, return_images = False):
    print('is this thing even called?')
    retry_makedirs(temp_images_path)
    print(' i guess so')
    if not filename.endswith('.tif') or 'thumb' in filename:
        return
    print('bitchass..')
    image_path = os.path.join(images_path, filename)
    print(image_path)
    temp_image_path = os.path.join(temp_images_path, f"{filename.split('.')[0]}_{{}}.png")
    print('ok?')
    attempts = 0
    while attempts < 10:
        try: 
            image = read_image_with_retry(image_path, cv2.IMREAD_GRAYSCALE)
            halfs, coords_pair = process_image(image)
            break
        except Exception as e:
            print(f'(Utils-pasi1) {e}')
            LoggerSingleton().error('(Utils-pasi) ' +  e.__str__())
            time.sleep(0.1)
            attempts += 1
            if attempts >= 10: return
    print('ok??')
    labels = ['left', 'right']
    
    attempts = 0

    paths = []

    for half, label, coords in zip(halfs, labels, coords_pair):
        while attempts < 10:
            try:
                new_img_path = temp_image_path.format(label)
                if not new_img_path in paths:
                    paths.append(new_img_path)
                write_image_with_retry(temp_image_path.format(label), half)
                
                if results is not None:
                    results.append((new_img_path, coords))
                break
            except Exception as e:
                print(f'(Utils-pasi2) {e}')
                LoggerSingleton().error('(Utils-pasi) ' +  e.__str__())
                time.sleep(5)
                attempts += 1
                if attempts >= 10: return
    print('ok???')
    if lock is not None:
        with lock:
            counter.value += 1
            # progress = 100 * counter.value / total_files
            values = [int(total_files * i) for i in [0.01, 0.25, 0.5, 0.75, 1]]
            if counter.value in values:
                print(f'{os.path.basename(images_path)} processing progress: {counter.value / total_files:.2f}%')

    if return_images:
        return halfs, paths, filename[:4]
    return paths

def process_images(images_path, temp_images_path):
    
    try:
        attempts = 0
        while attempts < 10:
            try:
                print(temp_images_path)
                retry_makedirs(temp_images_path)
            
                for filename in os.listdir(temp_images_path):
                    os.remove(os.path.join(temp_images_path, filename))
                break
            except Exception as e:
                LoggerSingleton().error('(Utils-pi)' + e.__str__())
                attempts += 1
                if attempts >= 10:
                    raise Exception('could not initiate image cutting')

        for i in range(5):
            debug(f'ok1 {i}')
            time.sleep(1)

        manager = Manager()
        debug('ok2')
        counter = manager.Value('i', 0)
        debug('ok3')
        lock = manager.Lock()
        debug('ok4')
        results = manager.list()
        debug('ok5')
        total_files = len([f for f in os.listdir(images_path) if f.endswith('.tif') and 'thumb' not in f])
        debug('ok6')
        filenames = [f for f in os.listdir(images_path) if f.endswith('.tif') and 'thumb' not in f]
        debug('ok7')
        output_xml_path = os.path.join(temp_images_path, 'coord_map.xml')
        debug('ok8')
        LoggerSingleton().log(f'(Utils-pi) {os.path.basename(images_path)} processing progress: 0%')
        debug('ok9')
        with ProcessPoolExecutor(max_workers=min(int(os.getenv("INSPECTION_CLIENT_MAX_CORES")), cpu_count())) as executor:
            futures = [
                executor.submit(
                    process_and_save_image,
                    filename,
                    images_path,
                    temp_images_path,
                    counter,
                    total_files,
                    lock,
                    results
                )
                for filename in filenames
            ]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(f'(Utils-pi) Future exception: {e}')
        write_results_to_xml(results, output_xml_path)
    except Exception as e:
        print(f'(Utils-pii) {e}')

def write_results_to_xml(results, output_path):
    root = ET.Element("frames")

    for new_img_path, coords in results:
        frame = ET.SubElement(root, "frame")
        basename = ET.SubElement(frame, "basename")
        basename.text = os.path.basename(new_img_path)
        coords_element = ET.SubElement(frame, "coords")
        coords_element.text = str(coords)

    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)

# coords: [(x, y), ..]
def divide_into_patches(img, dimensions):
    if img is None:
        raise ZeroDivisionError('corrupt image')

    patches = []
    coords = []
    gridcoords = []
    h, w = img.shape[:2]
    patch_width = w // dimensions[0]
    patch_height = h // dimensions[1]


    row_index = 0
    
    for row in range(patch_height // 2, h - patch_height // 2, patch_height):
        col_index = 0
        for col in range(patch_width // 2, w - patch_width // 2, patch_width):
            patch = img[row:row+patch_height, col:col+patch_width]
            patches.append(patch)
            coords.append((col, row))
            gridcoords.append((col_index, row_index))

            col_index += 1
        row_index += 1
    return patches, coords, gridcoords

def remove_surrounding_non_pages(image, square_size=int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE"))):
    gray = image

    # Apply GaussianBlur to reduce noise and improve contour detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    rows, cols = image.shape[:2]
    total_area = rows * cols

    last_w, last_h = 100000, 100000
    upper_left_x, upper_left_y = 0, 0
    lower_right_x, lower_right_y = cols, rows

    for i in range(5):
        # Find contours in the binary image
        _, thresholded = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # If no contours were found, return the original image
        if not contours:
            break

        # Find the largest contour by area
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Get the bounding box of the largest contour
        x, y, w, h = cv2.boundingRect(largest_contour)

        if w * h < 0.6 * total_area or last_w * last_h <= w * h:
            break
        last_w, last_h = w, h

        # Update the coordinates
        upper_left_x += x
        upper_left_y += y
        
        # Crop the image to the bounding box
        image = image[y:y+h, x:x+w]

        # Recalculate the gray, blurred, and thresholded images for the cropped image
        #gray = gray[y:y+h, x:x+w]
        blurred = blurred[y:y+h, x:x+w]
    
    new_rows, new_cols = image.shape[:2]
    # Update the lower right coordinates based on the resizing
    lower_right_x = upper_left_x + new_cols
    lower_right_y = upper_left_y + new_rows

    # Resize image
    image = cv2.resize(image, (square_size, square_size))

    return image, [upper_left_x, upper_left_y], [int(lower_right_x), int(lower_right_y)]

def save_images(images, base_path, frame_name):
    print(f"Saving images for {frame_name}")
    for field_name, image in images.items():
        if(field_name[0] == '_'):
            continue
        folder = os.path.join(base_path, field_name) # o fakelos orizetai ston fakelo toy vivlioy
        try:
            retry_makedirs(folder)
        except Exception as e:
            print(f"Error creating directory {folder}: {e}")
            continue
        path = os.path.join(folder, f"{frame_name}.tif")   # This line is needed later
        #path = os.path.join(base_path, f"{field_name}.tif")
        try:
            write_image_with_retry(path, image)
        except Exception as e:
            print(f"Error writing image to {path}: {e}")

def split_image(image):
    rows, cols = image.shape[:2]

    left_half = image[:, :cols//2]
    right_half = image[:, cols//2:]
    
    return left_half, right_half