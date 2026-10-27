"""Apply explicit review decisions to privacy-safe source-group candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ResolutionError(ValueError):
    """Raised when review evidence is incomplete or does not bind the audit."""


class UnionFind:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def resolve_candidates(audit: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    if audit.get("schemaVersion") != "regional-skin-type-source-group-audit-v1":
        raise ResolutionError("unsupported audit schema")
    if decisions.get("schemaVersion") != "regional-skin-type-source-group-decisions-v1":
        raise ResolutionError("unsupported decisions schema")
    archive_sha = audit.get("source", {}).get("archiveSHA256")
    if decisions.get("source", {}).get("archiveSHA256") != archive_sha:
        raise ResolutionError("decision archive does not match audit")

    candidates = audit.get("candidates")
    rows = decisions.get("decisions")
    if not isinstance(candidates, list) or not isinstance(rows, list):
        raise ResolutionError("candidate and decision lists are required")
    by_id = {row.get("candidateId"): row for row in candidates}
    decision_by_id = {row.get("candidateId"): row for row in rows}
    if None in by_id or None in decision_by_id or len(by_id) != len(candidates) or len(decision_by_id) != len(rows):
        raise ResolutionError("candidate ids must be unique and non-empty")
    if set(by_id) != set(decision_by_id):
        raise ResolutionError("every candidate must have exactly one decision")

    allowed = {"same_source_or_person", "different_source_or_person"}
    source_ids = {
        source_id
        for row in candidates
        for source_id in (row["leftSourceId"], row["rightSourceId"])
    }
    union = UnionFind(source_ids)
    same_count = 0
    different_count = 0
    for candidate_id, decision in decision_by_id.items():
        result = decision.get("result")
        if result not in allowed:
            raise ResolutionError(f"invalid decision for {candidate_id}")
        candidate = by_id[candidate_id]
        if result == "same_source_or_person":
            union.union(candidate["leftSourceId"], candidate["rightSourceId"])
            same_count += 1
        else:
            different_count += 1

    grouped: dict[str, set[str]] = {}
    for source_id in source_ids:
        grouped.setdefault(union.find(source_id), set()).add(source_id)
    confirmed_groups = []
    for members in grouped.values():
        if len(members) < 2:
            continue
        member_list = sorted(members)
        split_pairs = sorted({
            split_pair
            for candidate in candidates
            if candidate["leftSourceId"] in members and candidate["rightSourceId"] in members
            for split_pair in candidate["splitPairs"]
        })
        group_id = hashlib.sha256(":".join(member_list).encode("utf-8")).hexdigest()[:24]
        confirmed_groups.append({
            "groupId": group_id,
            "memberSourceIds": member_list,
            "splitPairs": split_pairs,
            "crossSplit": bool(split_pairs),
        })
    confirmed_groups.sort(key=lambda row: row["groupId"])

    unique_sources = audit.get("inventory", {}).get("uniqueSourceIds")
    confirmed_members = len({member for group in confirmed_groups for member in group["memberSourceIds"]})
    if not isinstance(unique_sources, int) or unique_sources < confirmed_members:
        raise ResolutionError("invalid unique source inventory")
    return {
        "schemaVersion": "regional-skin-type-source-group-resolution-v1",
        "source": {
            "archiveSHA256": archive_sha,
            "candidateAuditSchema": audit["schemaVersion"],
            "decisionSchema": decisions["schemaVersion"],
        },
        "review": {
            "reviewerRole": decisions.get("reviewerRole"),
            "candidateDecisions": len(rows),
            "sameSourceOrPersonDecisions": same_count,
            "differentSourceOrPersonDecisions": different_count,
            "allCandidatesResolved": True,
            "rawImagesCommitted": False,
            "rawFileNamesCommitted": False,
        },
        "coverage": {
            "uniqueSourceIds": unique_sources,
            "confirmedGroups": len(confirmed_groups),
            "confirmedGroupMembers": confirmed_members,
            "unreviewedSingletonSources": unique_sources - confirmed_members,
            "fullPersonIdentityCoverageEstablished": False,
            "confirmedCrossSplitGroups": sum(1 for group in confirmed_groups if group["crossSplit"]),
        },
        "confirmedGroups": confirmed_groups,
        "decision": {
            "splitIndependenceEstablished": False,
            "splitIndependenceViolated": any(group["crossSplit"] for group in confirmed_groups),
            "trainingAuthorized": False,
            "testEligibleForFinalAcceptance": False,
            "reason": "Confirmed cross-split source/person grouping exists and complete person identity coverage is missing.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    result = resolve_candidates(audit, decisions)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
