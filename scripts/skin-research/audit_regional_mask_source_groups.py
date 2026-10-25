#!/usr/bin/env python3
"""Audit the frozen regional Oily/Redness COCO export without mutating it.

The output contains privacy-safe aggregate geometry and candidate-only
cross-split similarity evidence. It deliberately cannot establish person
independence or authorize training, even when no perceptual candidate is found.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from audit_regional_skin_type_source_groups import (
    AuditError,
    SHA256,
    SPLITS,
    audit_source_groups,
)


EXPECTED_CLASSES = ("Oily", "Redness")
EXPECTED_IMAGES = 337
EXPECTED_SPLITS = {"train": 244, "valid": 63, "test": 30}


def _load_coco(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("invalid COCO annotations") from exc
    if not isinstance(value, dict):
        raise AuditError("COCO root must be an object")
    return value


def _audit_geometry(root: Path) -> dict[str, Any]:
    split_images: dict[str, int] = {}
    split_labels: dict[str, dict[str, int]] = {}
    class_labels: Counter[str] = Counter()
    polygon_annotations = 0
    invalid_polygons = 0
    non_polygon_annotations = 0
    total_annotations = 0

    for split in SPLITS:
        coco = _load_coco(root / split / "_annotations.coco.json")
        images = coco.get("images")
        annotations = coco.get("annotations")
        categories = coco.get("categories")
        if not all(isinstance(rows, list) for rows in (images, annotations, categories)):
            raise AuditError(f"missing COCO arrays for {split}")
        dimensions = {
            row.get("id"): (row.get("width"), row.get("height"))
            for row in images
            if isinstance(row, dict)
        }
        names = {
            row.get("id"): row.get("name")
            for row in categories
            if isinstance(row, dict)
        }
        counts: Counter[str] = Counter()
        for row in annotations:
            if not isinstance(row, dict):
                raise AuditError("annotation row is invalid")
            name = names.get(row.get("category_id"))
            if name not in EXPECTED_CLASSES:
                raise AuditError("used class inventory is not Oily/Redness only")
            width, height = dimensions.get(row.get("image_id"), (None, None))
            if not isinstance(width, int) or not isinstance(height, int):
                raise AuditError("annotation image reference is invalid")
            counts[name] += 1
            class_labels[name] += 1
            total_annotations += 1
            segmentation = row.get("segmentation")
            if not isinstance(segmentation, list) or not segmentation:
                non_polygon_annotations += 1
                continue
            polygon_annotations += 1
            valid = True
            for polygon in segmentation:
                if not isinstance(polygon, list) or len(polygon) < 6 or len(polygon) % 2:
                    valid = False
                    break
                for index in range(0, len(polygon), 2):
                    x, y = polygon[index], polygon[index + 1]
                    if (
                        not isinstance(x, (int, float))
                        or not isinstance(y, (int, float))
                        or x < 0
                        or y < 0
                        or x > width
                        or y > height
                    ):
                        valid = False
                        break
                if not valid:
                    break
            if not valid:
                invalid_polygons += 1
        split_images[split] = len(images)
        split_labels[split] = dict(sorted(counts.items()))

    if split_images != EXPECTED_SPLITS:
        raise AuditError("frozen split counts do not match the regional receipt")
    if sum(split_images.values()) != EXPECTED_IMAGES:
        raise AuditError("frozen image count does not match the regional receipt")
    if set(class_labels) != set(EXPECTED_CLASSES):
        raise AuditError("both Oily and Redness must have annotations")
    return {
        "images": EXPECTED_IMAGES,
        "annotations": total_annotations,
        "polygonAnnotations": polygon_annotations,
        "nonPolygonAnnotations": non_polygon_annotations,
        "invalidPolygonAnnotations": invalid_polygons,
        "splits": split_images,
        "splitLabels": split_labels,
        "classLabels": dict(sorted(class_labels.items())),
    }


def build_audit(
    root: Path,
    source_archive_sha256: str,
    provider_export_sha256: str,
    salt: str,
    *,
    dhash_max_distance: int = 8,
    phash_max_distance: int = 12,
) -> tuple[dict[str, Any], dict[str, str]]:
    for value in (source_archive_sha256, provider_export_sha256):
        if not SHA256.fullmatch(value):
            raise AuditError("archive digests must be lowercase sha256 values")
    geometry = _audit_geometry(root)
    similarity, resolver = audit_source_groups(
        root,
        provider_export_sha256,
        salt,
        dhash_max_distance=dhash_max_distance,
        phash_max_distance=phash_max_distance,
    )
    inventory = dict(similarity["inventory"])
    inventory.update(geometry)
    audit = {
        "schemaVersion": "regional-mask-source-group-audit-v1",
        "source": {
            "sourceArchiveSHA256": source_archive_sha256,
            "providerExportSHA256": provider_export_sha256,
            "providerExportFormat": "coco",
            "project": "tolgar-sasmaz/attune-skin-regional-skin-map",
            "versionNumber": 1,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "resolverCommitted": False,
            "identifierMethod": "salted-sha256-prefix-24",
        },
        "inventory": inventory,
        "method": similarity["method"],
        "candidates": similarity["candidates"],
        "coverage": {
            "completeReviewedPersonOrSourceGroups": 0,
            "unreviewedSourceIds": inventory["uniqueSourceIds"],
            "allRecordsRepresented": True,
        },
        "decision": {
            "personIndependenceEstablished": False,
            "replacementSplitReady": False,
            "trainingAuthorized": False,
            "testEligibleForFinalAcceptance": False,
            "reason": (
                "ZERO_PERCEPTUAL_CANDIDATES_DOES_NOT_ESTABLISH_PERSON_IDENTITY_COVERAGE"
                if not similarity["candidates"]
                else "REVIEW_CANDIDATES_AND_COMPLETE_PERSON_IDENTITY_COVERAGE"
            ),
        },
    }
    return audit, resolver


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--provider-export-sha256", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--dhash-max-distance", type=int, default=8)
    parser.add_argument("--phash-max-distance", type=int, default=12)
    args = parser.parse_args()
    audit, resolver = build_audit(
        args.root,
        args.source_archive_sha256,
        args.provider_export_sha256,
        args.salt,
        dhash_max_distance=args.dhash_max_distance,
        phash_max_distance=args.phash_max_distance,
    )
    args.output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
