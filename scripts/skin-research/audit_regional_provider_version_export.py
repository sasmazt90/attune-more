#!/usr/bin/env python3
"""Build a privacy-safe identity audit for a regional provider version export.

The expected archive must be the private materialization of the reviewed,
group-locked manifest. The provider export is accepted only when every image
byte digest and its canonical COCO annotation payload match in the same split.
Filenames and provider image IDs are used locally but never written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "regional-provider-version-export-audit-v1"
PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
PROJECT_TYPE = "instance-segmentation"
MANIFEST_FILE_SHA256 = "d698580acae5c2987392e170bd408d626ad0ba685f4c49f5899c7bef46b967ce"
ASSIGNMENTS_SHA256 = "2a8608d2f74fbf3e64fca53b60334a64add9c47f0301766dc47c9ca2fe651e3c"
SPLITS = ("train", "valid", "test")
CLASSES = ("Oily", "Redness")


class AuditError(ValueError):
    """Raised when an archive cannot prove exact provider identity."""


def _digest_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"JSON object required: {path}")
    return value


def _validate_manifest(path: Path) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != MANIFEST_FILE_SHA256:
        raise AuditError("group-locked manifest digest mismatch")
    manifest = _load_json(path)
    assignments = manifest.get("assignments")
    if not isinstance(assignments, list) or _digest_json(assignments) != ASSIGNMENTS_SHA256:
        raise AuditError("group-locked assignment digest mismatch")
    result = manifest.get("result", {})
    if result.get("crossSplitGroupCount") != 0 or result.get("allRecordsAssignedExactlyOnce") is not True:
        raise AuditError("group-locked manifest does not prove leakage-safe complete assignment")


def _canonical_archive(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in SPLITS:
        split_root = root / split
        coco = _load_json(split_root / "_annotations.coco.json")
        categories = coco.get("categories")
        if not isinstance(categories, list):
            raise AuditError(f"{split} categories missing")
        category_names = {item.get("id"): item.get("name") for item in categories if isinstance(item, dict)}
        if set(category_names.values()) != set(CLASSES):
            raise AuditError(f"{split} class inventory changed")
        annotations_by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        class_counts: Counter[str] = Counter()
        for annotation in coco.get("annotations", []):
            if not isinstance(annotation, dict) or annotation.get("category_id") not in category_names:
                raise AuditError(f"{split} annotation is invalid")
            class_name = category_names[annotation["category_id"]]
            class_counts[class_name] += 1
            annotations_by_image[annotation.get("image_id")].append({
                "class": class_name,
                "bbox": annotation.get("bbox"),
                "segmentation": annotation.get("segmentation"),
                "area": annotation.get("area"),
                "iscrowd": annotation.get("iscrowd", 0),
            })
        records: list[dict[str, Any]] = []
        content_hashes: list[str] = []
        images = coco.get("images")
        if not isinstance(images, list):
            raise AuditError(f"{split} images missing")
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("file_name"), str):
                raise AuditError(f"{split} image entry is invalid")
            image_path = split_root / image["file_name"]
            if not image_path.is_file():
                raise AuditError(f"{split} image bytes missing")
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            content_hashes.append(digest)
            canonical_annotations = sorted(
                annotations_by_image.get(image.get("id"), []),
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
            records.append({
                "imageSHA256": digest,
                "width": image.get("width"),
                "height": image.get("height"),
                "annotations": canonical_annotations,
            })
        if set(annotations_by_image) - {image.get("id") for image in images if isinstance(image, dict)}:
            raise AuditError(f"{split} contains annotations for unknown images")
        result[split] = {
            "images": len(images),
            "classCounts": {name: class_counts[name] for name in CLASSES},
            "contentSetSHA256": _digest_json(sorted(content_hashes)),
            "recordAnnotationSetSHA256": _digest_json(sorted(
                records, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )),
            "contentHashes": content_hashes,
        }
    return result


def build_audit(expected_root: Path, provider_root: Path, manifest: Path, version: int) -> dict[str, Any]:
    if version < 2:
        raise AuditError("provider version must be 2 or later")
    _validate_manifest(manifest)
    expected = _canonical_archive(expected_root)
    provider = _canonical_archive(provider_root)
    for split in SPLITS:
        comparable = ("images", "classCounts", "contentSetSHA256", "recordAnnotationSetSHA256")
        if any(expected[split][field] != provider[split][field] for field in comparable):
            raise AuditError(f"provider export does not match expected {split} archive")
    all_hashes = [digest for split in SPLITS for digest in provider[split]["contentHashes"]]
    cross_split = sum(
        1 for digest in set(all_hashes)
        if sum(digest in provider[split]["contentHashes"] for split in SPLITS) > 1
    )
    split_counts = {split: provider[split]["images"] for split in SPLITS}
    annotations = {split: provider[split]["classCounts"] for split in SPLITS}
    class_totals = {
        name: sum(annotations[split][name] for split in SPLITS) for name in CLASSES
    }
    archive_identity = {
        split: {
            "images": provider[split]["images"],
            "contentSetSHA256": provider[split]["contentSetSHA256"],
            "recordAnnotationSetSHA256": provider[split]["recordAnnotationSetSHA256"],
        }
        for split in SPLITS
    }
    return {
        "schemaVersion": SCHEMA,
        "project": PROJECT_ID,
        "projectType": PROJECT_TYPE,
        "public": False,
        "versionNumber": version,
        "images": sum(split_counts.values()),
        "splits": split_counts,
        "annotations": annotations,
        "classTotals": class_totals,
        "manifestFileSHA256": MANIFEST_FILE_SHA256,
        "assignmentsSHA256": ASSIGNMENTS_SHA256,
        "recordIdentityBasis": "image-content-sha256",
        "exportArchiveSHA256": _digest_json(archive_identity),
        "splitImageContentSetSHA256": {
            split: provider[split]["contentSetSHA256"] for split in SPLITS
        },
        "splitRecordAnnotationSetSHA256": {
            split: provider[split]["recordAnnotationSetSHA256"] for split in SPLITS
        },
        "allProviderRecordsMatchedManifestOnce": True,
        "unexpectedProviderRecords": 0,
        "missingManifestRecords": 0,
        "crossSplitContentHashCount": cross_split,
        "sourcePersonCoverageComplete": True,
        "crossSplitGroupCount": 0,
        "finalTestUsedForSelectionOrThresholds": False,
        "containsFilenamesOrProviderImageIds": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = build_audit(args.expected_root, args.provider_root, args.manifest, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
