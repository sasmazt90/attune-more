#!/usr/bin/env python3
"""Build a fail-closed expert protocol from the regional mask review queue.

The committed template contains privacy-safe review item identifiers only. It
cannot produce a protocol until every queued item has an explicit expert
decision and both class policies are locked. No pending value is interpreted
as normal, negative, approval, or ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_QUEUE_SHA256 = "cea2fb24724d89819db49ebd4f78927711c92824d725222b9c7f59cc587d7943"
EXPECTED_ARCHIVE_SHA256 = "a24793ca3490a48088abf47ba89fc9ab94e1c3a12c488ce52915e19b5bdf6fd6"
EXPECTED_PROVIDER_EXPORT_SHA256 = "ba7aa450ee2e98af35dcb1b60f3f9673fc7a6ef6b7709e7b94e1df1d32bdab3a"
EXPECTED_ITEMS = 81
EXPECTED_CLASS_COUNTS = {"Oily": 40, "Redness": 41}
CLASSES = tuple(EXPECTED_CLASS_COUNTS)
ASSESSABILITY = {"assessable", "unassessable", "ambiguous"}
MASK_EXTENT_DECISIONS = {
    "correct",
    "too_broad",
    "too_narrow",
    "fragmented",
    "not_assessable",
}
SEMANTIC_DECISIONS = {"keep", "correct_before_training", "exclude"}
PENDING = "pending_expert_review"


class ProtocolError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("receipt root must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_queue(queue: dict[str, Any], queue_sha256: str) -> dict[str, dict[str, str]]:
    if queue_sha256 != EXPECTED_QUEUE_SHA256:
        raise ProtocolError("review queue digest does not match the frozen queue")
    if queue.get("schemaVersion") != "regional-mask-expert-review-queue-v1":
        raise ProtocolError("review queue schema is invalid")
    source = queue.get("source", {})
    if (
        source.get("sourceArchiveSHA256") != EXPECTED_ARCHIVE_SHA256
        or source.get("providerExportSHA256") != EXPECTED_PROVIDER_EXPORT_SHA256
        or source.get("versionNumber") != 1
    ):
        raise ProtocolError("review queue source binding does not match")
    privacy = queue.get("privacy", {})
    for key in (
        "containsImageBytes",
        "containsFilenames",
        "containsRawSourceNames",
        "containsProviderImageIds",
        "resolverCommitted",
    ):
        if privacy.get(key) is not False:
            raise ProtocolError("review queue is not privacy safe")
    selection = queue.get("selection", {})
    if (
        selection.get("allowedSplits") != ["train", "valid"]
        or selection.get("testImagesRead") != 0
        or selection.get("testImagesSelected") != 0
        or selection.get("selectedUniqueImages") != EXPECTED_ITEMS
    ):
        raise ProtocolError("review queue selection is not frozen or test isolated")
    policy = queue.get("reviewPolicy", {})
    if (
        policy.get("reviewerRequired") != "expert_review"
        or policy.get("rednessIndependentLayer") is not True
        or policy.get("missingMaskMeansNormal") is not False
        or policy.get("missingClassIsNegative") is not False
        or policy.get("modelPredictionAcceptedAsTruth") is not False
    ):
        raise ProtocolError("review queue semantic invariants are invalid")
    items = queue.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_ITEMS:
        raise ProtocolError("review queue item inventory is invalid")
    by_id: dict[str, dict[str, str]] = {}
    counts = {name: 0 for name in CLASSES}
    for row in items:
        if not isinstance(row, dict):
            raise ProtocolError("review queue item is invalid")
        item_id = row.get("reviewItemId")
        class_name = row.get("className")
        split = row.get("split")
        if (
            not isinstance(item_id, str)
            or len(item_id) != 24
            or class_name not in CLASSES
            or split not in {"train", "valid"}
            or row.get("missingClassIsNegative") is not False
            or item_id in by_id
        ):
            raise ProtocolError("review queue item binding is invalid")
        by_id[item_id] = {"className": class_name, "split": split}
        counts[class_name] += 1
    if counts != EXPECTED_CLASS_COUNTS:
        raise ProtocolError("review queue class inventory is invalid")
    return by_id


def build_template(queue: dict[str, Any], queue_sha256: str) -> dict[str, Any]:
    by_id = validate_queue(queue, queue_sha256)
    return {
        "schemaVersion": "regional-mask-expert-review-decisions-v1",
        "reviewQueue": {
            "schemaVersion": queue["schemaVersion"],
            "sha256": queue_sha256,
            "items": len(by_id),
        },
        "reviewer": PENDING,
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "resolverCommitted": False,
        },
        "semanticInvariants": {
            "rednessIndependentLayer": True,
            "missingMaskMeansNormal": False,
            "missingClassIsNegative": False,
            "modelPredictionAcceptedAsTruth": False,
        },
        "classPolicies": [
            {
                "name": name,
                "maskExtentPolicyLocked": False,
                "hardNegativePolicyLocked": False,
                "ambiguousCasePolicyLocked": False,
            }
            for name in CLASSES
        ],
        "items": [
            {
                "reviewItemId": item_id,
                "className": binding["className"],
                "split": binding["split"],
                "expertReviewed": False,
                "assessability": PENDING,
                "maskExtentDecision": PENDING,
                "semanticDecision": PENDING,
            }
            for item_id, binding in sorted(by_id.items())
        ],
        "decision": {
            "expertReviewComplete": False,
            "maskProtocolReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }


def build_protocol(
    queue: dict[str, Any], queue_sha256: str, decisions: dict[str, Any]
) -> dict[str, Any]:
    by_id = validate_queue(queue, queue_sha256)
    if decisions.get("schemaVersion") != "regional-mask-expert-review-decisions-v1":
        raise ProtocolError("expert decision schema is invalid")
    binding = decisions.get("reviewQueue", {})
    if (
        binding.get("schemaVersion") != queue["schemaVersion"]
        or binding.get("sha256") != queue_sha256
        or binding.get("items") != len(by_id)
    ):
        raise ProtocolError("expert decisions are not bound to the frozen queue")
    if decisions.get("reviewer") != "expert_review":
        raise ProtocolError("expert reviewer confirmation is missing")
    privacy = decisions.get("privacy", {})
    if any(
        privacy.get(key) is not False
        for key in (
            "containsImageBytes",
            "containsFilenames",
            "containsRawSourceNames",
            "containsProviderImageIds",
            "resolverCommitted",
        )
    ):
        raise ProtocolError("expert decisions are not privacy safe")
    invariants = decisions.get("semanticInvariants", {})
    if (
        invariants.get("rednessIndependentLayer") is not True
        or invariants.get("missingMaskMeansNormal") is not False
        or invariants.get("missingClassIsNegative") is not False
        or invariants.get("modelPredictionAcceptedAsTruth") is not False
    ):
        raise ProtocolError("regional semantic invariants are not locked")

    policies = decisions.get("classPolicies")
    if not isinstance(policies, list) or len(policies) != len(CLASSES):
        raise ProtocolError("class policies are incomplete")
    by_class_policy: dict[str, dict[str, Any]] = {}
    for row in policies:
        if not isinstance(row, dict) or row.get("name") not in CLASSES or row["name"] in by_class_policy:
            raise ProtocolError("class policy row is invalid")
        if not all(
            row.get(key) is True
            for key in (
                "maskExtentPolicyLocked",
                "hardNegativePolicyLocked",
                "ambiguousCasePolicyLocked",
            )
        ):
            raise ProtocolError("class policy is not expert locked")
        by_class_policy[row["name"]] = row
    if set(by_class_policy) != set(CLASSES):
        raise ProtocolError("class policies are incomplete")

    rows = decisions.get("items")
    if not isinstance(rows, list) or len(rows) != len(by_id):
        raise ProtocolError("expert decision item inventory is incomplete")
    reviewed: dict[str, list[str]] = {name: [] for name in CLASSES}
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ProtocolError("expert decision item is invalid")
        item_id = row.get("reviewItemId")
        expected = by_id.get(item_id)
        if expected is None or item_id in seen:
            raise ProtocolError("expert decision item is unknown or duplicated")
        if row.get("className") != expected["className"] or row.get("split") != expected["split"]:
            raise ProtocolError("expert decision item class/split binding does not match")
        if row.get("expertReviewed") is not True:
            raise ProtocolError("every queue item requires explicit expert review")
        assessability = row.get("assessability")
        extent = row.get("maskExtentDecision")
        semantic = row.get("semanticDecision")
        if assessability not in ASSESSABILITY or extent not in MASK_EXTENT_DECISIONS or semantic not in SEMANTIC_DECISIONS:
            raise ProtocolError("expert decision contains a pending or invalid value")
        if assessability != "assessable" and semantic != "exclude":
            raise ProtocolError("ambiguous or unassessable items must be excluded")
        if assessability == "assessable" and extent == "not_assessable":
            raise ProtocolError("assessable item cannot use not_assessable extent")
        if assessability != "assessable" and extent != "not_assessable":
            raise ProtocolError("non-assessable item must use not_assessable extent")
        if extent != "correct" and assessability == "assessable" and semantic == "keep":
            raise ProtocolError("incorrect mask extent cannot be kept unchanged")
        reviewed[expected["className"]].append(item_id)
        seen.add(item_id)
    if seen != set(by_id):
        raise ProtocolError("expert decisions do not cover the frozen queue exactly")

    return {
        "schemaVersion": "regional-mask-expert-protocol-v1",
        "archiveSHA256": EXPECTED_ARCHIVE_SHA256,
        "providerExportSHA256": EXPECTED_PROVIDER_EXPORT_SHA256,
        "reviewQueueSchemaVersion": queue["schemaVersion"],
        "reviewQueueSHA256": queue_sha256,
        "reviewQueueItems": len(by_id),
        "reviewer": "expert_review",
        "rednessIndependentLayer": True,
        "missingMaskMeansNormal": False,
        "missingClassIsNegative": False,
        "modelPredictionAcceptedAsTruth": False,
        "classes": [
            {
                "name": name,
                "expertReviewed": True,
                "maskExtentPolicyLocked": True,
                "hardNegativePolicyLocked": True,
                "ambiguousCasePolicyLocked": True,
                "reviewedItemIds": sorted(reviewed[name]),
            }
            for name in CLASSES
        ],
        "decision": {
            "expertReviewComplete": True,
            "maskProtocolReady": True,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-queue", type=Path, required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.template == (args.decisions is not None):
        raise ProtocolError("choose exactly one of --template or --decisions")
    queue = _load(args.review_queue)
    digest = _sha256(args.review_queue)
    result = (
        build_template(queue, digest)
        if args.template
        else build_protocol(queue, digest, _load(args.decisions))
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
