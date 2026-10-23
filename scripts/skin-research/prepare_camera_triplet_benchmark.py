#!/usr/bin/env python3
"""Create a privacy-safe manifest for Attune three-pose camera smoke tests.

The manifest records hashes and capture geometry only. It never copies image
bytes and it deliberately keeps generated/unlabelled images outside accuracy
or real-camera acceptance evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


FILENAME_RE = re.compile(
    r"^(?P<subject>[1-9][0-9]*)\.(?P<label>[A-Za-z]+)_(?P<pose>front|side_1|side_2)\.jpg$",
    re.IGNORECASE,
)
EXPECTED_POSES = ("front", "side_1", "side_2")
SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


class ManifestError(ValueError):
    """Raised when the capture package cannot be used safely."""


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Read JPEG dimensions from a Start Of Frame marker."""

    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ManifestError("not a JPEG stream")
    offset = 2
    while offset + 1 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        segment_length = int.from_bytes(data[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(data):
            raise ManifestError("truncated JPEG segment")
        if marker in SOF_MARKERS:
            if segment_length < 7:
                raise ManifestError("invalid JPEG SOF segment")
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            if width <= 0 or height <= 0:
                raise ManifestError("invalid JPEG dimensions")
            return width, height
        offset += segment_length
    raise ManifestError("JPEG dimensions not found")


def build_manifest(input_dir: Path, *, declared_generated: bool) -> dict[str, Any]:
    files = sorted(input_dir.glob("*.jpg"))
    if not files:
        raise ManifestError("no .jpg files found")

    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    hash_to_names: dict[str, list[str]] = defaultdict(list)
    invalid_names: list[str] = []

    for path in files:
        match = FILENAME_RE.fullmatch(path.name)
        if not match:
            invalid_names.append(path.name)
            continue
        data = path.read_bytes()
        width, height = jpeg_size(data)
        digest = hashlib.sha256(data).hexdigest()
        subject_key = f"{match.group('subject')}.{match.group('label')}"
        pose = match.group("pose").lower()
        if pose in groups[subject_key]:
            raise ManifestError(f"duplicate pose for {subject_key}: {pose}")
        groups[subject_key][pose] = {
            "filename": path.name,
            "sha256": digest,
            "bytes": len(data),
            "width": width,
            "height": height,
        }
        hash_to_names[digest].append(path.name)

    if invalid_names:
        raise ManifestError("unexpected filenames: " + ", ".join(invalid_names))

    incomplete = {
        subject: sorted(set(EXPECTED_POSES) - set(poses))
        for subject, poses in groups.items()
        if set(poses) != set(EXPECTED_POSES)
    }
    if incomplete:
        details = "; ".join(f"{subject}: missing {','.join(missing)}" for subject, missing in incomplete.items())
        raise ManifestError("incomplete triplets: " + details)

    duplicate_bytes = sorted(
        names for names in hash_to_names.values() if len(names) > 1
    )
    if duplicate_bytes:
        raise ManifestError(f"duplicate image bytes: {duplicate_bytes}")

    subjects = []
    for subject in sorted(groups, key=lambda value: int(value.split(".", 1)[0])):
        poses = groups[subject]
        geometry = {(item["width"], item["height"]) for item in poses.values()}
        subjects.append(
            {
                "subjectKey": subject,
                "poses": {pose: poses[pose] for pose in EXPECTED_POSES},
                "consistentGeometry": len(geometry) == 1,
            }
        )

    geometry_ok = all(subject["consistentGeometry"] for subject in subjects)
    return {
        "schemaVersion": 1,
        "source": {
            "declaredGenerated": declared_generated,
            "expertGroundTruth": False,
            "realCameraCapture": False if declared_generated else None,
            "rawImagesCommitted": False,
        },
        "capturePackage": {
            "subjects": len(subjects),
            "images": len(files),
            "posesPerSubject": list(EXPECTED_POSES),
            "completeTriplets": True,
            "uniqueImageBytes": True,
            "consistentGeometryWithinTriplets": geometry_ok,
        },
        "eligibility": {
            "captureAndIntegrationSmokeTest": geometry_ok,
            "modelQualitativeProposalReview": True,
            "precisionRecallF1": False,
            "thresholdCalibration": False,
            "realCameraAcceptance": False,
            "expertLabelAcceptance": False,
        },
        "subjects": subjects,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--declared-generated", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = build_manifest(args.input_dir, declared_generated=args.declared_generated)
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
