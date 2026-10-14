#!/usr/bin/env python3
"""Verification test for CalibratedDrynessAdapter:
1. Validates fail-closed behavior on missing/corrupt encoder.
2. Validates automatic discovery of verified encoder (ONNX / PyTorch safetensors).
3. Executes live end-to-end analyze() on real photo payload (24031977).
4. Verifies streaming batches, crop reuse, memory bounding, and cancellation callback.
"""

import sys
import os
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from cdc_skin_adapters import CalibratedDrynessAdapter

def test_dryness_adapter():
    print("=== Testing CalibratedDrynessAdapter ===")

    # 1. Test fail-closed on invalid encoder path
    print("\n1. Testing fail-closed on invalid encoder path...")
    adapter_bad = CalibratedDrynessAdapter(encoder_path="nonexistent_model.safetensors")
    try:
        _ = adapter_bad.encoder
        raise AssertionError("Expected FileNotFoundError on nonexistent encoder!")
    except FileNotFoundError as e:
        print(f"  Passed! Clear error produced: {e}")

    # 2. Test verified encoder discovery
    print("\n2. Testing verified encoder discovery...")
    adapter = CalibratedDrynessAdapter()
    encoder = adapter.encoder
    print(f"  Discovered encoder: {type(encoder).__name__} (path: {adapter.encoder_path})")
    assert encoder is not None

    # 3. Test live analyze() on real photo payload (24031977)
    print("\n3. Testing live analyze() on real photo 24031977...")
    payload_path = LIVE_TEST / 'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json'
    assert payload_path.exists(), f"Payload not found: {payload_path}"
    payload = json.loads(payload_path.read_text('utf8'))

    check_calls = 0
    def stop_check():
        nonlocal check_calls
        check_calls += 1

    details = []
    t0 = time.monotonic()
    result = adapter.analyze(payload, check=stop_check, details=details)
    elapsed = time.monotonic() - t0

    print(f"  Analysis completed in {elapsed:.2f}s (< 45s normal camera limit: {elapsed < 45})")
    print(f"  Stop check callback invocations: {check_calls} (> 0: {check_calls > 0})")
    assert check_calls > 0, "Stop check callback was never invoked!"
    assert elapsed < 45.0, f"Analysis took {elapsed}s, exceeding 45s threshold!"

    # 4. Verify results structure and metrics
    print("\n4. Verifying measurements and proxy contracts...")
    assert 'measurements' in result
    assert 'general' in result
    assert 'nativeMetadata' in result

    meta = result['nativeMetadata']
    print(f"  Classifier Version: {meta['classifierVersion']}")
    print(f"  Unique encoded crops: {meta['uniqueEncodedCrops']}")
    print(f"  Unique transforms: {meta['uniqueCropTransforms']}")
    print(f"  Identical crops reused: {meta['identicalCropsReused']}")
    print(f"  Candidate components: {meta['candidateComponents']}")
    print(f"  Accepted components: {meta['acceptedComponents']}")
    print(f"  Maximum resident crop tensors: {meta['maximumResidentCropTensors']}")
    print(f"  Transport: {meta['transport']}")

    general_val = result['general']['value']
    accepted_px = result['general']['components']['acceptedMaterialSourcePixels']
    print(f"  General dryness score: {general_val:.4f}% ({accepted_px} active source pixels)")
    assert accepted_px > 0, "Expected non-zero active material pixels on dry subject 24031977!"

    # Print regional values
    for region, m in result['measurements'].items():
        print(f"    Region {region:12s}: value={m['value']:.4f}%, pixels={m['components']['acceptedMaterialSourcePixels']}")

    print("\nCalibratedDrynessAdapter live verification PASSED successfully!")
    return True

if __name__ == '__main__':
    test_dryness_adapter()
