#!/usr/bin/env python3
"""Build the source/person grouping release artifact without inventing identity.

The committed source-mapping receipt can only produce a blocked public
preflight.  A release artifact requires an opaque private ledger for every
selected archive.  Exact duplicates must be co-grouped and ambiguous visual
or filename candidates must be resolved by a human, but neither similarity,
singletons nor photo groups may be promoted to person identity.

Archive names, paths, URLs, raw record/group identifiers, reviewer identities
and model predictions are rejected from the manifest and never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "skin-source-person-grouping-input-v1"
PREFLIGHT_METHOD = "skin-source-person-grouping-preflight-v1"
ARTIFACT_METHOD = "skin-source-person-grouping-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
SELECTED_ARCHIVE_COUNT = 11
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "archive", "archiveName",
    "archivePath", "image", "images", "record", "records", "recordId",
    "recordIds", "groupId", "groupIds", "subject", "subjectId",
    "personId", "personIds", "reviewer", "reviewerId", "reviewerName",
    "prediction", "predictions", "embedding", "embeddings",
}
SAFE_POLICY = {
    "singletonAssignmentAcceptedAsIdentity": False,
    "similarityCandidateAcceptedAsIdentity": False,
    "filenameCandidateAcceptedAsIdentity": False,
    "photoGroupAcceptedAsPersonIdentity": False,
    "modelPredictionAcceptedAsIdentity": False,
    "excludedArchivesAccessed": False,
}


class GroupingInputError(ValueError):
    """Raised when grouping evidence is incomplete or unsafe."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GroupingInputError(f"{field} must be a nonnegative integer")
    return value


def _positive_int(value: Any, field: str) -> int:
    value = _nonnegative_int(value, field)
    if value == 0:
        raise GroupingInputError(f"{field} must be positive")
    return value


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise GroupingInputError(f"{location} contains private identity or raw grouping payload")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_committed_facts(receipt: dict[str, Any]) -> dict[str, Any]:
    """Replay observed grouping facts while keeping release fail-closed."""
    if receipt.get("schemaVersion") != 2 or receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise GroupingInputError("source mapping receipt identity changed")
    facts = receipt.get("auditFacts")
    if not isinstance(facts, dict):
        raise GroupingInputError("source mapping audit facts are missing")
    try:
        acquisition = facts["acquisition"]
        clean3 = facts["clean3"]
        under_eye = facts["underEye"]
        record_count = int(acquisition["images"]) + int(clean3["actualImages"]) + int(under_eye["images"])
        exact_cross_split = int(acquisition["crossSplitExactGroups"]) + int(clean3["crossSplitExactGroups"])
        filename_candidates = int(acquisition["crossSplitFilenameCandidateGroups"])
        perceptual_candidates = int(acquisition["crossSplitPerceptualCandidatePairs"])
        reviewed_under_eye = int(under_eye["reviewedCrossSplitGroups"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GroupingInputError("committed source grouping facts are incomplete") from exc
    if record_count != 7865 or exact_cross_split != 66:
        raise GroupingInputError("committed source grouping counts changed")
    if filename_candidates != 286 or perceptual_candidates != 1301 or reviewed_under_eye != 3:
        raise GroupingInputError("committed candidate grouping counts changed")
    if under_eye.get("sourcePersonCoverageComplete") is not False:
        raise GroupingInputError("under-eye source/person coverage fact changed")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "sourceFactsMethodVersion": SOURCE_RECEIPT_METHOD,
        "releaseRef": None,
        "sourceRegistryRef": None,
        "selectedArchiveCount": 0,
        "knownRecordCount": record_count,
        "knownExactCrossSplitGroupCount": exact_cross_split,
        "knownFilenameCandidateGroupCount": filename_candidates,
        "knownPerceptualCandidatePairCount": perceptual_candidates,
        "underEyeReviewedCrossSplitGroupCount": reviewed_under_eye,
        "sourcePersonGroupingComplete": False,
        "crossSplitGroupCount": exact_cross_split,
        **SAFE_POLICY,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "selected_archive_grouping_coverage_incomplete",
            "known_cross_split_exact_groups_present",
            "filename_candidates_require_human_resolution",
            "perceptual_candidates_require_human_resolution",
            "under_eye_source_person_coverage_incomplete",
            "opaque_private_grouping_ledger_missing",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque per-archive grouping ledger."""
    if not isinstance(manifest, dict):
        raise GroupingInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise GroupingInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise GroupingInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    if not _is_opaque(registry_ref):
        blockers.append("source_registry_ref_missing_or_invalid")
    if manifest.get("selectedArchiveCountExpected") != SELECTED_ARCHIVE_COUNT:
        raise GroupingInputError("selected archive count contract changed")
    policy = manifest.get("identityPolicy")
    if not isinstance(policy, dict):
        blockers.append("identity_policy_missing")
    elif set(policy) != set(SAFE_POLICY):
        raise GroupingInputError("identity policy fields changed")
    else:
        for field, expected in SAFE_POLICY.items():
            if policy.get(field) != expected:
                raise GroupingInputError(f"unsafe grouping identity policy: {field}")

    entries = manifest.get("selectedArchives", [])
    if not isinstance(entries, list):
        raise GroupingInputError("selectedArchives must be a list")
    if not entries:
        blockers.append("selected_archive_grouping_registry_empty")
    if len(entries) != SELECTED_ARCHIVE_COUNT:
        blockers.append("selected_archive_count_mismatch")
    allowed = {
        "opaqueId", "groupingEvidenceSHA256", "recordCount", "groupCount",
        "exactDuplicateGroupCount", "ambiguousCandidateGroupCount",
        "unresolvedAmbiguousCandidateGroupCount", "allRecordsAssignedExactlyOnce",
        "exactDuplicatesCoGrouped", "ambiguousCandidatesHumanReviewed",
        "sourcePersonCoverageComplete", "crossSplitGroupCount",
        *SAFE_POLICY.keys(),
    }
    opaque_ids: list[str] = []
    hashes: list[str] = []
    canonical: list[dict[str, Any]] = []
    total_records = 0
    total_groups = 0
    total_exact_groups = 0
    total_candidates = 0
    total_unresolved = 0
    total_cross_split = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise GroupingInputError(f"selected archive {index} must be an object")
        if set(entry) - allowed:
            raise GroupingInputError(f"selected archive {index} contains unsupported fields")
        opaque_id = entry.get("opaqueId")
        evidence_hash = entry.get("groupingEvidenceSHA256")
        if not _is_opaque(opaque_id):
            blockers.append(f"selected_archive_{index}_opaque_id_invalid")
        else:
            opaque_ids.append(opaque_id)
        if not _is_sha256(evidence_hash):
            blockers.append(f"selected_archive_{index}_evidence_sha256_invalid")
        else:
            hashes.append(evidence_hash)
        record_count = _positive_int(entry.get("recordCount"), f"selected archive {index} recordCount")
        group_count = _positive_int(entry.get("groupCount"), f"selected archive {index} groupCount")
        exact_count = _nonnegative_int(entry.get("exactDuplicateGroupCount"), f"selected archive {index} exactDuplicateGroupCount")
        candidate_count = _nonnegative_int(entry.get("ambiguousCandidateGroupCount"), f"selected archive {index} ambiguousCandidateGroupCount")
        unresolved_count = _nonnegative_int(entry.get("unresolvedAmbiguousCandidateGroupCount"), f"selected archive {index} unresolvedAmbiguousCandidateGroupCount")
        cross_split_count = _nonnegative_int(entry.get("crossSplitGroupCount"), f"selected archive {index} crossSplitGroupCount")
        if group_count > record_count:
            raise GroupingInputError(f"selected archive {index} groupCount exceeds recordCount")
        if exact_count > group_count or candidate_count > group_count:
            raise GroupingInputError(f"selected archive {index} grouped count exceeds groupCount")
        if unresolved_count > candidate_count:
            raise GroupingInputError(f"selected archive {index} unresolved candidates exceed candidates")
        for field in (
            "allRecordsAssignedExactlyOnce", "exactDuplicatesCoGrouped",
            "ambiguousCandidatesHumanReviewed", "sourcePersonCoverageComplete",
        ):
            if entry.get(field) is not True:
                blockers.append(f"selected_archive_{index}_{field}_incomplete")
        for field, expected in SAFE_POLICY.items():
            if entry.get(field) != expected:
                raise GroupingInputError(f"unsafe archive grouping identity policy: {field}")
        if unresolved_count != 0:
            blockers.append(f"selected_archive_{index}_ambiguous_candidates_unresolved")
        if cross_split_count != 0:
            blockers.append(f"selected_archive_{index}_cross_split_groups_present")
        total_records += record_count
        total_groups += group_count
        total_exact_groups += exact_count
        total_candidates += candidate_count
        total_unresolved += unresolved_count
        total_cross_split += cross_split_count
        if _is_opaque(opaque_id) and _is_sha256(evidence_hash):
            canonical.append({
                "opaqueId": opaque_id,
                "groupingEvidenceSHA256": evidence_hash,
                "recordCount": record_count,
                "groupCount": group_count,
                "exactDuplicateGroupCount": exact_count,
                "ambiguousCandidateGroupCount": candidate_count,
            })
    if len(opaque_ids) != len(set(opaque_ids)):
        raise GroupingInputError("selected archive opaque IDs must be unique")
    if len(hashes) != len(set(hashes)):
        raise GroupingInputError("grouping evidence hashes must be unique")
    blockers = sorted(set(blockers))
    digest = hashlib.sha256(_canonical_bytes(sorted(canonical, key=lambda item: item["opaqueId"]))).hexdigest() if canonical else None
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "selectedArchiveCount": len(entries),
        "recordCount": total_records,
        "groupCount": total_groups,
        "exactDuplicateGroupCount": total_exact_groups,
        "ambiguousCandidateGroupCount": total_candidates,
        "unresolvedAmbiguousCandidateGroupCount": total_unresolved,
        "groupingRegistryDigest": digest,
        "sourcePersonGroupingComplete": not blockers,
        "crossSplitGroupCount": total_cross_split,
        **SAFE_POLICY,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise GroupingInputError("source/person grouping is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "selectedArchiveCount": preflight["selectedArchiveCount"],
        "groupingRegistryDigest": preflight["groupingRegistryDigest"],
        "recordCount": preflight["recordCount"],
        "groupCount": preflight["groupCount"],
        "sourcePersonGroupingComplete": True,
        "crossSplitGroupCount": 0,
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
            raise GroupingInputError("committed partial facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
