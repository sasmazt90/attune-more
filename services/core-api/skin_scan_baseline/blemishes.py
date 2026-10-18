"""Blemish detection using rule-based heuristics."""
import cv2
import numpy as np


def blemish_map(img_bgr: np.ndarray, masks: dict[str, np.ndarray]) -> np.ndarray:
    """
    Compute blemish map using rule-based detection.

    Combines oiliness detection, pore-like features, and color variance
    to identify potential blemishes (acne, spots, imperfections).

    Args:
        img_bgr: Input image in BGR format
        masks: Dict of region masks

    Returns:
        Normalized blemish map [0, 1]
    """
    # Convert to different color spaces
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

    # Create face mask
    face_mask = np.zeros(img_bgr.shape[:2], dtype=bool)
    for region_mask in masks.values():
        face_mask |= region_mask > 0

    if not face_mask.any():
        return np.zeros(img_bgr.shape[:2], dtype=np.float32)

    # Feature 1: Redness (a* channel in LAB)
    a_channel = lab[..., 1].astype(np.float32)
    red_mask = a_channel > np.percentile(a_channel[face_mask], 70)

    # Feature 2: Darker than surrounding (local brightness deficit)
    blur_gray = cv2.GaussianBlur(gray, (15, 15), 0)
    brightness_diff = blur_gray.astype(np.float32) - gray.astype(np.float32)
    dark_spots = brightness_diff > 5  # Darker than local average

    # Feature 3: Color variance (different from surrounding skin tone)
    l_channel = lab[..., 0].astype(np.float32)
    l_blur = cv2.GaussianBlur(l_channel, (15, 15), 0)
    color_variance = np.abs(l_channel - l_blur)
    high_variance = color_variance > np.percentile(color_variance[face_mask], 60)

    # Feature 4: Small blob-like structures
    # Use morphological top-hat
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    _, blob_mask = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Combine features
    blemish_candidates = (
        red_mask.astype(np.uint8)
        + dark_spots.astype(np.uint8)
        + high_variance.astype(np.uint8)
        + (blob_mask > 0).astype(np.uint8)
    )

    # Threshold: need at least 2 features
    blemish_binary = (blemish_candidates >= 2).astype(np.uint8) * 255

    # Clean up small noise
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    blemish_clean = cv2.morphologyEx(blemish_binary, cv2.MORPH_OPEN, kernel_clean)

    # Create density map
    blemish_density = cv2.GaussianBlur(blemish_clean.astype(np.float32), (11, 11), 3)

    # Normalize to [0, 1]
    if face_mask.any():
        face_vals = blemish_density[face_mask]
        b_max = face_vals.max()
        if b_max > 1e-6:
            blemish_density = blemish_density / b_max

    blemish_density = np.clip(blemish_density, 0, 1)
    blemish_density[~face_mask] = 0

    return blemish_density.astype(np.float32)
