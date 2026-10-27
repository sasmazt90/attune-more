#!/usr/bin/env python3
"""Build and verify a privacy-safe regional source/person coverage review.

The frozen regional export has one opaque source token per image and no
cross-split perceptual candidates.  Neither fact establishes person identity.
This tool turns every record into an explicit review item and validates a
separate decision document without reading model predictions or converting
missing annotations into Normal/negative truth.

Only the public queue and blank decision template are suitable for Git.  The
optional resolver contains private file paths and must remain outside Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from audit_regional_skin_type_source_groups import AuditError, SHA256, SPLITS


EXPECTED_SPLITS = {"train": 244, "valid": 63, "test": 30}
EXPECTED_CLASSES = ("Oily", "Redness")
GROUP_ID = re.compile(r"sg-[a-f0-9]{24}")
REVIEW_METHODS = {
    "provider_subject_id",
    "source_provenance",
    "visual_same_person_review",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("invalid COCO annotations") from exc
    if not isinstance(value, dict):
        raise AuditError("COCO root must be an object")
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _review_id(export_sha256: str, split: str, file_name: str) -> str:
    # Pseudonymous and reproducible from the private export.  No raw provider
    # identifier or filename is written to the public queue.
    payload = f"regional-mask-source-person-review-v1\0{export_sha256}\0{split}\0{file_name}"
    return "ri-" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def build_review(
    root: Path,
    source_archive_sha256: str,
    provider_export_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    for value in (source_archive_sha256, provider_export_sha256):
        if not SHA256.fullmatch(value):
            raise AuditError("archive digests must be lowercase sha256 values")

    items: list[dict[str, Any]] = []
    resolver: dict[str, str] = {}
    split_counts: dict[str, int] = {}
    class_counts = {name: 0 for name in EXPECTED_CLASSES}

    for split in SPLITS:
        payload = _load(root / split / "_annotations.coco.json")
        images = payload.get("images")
        annotations = payload.get("annotations")
        categories = payload.get("categories")
        if not all(isinstance(value, list) for value in (images, annotations, categories)):
            raise AuditError("missing COCO arrays")
        names = {row.get("id"): row.get("name") for row in categories if isinstance(row, dict)}
        if not set(EXPECTED_CLASSES).issubset(set(names.values())):
            raise AuditError("regional export must contain Oily and Redness")
        by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in annotations:
            if not isinstance(annotation, dict) or names.get(annotation.get("category_id")) not in EXPECTED_CLASSES:
                raise AuditError("annotation class is invalid")
            by_image[annotation.get("image_id")].append(annotation)
            class_counts[names[annotation["category_id"]]] += 1

        split_counts[split] = len(images)
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("file_name"), str):
                raise AuditError("image metadata is invalid")
            file_name = image["file_name"]
            review_id = _review_id(provider_export_sha256, split, file_name)
            if review_id in resolver:
                raise AuditError("review identifier collision")
            resolver[review_id] = str(root / split / Path(file_name).name)
            rows = by_image.get(image.get("id"), [])
            present = sorted({names[row["category_id"]] for row in rows})
            items.append({
                "reviewItemId": review_id,
                "currentSplit": split,
                "sourceClassesPresent": present,
                "sourceAnnotationCounts": {
                    name: sum(names[row["category_id"]] == name for row in rows)
                    for name in EXPECTED_CLASSES
                },
                "sourceAnnotationsAreExpertIdentityEvidence": False,
                "missingClassIsNegativeOrNormal": False,
                "currentSplitIsAcceptedIdentityTruth": False,
                "reviewStatus": "unreviewed",
            })

    if split_counts != EXPECTED_SPLITS:
        raise AuditError("split counts do not match the frozen regional export")
    if class_counts != {"Oily": 1065, "Redness": 571}:
        raise AuditError("class counts do not match the frozen regional export")
    if len(items) != 337 or len(resolver) != 337:
        raise AuditError("all 337 records must be represented exactly once")

    items = sorted(items, key=lambda row: row["reviewItemId"])
    binding = _digest(items)
    queue = {
        "schemaVersion": "regional-mask-source-person-review-queue-v1",
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
            "identifierMethod": "context-bound-sha256-prefix-24",
            "identifiersArePseudonymousNotAnonymous": True,
        },
        "coverage": {
            "records": 337,
            "splits": split_counts,
            "allRecordsRepresented": True,
            "reviewedRecords": 0,
            "unreviewedRecords": 337,
            "queueItemsSHA256": binding,
        },
        "policy": {
            "reviewScope": "source/person grouping only",
            "reviewerMustUsePrivateResolver": True,
            "perceptualSimilarityMayAutoConfirmIdentity": False,
            "oneSourceTokenPerImageEstablishesPersonIndependence": False,
            "modelPredictionAcceptedAsIdentityOrExpertTruth": False,
            "missingAnnotationAcceptedAsNegativeOrNormal": False,
            "rednessRemainsIndependentLayer": True,
        },
        "items": items,
        "decision": {
            "personOrSourceCoverageComplete": False,
            "currentSplitIndependent": False,
            "replacementSplitReady": False,
            "trainingAuthorized": False,
            "finalTestAuthorized": False,
            "activationAllowed": False,
        },
    }
    template = {
        "schemaVersion": "regional-mask-source-person-review-decisions-v1",
        "queueItemsSHA256": binding,
        "reviewerRole": None,
        "items": [
            {
                "reviewItemId": row["reviewItemId"],
                "sourcePersonGroupId": None,
                "reviewMethod": None,
                "decision": "unreviewed",
            }
            for row in items
        ],
        "attestations": {
            "allRecordsVisuallyOrProvenanceReviewed": False,
            "groupIdsAreOpaque": False,
            "sourceAnnotationsNotUsedAsIdentityTruth": False,
            "missingLabelsNotUsedAsNegativeOrNormal": False,
        },
    }
    return queue, template, resolver


def evaluate_decisions(queue: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    if queue.get("schemaVersion") != "regional-mask-source-person-review-queue-v1":
        raise AuditError("queue schema is invalid")
    if decisions.get("schemaVersion") != "regional-mask-source-person-review-decisions-v1":
        raise AuditError("decision schema is invalid")
    items = queue.get("items")
    rows = decisions.get("items")
    if not isinstance(items, list) or not isinstance(rows, list):
        raise AuditError("review items are invalid")
    binding = queue.get("coverage", {}).get("queueItemsSHA256")
    if binding != _digest(items) or decisions.get("queueItemsSHA256") != binding:
        raise AuditError("decision document is not bound to the exact queue")
    queue_ids = [row.get("reviewItemId") for row in items if isinstance(row, dict)]
    decision_ids = [row.get("reviewItemId") for row in rows if isinstance(row, dict)]
    if len(queue_ids) != 337 or len(set(queue_ids)) != 337 or set(decision_ids) != set(queue_ids):
        raise AuditError("decisions must cover every exact queue item once")
    if len(decision_ids) != len(set(decision_ids)):
        raise AuditError("duplicate decision item")

    complete_rows = []
    group_splits: dict[str, set[str]] = defaultdict(set)
    split_for = {row["reviewItemId"]: row["currentSplit"] for row in items}
    for row in rows:
        if not isinstance(row, dict):
            raise AuditError("decision row is invalid")
        group_id = row.get("sourcePersonGroupId")
        complete = (
            row.get("decision") == "reviewed_group"
            and isinstance(group_id, str)
            and GROUP_ID.fullmatch(group_id) is not None
            and row.get("reviewMethod") in REVIEW_METHODS
        )
        complete_rows.append(complete)
        if complete:
            group_splits[group_id].add(split_for[row["reviewItemId"]])

    attestations = decisions.get("attestations", {})
    all_attested = all(attestations.get(key) is True for key in (
        "allRecordsVisuallyOrProvenanceReviewed",
        "groupIdsAreOpaque",
        "sourceAnnotationsNotUsedAsIdentityTruth",
        "missingLabelsNotUsedAsNegativeOrNormal",
    ))
    reviewer_ok = decisions.get("reviewerRole") == "authorized_source_identity_reviewer"
    complete = all(complete_rows) and all_attested and reviewer_ok
    crossings = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    independent = complete and not crossings
    return {
        "schemaVersion": "regional-mask-source-person-review-result-v1",
        "queueItemsSHA256": binding,
        "reviewedRecords": sum(complete_rows),
        "unreviewedRecords": 337 - sum(complete_rows),
        "personOrSourceCoverageComplete": complete,
        "crossSplitGroupCount": len(crossings),
        "crossSplitGroupIds": crossings,
        "currentSplitIndependent": independent,
        "replacementSplitRequired": complete and bool(crossings),
        "replacementSplitReady": False,
        "trainingAuthorized": False,
        "finalTestAuthorized": False,
        "activationAllowed": False,
        "blockers": [
            reason
            for condition, reason in (
                (complete, "source_person_review_incomplete"),
                (independent, "current_split_not_person_source_independent"),
                (False, "group_locked_replacement_version_missing"),
                (False, "expert_semantic_mask_protocol_not_accepted"),
            )
            if not condition
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--provider-export-sha256", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    queue, template, resolver = build_review(
        args.root, args.source_archive_sha256, args.provider_export_sha256
    )
    args.queue.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    if not args.decisions.exists():
        args.decisions.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    if args.evaluate:
        if args.result is None:
            raise AuditError("--result is required with --evaluate")
        result = evaluate_decisions(
            queue, json.loads(args.decisions.read_text(encoding="utf-8"))
        )
        args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
