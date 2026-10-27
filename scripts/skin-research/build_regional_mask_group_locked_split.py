#!/usr/bin/env python3
"""Build a privacy-safe, source/person-group-locked regional COCO split.

The public manifest contains only pseudonymous review IDs and opaque group IDs.
Private filenames and image bytes are used only when ``--materialize-root`` is
requested with the uncommitted resolver produced by the coverage-review tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


TARGETS = {"train": 236, "valid": 50, "final_test": 51}
CLASSES = ("Oily", "Redness")


class SplitError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SplitError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SplitError(f"JSON root must be an object: {path}")
    return value


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def _validate(queue: dict[str, Any], decisions: dict[str, Any]) -> None:
    if queue.get("schemaVersion") != "regional-mask-source-person-review-queue-v1":
        raise SplitError("queue schema is invalid")
    if decisions.get("schemaVersion") != "regional-mask-source-person-review-decisions-v1":
        raise SplitError("decision schema is invalid")
    items = queue.get("items")
    rows = decisions.get("items")
    if not isinstance(items, list) or not isinstance(rows, list) or len(items) != 337:
        raise SplitError("exactly 337 queue and decision records are required")
    binding = queue.get("coverage", {}).get("queueItemsSHA256")
    if binding != _digest(items) or decisions.get("queueItemsSHA256") != binding:
        raise SplitError("decisions are not bound to the exact queue")
    by_id = {row.get("reviewItemId"): row for row in rows if isinstance(row, dict)}
    if len(by_id) != 337:
        raise SplitError("decision IDs must be unique and complete")
    for item in items:
        row = by_id.get(item.get("reviewItemId"))
        if not row or row.get("decision") != "reviewed_group":
            raise SplitError("all records require completed source/person review")
        group_id = row.get("sourcePersonGroupId")
        if not isinstance(group_id, str) or not group_id.startswith("sg-"):
            raise SplitError("all completed records require an opaque group ID")
    if decisions.get("attestations", {}).get("allRecordsVisuallyOrProvenanceReviewed") is not True:
        raise SplitError("full review attestation is required")


def build_manifest(queue: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    _validate(queue, decisions)
    decision_for = {row["reviewItemId"]: row for row in decisions["items"]}
    item_for = {row["reviewItemId"]: row for row in queue["items"]}
    groups: dict[str, list[str]] = defaultdict(list)
    for review_id, row in decision_for.items():
        groups[row["sourcePersonGroupId"]].append(review_id)

    group_stats: dict[str, dict[str, Any]] = {}
    total_annotations = {name: 0 for name in CLASSES}
    for group_id, review_ids in groups.items():
        annotations = {
            name: sum(item_for[review_id]["sourceAnnotationCounts"][name] for review_id in review_ids)
            for name in CLASSES
        }
        group_stats[group_id] = {
            "records": len(review_ids),
            "annotations": annotations,
        }
        for name in CLASSES:
            total_annotations[name] += annotations[name]

    counts = {split: 0 for split in TARGETS}
    class_counts = {split: {name: 0 for name in CLASSES} for split in TARGETS}
    group_split: dict[str, str] = {}
    ordered_groups = sorted(
        groups,
        key=lambda group_id: hashlib.sha256(
            ("regional-group-locked-split-v1\0" + group_id).encode()
        ).hexdigest(),
    )
    for group_id in ordered_groups:
        stats = group_stats[group_id]
        candidates = []
        for split, target in TARGETS.items():
            record_need = (target - counts[split]) / target
            class_need = sum(
                (
                    total_annotations[name] * target / 337
                    - class_counts[split][name]
                )
                / max(total_annotations[name] * target / 337, 1)
                for name in CLASSES
            ) / len(CLASSES)
            overshoot = max(0, counts[split] + stats["records"] - target)
            candidates.append((overshoot == 0, record_need + 0.25 * class_need, split))
        _, _, chosen = max(candidates)
        group_split[group_id] = chosen
        counts[chosen] += stats["records"]
        for name in CLASSES:
            class_counts[chosen][name] += stats["annotations"][name]

    # With predominantly singleton groups, the proportional greedy assignment
    # reaches the exact targets.  Fail closed instead of silently relaxing the
    # preregistered final-test size or moving one member of a reviewed group.
    if counts != TARGETS:
        raise SplitError(f"could not satisfy exact record targets without splitting groups: {counts}")
    if counts["final_test"] < 50:
        raise SplitError("new untouched final test must contain at least 50 records")
    if any(class_counts[split][name] == 0 for split in TARGETS for name in CLASSES):
        raise SplitError("each target split must retain both labeled classes")

    assignments = [
        {
            "reviewItemId": review_id,
            "sourcePersonGroupId": decision_for[review_id]["sourcePersonGroupId"],
            "targetSplit": group_split[decision_for[review_id]["sourcePersonGroupId"]],
        }
        for review_id in sorted(item_for)
    ]
    return {
        "schemaVersion": "regional-mask-group-locked-split-v1",
        "source": {
            "project": queue["source"]["project"],
            "sourceVersionNumber": queue["source"]["versionNumber"],
            "providerExportSHA256": queue["source"]["providerExportSHA256"],
            "queueItemsSHA256": queue["coverage"]["queueItemsSHA256"],
            "reviewDecisionsSHA256": _digest(decisions),
        },
        "policy": {
            "sourcePersonGroupsLocked": True,
            "targetRecords": TARGETS,
            "finalTestMinimumRecords": 50,
            "finalTestUsedForSelectionOrThresholds": False,
            "missingLabelTreatedAsNegativeOrNormal": False,
            "modelPredictionTreatedAsExpertTruth": False,
            "rednessRemainsIndependentLayer": True,
        },
        "result": {
            "records": counts,
            "annotationCounts": class_counts,
            "groups": {
                split: sum(value == split for value in group_split.values())
                for split in TARGETS
            },
            "crossSplitGroupCount": 0,
            "allRecordsAssignedExactlyOnce": len(assignments) == 337,
            "replacementSplitReadyForMaterialization": True,
            "trainingAuthorized": False,
            "finalTestAuthorized": False,
            "activationAllowed": False,
            "remainingBlockers": [
                "expert_semantic_mask_protocol_not_accepted",
                "provider_version_2_not_created",
                "independent_physical_camera_holdout_missing",
            ],
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenamesOrPaths": False,
            "containsRawIdentity": False,
            "identifiersArePseudonymousNotAnonymous": True,
        },
        "assignments": assignments,
    }


def materialize(
    manifest: dict[str, Any], resolver: dict[str, str], output_root: Path
) -> dict[str, Any]:
    assignment_for = {
        row["reviewItemId"]: row["targetSplit"] for row in manifest["assignments"]
    }
    if set(resolver) != set(assignment_for):
        raise SplitError("private resolver must cover the exact manifest")

    source_payloads: dict[Path, dict[str, Any]] = {}
    source_images: dict[Path, dict[str, Any]] = {}
    source_annotations: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    categories: list[dict[str, Any]] | None = None
    for raw_path in resolver.values():
        image_path = Path(raw_path)
        annotation_path = image_path.parent / "_annotations.coco.json"
        if annotation_path not in source_payloads:
            payload = _load(annotation_path)
            source_payloads[annotation_path] = payload
            if categories is None:
                categories = payload["categories"]
            elif payload["categories"] != categories:
                raise SplitError("source categories differ across splits")
            by_id = {row["id"]: row for row in payload["images"]}
            for row in payload["images"]:
                source_images[image_path.parent / Path(row["file_name"]).name] = row
            for row in payload["annotations"]:
                source_annotations[annotation_path].append(row)

    if output_root.exists() and any(output_root.iterdir()):
        raise SplitError("materialization output must be empty")
    output_root.mkdir(parents=True, exist_ok=True)
    rows_by_split: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for review_id, raw_path in resolver.items():
        rows_by_split[assignment_for[review_id]].append((review_id, Path(raw_path)))

    digests: dict[str, str] = {}
    folder_for = {"train": "train", "valid": "valid", "final_test": "test"}
    for split in TARGETS:
        folder = output_root / folder_for[split]
        folder.mkdir()
        images: list[dict[str, Any]] = []
        annotations: list[dict[str, Any]] = []
        next_annotation_id = 1
        for next_image_id, (_, source_path) in enumerate(sorted(rows_by_split[split]), 1):
            if source_path not in source_images or not source_path.is_file():
                raise SplitError(f"resolver image is missing: {source_path}")
            source_image = source_images[source_path]
            source_annotation_path = source_path.parent / "_annotations.coco.json"
            target_name = source_path.name
            shutil.copy2(source_path, folder / target_name)
            image = dict(source_image)
            old_image_id = image["id"]
            image["id"] = next_image_id
            image["file_name"] = target_name
            images.append(image)
            for source_annotation in source_annotations[source_annotation_path]:
                if source_annotation.get("image_id") != old_image_id:
                    continue
                annotation = dict(source_annotation)
                annotation["id"] = next_annotation_id
                annotation["image_id"] = next_image_id
                next_annotation_id += 1
                annotations.append(annotation)
        payload = {"images": images, "annotations": annotations, "categories": categories}
        annotation_path = folder / "_annotations.coco.json"
        annotation_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        digests[split] = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    return {"materializedAnnotationSHA256": digests}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--materialize-root", type=Path)
    parser.add_argument("--private-receipt", type=Path)
    args = parser.parse_args()
    manifest = build_manifest(_load(args.queue), _load(args.decisions))
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.materialize_root:
        if not args.private_resolver or not args.private_receipt:
            raise SplitError("materialization requires --private-resolver and --private-receipt")
        receipt = materialize(_load(args.manifest), _load(args.private_resolver), args.materialize_root)
        args.private_receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
