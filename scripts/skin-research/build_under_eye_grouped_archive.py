#!/usr/bin/env python3
"""Build a deterministic, leakage-reduced under-eye COCO archive.

The builder is deliberately narrow. It accepts an augmentation-free Roboflow
COCO export and a reviewed source-photo-pair receipt. It may only move members
of reviewed cross-split pairs to ``train``. Image bytes, polygon geometry,
classes and every annotation field other than COCO identifiers are preserved.

This utility never uploads data, starts training, or authorizes activation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


SPLITS = ("train", "valid", "test")
RF_SUFFIX = re.compile(r"\.rf\.[0-9a-f]{16,64}(?=\.[^.]+$)", re.IGNORECASE)
PRODUCTION_EXPECTED = {
    "images": 399,
    "annotations": 869,
    "splits": {"train": 279, "valid": 81, "test": 39},
    "classes": {"darkcircle": 382, "eyebag": 487},
    "reviewed_cross_split_pairs": 3,
    "moved_images": 4,
    "output_splits": {"train": 283, "valid": 78, "test": 38},
}


class ArchiveValidationError(ValueError):
    """Raised when an input cannot be transformed without weakening evidence."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_name(filename: str) -> str:
    return RF_SUFFIX.sub("", Path(filename).name)


def _validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
        raise ArchiveValidationError(f"unsafe ZIP member: {info.filename!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ArchiveValidationError(f"symbolic link not allowed: {info.filename!r}")


def _validate_segmentation(annotation: dict[str, Any]) -> None:
    segmentation = annotation.get("segmentation")
    if not isinstance(segmentation, list) or not segmentation:
        raise ArchiveValidationError("every annotation must contain polygon segmentation")
    for polygon in segmentation:
        if not isinstance(polygon, list) or len(polygon) < 6 or len(polygon) % 2:
            raise ArchiveValidationError("invalid polygon geometry")
        if not all(isinstance(value, (int, float)) for value in polygon):
            raise ArchiveValidationError("non-numeric polygon coordinate")


def _load_source(
    source_zip: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], dict[str, bytes]]:
    datasets: dict[str, dict[str, Any]] = {}
    images: dict[str, bytes] = {}
    extras: dict[str, bytes] = {}
    with zipfile.ZipFile(source_zip) as archive:
        for info in archive.infolist():
            _validate_member(info)
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            payload = archive.read(info)
            if len(parts) == 2 and parts[0] in SPLITS and parts[1] == "_annotations.coco.json":
                datasets[parts[0]] = json.loads(payload)
            elif len(parts) == 2 and parts[0] in SPLITS:
                images[info.filename] = payload
            else:
                extras[info.filename] = payload
    if set(datasets) != set(SPLITS):
        raise ArchiveValidationError("archive must contain train/valid/test COCO files")
    return datasets, images, extras


def _reviewed_groups(review: dict[str, Any]) -> list[set[str]]:
    groups: list[set[str]] = []
    for item in review.get("reviewedSourcePhotoPairs", []):
        if item.get("crossSplit") is not True:
            continue
        members = item.get("members")
        if not isinstance(members, list) or len(members) < 2:
            raise ArchiveValidationError("cross-split review group needs at least two members")
        canonical = {_canonical_name(str(member)) for member in members}
        if len(canonical) != len(members):
            raise ArchiveValidationError("duplicate member in reviewed group")
        groups.append(canonical)
    if not groups:
        raise ArchiveValidationError("no reviewed cross-split source-photo groups")
    return groups


def _annotation_payload(annotation: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(annotation)
    result.pop("id", None)
    result.pop("image_id", None)
    return result


def build_grouped_archive(
    source_zip: str | Path,
    review_receipt: str | Path,
    output_zip: str | Path,
    *,
    expected: dict[str, Any] | None = None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate, regroup and write a deterministic archive plus safe receipt."""

    source_path = Path(source_zip)
    review_path = Path(review_receipt)
    output_path = Path(output_zip)
    expected = expected or PRODUCTION_EXPECTED
    source_sha = _sha256_file(source_path)
    if expected_source_sha256 and source_sha != expected_source_sha256:
        raise ArchiveValidationError("source archive SHA256 does not match the pinned export")

    datasets, image_bytes, extras = _load_source(source_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    groups = _reviewed_groups(review)
    if len(groups) != expected["reviewed_cross_split_pairs"]:
        raise ArchiveValidationError("unexpected reviewed cross-split group count")

    category_maps: dict[str, dict[int, str]] = {}
    source_records: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    seen_canonical: set[str] = set()
    for split in SPLITS:
        dataset = datasets[split]
        category_maps[split] = {
            int(category["id"]): str(category["name"])
            for category in dataset.get("categories", [])
        }
        annotations_by_image: dict[int, list[dict[str, Any]]] = {}
        for annotation in dataset.get("annotations", []):
            _validate_segmentation(annotation)
            annotations_by_image.setdefault(int(annotation["image_id"]), []).append(annotation)
            name = category_maps[split].get(int(annotation["category_id"]))
            if name in expected["classes"]:
                class_counts[name] += 1
        for image in dataset.get("images", []):
            filename = str(image["file_name"])
            canonical = _canonical_name(filename)
            if canonical in seen_canonical:
                raise ArchiveValidationError(f"duplicate canonical source image: {canonical}")
            seen_canonical.add(canonical)
            member = f"{split}/{filename}"
            if member not in image_bytes:
                raise ArchiveValidationError(f"missing image bytes: {member}")
            source_records.append(
                {
                    "source_split": split,
                    "target_split": split,
                    "canonical": canonical,
                    "filename": filename,
                    "image": copy.deepcopy(image),
                    "annotations": [copy.deepcopy(a) for a in annotations_by_image.get(int(image["id"]), [])],
                    "bytes": image_bytes[member],
                }
            )
            split_counts[split] += 1

    if len(source_records) != expected["images"] or sum(class_counts.values()) != expected["annotations"]:
        raise ArchiveValidationError("source image/annotation totals differ from the pinned contract")
    if dict(split_counts) != expected["splits"]:
        raise ArchiveValidationError("source split counts differ from the pinned contract")
    if dict(class_counts) != expected["classes"]:
        raise ArchiveValidationError("source class counts differ from the pinned contract")

    by_canonical = {record["canonical"]: record for record in source_records}
    moved: set[str] = set()
    for group in groups:
        missing = group - set(by_canonical)
        if missing:
            raise ArchiveValidationError("reviewed group member not present in provider export")
        source_splits = {by_canonical[name]["source_split"] for name in group}
        if len(source_splits) < 2:
            raise ArchiveValidationError("reviewed cross-split group is no longer cross-split")
        for name in group:
            record = by_canonical[name]
            if record["target_split"] != "train":
                record["target_split"] = "train"
                moved.add(name)
    if len(moved) != expected["moved_images"]:
        raise ArchiveValidationError("unexpected moved-image count")

    output_datasets: dict[str, dict[str, Any]] = {}
    output_entries: dict[str, bytes] = dict(extras)
    output_split_counts: Counter[str] = Counter()
    geometry_changed = 0
    image_bytes_changed = 0
    for split in SPLITS:
        template = copy.deepcopy(datasets[split])
        template["images"] = []
        template["annotations"] = []
        records = sorted(
            (record for record in source_records if record["target_split"] == split),
            key=lambda record: record["filename"],
        )
        annotation_id = 1
        for image_id, record in enumerate(records, start=1):
            output_image = copy.deepcopy(record["image"])
            output_image["id"] = image_id
            template["images"].append(output_image)
            output_entries[f"{split}/{record['filename']}"] = record["bytes"]
            if _sha256_bytes(record["bytes"]) != _sha256_bytes(image_bytes[f"{record['source_split']}/{record['filename']}"]):
                image_bytes_changed += 1
            for source_annotation in sorted(record["annotations"], key=lambda item: int(item["id"])):
                output_annotation = copy.deepcopy(source_annotation)
                output_annotation["id"] = annotation_id
                output_annotation["image_id"] = image_id
                if _annotation_payload(output_annotation) != _annotation_payload(source_annotation):
                    geometry_changed += 1
                template["annotations"].append(output_annotation)
                annotation_id += 1
        output_split_counts[split] = len(records)
        output_datasets[split] = template
        output_entries[f"{split}/_annotations.coco.json"] = (
            json.dumps(template, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")

    if dict(output_split_counts) != expected["output_splits"]:
        raise ArchiveValidationError("grouped split counts differ from the pinned contract")
    if image_bytes_changed or geometry_changed:
        raise ArchiveValidationError("builder changed protected image or annotation content")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(output_entries):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100644 & 0xFFFF) << 16
                info.create_system = 3
                archive.writestr(info, output_entries[name])
        os.replace(temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-archive-v1",
        "sourceArchiveSHA256": source_sha,
        "outputArchiveSHA256": _sha256_file(output_path),
        "outputArchiveBytes": output_path.stat().st_size,
        "source": {
            "images": len(source_records),
            "annotations": sum(class_counts.values()),
            "splits": dict(split_counts),
            "classCounts": dict(class_counts),
        },
        "output": {
            "images": len(source_records),
            "annotations": sum(class_counts.values()),
            "splits": dict(output_split_counts),
            "classCounts": dict(class_counts),
        },
        "reviewedCrossSplitGroups": len(groups),
        "movedImages": len(moved),
        "imageBytesChanged": image_bytes_changed,
        "annotationPayloadsChanged": geometry_changed,
        "personIndependent": False,
        "expertReviewed": False,
        "trainingAuthorized": False,
        "activationAllowed": False,
        "limitations": [
            "Grouping covers only three manually reviewed source-photo pairs.",
            "The split is not person-independent and is not an independent camera cohort.",
            "This receipt does not authorize upload, training, activation, or roadmap acceptance.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--review-receipt", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args()
    receipt = build_grouped_archive(
        args.source_zip,
        args.review_receipt,
        args.output_zip,
        expected_source_sha256=args.source_sha256,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
