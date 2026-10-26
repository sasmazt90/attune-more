#!/usr/bin/env python3
"""Build a privacy-safe manifest for the independent physical-camera set.

The input is a private JSON object with a ``captures`` array.  The output
contains only opaque subject/consent/capture references and immutable hashes;
image bytes, paths, names, contact data, model predictions, and expert labels
are deliberately outside this manifest.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


POSES = {"front", "left", "right"}
ALLOWED_SPLIT = "camera_final"
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "filepath", "path", "uri", "url", "email",
    "phone", "address", "rawimage", "imagebytes", "bytes", "prediction",
    "predictions", "modeloutput", "expertlabel", "labels",
}
REQUIRED_FIELDS = {
    "subjectRef", "captureRef", "consentRef", "imageSha256", "pose",
    "deviceClass", "lightingBin", "skinToneBin", "captureQualityGateRef",
    "captureQuality", "sourceType", "generated", "split",
    "usedForTraining", "usedForValidation", "usedForThresholdSelection",
}


class CameraManifestError(ValueError):
    """Raised when a camera index violates privacy or independence rules."""


def _assert_no_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in FORBIDDEN_KEYS:
                raise CameraManifestError(f"forbidden private field at {location}.{key}")
            _assert_no_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, f"{location}[{index}]")


def _require_opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise CameraManifestError(f"{field} must be an opaque reference")
    return value


def build_manifest(private_index: dict[str, Any]) -> dict[str, Any]:
    _assert_no_forbidden_keys(private_index)
    captures = private_index.get("captures")
    if not isinstance(captures, list) or not captures:
        raise CameraManifestError("captures must be a non-empty array")

    safe_records: list[dict[str, Any]] = []
    subject_poses: dict[str, set[str]] = defaultdict(set)
    hashes: set[str] = set()
    capture_refs: set[str] = set()
    counters = {
        "deviceClass": Counter(),
        "lightingBin": Counter(),
        "skinToneBin": Counter(),
        "pose": Counter(),
    }

    for index, record in enumerate(captures):
        if not isinstance(record, dict):
            raise CameraManifestError(f"capture {index} must be an object")
        missing = sorted(REQUIRED_FIELDS - set(record))
        if missing:
            raise CameraManifestError(f"capture {index} missing fields: {', '.join(missing)}")

        subject_ref = _require_opaque(record["subjectRef"], "subjectRef")
        capture_ref = _require_opaque(record["captureRef"], "captureRef")
        consent_ref = _require_opaque(record["consentRef"], "consentRef")
        quality_ref = _require_opaque(record["captureQualityGateRef"], "captureQualityGateRef")
        image_hash = record["imageSha256"]
        if not isinstance(image_hash, str) or SHA256_RE.fullmatch(image_hash) is None:
            raise CameraManifestError("imageSha256 must be a lowercase SHA-256")
        if image_hash in hashes:
            raise CameraManifestError("duplicate imageSha256")
        if capture_ref in capture_refs:
            raise CameraManifestError("duplicate captureRef")

        pose = record["pose"]
        if pose not in POSES:
            raise CameraManifestError("pose must be front, left, or right")
        if pose in subject_poses[subject_ref]:
            raise CameraManifestError("duplicate subject pose")
        if record["sourceType"] != "physical-camera" or record["generated"] is not False:
            raise CameraManifestError("generated or non-camera source cannot enter camera_final")
        if record["split"] != ALLOWED_SPLIT:
            raise CameraManifestError("split must be camera_final")
        if any(record[field] is not False for field in (
            "usedForTraining", "usedForValidation", "usedForThresholdSelection"
        )):
            raise CameraManifestError("camera_final capture leaks into training, validation, or threshold selection")
        if record["captureQuality"] != "pass":
            raise CameraManifestError("camera_final requires a passed capture-quality gate")

        for field in ("deviceClass", "lightingBin", "skinToneBin"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise CameraManifestError(f"{field} must be a non-empty controlled value")

        safe = {
            "subjectRef": subject_ref,
            "captureRef": capture_ref,
            "consentRef": consent_ref,
            "imageSha256": image_hash,
            "pose": pose,
            "deviceClass": record["deviceClass"],
            "lightingBin": record["lightingBin"],
            "skinToneBin": record["skinToneBin"],
            "captureQualityGateRef": quality_ref,
            "captureQuality": "pass",
            "sourceType": "physical-camera",
            "generated": False,
            "split": ALLOWED_SPLIT,
            "usedForTraining": False,
            "usedForValidation": False,
            "usedForThresholdSelection": False,
        }
        safe_records.append(safe)
        hashes.add(image_hash)
        capture_refs.add(capture_ref)
        subject_poses[subject_ref].add(pose)
        for field in counters:
            counters[field][safe[field]] += 1

    incomplete = sorted(subject for subject, poses in subject_poses.items() if poses != POSES)
    if incomplete:
        raise CameraManifestError("every subject requires an exact front/left/right triplet")

    safe_records.sort(key=lambda item: (item["subjectRef"], item["pose"], item["captureRef"]))
    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-benchmark-manifest-v1",
        "sourceType": "physical-camera",
        "generated": False,
        "split": ALLOWED_SPLIT,
        "subjectCount": len(subject_poses),
        "captureCount": len(safe_records),
        "completeThreePoseTriplets": True,
        "subjectIndependentFromTrainingValidationThresholdSelection": True,
        "containsImageBytesOrPaths": False,
        "containsModelPredictions": False,
        "containsExpertTruth": False,
        "expertTruthMustRemainSeparateAndHumanAuthored": True,
        "sliceCounts": {key: dict(sorted(value.items())) for key, value in counters.items()},
        "captures": safe_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(json.loads(args.private_index.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
