"""Audit a COCO export used for regional dry/oily research.

The audit is deliberately geometry-aware and fail closed. Object-detection
boxes are inventoried as boxes; they are never promoted to polygon/mask truth,
and the absence of a dry/oily box is never interpreted as normal skin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


SPLITS = ("train", "valid", "test")
EXPECTED_CLASSES = {"dry", "oily"}
SOURCE_NAME = re.compile(
    r"^(?P<source>.+?)_jpg\.rf\.[0-9a-f]{32}\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AuditError(ValueError):
    """Raised when the export cannot be audited without guessing."""


def _source_id(file_name: str) -> str:
    match = SOURCE_NAME.fullmatch(Path(file_name).name)
    if not match:
        raise AuditError("image filename does not expose a stable Roboflow source id")
    return hashlib.sha256(match.group("source").encode("utf-8")).hexdigest()[:24]


def _load_split(root: Path, split: str) -> dict[str, Any]:
    path = root / split / "_annotations.coco.json"
    if not path.is_file():
        raise AuditError(f"missing COCO annotations for {split}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid COCO annotations for {split}") from exc
    if not all(isinstance(payload.get(key), list) for key in ("images", "annotations", "categories")):
        raise AuditError(f"incomplete COCO document for {split}")
    return payload


def audit_export(root: Path, archive_sha256: str, project: str, version: int) -> dict[str, Any]:
    if not SHA256.fullmatch(archive_sha256):
        raise AuditError("archive sha256 must be a lowercase 64-character digest")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise AuditError("version must be a positive integer")

    split_summaries: dict[str, Any] = {}
    split_sources: dict[str, set[str]] = {}
    total_images = 0
    total_annotations = 0
    total_segmentations = 0
    total_images_without_annotations = 0
    aggregate_classes: Counter[str] = Counter()

    for split in SPLITS:
        payload = _load_split(root, split)
        category_by_id = {
            row.get("id"): row.get("name")
            for row in payload["categories"]
            if row.get("name") in EXPECTED_CLASSES
        }
        present_classes = set(category_by_id.values())
        if present_classes != EXPECTED_CLASSES:
            raise AuditError(f"{split} must contain exactly the dry and oily target classes")

        images: dict[Any, dict[str, Any]] = {}
        sources: list[str] = []
        for image in payload["images"]:
            image_id = image.get("id")
            width = image.get("width")
            height = image.get("height")
            file_name = image.get("file_name")
            if image_id in images:
                raise AuditError(f"duplicate image id in {split}")
            if (not isinstance(width, int) or not isinstance(height, int)
                    or width <= 0 or height <= 0 or not isinstance(file_name, str)):
                raise AuditError(f"invalid image record in {split}")
            images[image_id] = image
            sources.append(_source_id(file_name))

        class_counts: Counter[str] = Counter()
        annotations_by_image: Counter[Any] = Counter()
        segmentation_count = 0
        for annotation in payload["annotations"]:
            image_id = annotation.get("image_id")
            image = images.get(image_id)
            class_name = category_by_id.get(annotation.get("category_id"))
            bbox = annotation.get("bbox")
            if image is None or class_name is None:
                raise AuditError(f"annotation references an unknown image or class in {split}")
            if (not isinstance(bbox, list) or len(bbox) != 4
                    or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                           or not math.isfinite(value) for value in bbox)):
                raise AuditError(f"invalid bbox in {split}")
            x, y, width, height = bbox
            if (x < 0 or y < 0 or width <= 0 or height <= 0
                    or x + width > image["width"] + 1e-6
                    or y + height > image["height"] + 1e-6):
                raise AuditError(f"out-of-bounds bbox in {split}")
            segmentation = annotation.get("segmentation")
            if isinstance(segmentation, (list, dict)) and len(segmentation) > 0:
                segmentation_count += 1
            class_counts[class_name] += 1
            annotations_by_image[image_id] += 1

        source_set = set(sources)
        split_sources[split] = source_set
        images_without_annotations = len(set(images) - set(annotations_by_image))
        split_summaries[split] = {
            "images": len(images),
            "uniqueSourceIds": len(source_set),
            "augmentationCopiesBeyondUniqueSources": len(images) - len(source_set),
            "annotations": len(payload["annotations"]),
            "classAnnotations": dict(sorted(class_counts.items())),
            "nonEmptySegmentations": segmentation_count,
            "imagesWithoutAnnotations": images_without_annotations,
        }
        total_images += len(images)
        total_annotations += len(payload["annotations"])
        total_segmentations += segmentation_count
        total_images_without_annotations += images_without_annotations
        aggregate_classes.update(class_counts)

    cross_split = {
        f"{left}-{right}": len(split_sources[left] & split_sources[right])
        for index, left in enumerate(SPLITS)
        for right in SPLITS[index + 1:]
    }
    unique_sources = set().union(*split_sources.values())
    reasons = [
        "BOX_ONLY_GEOMETRY_CANNOT_SERVE_AS_REGIONAL_MASK_TRUTH",
        "EVALUATED_NORMAL_CLASS_MISSING",
        "PERSON_INDEPENDENCE_UNESTABLISHED",
        "EXPERT_LABEL_PROTOCOL_UNVERIFIED",
        "CAMERA_ACCEPTANCE_MISSING",
    ]
    if any(cross_split.values()):
        reasons.append("SOURCE_ID_CROSSES_SPLITS")

    return {
        "schemaVersion": "regional-skin-type-box-audit-v1",
        "source": {
            "project": project,
            "version": version,
            "archiveSHA256": archive_sha256,
            "exportFormat": "coco",
        },
        "taskSemantics": {
            "providerTaskType": "object-detection",
            "observedGeometry": "bounding_boxes",
            "targetClasses": sorted(EXPECTED_CLASSES),
            "normalClassPresent": False,
            "boxToMaskConversionAllowed": False,
            "missingAnnotationMeansNormal": False,
        },
        "inventory": {
            "images": total_images,
            "uniqueSourceIds": len(unique_sources),
            "augmentationCopiesBeyondUniqueSources": total_images - len(unique_sources),
            "annotations": total_annotations,
            "classAnnotations": dict(sorted(aggregate_classes.items())),
            "nonEmptySegmentations": total_segmentations,
            "imagesWithoutAnnotations": total_images_without_annotations,
            "splits": split_summaries,
            "crossSplitSourceIds": cross_split,
        },
        "decision": {
            "regionalTruthEligible": False,
            "trainingAuthorized": False,
            "modelAccepted": False,
            "productActivationAllowed": False,
            "reasons": reasons,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_export(args.root, args.archive_sha256, args.project, args.version)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
