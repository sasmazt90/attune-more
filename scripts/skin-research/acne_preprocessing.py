#!/usr/bin/env python3
"""Shared Canonical Preprocessing and Tile Generation for Acne Detection.

Contract & Alignment:
- Tile Size: 384x384
- Stride: 288 (75% overlap)
- Padding: 114 (YOLOX standard letterbox background)
- Color Space: BGR [0..255] float32, channels-first (3, 384, 384)
- Identical tile slicing across Training and Canonical Inference.
"""

from typing import List, Tuple, Dict, Any
import numpy as np
import torch

PREPROCESSING_VERSION = "canonical-yolox-bgr-384-pad114-v1"
TILE_SIZE = 384
STRIDE = 288
PAD_VAL = 114


def extract_tile_bgr(
    full_bgr: np.ndarray,
    rect: Tuple[int, int, int, int],
    tile_size: int = TILE_SIZE,
    pad_val: int = PAD_VAL
) -> np.ndarray:
    """Extract karo slice from full BGR image with deterministic 114 padding.
    
    Args:
        full_bgr: Source image array [H, W, 3] in BGR format
        rect: [x0, y0, x1, y1] bounding coordinates
        tile_size: Fixed square tile dimension (default 384)
        pad_val: Constant padding value for canvas (default 114)
    Returns:
        Square tile array of shape [tile_size, tile_size, 3] in uint8
    """
    a, b, endx, endy = rect
    h, w = full_bgr.shape[:2]
    
    # Clip slice boundaries to actual image bounds
    src_x0 = max(0, a)
    src_y0 = max(0, b)
    src_x1 = min(w, endx)
    src_y1 = min(h, endy)

    canvas = np.full((tile_size, tile_size, 3), pad_val, dtype=np.uint8)
    
    if src_x1 > src_x0 and src_y1 > src_y0:
        crop = full_bgr[src_y0:src_y1, src_x0:src_x1]
        canvas[:crop.shape[0], :crop.shape[1]] = crop
        
    return canvas


def tile_to_tensor(tile_bgr: np.ndarray) -> torch.Tensor:
    """Convert [tile_size, tile_size, 3] uint8 BGR tile to [3, tile_size, tile_size] float32 tensor."""
    return torch.from_numpy(tile_bgr.transpose(2, 0, 1).copy()).float()


def prepare_sample_tensor(
    full_bgr: np.ndarray,
    rect: Tuple[int, int, int, int],
    tile_size: int = TILE_SIZE,
    pad_val: int = PAD_VAL
) -> torch.Tensor:
    """Single standard entry point for both training and inference tile tensor extraction."""
    tile_bgr = extract_tile_bgr(full_bgr, rect, tile_size=tile_size, pad_val=pad_val)
    return tile_to_tensor(tile_bgr)


def generate_sliding_tile_rects(
    crop_x0: int,
    crop_y0: int,
    crop_x1: int,
    crop_y1: int,
    img_w: int,
    img_h: int,
    tile_size: int = TILE_SIZE,
    stride: int = STRIDE
) -> List[Tuple[int, int, int, int]]:
    """Generate exact deterministic sliding tile grid matching training and inference."""
    xs = sorted(set([*range(crop_x0, max(crop_x0 + 1, crop_x1 - tile_size + 1), stride), max(crop_x0, crop_x1 - tile_size)]))
    ys = sorted(set([*range(crop_y0, max(crop_y0 + 1, crop_y1 - tile_size + 1), stride), max(crop_y0, crop_y1 - tile_size)]))

    rects = []
    for a in xs:
        for b in ys:
            endx = min(img_w, a + tile_size)
            endy = min(img_h, b + tile_size)
            rects.append((a, b, endx, endy))
    return rects


def verify_preprocessing_parity(t_train: torch.Tensor, t_eval: torch.Tensor) -> bool:
    """Strictly assert numerical parity between training and evaluation tensors."""
    assert t_train.shape == t_eval.shape, f"Shape mismatch: {t_train.shape} vs {t_eval.shape}"
    assert t_train.dtype == t_eval.dtype, f"Dtype mismatch: {t_train.dtype} vs {t_eval.dtype}"
    max_diff = (t_train - t_eval).abs().max().item()
    assert max_diff == 0.0, f"Tensor content mismatch! Max diff: {max_diff}"
    return True
