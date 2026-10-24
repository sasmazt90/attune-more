#!/usr/bin/env python3
"""Fail-closed release gate for a replacement acne dataset split.

The gate consumes privacy-safe receipts only. It never assigns images to a
split, changes labels, or starts training. Training remains blocked until a
reviewed group receipt covers every hashed record exactly once, keeps the
locked test records in test, and an expert semantic/negative review is complete
for every product class.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


SPLITS = ("train", "valid", "test")
CLASSES = ("Pimple", "Post acne", "Pigmentation")


class GateError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc


def require_record_index(source: dict[str, Any]) -> dict[str, str]:
    if source.get("schemaVersion") != "acne-source-group-review-v1":
        raise GateError("source review schema is invalid")
    privacy = source.get("privacy", {})
    if any(privacy.get(key) is not False for key in (
        "containsImageBytes", "containsFilenames", "containsRawSourceNames"
    )):
        raise GateError("source review is not privacy safe")
    records = source.get("recordIndex")
    if not isinstance(records, list):
        raise GateError("source review has no privacy-safe record index")
    result: dict[str, str] = {}
    for row in records:
        if not isinstance(row, dict):
            raise GateError("record index row is invalid")
        record_id, split = row.get("recordId"), row.get("split")
        if not isinstance(record_id, str) or not record_id or split not in SPLITS:
            raise GateError("record index row is incomplete")
        if record_id in result:
            raise GateError("record index ids are duplicated")
        result[record_id] = split
    expected = source.get("dataset", {}).get("images")
    if expected != len(result):
        raise GateError("record index does not cover the dataset")
    expected_splits = source.get("dataset", {}).get("splits")
    if not isinstance(expected_splits, dict):
        raise GateError("source split counts are missing")
    actual_splits = Counter(result.values())
    if any(actual_splits[split] != expected_splits.get(split) for split in SPLITS):
        raise GateError("record index split counts do not match the dataset")
    return result


def validate_group_coverage(
    receipt: dict[str, Any] | None,
    records: dict[str, str],
) -> dict[str, Any]:
    if receipt is None:
        return {
            "receiptSupplied": False,
            "coveredRecords": 0,
            "missingRecords": len(records),
            "duplicateAssignments": 0,
            "unknownAssignments": 0,
            "testRecordsMoved": 0,
            "complete": False,
        }
    if receipt.get("schemaVersion") != "acne-source-person-group-coverage-v1":
        raise GateError("group coverage schema is invalid")
    if receipt.get("reviewer") not in {"engineering_visual_review", "expert_review"}:
        raise GateError("group coverage reviewer is invalid")
    assignments: dict[str, list[tuple[str, str]]] = {}
    for group in receipt.get("groups", []):
        if not isinstance(group, dict):
            raise GateError("group coverage row is invalid")
        group_id, target_split = group.get("groupId"), group.get("targetSplit")
        members = group.get("members")
        if (not isinstance(group_id, str) or not group_id
                or target_split not in SPLITS or not isinstance(members, list)
                or not members):
            raise GateError("group coverage row is incomplete")
        for record_id in members:
            if not isinstance(record_id, str) or not record_id:
                raise GateError("group member id is invalid")
            assignments.setdefault(record_id, []).append((group_id, target_split))
    duplicate = sum(len(values) - 1 for values in assignments.values() if len(values) > 1)
    unknown = sum(record_id not in records for record_id in assignments)
    covered = sum(record_id in records and len(values) == 1 for record_id, values in assignments.items())
    missing = len(records) - covered
    test_moved = sum(
        records.get(record_id) == "test" and values[0][1] != "test"
        for record_id, values in assignments.items()
        if record_id in records and len(values) == 1
    )
    complete = (
        missing == 0 and duplicate == 0 and unknown == 0 and test_moved == 0
        and receipt.get("allRecordsReviewed") is True
        and receipt.get("testSplitPolicy") == "locked_existing_test_records"
    )
    return {
        "receiptSupplied": True,
        "coveredRecords": covered,
        "missingRecords": missing,
        "duplicateAssignments": duplicate,
        "unknownAssignments": unknown,
        "testRecordsMoved": test_moved,
        "complete": complete,
    }


def validate_semantic_review(receipt: dict[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {
            "receiptSupplied": False,
            "completeClasses": [],
            "missingClasses": list(CLASSES),
            "complete": False,
        }
    if receipt.get("schemaVersion") != "acne-semantic-negative-review-v1":
        raise GateError("semantic review schema is invalid")
    rows = receipt.get("classes")
    if not isinstance(rows, list):
        raise GateError("semantic review classes are missing")
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("name") not in CLASSES:
            raise GateError("semantic review class row is invalid")
        if row["name"] in by_name:
            raise GateError("semantic review classes are duplicated")
        by_name[row["name"]] = row
    complete_classes = sorted(
        name for name, row in by_name.items()
        if row.get("expertReviewed") is True
        and row.get("positiveDefinitionLocked") is True
        and row.get("hardNegativePolicyLocked") is True
        and row.get("ambiguousCasePolicyLocked") is True
    )
    missing = [name for name in CLASSES if name not in complete_classes]
    return {
        "receiptSupplied": True,
        "completeClasses": complete_classes,
        "missingClasses": missing,
        "complete": not missing,
    }


def build_gate(
    source_review: dict[str, Any],
    group_coverage: dict[str, Any] | None = None,
    semantic_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = require_record_index(source_review)
    grouping = validate_group_coverage(group_coverage, records)
    semantics = validate_semantic_review(semantic_review)
    leakage_groups = source_review.get("reviewSummary", {}).get(
        "confirmedCrossSplitSourceLeakageGroups"
    )
    if not isinstance(leakage_groups, int) or leakage_groups < 0:
        raise GateError("confirmed leakage group count is invalid")
    confirmed_members = {
        member.get("recordId")
        for group in source_review.get("regroupingPlan", {}).get("confirmedGroups", [])
        if isinstance(group, dict)
        for member in group.get("members", [])
        if isinstance(member, dict) and member.get("recordId") in records
    }
    blocked_reasons: list[str] = []
    if leakage_groups:
        blocked_reasons.append("CURRENT_SPLIT_HAS_CONFIRMED_SOURCE_PERSON_LEAKAGE")
    if not grouping["complete"]:
        blocked_reasons.append("FULL_REVIEWED_GROUP_COVERAGE_MISSING")
    if not semantics["complete"]:
        blocked_reasons.append("EXPERT_SEMANTIC_NEGATIVE_REVIEW_MISSING")
    replacement_ready = grouping["complete"] and semantics["complete"]
    return {
        "schemaVersion": "acne-split-release-gate-v1",
        "dataset": {
            "archiveSHA256": source_review.get("dataset", {}).get("archiveSHA256"),
            "records": len(records),
            "splits": {split: sum(value == split for value in records.values()) for split in SPLITS},
        },
        "currentSplit": {
            "confirmedCrossSplitSourcePersonGroups": leakage_groups,
            "confirmedLeakageMembers": len(confirmed_members),
            "independenceEstablished": False,
        },
        "replacementSplit": grouping,
        "semanticNegativeReview": semantics,
        "decision": {
            "readyToGenerateReplacementSplit": replacement_ready,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "blockedReasons": blocked_reasons,
            "note": (
                "Even a complete receipt only authorizes deterministic split generation; "
                "a generated split must be re-audited before training is authorized."
            ),
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "recordIdsAreHashed": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--group-coverage", type=Path)
    parser.add_argument("--semantic-review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_gate(
            load_json(args.source_review),
            load_json(args.group_coverage) if args.group_coverage else None,
            load_json(args.semantic_review) if args.semantic_review else None,
        )
    except GateError as exc:
        print(f"split release blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
