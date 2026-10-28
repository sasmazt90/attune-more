#!/usr/bin/env python3
"""Build a group-locked train/validation/final-test split artifact.

Committed partial source facts stay blocked.  A release artifact can only be
emitted from an opaque private split manifest bound to the completed
source/person grouping evidence.  The final test set is hidden from training,
threshold selection and model selection, and physical-camera subjects are not
part of the source registry split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "skin-source-group-locked-split-input-v1"
PREFLIGHT_METHOD = "skin-source-group-locked-split-preflight-v1"
ARTIFACT_METHOD = "skin-source-group-locked-split-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
TARGETS = ("acne", "oil", "dry", "redness", "tone", "lines", "dark", "bags", "type", "sag")
SELECTED_ARCHIVE_COUNT = 11
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "archive", "archiveName",
    "archivePath", "image", "images", "record", "records", "recordId",
    "recordIds", "groupId", "groupIds", "subject", "subjectId",
    "personId", "personIds", "reviewer", "reviewerId", "reviewerName",
    "prediction", "predictions", "labelPayload", "annotations",
}
SAFE_POLICY = {
    "groupLocked": True,
    "allRecordsAssignedExactlyOnce": True,
    "crossSplitGroupCount": 0,
    "finalTestUsedForTraining": False,
    "finalTestUsedForSelection": False,
    "finalTestUsedForThresholds": False,
    "finalTestLabelsHiddenDuringDevelopment": True,
    "cameraSubjectsIncluded": False,
    "excludedArchivesIncluded": False,
    "modelPredictionsUsedToAssignSplits": False,
}


class SplitInputError(ValueError):
    """Raised when split evidence is incomplete, private or unsafe."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SplitInputError(f"{field} must be a positive integer")
    return value


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise SplitInputError(f"{location} contains private identity, label or raw split payload")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_committed_facts(receipt: dict[str, Any]) -> dict[str, Any]:
    """Replay current source facts without claiming a locked split exists."""
    if receipt.get("schemaVersion") != 2 or receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise SplitInputError("source mapping receipt identity changed")
    facts = receipt.get("auditFacts")
    candidate = receipt.get("acceptanceCandidate")
    if not isinstance(facts, dict) or not isinstance(candidate, dict):
        raise SplitInputError("source mapping receipt facts are incomplete")
    try:
        record_count = int(facts["acquisition"]["images"]) + int(facts["clean3"]["actualImages"]) + int(facts["underEye"]["images"])
        exact_cross_split = int(facts["acquisition"]["crossSplitExactGroups"]) + int(facts["clean3"]["crossSplitExactGroups"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SplitInputError("committed split facts are incomplete") from exc
    if record_count != 7865 or exact_cross_split != 66:
        raise SplitInputError("committed split counts changed")
    if candidate.get("sourcePersonGroupingComplete") is not False:
        raise SplitInputError("source/person grouping candidate fact changed")
    if candidate.get("lockedTrainValidationFinalTestSplit") is not False:
        raise SplitInputError("locked split candidate fact changed")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "sourceFactsMethodVersion": SOURCE_RECEIPT_METHOD,
        "releaseRef": None,
        "sourceRegistryRef": None,
        "splitRef": None,
        "knownRecordCount": record_count,
        "knownExactCrossSplitGroupCount": exact_cross_split,
        "counts": {"train": 0, "validation": 0, "final_test": 0},
        **SAFE_POLICY,
        "groupLocked": False,
        "allRecordsAssignedExactlyOnce": False,
        "crossSplitGroupCount": exact_cross_split,
        "finalTestLabelsHiddenDuringDevelopment": False,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "source_person_grouping_artifact_missing",
            "source_person_grouping_incomplete",
            "known_cross_split_exact_groups_present",
            "locked_split_assignment_missing",
            "final_test_reservation_missing",
            "per_target_split_coverage_unverified",
            "camera_subject_exclusion_unverified",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque split manifest bound to completed grouping evidence."""
    if not isinstance(manifest, dict):
        raise SplitInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise SplitInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise SplitInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    split_ref = manifest.get("splitRef")
    for value, blocker in (
        (release_ref, "release_ref_missing_or_invalid"),
        (registry_ref, "source_registry_ref_missing_or_invalid"),
        (split_ref, "split_ref_missing_or_invalid"),
    ):
        if not _is_opaque(value):
            blockers.append(blocker)
    if manifest.get("selectedArchiveCount") != SELECTED_ARCHIVE_COUNT:
        blockers.append("selected_archive_count_mismatch")
    grouping = manifest.get("sourcePersonGroupingEvidence")
    if not isinstance(grouping, dict):
        blockers.append("source_person_grouping_evidence_missing")
        grouping_artifact_hash = None
        grouping_registry_digest = None
    else:
        allowed_grouping = {
            "artifactSHA256", "groupingRegistryDigest", "recordCount",
            "sourcePersonGroupingComplete", "crossSplitGroupCount",
            "singletonAssignmentAcceptedAsIdentity",
            "similarityCandidateAcceptedAsIdentity",
        }
        if set(grouping) - allowed_grouping:
            raise SplitInputError("grouping evidence contains unsupported fields")
        grouping_artifact_hash = grouping.get("artifactSHA256")
        grouping_registry_digest = grouping.get("groupingRegistryDigest")
        if not _is_sha256(grouping_artifact_hash) or not _is_sha256(grouping_registry_digest):
            blockers.append("source_person_grouping_digest_missing_or_invalid")
        for field, expected in {
            "sourcePersonGroupingComplete": True,
            "crossSplitGroupCount": 0,
            "singletonAssignmentAcceptedAsIdentity": False,
            "similarityCandidateAcceptedAsIdentity": False,
        }.items():
            if grouping.get(field) != expected:
                blockers.append(f"source_person_grouping_{field}_invalid")
    total_records = _positive_int(manifest.get("recordCount"), "recordCount")
    if isinstance(grouping, dict) and grouping.get("recordCount") != total_records:
        blockers.append("grouping_record_count_mismatch")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or set(counts) != {"train", "validation", "final_test"}:
        raise SplitInputError("split counts must contain train, validation and final_test")
    normalized_counts = {name: _positive_int(counts[name], f"counts.{name}") for name in ("train", "validation", "final_test")}
    if sum(normalized_counts.values()) != total_records:
        blockers.append("split_record_count_mismatch")
    policy = manifest.get("splitPolicy")
    if not isinstance(policy, dict):
        blockers.append("split_policy_missing")
    elif set(policy) != set(SAFE_POLICY):
        raise SplitInputError("split policy fields changed")
    else:
        for field, expected in SAFE_POLICY.items():
            if policy.get(field) != expected:
                raise SplitInputError(f"unsafe split policy: {field}")
    assignment_hash = manifest.get("splitAssignmentSHA256")
    if not _is_sha256(assignment_hash):
        blockers.append("split_assignment_sha256_missing_or_invalid")
    entries = manifest.get("targetCoverage", [])
    if not isinstance(entries, list):
        raise SplitInputError("targetCoverage must be a list")
    if not entries:
        blockers.append("target_coverage_empty")
    targets: list[str] = []
    canonical_coverage: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SplitInputError(f"target coverage {index} must be an object")
        if set(entry) != {"target", "counts", "expertLabelsOnly", "unknownExcludedFromPositiveCoverage"}:
            raise SplitInputError(f"target coverage {index} fields changed")
        target = entry.get("target")
        if target not in TARGETS:
            blockers.append(f"target_coverage_{index}_target_invalid")
        else:
            targets.append(target)
        target_counts = entry.get("counts")
        if not isinstance(target_counts, dict) or set(target_counts) != {"train", "validation", "final_test"}:
            raise SplitInputError(f"target coverage {index} counts changed")
        normalized_target_counts = {
            name: _positive_int(target_counts[name], f"targetCoverage.{index}.{name}")
            for name in ("train", "validation", "final_test")
        }
        if entry.get("expertLabelsOnly") is not True or entry.get("unknownExcludedFromPositiveCoverage") is not True:
            blockers.append(f"target_coverage_{index}_expert_coverage_invalid")
        if target in TARGETS:
            canonical_coverage.append({"target": target, "counts": normalized_target_counts})
    if len(targets) != len(set(targets)):
        raise SplitInputError("target coverage entries must be unique")
    if set(targets) != set(TARGETS) or len(entries) != len(TARGETS):
        blockers.append("target_coverage_inventory_incomplete")
    blockers = sorted(set(blockers))
    coverage_digest = hashlib.sha256(_canonical_bytes(sorted(canonical_coverage, key=lambda item: item["target"]))).hexdigest() if canonical_coverage else None
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "splitRef": split_ref if _is_opaque(split_ref) else None,
        "selectedArchiveCount": manifest.get("selectedArchiveCount"),
        "recordCount": total_records,
        "counts": normalized_counts,
        "sourcePersonGroupingArtifactSHA256": grouping_artifact_hash if _is_sha256(grouping_artifact_hash) else None,
        "groupingRegistryDigest": grouping_registry_digest if _is_sha256(grouping_registry_digest) else None,
        "splitAssignmentSHA256": assignment_hash if _is_sha256(assignment_hash) else None,
        "targets": list(TARGETS),
        "targetCoverageDigest": coverage_digest,
        **SAFE_POLICY,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise SplitInputError("group-locked split is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "splitRef": preflight["splitRef"],
        "selectedArchiveCount": preflight["selectedArchiveCount"],
        "recordCount": preflight["recordCount"],
        "counts": preflight["counts"],
        "sourcePersonGroupingArtifactSHA256": preflight["sourcePersonGroupingArtifactSHA256"],
        "groupingRegistryDigest": preflight["groupingRegistryDigest"],
        "splitAssignmentSHA256": preflight["splitAssignmentSHA256"],
        "targets": list(TARGETS),
        "targetCoverageDigest": preflight["targetCoverageDigest"],
        **SAFE_POLICY,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-mapping-receipt", type=Path)
    source.add_argument("--private-manifest", type=Path)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if args.source_mapping_receipt is not None:
        receipt = json.loads(args.source_mapping_receipt.read_text(encoding="utf-8"))
        preflight = summarize_committed_facts(receipt)
        if args.artifact_output is not None:
            raise SplitInputError("committed partial facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
