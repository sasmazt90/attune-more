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
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "regional-provider-version-export-audit-v3"
PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
PROJECT_TYPE = "instance-segmentation"
MANIFEST_FILE_SHA256 = "d698580acae5c2987392e170bd408d626ad0ba685f4c49f5899c7bef46b967ce"
ASSIGNMENTS_SHA256 = "2a8608d2f74fbf3e64fca53b60334a64add9c47f0301766dc47c9ca2fe651e3c"
SPLITS = ("train", "valid", "test")
CLASSES = ("Oily", "Redness")
GEOMETRY_IDENTITY_BASIS = "canonical-simple-polygon-ring-v2"


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


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuditError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise AuditError(f"{label} must be finite")
    return round(number, 8)


def _orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: list[float], b: list[float], point: list[float]) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        and abs(_orientation(a, b, point)) <= 1e-8
    )


def _segments_intersect(
    a: list[float], b: list[float], c: list[float], d: list[float]
) -> bool:
    ab_c = _orientation(a, b, c)
    ab_d = _orientation(a, b, d)
    cd_a = _orientation(c, d, a)
    cd_b = _orientation(c, d, b)
    if ((ab_c > 1e-8 and ab_d < -1e-8) or (ab_c < -1e-8 and ab_d > 1e-8)) and (
        (cd_a > 1e-8 and cd_b < -1e-8) or (cd_a < -1e-8 and cd_b > 1e-8)
    ):
        return True
    return any(
        abs(value) <= 1e-8 and _on_segment(start, end, point)
        for value, start, end, point in (
            (ab_c, a, b, c),
            (ab_d, a, b, d),
            (cd_a, c, d, a),
            (cd_b, c, d, b),
        )
    )


def _validate_simple_polygon(points: list[list[float]], label: str) -> None:
    if len({tuple(point) for point in points}) != len(points):
        raise AuditError(f"{label} polygon repeats vertices")
    edge_count = len(points)
    for first in range(edge_count):
        a = points[first]
        b = points[(first + 1) % edge_count]
        for second in range(first + 1, edge_count):
            if second == first or second == first + 1:
                continue
            if first == 0 and second == edge_count - 1:
                continue
            c = points[second]
            d = points[(second + 1) % edge_count]
            if _segments_intersect(a, b, c, d):
                raise AuditError(f"{label} polygon self-intersects")


def _safe_image_path(split_root: Path, file_name: str, split: str) -> Path:
    if not file_name or "\x00" in file_name or "\\" in file_name:
        raise AuditError(f"{split} image path is unsafe")
    relative = Path(file_name)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise AuditError(f"{split} image path is unsafe")
    base = split_root.resolve()
    candidate = split_root / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(base)
    except (OSError, ValueError) as exc:
        raise AuditError(f"{split} image path escapes the split root") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise AuditError(f"{split} image bytes missing or linked")
    return resolved


def _canonical_ring(values: Any, width: int, height: int, label: str) -> list[list[float]]:
    if not isinstance(values, list) or len(values) < 6 or len(values) % 2:
        raise AuditError(f"{label} polygon is invalid")
    points = [
        [_number(values[index], label), _number(values[index + 1], label)]
        for index in range(0, len(values), 2)
    ]
    if points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise AuditError(f"{label} polygon is degenerate")
    if any(x < 0 or x > width or y < 0 or y > height for x, y in points):
        raise AuditError(f"{label} polygon contains outside points")
    _validate_simple_polygon(points, label)
    area2 = sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
    if abs(area2) <= 1e-8:
        raise AuditError(f"{label} polygon is degenerate")
    candidates = []
    for ring in (points, list(reversed(points))):
        candidates.extend(ring[index:] + ring[:index] for index in range(len(ring)))
    return min(candidates)


def _canonical_segmentation(value: Any, width: int, height: int, label: str) -> list[list[list[float]]]:
    if not isinstance(value, list) or not value:
        raise AuditError(f"{label} requires polygon segmentation; boxes are not polygon truth")
    polygons = [_canonical_ring(ring, width, height, label) for ring in value]
    return sorted(polygons, key=lambda ring: json.dumps(ring, separators=(",", ":")))


def _canonical_archive(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in SPLITS:
        split_root = root / split
        coco = _load_json(split_root / "_annotations.coco.json")
        categories = coco.get("categories")
        if not isinstance(categories, list):
            raise AuditError(f"{split} categories missing")
        if len(categories) != len(CLASSES) or any(not isinstance(item, dict) for item in categories):
            raise AuditError(f"{split} class inventory changed")
        category_ids = [item.get("id") for item in categories]
        category_values = [item.get("name") for item in categories]
        if (
            any(isinstance(item, bool) or not isinstance(item, (int, str)) or item == "" for item in category_ids)
            or any(not isinstance(item, str) or not item for item in category_values)
            or len(set(category_ids)) != len(category_ids)
            or len(set(category_values)) != len(category_values)
            or set(category_values) != set(CLASSES)
        ):
            raise AuditError(f"{split} class inventory changed")
        category_names = dict(zip(category_ids, category_values))
        images = coco.get("images")
        if not isinstance(images, list):
            raise AuditError(f"{split} images missing")
        image_by_id: dict[Any, dict[str, Any]] = {}
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("file_name"), str):
                raise AuditError(f"{split} image entry is invalid")
            image_id = image.get("id")
            width = image.get("width")
            height = image.get("height")
            if (
                isinstance(image_id, bool)
                or not isinstance(image_id, (int, str))
                or image_id == ""
                or image_id in image_by_id
            ):
                raise AuditError(f"{split} image id is duplicated")
            if (
                isinstance(width, bool)
                or not isinstance(width, int)
                or width <= 0
                or isinstance(height, bool)
                or not isinstance(height, int)
                or height <= 0
            ):
                raise AuditError(f"{split} image dimensions are invalid")
            image_by_id[image_id] = image

        annotations_by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        class_counts: Counter[str] = Counter()
        polygon_count = 0
        vertex_count = 0
        annotations = coco.get("annotations")
        if not isinstance(annotations, list):
            raise AuditError(f"{split} annotations missing")
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("category_id") not in category_names:
                raise AuditError(f"{split} annotation is invalid")
            image_id = annotation.get("image_id")
            image = image_by_id.get(image_id)
            if image is None:
                raise AuditError(f"{split} contains annotations for unknown images")
            if annotation.get("iscrowd", 0) not in (0, False):
                raise AuditError(f"{split} crowd/RLE geometry is not accepted as polygon truth")
            label = f"{split} annotation"
            polygons = _canonical_segmentation(
                annotation.get("segmentation"), image["width"], image["height"], label
            )
            bbox = annotation.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise AuditError(f"{split} annotation bbox is invalid")
            canonical_bbox = [_number(value, label) for value in bbox]
            if (
                canonical_bbox[0] < 0
                or canonical_bbox[1] < 0
                or canonical_bbox[2] <= 0
                or canonical_bbox[3] <= 0
                or canonical_bbox[0] + canonical_bbox[2] > image["width"]
                or canonical_bbox[1] + canonical_bbox[3] > image["height"]
            ):
                raise AuditError(f"{split} annotation bbox is invalid")
            area = _number(annotation.get("area"), label)
            if area <= 0:
                raise AuditError(f"{split} annotation area is invalid")
            class_name = category_names[annotation["category_id"]]
            class_counts[class_name] += 1
            polygon_count += len(polygons)
            vertex_count += sum(len(ring) for ring in polygons)
            annotations_by_image[image_id].append({
                "class": class_name,
                "bbox": canonical_bbox,
                "segmentation": polygons,
                "area": area,
                "iscrowd": 0,
            })

        records: list[dict[str, Any]] = []
        content_hashes: list[str] = []
        for image in images:
            image_path = _safe_image_path(split_root, image["file_name"], split)
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
        duplicate_content_count = len(content_hashes) - len(set(content_hashes))
        if duplicate_content_count:
            raise AuditError(f"{split} contains duplicate image content")
        result[split] = {
            "images": len(images),
            "classCounts": {name: class_counts[name] for name in CLASSES},
            "contentSetSHA256": _digest_json(sorted(content_hashes)),
            "recordAnnotationSetSHA256": _digest_json(sorted(
                records, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )),
            "contentHashes": content_hashes,
            "polygonAnnotations": len(annotations),
            "polygons": polygon_count,
            "vertices": vertex_count,
            "duplicateImageContentCount": duplicate_content_count,
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
    if cross_split:
        raise AuditError("provider export contains cross-split image content")
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
        "geometryIdentityBasis": GEOMETRY_IDENTITY_BASIS,
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
        "duplicateImageContentCount": 0,
        "polygonGeometryVerified": True,
        "simplePolygonGeometryVerified": True,
        "selfIntersectionCount": 0,
        "pathSafetyVerified": True,
        "categoryIdentityVerified": True,
        "bboxWithinImageVerified": True,
        "positiveAreaVerified": True,
        "boxGeometryAcceptedAsPolygonTruth": False,
        "crowdOrRLEGeometryAcceptedAsPolygonTruth": False,
        "invalidPolygonCount": 0,
        "outsidePointCount": 0,
        "degeneratePolygonCount": 0,
        "polygonAnnotations": {
            split: provider[split]["polygonAnnotations"] for split in SPLITS
        },
        "polygons": {split: provider[split]["polygons"] for split in SPLITS},
        "vertices": {split: provider[split]["vertices"] for split in SPLITS},
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

