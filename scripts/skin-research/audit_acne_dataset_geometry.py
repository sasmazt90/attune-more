#!/usr/bin/env python3
"""Audit acne/post-acne/pigmentation COCO geometry without changing labels.

The report is aggregate-only: it never embeds image bytes or filenames. It is
intended to decide whether a targeted data/resolution change is justified
before another training run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SPLITS = ("train", "valid", "test")
CLASSES = ("Pimple", "Post acne", "Pigmentation")
TINY_AREA_FRACTION = 0.0004


class AuditError(ValueError):
    pass


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise AuditError("cannot calculate a quantile for an empty class")
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def load_coco(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"{path} must contain an object")
    return value


def audit(root: Path, tiny_area_fraction: float = TINY_AREA_FRACTION) -> dict[str, Any]:
    if not (0 < tiny_area_fraction < 1):
        raise AuditError("tiny area fraction must be between zero and one")
    class_areas: dict[str, list[float]] = {name: [] for name in CLASSES}
    class_images: dict[str, dict[str, int]] = {}
    split_rows: dict[str, Any] = {}
    hashes: dict[str, list[str]] = defaultdict(list)
    total_images = total_annotations = 0

    for split in SPLITS:
        folder = root / split
        coco = load_coco(folder / "_annotations.coco.json")
        categories = coco.get("categories")
        images = coco.get("images")
        annotations = coco.get("annotations")
        if not all(isinstance(rows, list) for rows in (categories, images, annotations)):
            raise AuditError(f"{split} COCO arrays are missing")
        all_categories = {
            row.get("id"): row.get("name") for row in categories if isinstance(row, dict)
        }
        category_map = {
            category_id: name for category_id, name in all_categories.items()
            if name in CLASSES
        }
        if set(category_map.values()) != set(CLASSES):
            raise AuditError(f"{split} class inventory mismatch")
        image_map = {
            row.get("id"): row for row in images
            if isinstance(row, dict) and isinstance(row.get("id"), int)
        }
        if len(image_map) != len(images):
            raise AuditError(f"{split} image ids are invalid or duplicated")
        by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
        split_counts = Counter()
        split_areas: dict[str, list[float]] = {name: [] for name in CLASSES}
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("image_id") not in image_map:
                raise AuditError(f"{split} annotation references an unknown image")
            name = category_map.get(annotation.get("category_id"))
            bbox = annotation.get("bbox")
            if name not in CLASSES or not isinstance(bbox, list) or len(bbox) != 4:
                raise AuditError(f"{split} annotation class or bbox is invalid")
            image = image_map[annotation["image_id"]]
            width, height = image.get("width"), image.get("height")
            if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0
                       for value in (width, height)):
                raise AuditError(f"{split} image dimensions are invalid")
            x, y, box_width, box_height = bbox
            if (not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                        and math.isfinite(value) for value in bbox)
                    or x < 0 or y < 0 or box_width <= 0 or box_height <= 0
                    or x + box_width > width + 1e-6 or y + box_height > height + 1e-6):
                raise AuditError(f"{split} bbox falls outside its image")
            area_fraction = box_width * box_height / (width * height)
            split_counts[name] += 1
            split_areas[name].append(area_fraction)
            class_areas[name].append(area_fraction)
            by_image[annotation["image_id"]].append(annotation)

        images_with_class = Counter()
        cooccurrence = Counter()
        for image_id, image in image_map.items():
            file_name = image.get("file_name")
            if not isinstance(file_name, str) or not file_name:
                raise AuditError(f"{split} image filename is invalid")
            file_path = folder / file_name
            try:
                digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise AuditError(f"{split} image file is missing") from exc
            hashes[digest].append(split)
            names = tuple(sorted({
                category_map[row["category_id"]] for row in by_image.get(image_id, [])
            }))
            cooccurrence[" + ".join(names) if names else "unlabelled"] += 1
            images_with_class.update(names)

        class_images[split] = {name: images_with_class[name] for name in CLASSES}
        split_rows[split] = {
            "images": len(images),
            "annotations": len(annotations),
            "annotationsByClass": {name: split_counts[name] for name in CLASSES},
            "imagesWithClass": class_images[split],
            "cooccurrenceImages": dict(sorted(cooccurrence.items())),
            "areaFractionByClass": {
                name: {
                    "median": quantile(split_areas[name], 0.5),
                    "p90": quantile(split_areas[name], 0.9),
                    "tinyCount": sum(value < tiny_area_fraction for value in split_areas[name]),
                    "tinyFraction": (
                        sum(value < tiny_area_fraction for value in split_areas[name])
                        / len(split_areas[name])
                    ),
                }
                for name in CLASSES
            },
        }
        total_images += len(images)
        total_annotations += len(annotations)

    exact_cross_split = sorted(
        digest for digest, locations in hashes.items() if len(set(locations)) > 1
    )
    totals = {name: len(class_areas[name]) for name in CLASSES}
    smallest = min(totals, key=totals.get)
    largest = max(totals, key=totals.get)
    aggregate = {
        name: {
            "annotations": totals[name],
            "medianAreaFraction": quantile(class_areas[name], 0.5),
            "p10AreaFraction": quantile(class_areas[name], 0.1),
            "p90AreaFraction": quantile(class_areas[name], 0.9),
            "tinyCount": sum(value < tiny_area_fraction for value in class_areas[name]),
            "tinyFraction": (
                sum(value < tiny_area_fraction for value in class_areas[name])
                / totals[name]
            ),
        }
        for name in CLASSES
    }
    return {
        "schemaVersion": "acne-dataset-geometry-audit-v1",
        "dataset": {
            "images": total_images,
            "annotations": total_annotations,
            "classes": list(CLASSES),
            "splits": split_rows,
        },
        "geometry": {
            "tinyAreaFractionThreshold": tiny_area_fraction,
            "aggregateByClass": aggregate,
        },
        "balance": {
            "largestClass": largest,
            "smallestClass": smallest,
            "largestToSmallestAnnotationRatio": totals[largest] / totals[smallest],
            "postAcneToPimpleRatio": totals["Post acne"] / totals["Pimple"],
            "postAcneToPigmentationRatio": totals["Post acne"] / totals["Pigmentation"],
        },
        "splitIdentity": {
            "exactCrossSplitDuplicateGroups": len(exact_cross_split),
            "exactCrossSplitDuplicateSHA256": exact_cross_split,
            "personOrSourceGroupIdentityAvailable": False,
            "independenceEstablished": False,
        },
        "decision": {
            "trainingAuthorized": False,
            "modelAccepted": False,
            "reason": (
                "TARGETED_DATA_RESOLUTION_AND_SOURCE_GROUP_REVIEW_REQUIRED;"
                " DO_NOT_BLINDLY_RETRAIN"
            ),
            "next": [
                "review class semantics and negative coverage with experts",
                "create source/person groups before a new locked split",
                "test higher-resolution or crop-aware training on validation only",
                "rebalance Pigmentation and Pimple without fabricating labels",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tiny-area-fraction", type=float, default=TINY_AREA_FRACTION)
    args = parser.parse_args(argv)
    try:
        result = audit(args.dataset, args.tiny_area_fraction)
    except AuditError as exc:
        print(f"dataset geometry audit blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
