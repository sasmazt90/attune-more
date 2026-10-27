#!/usr/bin/env python3
"""Build and validate a privacy-safe under-eye expert review package.

Only train/valid COCO payloads are read. The locked test annotation payload and
test image bytes are never read. Source annotations merely select candidates:
they are not promoted to expert truth, and an absent target annotation is not
interpreted as a negative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


CLASSES = ("darkcircle", "eyebag")
REVIEW_SPLITS = ("train", "valid")
EXPECTED_ARCHIVE_SHA256 = "8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"
EXPECTED = {
    "splits": {"train": 284, "valid": 77, "test": 38},
    "reviewClassCounts": {
        "train": {"darkcircle": 271, "eyebag": 361},
        "valid": {"darkcircle": 70, "eyebag": 79},
    },
}
TARGETS = {
    (name, split, kind): count
    for name in CLASSES
    for split, positive, negative in (("train", 24, 8), ("valid", 8, 4))
    for kind, count in (("source_positive", positive), ("candidate_hard_negative", negative))
}
PENDING = "pending_expert_review"


class ReviewError(ValueError):
    """Raised when the frozen archive or expert decision contract is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _private_id(salt: str, *parts: str) -> str:
    return hashlib.sha256((salt + "\0" + "\0".join(parts)).encode()).hexdigest()[:24]


def _safe_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
        raise ReviewError("unsafe ZIP member")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ReviewError("symbolic links are not allowed")


def _polygon_area(values: list[Any], width: int, height: int) -> tuple[float, int, int]:
    if len(values) < 6 or len(values) % 2 or not all(isinstance(v, (int, float)) for v in values):
        raise ReviewError("invalid polygon geometry")
    points = [(float(values[i]), float(values[i + 1])) for i in range(0, len(values), 2)]
    if not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
        raise ReviewError("non-finite polygon coordinate")
    outside = sum(x < 0 or x > width or y < 0 or y > height for x, y in points)
    area = abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )) / 2
    return area, len(points), outside


def _load_review_records(
    archive: zipfile.ZipFile,
    expected: dict[str, Any],
    salt: str,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    resolver: dict[str, str] = {}
    audit: dict[str, Any] = {}
    names = {info.filename: info for info in archive.infolist() if not info.is_dir()}
    for info in names.values():
        _safe_member(info)
    for split in REVIEW_SPLITS:
        member = f"{split}/_annotations.coco.json"
        if member not in names:
            raise ReviewError("review split COCO payload is missing")
        payload = json.loads(archive.read(member))
        images, annotations, categories = (
            payload.get("images"), payload.get("annotations"), payload.get("categories")
        )
        if not all(isinstance(value, list) for value in (images, annotations, categories)):
            raise ReviewError("COCO arrays are missing")
        if len(images) != expected["splits"][split]:
            raise ReviewError("review split image count changed")
        category_names = {
            row.get("id"): row.get("name") for row in categories if isinstance(row, dict)
        }
        if not set(CLASSES).issubset(set(category_names.values())):
            raise ReviewError("under-eye class inventory changed")
        by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        class_counts: Counter[str] = Counter()
        geometry = {
            name: {"polygons": 0, "vertices": 0, "outsidePoints": 0, "degeneratePolygons": 0}
            for name in CLASSES
        }
        for annotation in annotations:
            if not isinstance(annotation, dict):
                raise ReviewError("annotation row is invalid")
            name = category_names.get(annotation.get("category_id"))
            if name not in CLASSES:
                raise ReviewError("annotation class is invalid")
            segmentation = annotation.get("segmentation")
            if not isinstance(segmentation, list) or not segmentation:
                raise ReviewError("polygon segmentation is required")
            polygon_area = 0.0
            vertices = 0
            outside = 0
            degenerate = 0
            for polygon in segmentation:
                if not isinstance(polygon, list):
                    raise ReviewError("polygon segmentation is invalid")
                image = next((row for row in images if row.get("id") == annotation.get("image_id")), None)
                if not isinstance(image, dict):
                    raise ReviewError("annotation references an unknown image")
                area, count, out = _polygon_area(polygon, int(image["width"]), int(image["height"]))
                polygon_area += area
                vertices += count
                outside += out
                degenerate += int(area <= 0)
            row = dict(annotation)
            row["_class"] = name
            row["_polygonArea"] = polygon_area
            row["_vertices"] = vertices
            by_image[annotation.get("image_id")].append(row)
            class_counts[name] += 1
            geometry[name]["polygons"] += len(segmentation)
            geometry[name]["vertices"] += vertices
            geometry[name]["outsidePoints"] += outside
            geometry[name]["degeneratePolygons"] += degenerate
        if dict(class_counts) != expected["reviewClassCounts"][split]:
            raise ReviewError("review split class counts changed")
        if any(
            values["outsidePoints"] or values["degeneratePolygons"]
            for values in geometry.values()
        ):
            raise ReviewError("invalid source polygon geometry")
        audit[split] = {
            "images": len(images),
            "annotations": len(annotations),
            "classCounts": dict(class_counts),
            "geometry": geometry,
        }
        seen_ids: set[Any] = set()
        for image in images:
            if not isinstance(image, dict) or image.get("id") in seen_ids:
                raise ReviewError("image row is invalid or duplicated")
            seen_ids.add(image.get("id"))
            filename = image.get("file_name")
            width, height = image.get("width"), image.get("height")
            if (
                not isinstance(filename, str)
                or PurePosixPath(filename).name != filename
                or not isinstance(width, int) or width <= 0
                or not isinstance(height, int) or height <= 0
                or f"{split}/{filename}" not in names
            ):
                raise ReviewError("image metadata or bytes are missing")
            image_member = f"{split}/{filename}"
            image_sha = hashlib.sha256(archive.read(image_member)).hexdigest()
            record_id = _private_id(salt, "under-eye-record", image_sha)
            if record_id in resolver:
                raise ReviewError("duplicate review image bytes or identifier collision")
            resolver[record_id] = f"{split}/{filename}"
            class_rows: dict[str, list[dict[str, Any]]] = {
                name: [row for row in by_image.get(image.get("id"), []) if row["_class"] == name]
                for name in CLASSES
            }
            records.append({
                "recordId": record_id,
                "split": split,
                "presentClasses": sorted(name for name, rows in class_rows.items() if rows),
                "classRows": class_rows,
                "imageArea": width * height,
            })
    test_images = [
        name for name in names
        if name.startswith("test/") and name != "test/_annotations.coco.json"
    ]
    if len(test_images) != expected["splits"]["test"]:
        raise ReviewError("locked test member count changed")
    return records, resolver, audit


def _summary(record: dict[str, Any], target: str) -> tuple[float, int, int]:
    rows = record["classRows"][target]
    return (
        sum(row["_polygonArea"] for row in rows) / record["imageArea"],
        len(rows),
        sum(row["_vertices"] for row in rows),
    )


def _select(rows: list[dict[str, Any]], target: str, count: int) -> list[tuple[dict[str, Any], list[str]]]:
    if len(rows) < count:
        raise ReviewError("not enough review candidates")
    orders = (
        ("small_mask_support", lambda row: (_summary(row, target)[0], row["recordId"])),
        ("broad_mask_support", lambda row: (-_summary(row, target)[0], row["recordId"])),
        ("few_instances", lambda row: (_summary(row, target)[1], row["recordId"])),
        ("many_instances", lambda row: (-_summary(row, target)[1], row["recordId"])),
        ("complex_boundaries", lambda row: (-_summary(row, target)[2], row["recordId"])),
    )
    selected: dict[str, tuple[dict[str, Any], list[str]]] = {}
    depth = 0
    ordered = [(reason, sorted(rows, key=key)) for reason, key in orders]
    while len(selected) < count:
        for reason, values in ordered:
            if depth >= len(values):
                continue
            row = values[depth]
            current = selected.setdefault(row["recordId"], (row, []))
            if reason not in current[1]:
                current[1].append(reason)
            if len(selected) == count:
                break
        depth += 1
    return [selected[key] for key in sorted(selected)]


def build_queue(
    archive_path: Path,
    salt: str,
    *,
    expected: dict[str, Any] | None = None,
    expected_archive_sha256: str = EXPECTED_ARCHIVE_SHA256,
) -> tuple[dict[str, Any], dict[str, str]]:
    expected = expected or EXPECTED
    if len(salt) < 16:
        raise ReviewError("privacy salt must contain at least 16 characters")
    archive_sha = _sha256(archive_path)
    if archive_sha != expected_archive_sha256:
        raise ReviewError("archive SHA256 does not match the frozen grouped candidate")
    with zipfile.ZipFile(archive_path) as archive:
        records, resolver, geometry_audit = _load_review_records(archive, expected, salt)
    items: list[dict[str, Any]] = []
    selected_records: set[str] = set()
    for target in CLASSES:
        other = next(name for name in CLASSES if name != target)
        for split in REVIEW_SPLITS:
            positives = [
                row for row in records if row["split"] == split and target in row["presentClasses"]
            ]
            negatives = [
                row for row in records
                if row["split"] == split and target not in row["presentClasses"] and other in row["presentClasses"]
            ]
            for kind, candidates, geometry_target in (
                ("source_positive", positives, target),
                ("candidate_hard_negative", negatives, other),
            ):
                count = TARGETS[(target, split, kind)]
                for row, focus in _select(candidates, geometry_target, count):
                    area, instances, vertices = _summary(row, geometry_target)
                    review_id = _private_id(salt, "under-eye-item", target, kind, row["recordId"])
                    items.append({
                        "reviewItemId": review_id,
                        "recordId": row["recordId"],
                        "split": split,
                        "targetClass": target,
                        "selectionKind": kind,
                        "sourceClassesPresent": row["presentClasses"],
                        "selectionGeometryClass": geometry_target,
                        "selectionAreaFraction": round(area, 8),
                        "selectionInstances": instances,
                        "selectionVertices": vertices,
                        "reviewFocus": focus,
                        "sourceAnnotationIsExpertTruth": False,
                        "missingTargetAnnotationIsNegative": False,
                    })
                    selected_records.add(row["recordId"])
    items.sort(key=lambda row: (row["targetClass"], row["split"], row["selectionKind"], row["reviewItemId"]))
    selected_resolver = {
        item["reviewItemId"]: resolver[item["recordId"]]
        for item in items
    }
    queue = {
        "schemaVersion": "under-eye-expert-review-queue-v1",
        "dataset": {
            "candidateArchiveSHA256": archive_sha,
            "candidateArchiveAuthorizedForUpload": False,
            "project": "tolgar-sasmaz/attune-skin-under-eye-grouped-research",
            "reviewSplits": list(REVIEW_SPLITS),
            "reviewPoolImages": sum(expected["splits"][split] for split in REVIEW_SPLITS),
            "lockedTestImages": expected["splits"]["test"],
            "testAnnotationPayloadRead": False,
            "testImageBytesRead": False,
            "reviewImageBytesReadForPrivateIdentifiers": True,
            "testSelectedForReview": 0,
            "personIndependent": False,
        },
        "classes": list(CLASSES),
        "selectionTargets": {
            f"{name}:{split}:{kind}": count
            for (name, split, kind), count in TARGETS.items()
        },
        "selection": {
            "items": len(items),
            "uniqueImages": len(selected_records),
            "candidateGeometryOnly": True,
        },
        "reviewGeometryAudit": geometry_audit,
        "reviewPolicy": {
            "expertReviewerRequired": True,
            "darkCircleAndEyeBagIndependent": True,
            "missingTargetAnnotationIsNegative": False,
            "sourceAnnotationIsExpertTruth": False,
            "modelPredictionAcceptedAsTruth": False,
            "boxAcceptedAsPolygon": False,
            "ambiguousOrUnassessableBecomesNormal": False,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "privateResolverCommitted": False,
            "identifierMethod": "salted-sha256-prefix-24",
        },
        "items": items,
        "decision": {
            "expertReviewComplete": False,
            "classPoliciesLocked": False,
            "personIndependentSplitReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }
    return queue, selected_resolver


def build_template(queue: dict[str, Any]) -> dict[str, Any]:
    items = queue.get("items")
    if queue.get("schemaVersion") != "under-eye-expert-review-queue-v1" or not isinstance(items, list):
        raise ReviewError("review queue is invalid")
    return {
        "schemaVersion": "under-eye-expert-review-decisions-v1",
        "reviewQueueCanonicalSHA256": _canonical_sha(queue),
        "reviewerRole": PENDING,
        "classPolicies": [{
            "name": name,
            "positiveDefinitionLocked": False,
            "maskExtentPolicyLocked": False,
            "hardNegativePolicyLocked": False,
            "ambiguousCasePolicyLocked": False,
        } for name in CLASSES],
        "items": [{
            "reviewItemId": row["reviewItemId"],
            "targetClass": row["targetClass"],
            "split": row["split"],
            "selectionKind": row["selectionKind"],
            "expertReviewed": False,
            "assessability": PENDING,
            "targetPresence": PENDING,
            "maskExtentDecision": PENDING,
            "semanticDecision": PENDING,
        } for row in items],
        "decision": {
            "expertReviewComplete": False,
            "semanticProtocolReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }


def build_protocol(queue: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    if decisions.get("schemaVersion") != "under-eye-expert-review-decisions-v1":
        raise ReviewError("expert decision schema is invalid")
    if decisions.get("reviewQueueCanonicalSHA256") != _canonical_sha(queue):
        raise ReviewError("expert decisions are not bound to the queue")
    if decisions.get("reviewerRole") != "expert_review":
        raise ReviewError("expert reviewer confirmation is missing")
    policies = decisions.get("classPolicies")
    if not isinstance(policies, list) or len(policies) != len(CLASSES):
        raise ReviewError("class policies are incomplete")
    seen_policies: set[str] = set()
    for row in policies:
        if not isinstance(row, dict) or row.get("name") not in CLASSES or row["name"] in seen_policies:
            raise ReviewError("class policy is invalid")
        if not all(row.get(key) is True for key in (
            "positiveDefinitionLocked", "maskExtentPolicyLocked",
            "hardNegativePolicyLocked", "ambiguousCasePolicyLocked",
        )):
            raise ReviewError("class policy is not expert locked")
        seen_policies.add(row["name"])
    queue_rows = {row["reviewItemId"]: row for row in queue.get("items", [])}
    rows = decisions.get("items")
    if not isinstance(rows, list) or len(rows) != len(queue_rows):
        raise ReviewError("expert decision inventory is incomplete")
    seen: set[str] = set()
    reviewed: dict[str, list[str]] = {name: [] for name in CLASSES}
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewError("expert decision item is invalid")
        item_id = row.get("reviewItemId")
        source = queue_rows.get(item_id)
        if source is None or item_id in seen:
            raise ReviewError("expert decision item is unknown or duplicated")
        if any(row.get(key) != source.get(key) for key in ("targetClass", "split", "selectionKind")):
            raise ReviewError("expert decision item binding changed")
        if row.get("expertReviewed") is not True:
            raise ReviewError("every item requires explicit expert review")
        assessability = row.get("assessability")
        presence = row.get("targetPresence")
        extent = row.get("maskExtentDecision")
        semantic = row.get("semanticDecision")
        if assessability not in {"assessable", "ambiguous", "unassessable"}:
            raise ReviewError("assessability is pending or invalid")
        if presence not in {"present", "absent", "ambiguous", "unassessable"}:
            raise ReviewError("target presence is pending or invalid")
        if extent not in {"correct", "too_broad", "too_narrow", "fragmented", "not_applicable"}:
            raise ReviewError("mask extent is pending or invalid")
        if semantic not in {"keep", "correct_before_training", "exclude"}:
            raise ReviewError("semantic decision is pending or invalid")
        if assessability != "assessable" or presence in {"ambiguous", "unassessable"}:
            if extent != "not_applicable" or semantic != "exclude":
                raise ReviewError("ambiguous or unassessable items must be excluded")
        elif presence == "absent":
            if extent != "not_applicable":
                raise ReviewError("absent target cannot have a mask extent")
            if source["selectionKind"] == "source_positive" and semantic == "keep":
                raise ReviewError("expert-rejected source positive cannot be kept")
        else:
            if extent == "not_applicable":
                raise ReviewError("present target requires a mask extent decision")
            if extent != "correct" and semantic == "keep":
                raise ReviewError("incorrect mask cannot be kept")
            if source["selectionKind"] == "candidate_hard_negative" and semantic == "keep":
                raise ReviewError("false-negative annotation cannot be kept")
        reviewed[source["targetClass"]].append(item_id)
        seen.add(item_id)
    if seen != set(queue_rows):
        raise ReviewError("expert decisions do not cover the queue exactly")
    return {
        "schemaVersion": "under-eye-expert-semantic-protocol-v1",
        "candidateArchiveSHA256": queue["dataset"]["candidateArchiveSHA256"],
        "reviewQueueCanonicalSHA256": _canonical_sha(queue),
        "reviewerRole": "expert_review",
        "classes": [{
            "name": name,
            "expertReviewed": True,
            "positiveDefinitionLocked": True,
            "maskExtentPolicyLocked": True,
            "hardNegativePolicyLocked": True,
            "ambiguousCasePolicyLocked": True,
            "reviewedItemIds": sorted(reviewed[name]),
        } for name in CLASSES],
        "semanticInvariants": queue["reviewPolicy"],
        "decision": {
            "expertReviewComplete": True,
            "semanticProtocolReady": True,
            "personIndependentSplitReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    queue_parser = subparsers.add_parser("queue")
    queue_parser.add_argument("--archive", type=Path, required=True)
    queue_parser.add_argument("--salt", required=True)
    queue_parser.add_argument("--output", type=Path, required=True)
    queue_parser.add_argument("--private-resolver", type=Path)
    template_parser = subparsers.add_parser("template")
    template_parser.add_argument("--queue", type=Path, required=True)
    template_parser.add_argument("--output", type=Path, required=True)
    protocol_parser = subparsers.add_parser("protocol")
    protocol_parser.add_argument("--queue", type=Path, required=True)
    protocol_parser.add_argument("--decisions", type=Path, required=True)
    protocol_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "queue":
        result, resolver = build_queue(args.archive, args.salt)
        if args.private_resolver:
            args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    else:
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
        result = build_template(queue) if args.command == "template" else build_protocol(
            queue, json.loads(args.decisions.read_text(encoding="utf-8"))
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
