"""Oiliness map via specular highlight detection."""
import cv2
import numpy as np


def oiliness_map(img_bgr: np.ndarray, masks: dict[str, np.ndarray]) -> np.ndarray:
    """
    Compute oiliness map from BGR image.

    Detects specular highlights (shiny areas) using HSV thresholding.
    High value (V) + low saturation (S) = specular reflection.

    Args:
        img_bgr: Input image in BGR format
        masks: Dict of region masks

    Returns:
        Normalized oiliness map [0, 1]
    """
    # Convert to HSV
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Create face mask
    face_mask = np.zeros(img_bgr.shape[:2], dtype=bool)
    for region_mask in masks.values():
        face_mask |= region_mask > 0

    if not face_mask.any():
        return np.zeros(img_bgr.shape[:2], dtype=np.float32)

    # Detect specular highlights: high V, low S
    # Thresholds tuned for skin under typical lighting
    high_v = v > 200  # Bright areas
    low_s = s < 80  # Low saturation (desaturated = specular)

    specular = (high_v & low_s).astype(np.uint8) * 255

    # Confirm with gradient magnitude to avoid flat bright areas
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    # High gradient = edge, not uniform specular
    # We want moderate gradient (smooth highlight)
    grad_mask = (grad_mag < 50).astype(np.uint8) * 255

    # Combine specular with gradient constraint
    specular_refined = cv2.bitwise_and(specular, grad_mask)

    # Morphological opening to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    specular_clean = cv2.morphologyEx(specular_refined, cv2.MORPH_OPEN, kernel)

    # Dilate slightly to capture highlight regions
    specular_dilated = cv2.dilate(specular_clean, kernel, iterations=1)

    # Normalize to [0, 1]
    oiliness = specular_dilated.astype(np.float32) / 255.0

    # Apply face mask
    oiliness[~face_mask] = 0

    return oiliness
