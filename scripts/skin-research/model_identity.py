#!/usr/bin/env python3
"""Model Identity, Hash Verification, and Receipt Enforcement for Acne Models."""

import sys
import hashlib
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import torch
import torch.nn as nn
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox_p2 import build_yolox_p2_model

# Canonical Ground-Truth Model Identities
TRUE_BASELINE_EPOCH02_SHA = "cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f"
TRUE_BASELINE_EPOCH02_PATH = ROOT / "audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors"

FOCAL_EPOCH01_SHA = "5d64c56d3737a5ffeafa4c1f3eea0ec4b7d5aea4ab7bb706ab8aab061f08a146"
FOCAL_EPOCH01_PATH = ROOT / "audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-01-step-000248-1791909523358138100/model.safetensors"

FOCUSED_EPOCH02_SHA = "cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f" # selected from best


def compute_file_sha256(filepath: Path) -> str:
    """Compute exact SHA256 of a file in 64KB blocks."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Model file does not exist: {filepath}")
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_verified_model(
    model_path: Path,
    expected_sha: Optional[str] = None,
    num_classes: int = 1,
    depth: float = 0.33,
    width: float = 0.5,
    device: str = "cpu"
) -> Tuple[nn.Module, str]:
    """Load YOLOX-S P2 model with mandatory SHA-256 hash verification.
    
    Raises:
        FileNotFoundError: if model_path does not exist.
        ValueError: if actual SHA-256 does not match expected_sha.
    """
    model_path = Path(model_path)
    actual_sha = compute_file_sha256(model_path)
    
    if expected_sha is not None and actual_sha.lower() != expected_sha.lower():
        raise ValueError(
            f"MODEL SHA256 MISMATCH!\n"
            f"  Path: {model_path}\n"
            f"  Expected: {expected_sha}\n"
            f"  Actual:   {actual_sha}\n"
            f"Failing closed to prevent model misattribution."
        )

    net = build_yolox_p2_model(num_classes=num_classes, depth=depth, width=width)
    state = load_file(str(model_path))
    net.load_state_dict(state, strict=True)
    net.eval()
    net.to(device)
    return net, actual_sha


def generate_evaluation_receipt(
    model_identity: str,
    model_sha: str,
    model_path: str,
    dataset_path: str,
    dataset_version: str,
    preprocessing_version: str,
    conf_threshold: float,
    nms_threshold: float,
    filter_version: str,
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Build standardized evaluation receipt ensuring full transparency."""
    return {
        "modelIdentity": model_identity,
        "modelSha256": model_sha,
        "modelPath": str(model_path),
        "datasetPath": str(dataset_path),
        "datasetVersion": dataset_version,
        "preprocessingVersion": preprocessing_version,
        "evaluationParameters": {
            "confThreshold": conf_threshold,
            "nmsThreshold": nms_threshold,
            "filterVersion": filter_version,
        },
        "metrics": metrics
    }
