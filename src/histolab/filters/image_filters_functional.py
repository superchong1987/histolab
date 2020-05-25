import math
import PIL

import numpy as np
import skimage.color as sk_color
import skimage.exposure as sk_exposure
import skimage.feature as sk_feature
import skimage.filters as sk_filters
import skimage.future as sk_future
import skimage.morphology as sk_morphology
import skimage.segmentation as sk_segmentation

from PIL import Image, ImageOps
from functools import reduce
from .util import mask_percent
from ..util import np_to_pil


def invert(img: PIL.Image.Image) -> PIL.Image.Image:
    """Invert an image, i.e. take the complement of the correspondent array.

    Parameters
    ----------
    img : PIL.Image.Image
        Input image

    Returns
    -------
    PIL.Image.Image
        Inverted image
    """
    if img.mode == "RGBA":
        r, g, b, a = img.split()
        rgb_img = Image.merge("RGB", (r, g, b))

        inverted_img_rgb = ImageOps.invert(rgb_img)

        r2, g2, b2 = inverted_img_rgb.split()
        inverted_img = Image.merge("RGBA", (r2, g2, b2, a))

    else:
        inverted_img = ImageOps.invert(img)

    return inverted_img


def rgb_to_hed(img: PIL.Image.Image) -> PIL.Image.Image:
    """Convert RGB channels to HED channels.

    image color space (RGB) is converted to Hematoxylin-Eosin-Diaminobenzidine space.

    Parameters
    ----------
    img : PIL.Image.Image
        Input image

    Returns
    -------
    PIL.Image.Image
        Image in HED space
    """
    if img.mode not in ["RGB", "RGBA"]:
        raise Exception("Input image must be RGB or RGBA")
    img_arr = np.array(img)
    hed_arr = sk_color.rgb2hed(img_arr)
    hed = np_to_pil(hed_arr)

    return hed


def rgb_to_hsv(img: PIL.Image.Image) -> PIL.Image.Image:
    """Convert RGB channels to HSV channels.

     image color space (RGB) is converted to Hue - Saturation - Value (HSV) space.

     Parameters
     ----------
     img : PIL.Image.Image
          Input image

     Returns
     -------
     PIL.Image.Image
         Image in HED space
     """
    if img.mode != "RGB":
        raise Exception("Input image must be RGB")
    img_arr = np.array(img)
    hsv_arr = sk_color.rgb2hsv(img_arr)
    hsv = np_to_pil(hsv_arr)
    return hsv


# TODO setup logger warning + greyscale --> invert ---> contrast stretch


def stretch_contrast(
    img: PIL.Image.Image, low: int = 40, high: int = 60
) -> PIL.Image.Image:
    """Increase image contrast.

    Th contrast in image is increased based on intensities in a specified range

    Parameters
    ----------
    img: PIL.Image.Image
         Input image
    low: int
         Range low value (0 to 255).
    high: int
        Range high value (0 to 255).

    Returns
    -------
    PIL.Image.Image
            Image with contrast enhanced.
    """
    if low not in range(256) or high not in range(256):
        raise Exception("low and high values must be in range [0, 255]")
    img_arr = np.array(img)
    low_p, high_p = np.percentile(img_arr, (low * 100 / 255, high * 100 / 255))
    stretch_contrast = sk_exposure.rescale_intensity(img_arr, in_range=(low_p, high_p))
    return Image.fromarray(stretch_contrast)


def histogram_equalization(img: PIL.Image.Image, nbins: int = 256) -> PIL.Image.Image:
    """Increase image contrast using histogram equalization.

    The input image (gray or RGB) is filterd using histogram equalization to increase
    contrast.

    Parameters
    ----------
    img : PIL.Image.Image
          Input image.
    nbins : iny. optional (default is 256)
          Number of histogram bins.

    Returns
    -------
    NumPy array (float or uint8) with contrast enhanced by histogram equalization.
    """
    img_arr = np.array(img)
    hist_equ = sk_exposure.equalize_hist(img_arr, nbins=nbins)
    return np_to_pil(hist_equ)


def adaptive_equalization(
    img: PIL.Image.Image, nbins: int = 256, clip_limit: float = 0.01
) -> PIL.Image.Image:
    """Increase image contrast using adaptive equalization.

     Contrast in local region of input image (gray or RGB) is increased using
     adaptive equalization

     Parameters
     ----------
     img : PIL.Image.Image
            Input image (gray or RGB)
     nbins : int
            Number of histogram bins.
     clip_limit : float, optional (default is 0.01)
            Clipping limit where higher value increases contrast.

     Returns
     -------
     PIL.Image.Image
          image with contrast enhanced by adaptive equalization.
     """
    if not (isinstance(nbins, int) and nbins > 0):
        raise ValueError("Number of histogram bins must be positive integer")
    img_arr = np.array(img)
    adapt_equ = sk_exposure.equalize_adapthist(img_arr, nbins, clip_limit)
    adapt_equ = np_to_pil(adapt_equ)
    return adapt_equ


def local_equalization(img: PIL.Image.Image, disk_size: int = 50) -> PIL.Image.Image:
    """Filter gray image using local equalization.

    Local equalization method uses local histograms based on a disk structuring element.

    Parameters
    ---------
    img: PIL.Image.Image
        Input image. Notice that it must be 2D
    disk_size: int, optional (default is 50)
        Radius of the disk structuring element used for the local histograms

    Returns
    -------
    PIL.Image.Image
        2D image with contrast enhanced using local equalization.
    """

    if len(np.array(img).shape) != 2:
        raise ValueError("Input must be 2D.")
    local_equ = sk_filters.rank.equalize(
        np.array(img), selem=sk_morphology.disk(disk_size)
    )
    return np_to_pil(local_equ)


def kmeans_segmentation(
    img: PIL.Image.Image, compactness: float = 10.0, n_segments: int = 800
) -> PIL.Image.Image:
    """Segment an RGB image with K-means segmentation

    By using K-means segmentation (color/space proximity) each segment is
    colored based on the average color for that segment.

    Parameters
    ---------
    img : PIL.Image.Image
        Input image
    compactness : float, optional (default is 10.0)
        Color proximity versus space proximity factor.
    n_segments : int, optional (default is 800)
        The number of segments.

    Returns
    -------
    PIL.Image.Image
        Image where each segment has been colored based on the average
        color for that segment.
    """
    img_arr = np.array(img)
    labels = sk_segmentation.slic(img_arr, compactness, n_segments)
    kmeans_segmentation = sk_color.label2rgb(labels, img_arr, kind="avg")
    return np_to_pil(kmeans_segmentation)


def rag_threshold(
    img: PIL.Image.Image,
    compactness: float = 10.0,
    n_segments: int = 800,
    threshold: int = 9,
) -> PIL.Image.Image:
    """Combine similar K-means segmented regions based on threshold value.

    Segment an image with K-means, build region adjacency graph based on
    the segments, combine similar regions based on threshold value,
    and then output these resulting region segments.

    Parameters
    ----------
    img : PIL.Image.Image
        Input image
    compactness : float, optional (default is 10.0)
        Color proximity versus space proximity factor.
    n_segments :  int, optional (default is 800)
        The number of segments.
    threshold : int, optional (default is 9)
        Threshold value for combining regions.

    Returns
    -------
    PIL.Image.Image
        Each segment has been colored based on the average
        color for that segment (and similar segments have been combined).
    """
    if img.mode == "RGBA":
        raise ValueError("Input image cannot be RGBA")
    img_arr = np.array(img)
    labels = sk_segmentation.slic(img_arr, compactness, n_segments)
    g = sk_future.graph.rag_mean_color(img_arr, labels)
    labels2 = sk_future.graph.cut_threshold(labels, g, threshold)
    rag = sk_color.label2rgb(labels2, img_arr, kind="avg")
    return np_to_pil(rag)


def hysteresis_threshold(
    img: PIL.Image.Image, low: int = 50, high: int = 100
) -> PIL.Image.Image:
    """Apply two-level (hysteresis) threshold to an image.

    Parameters
    ----------
    img : PIL.Image.Image
        Input image
    low : int, optional (default is 50)c
        low threshold
    high : int, optional (default is 100)
        high threshold

    Returns
    -------
    PIL.Image.Image
        Boolean mask where True represents pixel above
        the hysteresis threshold
    """
    # TODO: warning grayscale input image (skimage doc)
    if low is None or high is None:
        raise ValueError("thresholds cannot be None")
    hyst = sk_filters.apply_hysteresis_threshold(np.array(img), low, high)
    return np_to_pil(hyst)


# -------- Branching function --------


def hysteresis_threshold_mask(
    img: PIL.Image.Image, low: int = 50, high: int = 100
) -> np.ndarray:
    """Mask an image using hysteresis threshold

    Compute the Hysteresis threshold on the complement of a greyscale image,
    and return boolean mask based on pixels above this threshold.

    Parameters
    ----------
    img : PIL.Image.Image
        Input image.
    low : int, optional (default is 50)
        low threshold
    high : int, optional (default is 100)
         high threshold

    Returns
    -------
    np.ndarray
     Boolean NumPy array where True represents a pixel above Otsu threshold.
    """
    gs = ImageOps.grayscale(img)
    comp = invert(gs)
    hyst_mask = sk_filters.apply_hysteresis_threshold(np.array(comp), low, high)
    return hyst_mask


def otsu_threshold(img: PIL.Image.Image) -> np.ndarray:
    """Mask image based on pixel above Otsu threshold.

    Compute Otsu threshold on image as a NumPy array and return boolean mask
    based on pixels above this threshold.

    Note that Otsu threshold is expected to work correctly only for grayscale images

    Parameters
    ----------
    img : PIL.Image.Image
        Input image.

    Returns
    -------
    np.ndarray
        Boolean NumPy array where True represents a pixel above Otsu threshold.
    """
    img_arr = np.array(img)
    otsu_thresh = sk_filters.threshold_otsu(img_arr)
    # TODO UserWarning: threshold_otsu is expected to work correctly only for grayscale images
    return _filter_threshold(img_arr, otsu_thresh)


def local_otsu_threshold(img: PIL.Image.Image, disk_size: int = 3) -> np.ndarray:
    """Mask image based on local Otsu threshold.

    Compute local Otsu threshold for each pixel and return boolean mask
    based on pixels being less than the local Otsu threshold.

    Note that the input image must be 2D.

    Parameters
    ----------
    img: PIL.Image.Image
        Input 2-dimensional image
    disk_size :int, optional (default is 3)
        Radius of the disk structuring element used to compute
        the Otsu threshold for each pixel.

    Returns
    -------
    np.ndarray
        NumPy boolean array representing the mask based on local Otsu threshold
    """
    if img.size != 2:
        raise ValueError("Input must be 2D.")
    img_arr = np.array(img)
    local_otsu = sk_filters.rank.otsu(img_arr, sk_morphology.disk(disk_size))
    return local_otsu


def filter_entropy(
    img: PIL.Image.Image, neighborhood: int = 9, threshold: int = 5
) -> np.ndarray:
    """Filter image based on entropy (complexity).

    The area of the image included in the local neighborhood is defined by a square
    neighborhoodxneighborhood

    Note that input must be 2D.

    Parameters:
    ----------
    img : PIL.Image.Image
        input 2-dimensional image
    neighborhood : int, optional (default is 9)
        Neighborhood size (defines height and width of 2D array of 1's).
    threshold : int, optional (default is 9)
        Threshold value.

    Returns
    -------
    np.ndarray
        NumPy boolean array where True represent a measure of complexity.
    """
    if img.size != 2:
        raise ValueError("Input must be 2D.")
    img_arr = np.array(img)
    entropy = sk_filters.rank.entropy(img_arr, np.ones((neighborhood, neighborhood)))
    return _filter_threshold(entropy, threshold)


# input of canny filter is a greyscale
def canny_edges(
    img: PIL.Image.Image,
    sigma: float = 1.0,
    low_threshold: float = 0.0,
    high_threshold: float = 25.0,
) -> np.ndarray:
    """Filter image based on Canny edge algorithm.

    Note that input image must be 2D

    Parameters
    ----------
    img : PIL.Image.Image
        Input 2-dimensional image
    sigma : float, optional (default is 1.0)
        Width (std dev) of Gaussian.
    low_threshold : float, optional (default is 0.0)
        Low hysteresis threshold value.
    high_threshold : float, optional (default is 25.0)
        High hysteresis threshold value.

    Returns
    -------
    np.ndarray
        Boolean NumPy array representing Canny edge map.
    """
    if img.size != 2:
        raise ValueError("Input must be 2D.")
    img_arr = np.array(img)
    canny_edges = sk_feature.canny(img_arr, sigma, low_threshold, high_threshold,)
    return canny_edges


def grays(img: PIL.Image.Image, tolerance: int = 15) -> np.ndarray:
    """Filter out gray pixels in RGB image.

     Grey pixels are those pixels where the red, green, and blue channel values
     are similar, i.e. under a specified tolerance.

     Parameters
     ----------
     img : PIL.Image.Image
         Input image
     tolerance : int, optional (default is 15)
         if difference between values is below this threshold,
         values are considered similar and thus filtered out

     Returns
     -------
     PIL.Image.Image
         Mask image where the grays values are masked out"""
    if img.size != 3:
        raise ValueError("Input must be 3D")
    # TODO: class image mode exception: raise exception if not RGB
    img_arr = np.array(img).astype(np.int)
    rg_diff = abs(img_arr[:, :, 0] - img_arr[:, :, 1]) > tolerance
    rb_diff = abs(img_arr[:, :, 0] - img_arr[:, :, 2]) > tolerance
    gb_diff = abs(img_arr[:, :, 1] - img_arr[:, :, 2]) > tolerance
    filter_grays = rg_diff | rb_diff | gb_diff
    return filter_grays


def _filter_threshold(img: PIL.Image.Image, threshold: float) -> np.ndarray:
    """Mask image with pixel below the threshold value.

    Parameters
    ----------
    img: PIL.Image.Image
        input image
    threshold: float
        The threshold value to exceed.

    Returns
    -------
    np.ndarray
        Boolean NumPy array representing a mask where a pixel has a value True
        if the corresponding input array pixel exceeds the threshold value.
    """
    img_arr = np.array(img)
    return img_arr > threshold


def green_channel_filter(
    img: PIL.Image.Image,
    green_thresh: int = 200,
    avoid_overmask: bool = True,
    overmask_thresh: float = 90.0,
) -> np.ndarray:
    """Mask pixels in an RGB image with G-channel greater than a specified threshold.

    Create a mask to filter out pixels with a green channel value greater than
    a particular threshold, since hematoxylin and eosin are purplish and pinkish,
    which do not have much green to them.

    Parameters
    ----------
    img : PIL.Image.Image
        Input RGB image
    green_thresh : float, optional (default is 200.0)
        Green channel threshold value (0 to 255).
        If value is greater than green_thresh, mask out pixel.
    avoid_overmask : bool, optional (default is True)
        If True, avoid masking above the overmask_thresh percentage.
    overmask_thresh : float, optional (default is 90.0)
        If avoid_overmask is True, avoid masking above this percentage value.

    Returns
    -------
    np.ndarray
        Boolean mask where pixels above a particular green channel
        threshold have been masked out.
    """
    # TODO: warning RGB and change print and discuss raise error thresh
    if green_thresh > 255.0 or green_thresh < 0.0:
        raise ValueError("threshold must be in range [0, 255]")
    g = np.array(img)[:, :, 1]
    g_mask = g <= green_thresh
    mask_percentage = mask_percent(g_mask)
    if avoid_overmask and (mask_percentage >= overmask_thresh) and (green_thresh < 255):
        new_green_thresh = math.ceil((255 + green_thresh) / 2)
        g_mask = green_channel_filter(
            np.array(img), new_green_thresh, avoid_overmask, overmask_thresh,
        )
    return g_mask


def red_filter(
    img: PIL.Image.Image, red_thresh: int, green_thresh: int, blue_thresh: int,
) -> np.ndarray:
    """Mask reddish colors in an RGB image.

    Create a mask to filter out reddish colors, where the mask is based on a pixel
    being above a red channel threshold value, below a green channel threshold value,
    and below a blue channel threshold value.

    Parameters
    ----------
    img : PIl.Image.Image
        Input RGB image
    red_lower_thresh : float
        Red channel lower threshold value.
    green_upper_thresh : float
        Green channel upper threshold value.
    blue_upper_thresh : float
        Blue channel upper threshold value.

    Returns
    -------
    np.ndarray
        Boolean NumPy array representing the mask.
    """
    img_arr = np.array(img)
    r = img_arr[:, :, 0] < red_thresh
    g = img_arr[:, :, 1] > green_thresh
    b = img_arr[:, :, 2] > blue_thresh
    red_filter = r | g | b
    return red_filter


def red_pen_filter(img: PIL.Image.Image) -> np.ndarray:
    """Filter out red pen marks on diagnostic slides.

    The resulting mask is a composition of red filters with different thresholds
    for the RGB channels.

    Parameters
    ----------
    img : PIL.Image.Image
        Input RGB image.

    Returns
    -------
        Boolean NumPy array representing the mask with the pen marks filtered out.
    """
    parameters = [
        {"red_thresh": 150, "green_thresh": 80, "blue_thresh": 90},
        {"red_thresh": 110, "green_thresh": 20, "blue_thresh": 30},
        {"red_thresh": 185, "green_thresh": 65, "blue_thresh": 105},
        {"red_thresh": 195, "green_thresh": 85, "blue_thresh": 125},
        {"red_thresh": 220, "green_thresh": 115, "blue_thresh": 145},
        {"red_thresh": 125, "green_thresh": 40, "blue_thresh": 70},
        {"red_thresh": 100, "green_thresh": 50, "blue_thresh": 65},
        {"red_thresh": 85, "green_thresh": 25, "blue_thresh": 45},
    ]
    red_pen_filter = reduce(
        (lambda x, y: x & y), [red_filter(img, **param) for param in parameters]
    )
    return red_pen_filter


def green_filter(
    img: PIL.Image.Image, red_thresh: int, green_thresh: int, blue_thresh: int,
) -> np.ndarray:
    """Filter out greenish colors in an RGB image.
    The mask is based on a pixel being above a red channel threshold value, below a
    green channel threshold value, and below a blue channel threshold value.

    Note that for the green ink, the green and blue channels tend to track together, so
    for blue channel we use a lower threshold rather than an upper threshold value.

    Parameters
    ----------
    img : PIL.image.Image
        RGB input image.
    red_thresh : int
        Red channel upper threshold value.
    green_thresh : int
        Green channel lower threshold value.
    blue_thresh : int
        Blue channel lower threshold value.

    Returns
    -------
    np.ndarray
        Boolean  NumPy array representing the mask.
    """
    img_arr = np.array(img)
    r = img_arr[:, :, 0] > red_thresh
    g = img_arr[:, :, 1] < green_thresh
    b = img_arr[:, :, 2] < blue_thresh
    green_filter = r | g | b
    return green_filter


def green_pen_filter(img: PIL.Image.Image) -> np.ndarray:
    """Filter out green pen marks from a diagnostic slide.

    The resulting mask is a composition of green filters with different thresholds
    for the RGB channels.

    Parameters
    ---------
    img : PIL.Image.Image
        Input RGB image

    Returns
    -------
    np.ndarray
        NumPy array representing the mask with the green pen marks filtered out.
    """
    parameters = [
        {"red_thresh": 150, "green_thresh": 160, "blue_thresh": 140},
        {"red_thresh": 70, "green_thresh": 110, "blue_thresh": 110},
        {"red_thresh": 45, "green_thresh": 115, "blue_thresh": 100},
        {"red_thresh": 30, "green_thresh": 75, "blue_thresh": 60},
        {"red_thresh": 195, "green_thresh": 220, "blue_thresh": 210},
        {"red_thresh": 225, "green_thresh": 230, "blue_thresh": 225},
        {"red_thresh": 170, "green_thresh": 210, "blue_thresh": 200},
        {"red_thresh": 20, "green_thresh": 30, "blue_thresh": 20},
        {"red_thresh": 50, "green_thresh": 60, "blue_thresh": 40},
        {"red_thresh": 30, "green_thresh": 50, "blue_thresh": 35},
        {"red_thresh": 65, "green_thresh": 70, "blue_thresh": 60},
        {"red_thresh": 100, "green_thresh": 110, "blue_thresh": 105},
        {"red_thresh": 165, "green_thresh": 180, "blue_thresh": 180},
        {"red_thresh": 140, "green_thresh": 140, "blue_thresh": 150},
        {"red_thresh": 185, "green_thresh": 195, "blue_thresh": 195},
    ]

    green_pen_filter = reduce(
        (lambda x, y: x & y), [green_filter(img, **param) for param in parameters]
    )
    return green_pen_filter


def blue_filter(
    img: PIL.Image.Image, red_thresh: int, green_thresh: int, blue_thresh: int
) -> np.ndarray:
    """Filter out blueish colors in an RGB image.

    Create a mask to filter out blueish colors, where the mask is based on a pixel
    being above a red channel threshold value, above a green channel threshold value,
    and below a blue channel threshold value.

    Parameters
    ----------
    img : PIl.Image.Image
        Input RGB image
    red_thresh : int
        Red channel lower threshold value.
    green_thresh : int
        Green channel lower threshold value.
    blue_thresh : int
        Blue channel upper threshold value.

    Returns
    -------
    np.ndarray
        Boolean NumPy array representing the mask.
    """
    img_arr = np.array(img)
    r = img_arr[:, :, 0] > red_thresh
    g = img_arr[:, :, 1] > green_thresh
    b = img_arr[:, :, 2] < blue_thresh
    blue_filter = r | g | b
    return blue_filter


def blue_pen_filter(img: PIL.Image.Image) -> np.ndarray:
    """Filter out blue pen marks from a diagnostic slide.

    The resulting mask is a composition of green filters with different thresholds
    for the RGB channels.

    Parameters
    ---------
    img : PIL.Image.Image
        Input RGB image

    Returns
    -------
    np.ndarray
        NumPy array representing the mask with the blue pen marks filtered out.
    """
    parameters = [
        {"red_thresh": 60, "green_thresh": 120, "blue_thresh": 190},
        {"red_thresh": 120, "green_thresh": 170, "blue_thresh": 200},
        {"red_thresh": 175, "green_thresh": 210, "blue_thresh": 230},
        {"red_thresh": 145, "green_thresh": 180, "blue_thresh": 210},
        {"red_thresh": 37, "green_thresh": 95, "blue_thresh": 160},
        {"red_thresh": 30, "green_thresh": 65, "blue_thresh": 130},
        {"red_thresh": 130, "green_thresh": 155, "blue_thresh": 180},
        {"red_thresh": 40, "green_thresh": 35, "blue_thresh": 85},
        {"red_thresh": 30, "green_thresh": 20, "blue_thresh": 65},
        {"red_thresh": 90, "green_thresh": 90, "blue_thresh": 140},
        {"red_thresh": 60, "green_thresh": 60, "blue_thresh": 120},
        {"red_thresh": 110, "green_thresh": 110, "blue_thresh": 175},
    ]

    blue_pen_filter = reduce(
        (lambda x, y: x & y), [blue_filter(img, **param) for param in parameters]
    )
    return blue_pen_filter


def pen_marks(img: PIL.Image.Image) -> np.ndarray:
    """Filter out pen marks from a diagnostic slide.

    Pen amrks are removed by applying Otsu threshold on the H channel of the image
    converted to the HSV space.

    Parameters
    ---------
    img : PIL.Image.Image
        Input RGB image

    Returns
    -------
    np.ndarray
        Boolean NumPy array representing the mask with the pen marks filtered out.
    """
    np_img = np.array(img)
    np_hsv = sk_color.convert_colorspace(np_img, "RGB", "HSV")
    hue = np_hsv[:, :, 0]
    threshold = sk_filters.threshold_otsu(hue)
    return hue > threshold