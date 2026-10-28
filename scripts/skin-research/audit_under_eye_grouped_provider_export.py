#!/usr/bin/env python3
"""Audit a grouped under-eye provider export against the authorized archive.

The audit is deliberately local and read-only. It compares image bytes, split
membership, image dimensions, classes and canonical polygon geometry while
ignoring COCO identifiers and filenames. The emitted receipt contains only
aggregate counts and hashes; it never includes filenames, provider image IDs,
or image bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "under-eye-grouped-provider-export-audit-v1"
PROJECT_ID = "tolgar-sasmaz/attune-skin-under-eye-grouped-research"
PROJECT_TYPE = "instance-segmentation"
AUTHORIZED_ARCHIVE_SHA256 = "8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"
SPLITS = ("train", "valid", "test")
CLASSES = ("darkcircle", "eyebag")
EXPECTED = {
    "images": 399,
    "annotations": 869,
    "splits": {"train": 284, "valid": 77, "test": 38},
    "classCounts": {"darkcircle": 382, "eyebag": 487},
}
MAX_MEMBERS = 5000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024


class AuditError(ValueError):
    """Raised when an archive cannot prove exact provider identity."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
        raise AuditError("unsafe ZIP member")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise AuditError("symbolic ZIP member is not allowed")
    if info.file_size > MAX_MEMBER_BYTES:
        raise AuditError("ZIP member exceeds size limit")


def _number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuditError("polygon coordinate must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise AuditError("polygon coordinate must be finite")
    try:
        decimal = Decimal(str(value)).normalize()
    except InvalidOperation as exc:
        raise AuditError("invalid polygon coordinate") from exc
    return format(decimal, "f")


def _canonical_ring(values: Any) -> list[list[str]]:
    if not isinstance(values, list) or len(values) < 6 or len(values) % 2:
        raise AuditError("every annotation must contain valid polygon geometry")
    points = [[_number(values[index]), _number(values[index + 1])] for index in range(0, len(values), 2)]
    if points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise AuditError("polygon must contain at least three distinct vertices")
    candidates: list[list[list[str]]] = []
    for sequence in (points, list(reversed(points))):
        candidates.extend(sequence[index:] + sequence[:index] for index in range(len(sequence)))
    return min(candidates, key=lambda item: json.dumps(item, separators=(",", ":")))


def _canonical_segmentation(value: Any) -> list[list[list[str]]]:
    if not isinstance(value, list) or not value:
        raise AuditError("boxes cannot substitute for polygon truth")
    rings = [_canonical_ring(ring) for ring in value]
    return sorted(rings, key=lambda item: json.dumps(item, separators=(",", ":")))


def _read_archive(path: Path) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise AuditError("invalid ZIP archive") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise AuditError("ZIP member count exceeds limit")
        names: set[str] = set()
        total = 0
        payloads: dict[str, bytes] = {}
        for info in infos:
            _validate_member(info)
            if info.filename in names:
                raise AuditError("duplicate ZIP member")
            names.add(info.filename)
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise AuditError("ZIP uncompressed size exceeds limit")
            if not info.is_dir():
                payloads[info.filename] = archive.read(info)

    split_results: dict[str, Any] = {}
    all_content_hashes: list[str] = []
    totals: Counter[str] = Counter()
    total_annotations = 0
    for split in SPLITS:
        annotation_name = f"{split}/_annotations.coco.json"
        try:
            coco = json.loads(payloads[annotation_name])
        except KeyError as exc:
            raise AuditError(f"{split} COCO annotations missing") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditError(f"{split} COCO annotations are invalid") from exc
        if not isinstance(coco, dict):
            raise AuditError(f"{split} COCO object required")
        categories = coco.get("categories")
        if not isinstance(categories, list):
            raise AuditError(f"{split} categories missing")
        all_category_names = {
            item.get("id"): item.get("name")
            for item in categories
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        category_names = {
            category_id: name
            for category_id, name in all_category_names.items()
            if name in CLASSES
        }
        if len(category_names) != len(CLASSES) or set(category_names.values()) != set(CLASSES):
            raise AuditError(f"{split} class inventory changed")

        annotations_by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        class_counts: Counter[str] = Counter()
        annotations = coco.get("annotations")
        if not isinstance(annotations, list):
            raise AuditError(f"{split} annotations missing")
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("category_id") not in category_names:
                raise AuditError(f"{split} annotation is invalid")
            class_name = category_names[annotation["category_id"]]
            class_counts[class_name] += 1
            annotations_by_image[annotation.get("image_id")].append({
                "class": class_name,
                "polygons": _canonical_segmentation(annotation.get("segmentation")),
                "iscrowd": int(annotation.get("iscrowd", 0)),
            })

        images = coco.get("images")
        if not isinstance(images, list):
            raise AuditError(f"{split} images missing")
        image_ids: set[Any] = set()
        content_hashes: list[str] = []
        records: list[dict[str, Any]] = []
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("file_name"), str):
                raise AuditError(f"{split} image entry is invalid")
            image_id = image.get("id")
            if image_id in image_ids:
                raise AuditError(f"{split} duplicate image ID")
            image_ids.add(image_id)
            member = f"{split}/{image['file_name']}"
            if member not in payloads:
                raise AuditError(f"{split} image bytes missing")
            content_hash = hashlib.sha256(payloads[member]).hexdigest()
            if content_hash in content_hashes:
                raise AuditError(f"{split} duplicate image bytes")
            content_hashes.append(content_hash)
            records.append({
                "imageSHA256": content_hash,
                "width": image.get("width"),
                "height": image.get("height"),
                "annotations": sorted(
                    annotations_by_image.get(image_id, []),
                    key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
                ),
            })
        if set(annotations_by_image) - image_ids:
            raise AuditError(f"{split} contains annotations for unknown images")
        all_content_hashes.extend(content_hashes)
        totals.update(class_counts)
        total_annotations += len(annotations)
        split_results[split] = {
            "images": len(images),
            "annotations": len(annotations),
            "classCounts": {name: class_counts[name] for name in CLASSES},
            "contentSetSHA256": _digest_json(sorted(content_hashes)),
            "recordPolygonSetSHA256": _digest_json(sorted(
                records,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )),
        }

    if len(set(all_content_hashes)) != len(all_content_hashes):
        raise AuditError("image bytes occur in more than one split")
    summary = {
        "images": len(all_content_hashes),
        "annotations": total_annotations,
        "splits": {split: split_results[split]["images"] for split in SPLITS},
        "classCounts": {name: totals[name] for name in CLASSES},
    }
    if summary != EXPECTED:
        raise AuditError("archive totals differ from the frozen grouped contract")
    return {"summary": summary, "splits": split_results}


def build_audit(
    expected_archive: Path,
    provider_archive: Path,
    version: int,
    *,
    expected_archive_sha256: str = AUTHORIZED_ARCHIVE_SHA256,
) -> dict[str, Any]:
    if version < 1:
        raise AuditError("provider version must be positive")
    if _sha256_file(expected_archive) != expected_archive_sha256:
        raise AuditError("expected archive is not the authorized grouped archive")
    expected = _read_archive(expected_archive)
    provider = _read_archive(provider_archive)
    for split in SPLITS:
        comparable = ("images", "annotations", "classCounts", "contentSetSHA256", "recordPolygonSetSHA256")
        if any(expected["splits"][split][field] != provider["splits"][split][field] for field in comparable):
            raise AuditError(f"provider export does not match authorized {split} archive")
    split_identity = {
        split: {
            "images": provider["splits"][split]["images"],
            "annotations": provider["splits"][split]["annotations"],
            "contentSetSHA256": provider["splits"][split]["contentSetSHA256"],
            "recordPolygonSetSHA256": provider["splits"][split]["recordPolygonSetSHA256"],
        }
        for split in SPLITS
    }
    return {
        "schemaVersion": SCHEMA,
        "project": PROJECT_ID,
        "projectType": PROJECT_TYPE,
        "public": False,
        "versionNumber": version,
        **provider["summary"],
        "authorizedArchiveSHA256": expected_archive_sha256,
        "providerExportArchiveSHA256": _sha256_file(provider_archive),
        "recordIdentityBasis": "image-content-sha256-plus-canonical-polygon-geometry",
        "splitImageContentSetSHA256": {
            split: split_identity[split]["contentSetSHA256"] for split in SPLITS
        },
        "splitRecordPolygonSetSHA256": {
            split: split_identity[split]["recordPolygonSetSHA256"] for split in SPLITS
        },
        "providerDatasetIdentitySHA256": _digest_json(split_identity),
        "allProviderRecordsMatchedAuthorizedArchiveOnce": True,
        "unexpectedProviderRecords": 0,
        "missingAuthorizedRecords": 0,
        "crossSplitContentHashCount": 0,
        "polygonGeometryVerified": True,
        "boxGeometryUsedAsPolygonTruth": False,
        "finalTestUsedForSelectionOrThresholds": False,
        "containsFilenamesOrProviderImageIds": False,
        "versionGenerationAuthorized": False,
        "researchTrainingAuthorized": False,
        "productActivationAllowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-archive", type=Path, required=True)
    parser.add_argument("--provider-archive", type=Path, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-archive-sha256", default=AUTHORIZED_ARCHIVE_SHA256)
    args = parser.parse_args()
    audit = build_audit(
        args.expected_archive,
        args.provider_archive,
        args.version,
        expected_archive_sha256=args.expected_archive_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
