#!/usr/bin/env python3
"""Build the privacy-safe excluded-archive inventory artifact.

The four excluded archives must be preserved and reconciled without exposing
their names, paths or contents.  This builder accepts only opaque archive
references and metadata-only preservation evidence; it never opens an archive,
enumerates its contents, recomputes its hash or authorizes any downstream use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "excluded-archive-inventory-reconciliation-input-v1"
PREFLIGHT_METHOD = "excluded-archive-inventory-reconciliation-preflight-v1"
ARTIFACT_METHOD = "excluded-archive-inventory-reconciliation-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
REQUIRED_ARCHIVE_COUNT = 4
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "names", "path", "paths", "url", "urls", "uri", "uris",
    "filename", "filenames", "archiveName", "archiveNames",
    "image", "images", "record", "records", "recordId", "recordIds",
    "person", "personId", "subject", "subjectId", "reviewer", "reviewerId",
    "contents", "members", "files", "labels", "annotations", "predictions",
}
ENTRY_FIELDS = {
    "opaqueArchiveRef",
    "presenceEvidenceSHA256",
    "preservationEvidenceSHA256",
    "metadataOnlyVerification",
    "presenceVerifiedWithoutContentAccess",
    "contentsEnumerated",
    "excludedArchiveAccessed",
    "mutationPerformed",
    "uploadPerformed",
    "trainingUsePerformed",
    "productUsePerformed",
    "sourceReleaseContributionAllowed",
}
SAFE_ENTRY_POLICY = {
    "metadataOnlyVerification": True,
    "presenceVerifiedWithoutContentAccess": True,
    "contentsEnumerated": False,
    "excludedArchiveAccessed": False,
    "mutationPerformed": False,
    "uploadPerformed": False,
    "trainingUsePerformed": False,
    "productUsePerformed": False,
    "sourceReleaseContributionAllowed": False,
}
SAFE_ARTIFACT_POLICY = {
    "inventoryReconciled": True,
    "preservationPolicyEnforced": True,
    "containsPublicNamesOrPaths": False,
    "excludedArchivesAccessed": False,
    "mutationPerformed": False,
    "uploadPerformed": False,
    "trainingUsePerformed": False,
    "productUsePerformed": False,
    "sourceReleaseContributionAllowed": False,
    "metadataOnlyVerification": True,
    "contentsEnumerated": False,
    "archiveHashesRecomputed": False,
}


class ExcludedArchiveInventoryInputError(ValueError):
    """Raised when excluded-archive evidence is incomplete or unsafe."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise ExcludedArchiveInventoryInputError(
                    f"{location} contains excluded archive identity or content payload"
                )
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_committed_facts(receipt: dict[str, Any]) -> dict[str, Any]:
    """Replay current public facts without accessing the excluded archives."""
    if receipt.get("schemaVersion") != 2 or receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise ExcludedArchiveInventoryInputError("source mapping receipt identity changed")
    facts = receipt.get("auditFacts")
    if not isinstance(facts, dict):
        raise ExcludedArchiveInventoryInputError("source mapping current facts are missing")
    excluded = facts.get("excludedArchives")
    if not isinstance(excluded, dict):
        raise ExcludedArchiveInventoryInputError("excluded archive facts are missing")
    expected = {
        "requiredPreservedCount": REQUIRED_ARCHIVE_COUNT,
        "mappingScriptListedCount": 3,
        "fullInventoryReconciled": False,
        "mutationPerformed": False,
    }
    for field, value in expected.items():
        if excluded.get(field) != value:
            raise ExcludedArchiveInventoryInputError(f"excluded archive fact changed: {field}")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "sourceFactsMethodVersion": SOURCE_RECEIPT_METHOD,
        "releaseRef": None,
        "requiredArchiveCount": REQUIRED_ARCHIVE_COUNT,
        "reconciledArchiveCount": 0,
        **SAFE_ARTIFACT_POLICY,
        "inventoryReconciled": False,
        "preservationPolicyEnforced": False,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "excluded_archive_private_inventory_missing",
            "fourth_excluded_archive_not_reconciled",
            "metadata_only_presence_evidence_missing",
            "preservation_policy_evidence_missing",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque four-archive preservation inventory."""
    if not isinstance(manifest, dict):
        raise ExcludedArchiveInventoryInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise ExcludedArchiveInventoryInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise ExcludedArchiveInventoryInputError("private manifest method changed")

    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    required_count = manifest.get("requiredArchiveCount")
    if required_count != REQUIRED_ARCHIVE_COUNT:
        raise ExcludedArchiveInventoryInputError("required excluded archive count changed")
    inventory_evidence = manifest.get("inventoryEvidenceSHA256")
    preservation_policy = manifest.get("preservationPolicySHA256")
    if not _is_sha256(inventory_evidence):
        blockers.append("inventory_evidence_missing_or_invalid")
    if not _is_sha256(preservation_policy):
        blockers.append("preservation_policy_missing_or_invalid")
    if inventory_evidence == preservation_policy and _is_sha256(inventory_evidence):
        raise ExcludedArchiveInventoryInputError("inventory and preservation evidence must be distinct")

    entries = manifest.get("excludedArchives")
    if not isinstance(entries, list):
        blockers.append("excluded_archive_inventory_missing")
        entries = []
    if len(entries) != REQUIRED_ARCHIVE_COUNT:
        blockers.append("excluded_archive_count_mismatch")

    canonical_entries: list[dict[str, Any]] = []
    opaque_refs: list[str] = []
    evidence_hashes: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ExcludedArchiveInventoryInputError(f"excluded archive entry {index} is not an object")
        if set(entry) != ENTRY_FIELDS:
            raise ExcludedArchiveInventoryInputError(f"excluded archive entry {index} fields changed")
        opaque_ref = entry.get("opaqueArchiveRef")
        if not _is_opaque(opaque_ref):
            blockers.append(f"excluded_archive_{index}_opaque_ref_missing_or_invalid")
        else:
            opaque_refs.append(opaque_ref)
        for field in ("presenceEvidenceSHA256", "preservationEvidenceSHA256"):
            digest = entry.get(field)
            if not _is_sha256(digest):
                blockers.append(f"excluded_archive_{index}_{field}_missing_or_invalid")
            else:
                evidence_hashes.append(digest)
        for field, expected in SAFE_ENTRY_POLICY.items():
            if entry.get(field) != expected:
                raise ExcludedArchiveInventoryInputError(
                    f"unsafe excluded archive inventory policy at entry {index}: {field}"
                )
        canonical_entries.append({key: entry.get(key) for key in sorted(ENTRY_FIELDS)})

    if len(opaque_refs) != len(set(opaque_refs)):
        raise ExcludedArchiveInventoryInputError("excluded archive opaque references must be unique")
    if len(evidence_hashes) != len(set(evidence_hashes)):
        raise ExcludedArchiveInventoryInputError("excluded archive evidence hashes must be unique")
    top_hashes = [value for value in (inventory_evidence, preservation_policy) if _is_sha256(value)]
    if set(top_hashes) & set(evidence_hashes):
        raise ExcludedArchiveInventoryInputError("top-level and per-archive evidence hashes must be distinct")

    blockers = sorted(set(blockers))
    canonical = {
        "releaseRef": release_ref,
        "requiredArchiveCount": required_count,
        "inventoryEvidenceSHA256": inventory_evidence,
        "preservationPolicySHA256": preservation_policy,
        "excludedArchives": sorted(canonical_entries, key=lambda item: str(item.get("opaqueArchiveRef"))),
    }
    digest = hashlib.sha256(_canonical_bytes(canonical)).hexdigest()
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "requiredArchiveCount": REQUIRED_ARCHIVE_COUNT,
        "reconciledArchiveCount": len(entries),
        "excludedArchiveInventoryDigest": digest,
        **SAFE_ARTIFACT_POLICY,
        "inventoryReconciled": not blockers,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise ExcludedArchiveInventoryInputError(
            "excluded archive inventory is incomplete: " + ", ".join(preflight["blockers"])
        )
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "requiredArchiveCount": REQUIRED_ARCHIVE_COUNT,
        "reconciledArchiveCount": REQUIRED_ARCHIVE_COUNT,
        "excludedArchiveInventoryDigest": preflight["excludedArchiveInventoryDigest"],
        **SAFE_ARTIFACT_POLICY,
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
            raise ExcludedArchiveInventoryInputError("committed partial facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
