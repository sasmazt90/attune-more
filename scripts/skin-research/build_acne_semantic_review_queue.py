#!/usr/bin/env python3
"""Build a privacy-safe expert semantic/hard-negative review queue.

The queue samples only train and validation records. Locked test records are
inventoried but never selected. Output contains hashed record IDs and aggregate
annotation geometry, never filenames, image bytes, raw source names or boxes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


SPLITS = ("train", "valid", "test")
REVIEW_SPLITS = ("train", "valid")
CLASSES = ("Pimple", "Post acne", "Pigmentation")
PURPOSE_LIMITS = {
    "positive_tiny": 6,
    "positive_large": 3,
    "positive_isolated": 3,
    "positive_cooccurrence": 4,
    "hard_negative_other_target": 8,
    "unlabelled_negative": 4,
}


class QueueError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueueError(f"cannot read {path}: {exc}") from exc


def digest_token(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def load_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split in SPLITS:
        folder = root / split
        coco = load_json(folder / "_annotations.coco.json")
        images = coco.get("images")
        annotations = coco.get("annotations")
        categories = coco.get("categories")
        if not all(isinstance(value, list) for value in (images, annotations, categories)):
            raise QueueError(f"{split} COCO arrays are missing")
        category_names = {
            row.get("id"): row.get("name")
            for row in categories if isinstance(row, dict)
        }
        if not set(CLASSES).issubset(set(category_names.values())):
            raise QueueError(f"{split} class inventory mismatch")
        by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for annotation in annotations:
            if not isinstance(annotation, dict):
                raise QueueError(f"{split} annotation is invalid")
            image_id = annotation.get("image_id")
            name = category_names.get(annotation.get("category_id"))
            bbox = annotation.get("bbox")
            if (not isinstance(image_id, int) or name not in CLASSES
                    or not isinstance(bbox, list) or len(bbox) != 4):
                raise QueueError(f"{split} annotation fields are invalid")
            by_image[image_id].append({"class": name, "bbox": bbox})
        seen_ids: set[int] = set()
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("id"), int):
                raise QueueError(f"{split} image row is invalid")
            image_id = image["id"]
            if image_id in seen_ids:
                raise QueueError(f"{split} image ids are duplicated")
            seen_ids.add(image_id)
            file_name = image.get("file_name")
            width, height = image.get("width"), image.get("height")
            if (not isinstance(file_name, str) or not file_name
                    or Path(file_name).name != file_name
                    or not isinstance(width, int) or width <= 0
                    or not isinstance(height, int) or height <= 0):
                raise QueueError(f"{split} image fields are invalid")
            image_path = folder / file_name
            try:
                content_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise QueueError(f"{split} image file is missing") from exc
            record_id = digest_token(split + "\0" + file_name + "\0" + content_sha)
            class_areas: dict[str, list[float]] = defaultdict(list)
            for row in by_image.get(image_id, []):
                _, _, box_width, box_height = row["bbox"]
                if not all(isinstance(value, (int, float)) for value in row["bbox"]):
                    raise QueueError(f"{split} bbox is non-numeric")
                area = max(0.0, float(box_width)) * max(0.0, float(box_height))
                class_areas[row["class"]].append(area / (width * height))
            records.append({
                "recordId": record_id,
                "split": split,
                "fileName": file_name,
                "presentClasses": sorted(class_areas),
                "classAreas": class_areas,
            })
    return records


def take_unique(
    records: list[dict[str, Any]],
    used: set[str],
    limit: int,
    key: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for record in sorted(records, key=key):
        if record["recordId"] in used:
            continue
        selected.append(record)
        used.add(record["recordId"])
        if len(selected) == limit:
            break
    return selected


def public_item(record: dict[str, Any], target: str, purpose: str) -> dict[str, Any]:
    areas = record["classAreas"].get(target, [])
    return {
        "reviewItemId": digest_token(target + "\0" + purpose + "\0" + record["recordId"]),
        "recordId": record["recordId"],
        "split": record["split"],
        "targetClass": target,
        "purpose": purpose,
        "presentClasses": record["presentClasses"],
        "targetAnnotationCount": len(areas),
        "targetAreaFraction": ({
            "min": min(areas),
            "median": statistics.median(areas),
            "max": max(areas),
        } if areas else None),
        "expertDecision": None,
    }


def build_queue(root: Path, archive_sha256: str) -> tuple[dict[str, Any], dict[str, str]]:
    if len(archive_sha256) != 64 or any(c not in "0123456789abcdef" for c in archive_sha256):
        raise QueueError("archive sha256 must be a lowercase 64-character digest")
    records = load_records(root)
    review_records = [record for record in records if record["split"] in REVIEW_SPLITS]
    test_records = [record for record in records if record["split"] == "test"]
    items: list[dict[str, Any]] = []
    per_class_counts: dict[str, dict[str, int]] = {}
    for target in CLASSES:
        positives = [record for record in review_records if target in record["presentClasses"]]
        other_targets = [
            record for record in review_records
            if target not in record["presentClasses"] and record["presentClasses"]
        ]
        unlabelled = [record for record in review_records if not record["presentClasses"]]
        used: set[str] = set()
        buckets: dict[str, list[dict[str, Any]]] = {}
        buckets["positive_tiny"] = take_unique(
            positives, used, PURPOSE_LIMITS["positive_tiny"],
            lambda row: (min(row["classAreas"][target]), row["recordId"]),
        )
        buckets["positive_large"] = take_unique(
            positives, used, PURPOSE_LIMITS["positive_large"],
            lambda row: (-max(row["classAreas"][target]), row["recordId"]),
        )
        buckets["positive_isolated"] = take_unique(
            [row for row in positives if row["presentClasses"] == [target]],
            used, PURPOSE_LIMITS["positive_isolated"],
            lambda row: row["recordId"],
        )
        buckets["positive_cooccurrence"] = take_unique(
            [row for row in positives if len(row["presentClasses"]) > 1],
            used, PURPOSE_LIMITS["positive_cooccurrence"],
            lambda row: (-len(row["presentClasses"]), row["recordId"]),
        )
        buckets["hard_negative_other_target"] = take_unique(
            other_targets, used, PURPOSE_LIMITS["hard_negative_other_target"],
            lambda row: (-len(row["presentClasses"]), row["recordId"]),
        )
        buckets["unlabelled_negative"] = take_unique(
            unlabelled, used, PURPOSE_LIMITS["unlabelled_negative"],
            lambda row: row["recordId"],
        )
        per_class_counts[target] = {}
        for purpose in PURPOSE_LIMITS:
            public = [public_item(row, target, purpose) for row in buckets[purpose]]
            items.extend(public)
            per_class_counts[target][purpose] = len(public)
    items.sort(key=lambda row: (row["targetClass"], row["purpose"], row["reviewItemId"]))
    resolver = {record["recordId"]: record["fileName"] for record in review_records}
    queue = {
        "schemaVersion": "acne-semantic-review-queue-v1",
        "dataset": {
            "archiveSHA256": archive_sha256,
            "images": len(records),
            "reviewPoolImages": len(review_records),
            "lockedTestImages": len(test_records),
            "reviewSplits": list(REVIEW_SPLITS),
            "testSelectedForReview": 0,
        },
        "classes": list(CLASSES),
        "purposeLimits": PURPOSE_LIMITS,
        "countsByClassAndPurpose": per_class_counts,
        "reviewItems": items,
        "decision": {
            "expertReviewComplete": False,
            "positiveDefinitionsLocked": False,
            "hardNegativePoliciesLocked": False,
            "ambiguousCasePoliciesLocked": False,
            "trainingAuthorized": False,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "recordIdsAreHashed": True,
            "privateResolverCommitted": False,
        },
    }
    return queue, resolver


def build_receipt_template(queue: dict[str, Any]) -> dict[str, Any]:
    package_bytes = (json.dumps(queue, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return {
        "schemaVersion": "acne-semantic-negative-review-v1",
        "datasetArchiveSHA256": queue["dataset"]["archiveSHA256"],
        "reviewPackageCanonicalSHA256": hashlib.sha256(package_bytes).hexdigest(),
        "reviewer": None,
        "classes": [{
            "name": name,
            "expertReviewed": False,
            "positiveDefinitionLocked": False,
            "hardNegativePolicyLocked": False,
            "ambiguousCasePolicyLocked": False,
            "reviewedItemIds": [],
            "notes": None,
        } for name in CLASSES],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--private-resolver-output", type=Path)
    args = parser.parse_args(argv)
    try:
        queue, resolver = build_queue(args.dataset, args.archive_sha256)
    except QueueError as exc:
        print(f"semantic review queue blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_text(
        json.dumps(build_receipt_template(queue), indent=2) + "\n", encoding="utf-8"
    )
    if args.private_resolver_output:
        args.private_resolver_output.parent.mkdir(parents=True, exist_ok=True)
        args.private_resolver_output.write_text(
            json.dumps(resolver, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
