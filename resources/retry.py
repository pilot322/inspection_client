# gamw to diktyo
import os
import cv2
import time
from resources.log import LoggerSingleton

def retry_on_exception(func, max_retries=5, delay=5):
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f'(Retry) Trying again in 5 seconds. Error: {e}')
                LoggerSingleton().error('(Retry) Trying again in 5 seconds. Error: '+ e.__str__())
                retries += 1
                time.sleep(delay)
        raise Exception(f"Failed after {max_retries} retries")
    return wrapper

@retry_on_exception
def retry_makedirs(path):
    return os.makedirs(path, exist_ok=True)


@retry_on_exception
def read_image_with_retry(image_path, mode):
    image = cv2.imread(image_path, mode)
    if image is None:
        raise Exception('image is none')
    
    if image.shape[0] == 0 or image.shape[1] == 0:
                raise ValueError(f"Image has invalid dimensions: {image_path}")
    return image

@retry_on_exception
def write_image_with_retry(image_path, image):
    if not cv2.imwrite(image_path, image):
        raise Exception('imwrite returned false')