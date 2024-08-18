
IMAGE_SIZE = 200

def predict_blur(images, model):
    from tensorflow.keras.preprocessing.image import img_to_array
    import cv2
    import numpy as np


    processed_images = []
    for img in images:
        img = cv2.resize(img, (IMAGE_SIZE, IMAGE_SIZE))
        img = img_to_array(img)
        img = img / 255.0
        img = np.expand_dims(img, axis=-1)  # Add a channel dimension for grayscale
        processed_images.append(img)
    
    processed_images = np.array(processed_images)
    predictions = model.predict(processed_images, verbose=0)
    
    return [pred[0] > pred[1] for pred in predictions]


# if __name__ == '__main__':
#     dataset_dir = '/media/michalis/T/cnn-training-data/patches/blurry'
#     names = os.listdir(dataset_dir)
#     shuffle(names)

#     model = load_model('blur_detection_model.keras')

#     for i in range(10):
#         print(predict_blur(os.path.join(dataset_dir, names[0]), model))