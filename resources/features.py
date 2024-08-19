import cv2
import numpy as np
from skimage import color
from skimage.feature import graycomatrix, graycoprops
from skimage.filters.rank import entropy
from skimage.morphology import disk


def local_power_spectrum_slope(gray_patch):
    # Step 1: Compute the 2D Fourier Transform of the patch
    dft = cv2.dft(np.float32(gray_patch), flags=cv2.DFT_COMPLEX_OUTPUT)
    dft_shift = np.fft.fftshift(dft)
    
    # Step 2: Compute the magnitude spectrum
    magnitude_spectrum = cv2.magnitude(dft_shift[:,:,0], dft_shift[:,:,1])
    
    # Step 3: Get the dimensions of the magnitude spectrum
    h, w = magnitude_spectrum.shape
    
    # Step 4: Create meshgrid for coordinates
    X, Y = np.meshgrid(np.arange(w), np.arange(h))
    
    # Step 5: Shift the coordinates so that the center of the spectrum is at (0,0)
    X, Y = X - w // 2, Y - h // 2
    
    # Step 6: Compute the radial distance from the center
    R = np.sqrt(X**2 + Y**2)
    R = R.astype(np.int32)
    
    # Step 7: Compute radial profile
    tbin = np.bincount(R.ravel(), magnitude_spectrum.ravel())
    nr = np.bincount(R.ravel())
    radialprofile = tbin / (nr + 1e-5)  # Adding a small constant to avoid division by zero
    
    # Step 8: Remove zero or negative values before log transformation
    radialprofile = radialprofile[1:]  # Skip the first element which is the DC component
    valid_indices = radialprofile > 0
    log_radialprofile = np.log(radialprofile[valid_indices] + 1e-5)
    log_radii = np.log(np.arange(1, len(radialprofile) + 1)[valid_indices])
    
    # Step 9: Fit a line to the log-log plot of the radial profile
    slope, _ = np.polyfit(log_radii, log_radialprofile, 1)
    
    return slope

def gradient_histogram_span(gray_patch):
    # percentage = 90
    # Step 1: Convert the patch to grayscale
    
    # Step 2: Calculate Sobel gradients in x and y directions
    grad_x = cv2.Sobel(gray_patch, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray_patch, cv2.CV_64F, 0, 1, ksize=3)

    
    # Step 3: Compute the gradient magnitude
    magnitude = np.sqrt(grad_x**2 + grad_y**2)
    
    # Step 4: Flatten the magnitude array to get all gradient values
    flat_magnitude = magnitude.flatten()
    
    # Step 5: Calculate the histogram of gradient magnitudes
    hist, bin_edges = np.histogram(flat_magnitude, bins=256, range=(0, 256))
    
    # Step 6: Calculate the cumulative histogram
    cumulative_hist = np.cumsum(hist)
    
    # Step 7: Normalize the cumulative histogram
    cumulative_hist_normalized = cumulative_hist / cumulative_hist[-1]
    

    # (100 - percentage) / 200.0
    # Step 8: Find the minimum and maximum bin edges that account for the given percentage
    lower_bound = np.searchsorted(cumulative_hist_normalized, 0.05)
    upper_bound = np.searchsorted(cumulative_hist_normalized, 0.95)
    
    # Step 9: Calculate the span
    span = bin_edges[upper_bound] - bin_edges[lower_bound]
    
    return span, grad_x, grad_y

def extract_features(gray_patch):
    slope = local_power_spectrum_slope(gray_patch)
    grad_span, grad_x, grad_y = gradient_histogram_span(gray_patch)
    
    # grad_x_var, grad_x_mean = grad_x.var(), grad_x.mean()
    # grad_y_var, grad_y_mean = grad_y.var(), grad_y.mean()

    grad_x_var = grad_x.var()
    grad_y_var = grad_y.var()

    # thresh = cv2.threshold(gray_patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    #entropy_ =  np.var(entropy(gray_patch, disk(5)))
    

    # Texture features (contrast, energy, homogeneity)
    glcm = graycomatrix(gray_patch, [1], [0], 256, symmetric=True, normed=True)
    contrast = graycoprops(glcm, 'contrast')[0, 0]

    # homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
    #dissimilarity = graycoprops(glcm, 'dissimilarity')[0, 0]
    # correlation = graycoprops(glcm, 'correlation')[0, 0]
    #hist = cv2.calcHist([gray_patch], [0], None, [256], [0, 256])
    #mode_intensity = np.argmax(hist)
    
    #features = [slope, grad_span, contrast, grad_x_var, grad_x_mean, grad_y_var, grad_y_mean]
    features = [slope, grad_span, contrast, grad_x_var, grad_y_var]

    return features

    # LAST
    #return [slope, grad_span, entropy_, contrast, dissimilarity, correlation, mode_intensity]
    
    # OK
    #return [slope, grad_span, entropy_, contrast, homogeneity, dissimilarity, correlation, mode_intensity]

    # GOOD
    # return [slope, grad_span, entropy_, dissimilarity]
    
    #return [slope, grad_span, entropy_, contrast, homogeneity, asm, dissimilarity, correlation, mode_intensity]
    

    # THIS, GREAT
    #return [slope, grad_span, entropy_, contrast, homogeneity]

   
    #return [slope, grad_span, laplacian_variance, entropy_, contrast, homogeneity]
    
    #return [slope , grad_span, laplacian_variance, mean, std, entropy_, contrast, energy, homogeneity, edge_density]
    #return [slope , grad_span, cv2.Laplacian(gray_patch, cv2.CV_64F).var(), cv2.countNonZero(thresh)]
    #return [slope , grad_span]

def extract_features_from_patches(patches):
    patches_features = []
    for patch in patches:
        patches_features.append((patch, extract_features(patch)))
    
    return patches_features