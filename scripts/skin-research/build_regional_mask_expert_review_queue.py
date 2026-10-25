#!/usr/bin/env python3
"""Build a privacy-safe, train/valid-only regional mask expert review queue.

The queue selects geometry extremes for Oily and Redness without treating an
absent source annotation as a negative. The current test split is never read or
selected. A private review-item resolver may be written locally, but it must
not be committed.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit_regional_skin_type_source_groups import AuditError, SHA256, _private_id


EXPECTED_SPLITS = {"train": 244, "valid": 63}
EXPECTED_CLASSES = ("Oily", "Redness")
TARGETS = {
    ("Oily", "train"): 32,
    ("Oily", "valid"): 8,
    ("Redness", "train"): 32,
    ("Redness", "valid"): 8,
}
MINIMUM_UNIQUE_REVIEW_IMAGES = 81


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("invalid COCO annotations") from exc
    if not isinstance(value, dict):
        raise AuditError("COCO root must be an object")
    return value


def _choose(rows: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    if len(rows) < target:
        raise AuditError("not enough class/split records for the review target")
    orders = (
        ("small_mask_support", lambda row: (row["areaFraction"], row["reviewItemId"])),
        ("broad_mask_support", lambda row: (-row["areaFraction"], row["reviewItemId"])),
        ("few_instances", lambda row: (row["instances"], row["reviewItemId"])),
        ("many_instances", lambda row: (-row["instances"], row["reviewItemId"])),
        ("complex_boundaries", lambda row: (-row["vertices"], row["reviewItemId"])),
    )
    selected: dict[str, dict[str, Any]] = {}
    depth = 0
    sorted_orders = [(reason, sorted(rows, key=key)) for reason, key in orders]
    while len(selected) < target:
        progressed = False
        for reason, ordered in sorted_orders:
            if depth >= len(ordered):
                continue
            row = ordered[depth]
            item = selected.setdefault(row["reviewItemId"], dict(row, reviewFocus=[]))
            if reason not in item["reviewFocus"]:
                item["reviewFocus"].append(reason)
            progressed = True
            if len(selected) == target:
                break
        if not progressed:
            break
        depth += 1
    if len(selected) < target:
        for row in sorted(rows, key=lambda item: item["reviewItemId"]):
            selected.setdefault(row["reviewItemId"], dict(row, reviewFocus=["coverage_fill"]))
            if len(selected) == target:
                break
    return sorted(selected.values(), key=lambda row: row["reviewItemId"])


def build_queue(
    root: Path,
    source_archive_sha256: str,
    provider_export_sha256: str,
    salt: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    for digest in (source_archive_sha256, provider_export_sha256):
        if not SHA256.fullmatch(digest):
            raise AuditError("archive digests must be lowercase sha256 values")
    if len(salt) < 16:
        raise AuditError("privacy salt must contain at least 16 characters")

    candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    resolver: dict[str, str] = {}
    cooccurrence: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}

    for split in ("train", "valid"):
        payload = _load(root / split / "_annotations.coco.json")
        images = payload.get("images")
        annotations = payload.get("annotations")
        categories = payload.get("categories")
        if not all(isinstance(value, list) for value in (images, annotations, categories)):
            raise AuditError("missing COCO arrays")
        split_counts[split] = len(images)
        names = {row.get("id"): row.get("name") for row in categories if isinstance(row, dict)}
        if not set(EXPECTED_CLASSES).issubset(set(names.values())):
            raise AuditError("Oily and Redness categories are required")
        by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in annotations:
            if not isinstance(annotation, dict) or names.get(annotation.get("category_id")) not in EXPECTED_CLASSES:
                raise AuditError("annotation class is invalid")
            by_image[annotation.get("image_id")].append(annotation)

        for image in images:
            if not isinstance(image, dict):
                raise AuditError("image row is invalid")
            file_name = image.get("file_name")
            width = image.get("width")
            height = image.get("height")
            if not isinstance(file_name, str) or not isinstance(width, int) or not isinstance(height, int):
                raise AuditError("image metadata is invalid")
            item_id = _private_id(salt, "regional-mask-review", f"{split}:{file_name}")
            resolver[item_id] = str(root / split / Path(file_name).name)
            rows = by_image.get(image.get("id"), [])
            present = sorted({names[row["category_id"]] for row in rows})
            per_class: dict[str, dict[str, Any]] = {}
            for class_name in EXPECTED_CLASSES:
                class_rows = [row for row in rows if names[row["category_id"]] == class_name]
                if not class_rows:
                    continue
                area = sum(float(row.get("area", 0)) for row in class_rows)
                vertices = sum(
                    len(polygon) // 2
                    for row in class_rows
                    for polygon in row.get("segmentation", [])
                    if isinstance(polygon, list)
                )
                per_class[class_name] = {
                    "reviewItemId": item_id,
                    "split": split,
                    "className": class_name,
                    "instances": len(class_rows),
                    "areaFraction": round(area / (width * height), 8),
                    "vertices": vertices,
                    "sourceClassesPresent": present,
                    "missingClassIsNegative": False,
                }
                candidates[(class_name, split)].append(per_class[class_name])
            if len(present) > 1:
                cooccurrence.append({
                    "reviewItemId": item_id,
                    "split": split,
                    "classes": present,
                    "reviewFocus": ["multi_layer_cooccurrence"],
                    "missingClassIsNegative": False,
                })

    if split_counts != EXPECTED_SPLITS:
        raise AuditError("train/valid image counts do not match the frozen export")

    selected: dict[str, dict[str, Any]] = {}
    for key, target in TARGETS.items():
        for row in _choose(candidates[key], target):
            existing = selected.get(row["reviewItemId"])
            if existing is None:
                selected[row["reviewItemId"]] = row
            else:
                existing.setdefault("additionalClassReviews", []).append({
                    key: value for key, value in row.items()
                    if key not in {"reviewItemId", "split"}
                })
    for row in cooccurrence:
        selected.setdefault(row["reviewItemId"], row)
    if len(selected) < MINIMUM_UNIQUE_REVIEW_IMAGES:
        all_candidates = sorted(
            (row for rows in candidates.values() for row in rows),
            key=lambda row: row["reviewItemId"],
        )
        for row in all_candidates:
            selected.setdefault(
                row["reviewItemId"],
                dict(row, reviewFocus=["unique_image_coverage_fill"]),
            )
            if len(selected) == MINIMUM_UNIQUE_REVIEW_IMAGES:
                break

    queue = {
        "schemaVersion": "regional-mask-expert-review-queue-v1",
        "source": {
            "sourceArchiveSHA256": source_archive_sha256,
            "providerExportSHA256": provider_export_sha256,
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
        "selection": {
            "allowedSplits": ["train", "valid"],
            "testImagesRead": 0,
            "testImagesSelected": 0,
            "targets": {f"{name}:{split}": count for (name, split), count in TARGETS.items()},
            "selectedUniqueImages": len(selected),
            "cooccurrenceImagesIncluded": len(cooccurrence),
            "candidateGeometryOnly": True,
        },
        "reviewPolicy": {
            "reviewerRequired": "expert_review",
            "rednessIndependentLayer": True,
            "missingMaskMeansNormal": False,
            "missingClassIsNegative": False,
            "modelPredictionAcceptedAsTruth": False,
            "requiredPerClassDecisions": [
                "mask_extent_correct",
                "hard_negative_policy",
                "ambiguous_case_policy",
                "assessability",
            ],
        },
        "items": sorted(selected.values(), key=lambda row: row["reviewItemId"]),
        "decision": {
            "expertReviewComplete": False,
            "maskProtocolReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }
    return queue, resolver


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--provider-export-sha256", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    args = parser.parse_args()
    queue, resolver = build_queue(
        args.root,
        args.source_archive_sha256,
        args.provider_export_sha256,
        args.salt,
    )
    args.output.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
