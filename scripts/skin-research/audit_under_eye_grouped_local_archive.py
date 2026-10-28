#!/usr/bin/env python3
"""Fail-closed local audit for the exact authorized grouped under-eye archive.

The receipt contains aggregate counts and digests only.  It never emits image
names, COCO identifiers, paths, pixels or polygon coordinates and it performs
no provider write, version generation, training or evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


AUTHORIZED_SHA256 = "8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"
EXPECTED_BYTES = 15_086_760
EXPECTED_IMAGES = {"train": 284, "valid": 77, "test": 38}
EXPECTED_ANNOTATIONS = {"train": 632, "valid": 149, "test": 88}
EXPECTED_CLASSES = {"darkcircle": 382, "eyebag": 487}
TARGET_CLASSES = frozenset(EXPECTED_CLASSES)
MAX_MEMBERS = 5_000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


class ArchiveAuditError(ValueError):
    """Raised when the local archive fails the frozen contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArchiveAuditError(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def _safe_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    _require(not path.is_absolute(), "absolute ZIP member")
    _require(".." not in path.parts and "\\" not in info.filename, "unsafe ZIP member")
    _require(not stat.S_ISLNK(info.external_attr >> 16), "symbolic ZIP member")
    _require(info.file_size <= MAX_MEMBER_BYTES, "ZIP member exceeds size limit")


def _polygon_area(points: list[float]) -> float:
    pairs = list(zip(points[::2], points[1::2]))
    return abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(pairs, pairs[1:] + pairs[:1])
    )) / 2.0


def audit_archive(path: str | Path, *, observed_at: str) -> dict[str, Any]:
    archive_path = Path(path)
    _require(archive_path.is_file(), "archive is missing")
    archive_sha = _sha256_file(archive_path)
    _require(archive_sha == AUTHORIZED_SHA256, "archive SHA256 is not authorized")
    _require(archive_path.stat().st_size == EXPECTED_BYTES, "archive byte count changed")

    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        _require(len(infos) <= MAX_MEMBERS, "ZIP member count exceeds limit")
        names: set[str] = set()
        total_uncompressed = 0
        for info in infos:
            _safe_member(info)
            _require(info.filename not in names, "duplicate ZIP member")
            names.add(info.filename)
            total_uncompressed += info.file_size
            _require(total_uncompressed <= MAX_TOTAL_BYTES, "ZIP expands beyond limit")

        all_content_hashes: set[str] = set()
        class_counts: Counter[str] = Counter()
        split_receipts: dict[str, Any] = {}
        polygon_count = 0
        vertex_count = 0
        for split in EXPECTED_IMAGES:
            annotation_name = f"{split}/_annotations.coco.json"
            _require(annotation_name in names, f"{split} annotations missing")
            coco = json.loads(archive.read(annotation_name))
            _require(isinstance(coco, dict), f"{split} COCO object required")
            images = coco.get("images")
            annotations = coco.get("annotations")
            categories = coco.get("categories")
            _require(isinstance(images, list), f"{split} images missing")
            _require(isinstance(annotations, list), f"{split} annotations missing")
            _require(isinstance(categories, list), f"{split} categories missing")
            _require(len(images) == EXPECTED_IMAGES[split], f"{split} image count changed")
            _require(len(annotations) == EXPECTED_ANNOTATIONS[split], f"{split} annotation count changed")

            category_names = {
                item.get("id"): item.get("name")
                for item in categories
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            target_ids = {key: value for key, value in category_names.items() if value in TARGET_CLASSES}
            _require(set(target_ids.values()) == TARGET_CLASSES, f"{split} target classes changed")

            image_meta: dict[Any, tuple[str, int, int]] = {}
            split_hashes: list[str] = []
            for image in images:
                _require(isinstance(image, dict), f"{split} image record invalid")
                image_id = image.get("id")
                file_name = image.get("file_name")
                width, height = image.get("width"), image.get("height")
                _require(image_id not in image_meta, f"{split} duplicate image ID")
                _require(isinstance(file_name, str), f"{split} image name invalid")
                _require(isinstance(width, int) and width > 0, f"{split} image width invalid")
                _require(isinstance(height, int) and height > 0, f"{split} image height invalid")
                member = f"{split}/{file_name}"
                _require(member in names, f"{split} image bytes missing")
                content_hash = hashlib.sha256(archive.read(member)).hexdigest()
                _require(content_hash not in all_content_hashes, "duplicate image bytes across splits")
                all_content_hashes.add(content_hash)
                split_hashes.append(content_hash)
                image_meta[image_id] = (content_hash, width, height)

            split_classes: Counter[str] = Counter()
            geometry_records: list[dict[str, Any]] = []
            for annotation in annotations:
                _require(isinstance(annotation, dict), f"{split} annotation invalid")
                image_id = annotation.get("image_id")
                class_name = target_ids.get(annotation.get("category_id"))
                _require(image_id in image_meta, f"{split} annotation image is unknown")
                _require(class_name in TARGET_CLASSES, f"{split} non-target annotation used")
                _require(annotation.get("iscrowd", 0) == 0, f"{split} crowd/RLE truth forbidden")
                segmentation = annotation.get("segmentation")
                _require(isinstance(segmentation, list) and segmentation, f"{split} polygon required")
                _, width, height = image_meta[image_id]
                ring_areas: list[float] = []
                for ring in segmentation:
                    _require(isinstance(ring, list) and len(ring) >= 6 and len(ring) % 2 == 0, f"{split} polygon invalid")
                    _require(all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in ring), f"{split} coordinate invalid")
                    _require(all(0 <= value <= width for value in ring[::2]), f"{split} x coordinate outside image")
                    _require(all(0 <= value <= height for value in ring[1::2]), f"{split} y coordinate outside image")
                    area = _polygon_area(ring)
                    _require(area > 0, f"{split} degenerate polygon")
                    ring_areas.append(round(area, 6))
                    polygon_count += 1
                    vertex_count += len(ring) // 2
                bbox = annotation.get("bbox")
                _require(isinstance(bbox, list) and len(bbox) == 4, f"{split} bbox metadata invalid")
                _require(all(isinstance(value, (int, float)) and math.isfinite(value) for value in bbox), f"{split} bbox metadata invalid")
                _require(bbox[2] > 0 and bbox[3] > 0, f"{split} bbox metadata degenerate")
                _require(isinstance(annotation.get("area"), (int, float)) and annotation["area"] > 0, f"{split} area metadata invalid")
                split_classes[class_name] += 1
                class_counts[class_name] += 1
                geometry_records.append({
                    "imageSHA256": image_meta[image_id][0],
                    "class": class_name,
                    "rings": len(segmentation),
                    "vertices": sum(len(ring) // 2 for ring in segmentation),
                    "ringAreas": ring_areas,
                })

            split_receipts[split] = {
                "images": len(images),
                "annotations": len(annotations),
                "classCounts": {name: split_classes[name] for name in sorted(TARGET_CLASSES)},
                "contentSetSHA256": _json_digest(sorted(split_hashes)),
                "geometrySummarySHA256": _json_digest(sorted(
                    geometry_records,
                    key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
                )),
            }

    _require(len(all_content_hashes) == sum(EXPECTED_IMAGES.values()), "unique image total changed")
    _require(dict(class_counts) == EXPECTED_CLASSES, "class totals changed")
    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-local-archive-audit-v1",
        "observedAt": observed_at,
        "archiveSHA256": archive_sha,
        "archiveBytes": archive_path.stat().st_size,
        "images": len(all_content_hashes),
        "annotations": sum(EXPECTED_ANNOTATIONS.values()),
        "classCounts": EXPECTED_CLASSES,
        "polygonCount": polygon_count,
        "vertexCount": vertex_count,
        "splits": split_receipts,
        "zipSafetyVerified": True,
        "crossSplitDuplicateImageBytes": 0,
        "polygonGeometryVerified": True,
        "boxUsedAsPolygonTruth": False,
        "containsImageNamesOrProviderIds": False,
        "providerMutationPerformed": False,
        "uploadPerformed": False,
        "versionGenerationAuthorized": False,
        "researchTrainingAuthorized": False,
        "testEvaluationAuthorized": False,
        "productActivationAllowed": False,
        "roadmapAccepted": False,
        "decision": "local_archive_identity_and_geometry_verified_only",
        "privacySafe": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit_archive(args.archive, observed_at=args.observed_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
