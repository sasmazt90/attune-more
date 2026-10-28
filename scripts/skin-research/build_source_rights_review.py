#!/usr/bin/env python3
"""Build a privacy-safe selected-source rights review artifact.

The committed mapping code records publisher declarations, while explicitly
stating that those declarations are not proof of every individual image's
rights.  This builder keeps that honest boundary.  A public current-facts
receipt can only produce a blocked preflight.  The exact
``source-rights-review-v1`` artifact can be emitted only from a private,
opaque, archive-by-archive manifest with individual-image review complete.

Names, paths, URLs, raw rights documents and reviewer identities are neither
accepted by the private manifest nor emitted by the public artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "source-rights-review-input-v1"
CURRENT_FACTS_METHOD = "source-rights-review-current-facts-v1"
PREFLIGHT_METHOD = "source-rights-review-preflight-v1"
ARTIFACT_METHOD = "source-rights-review-v1"
SELECTED_SOURCES_BLOB = "cfd24d16f86f3437dd3b1d925053cc7ebe543399"
EXPANDED_SOURCES_BLOB = "8771f1aed674f1c7f554dcb6fa539b20c7696f38"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "archive", "archiveName",
    "archivePath", "licenseText", "rightsDocument", "rightsDocuments",
    "document", "documents", "reviewer", "reviewerId", "reviewerName",
    "person", "personId", "email", "phone", "image", "images",
}


class RightsInputError(ValueError):
    """Raised when rights evidence violates privacy or release policy."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RightsInputError(f"{field} must be a nonnegative integer")
    return value


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise RightsInputError(f"{location} contains a private name/path/document field")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_current_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Replay the exact mapping facts without claiming a completed review."""
    if not isinstance(facts, dict):
        raise RightsInputError("current facts must be a JSON object")
    if facts.get("schemaVersion") != 1 or facts.get("methodVersion") != CURRENT_FACTS_METHOD:
        raise RightsInputError("current facts identity changed")
    blobs = facts.get("mappingGitBlobs")
    expected_blobs = {
        "selectedSources": SELECTED_SOURCES_BLOB,
        "expandedSources": EXPANDED_SOURCES_BLOB,
    }
    if blobs != expected_blobs or any(GIT_BLOB_RE.fullmatch(value) is None for value in blobs.values()):
        raise RightsInputError("mapping source blob identity changed")
    expected_count = facts.get("selectedArchiveCountExpected")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
        raise RightsInputError("selected archive count is invalid")
    required = {
        "publisherDeclarationPresent": True,
        "publisherDeclarationUsedAsIndividualImageRightsProof": False,
        "individualImageRightsReviewed": False,
        "unverifiedStockMarkersExcluded": True,
        "expandedSourceStatesDeclarationIsNotIndividualRightsProof": True,
        "excludedArchivesAccessed": False,
        "excludedArchiveInventoryReconciled": False,
    }
    for field, expected in required.items():
        if facts.get(field) != expected:
            raise RightsInputError(f"current rights fact changed: {field}")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": None,
        "sourceRegistryRef": None,
        "selectedArchiveCountExpected": expected_count,
        "selectedArchiveCount": 0,
        "allSelectedArchivesReviewed": False,
        "allIndividualImageRightsReviewed": False,
        "unresolvedRightsCount": None,
        "publisherDeclarationUsedAsIndividualImageRightsProof": False,
        "excludedArchivesAccessed": False,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "excluded_archive_inventory_unreconciled",
            "individual_image_rights_review_incomplete",
            "publisher_declaration_is_not_individual_image_rights_proof",
            "selected_archive_rights_registry_incomplete",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque private manifest and return a public preflight."""
    if not isinstance(manifest, dict):
        raise RightsInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise RightsInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise RightsInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    if not _is_opaque(registry_ref):
        blockers.append("source_registry_ref_missing_or_invalid")

    expected_count = manifest.get("selectedArchiveCountExpected")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
        expected_count = None
        blockers.append("selected_archive_count_expected_missing")

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        blockers.append("rights_policy_missing")
    else:
        required_policy = {
            "privateManifestOutsideGit": True,
            "publicNamesOrPathsAllowed": False,
            "rawRightsDocumentsCommitted": False,
            "reviewerIdentityAllowed": False,
            "excludedArchiveAccessAllowed": False,
            "publisherDeclarationAcceptedAsIndividualImageProof": False,
        }
        if set(policy) - set(required_policy):
            raise RightsInputError("rights policy contains unsupported fields")
        for field, expected in required_policy.items():
            value = policy.get(field)
            if value is None:
                blockers.append(f"policy_{field}_missing")
            elif value != expected:
                raise RightsInputError(f"unsafe rights policy: {field}")

    entries = manifest.get("selectedArchives", [])
    if not isinstance(entries, list):
        raise RightsInputError("selectedArchives must be a list")
    if not entries:
        blockers.append("selected_archive_rights_registry_empty")
    if expected_count is not None and len(entries) != expected_count:
        blockers.append("selected_archive_count_mismatch")

    opaque_ids: list[str] = []
    evidence_hashes: list[str] = []
    canonical: list[dict[str, Any]] = []
    unresolved_total = 0
    true_fields = (
        "archiveRightsReviewed",
        "allIndividualImageRightsReviewed",
        "researchTrainingUseAllowed",
        "modelEvaluationUseAllowed",
        "productInferenceUseAllowed",
        "derivativeArtifactsAllowed",
        "reviewerAuthorizationConfirmed",
    )
    false_fields = (
        "excludedArchive",
        "excludedArchiveAccessed",
        "containsUnverifiedStockSource",
        "publisherDeclarationUsedAsIndividualImageRightsProof",
    )
    allowed = {
        "opaqueId", "rightsEvidenceSHA256", "unresolvedRightsCount",
        *true_fields, *false_fields,
    }
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RightsInputError(f"selected archive {index} must be an object")
        if set(entry) - allowed:
            raise RightsInputError(f"selected archive {index} contains unsupported fields")
        opaque_id = entry.get("opaqueId")
        evidence_hash = entry.get("rightsEvidenceSHA256")
        if not _is_opaque(opaque_id):
            blockers.append(f"selected_archive_{index}_opaque_id_invalid")
        if not _is_sha256(evidence_hash):
            blockers.append(f"selected_archive_{index}_evidence_sha256_invalid")
        unresolved = _nonnegative_int(entry.get("unresolvedRightsCount"), f"selected archive {index} unresolvedRightsCount")
        unresolved_total += unresolved
        if unresolved != 0:
            blockers.append(f"selected_archive_{index}_unresolved_rights_present")
        for field in true_fields:
            if entry.get(field) is not True:
                blockers.append(f"selected_archive_{index}_{field}_incomplete")
        for field in false_fields:
            value = entry.get(field)
            if value is not False:
                if field in ("excludedArchive", "excludedArchiveAccessed") and value is True:
                    raise RightsInputError("excluded archives cannot enter or be accessed by the rights review")
                if field == "publisherDeclarationUsedAsIndividualImageRightsProof" and value is True:
                    raise RightsInputError("publisher declaration cannot substitute for individual-image rights review")
                blockers.append(f"selected_archive_{index}_{field}_unsafe_or_missing")
        if _is_opaque(opaque_id):
            opaque_ids.append(opaque_id)
        if _is_sha256(evidence_hash):
            evidence_hashes.append(evidence_hash)
        if _is_opaque(opaque_id) and _is_sha256(evidence_hash):
            canonical.append({
                "opaqueId": opaque_id,
                "rightsEvidenceSHA256": evidence_hash,
                "unresolvedRightsCount": unresolved,
            })
    if len(opaque_ids) != len(set(opaque_ids)):
        raise RightsInputError("selected archive opaque IDs must be unique")
    if len(evidence_hashes) != len(set(evidence_hashes)):
        raise RightsInputError("rights evidence hashes must be unique")
    blockers = sorted(set(blockers))
    digest = hashlib.sha256(_canonical_bytes(sorted(canonical, key=lambda item: item["opaqueId"]))).hexdigest() if canonical else None
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "selectedArchiveCount": len(entries),
        "rightsRegistryDigest": digest,
        "allSelectedArchivesReviewed": not blockers,
        "allIndividualImageRightsReviewed": not blockers,
        "unresolvedRightsCount": unresolved_total,
        "publisherDeclarationUsedAsIndividualImageRightsProof": False,
        "excludedArchivesAccessed": False,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise RightsInputError("rights review is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "selectedArchiveCount": preflight["selectedArchiveCount"],
        "rightsRegistryDigest": preflight["rightsRegistryDigest"],
        "allSelectedArchivesReviewed": True,
        "allIndividualImageRightsReviewed": True,
        "unresolvedRightsCount": 0,
        "publisherDeclarationUsedAsIndividualImageRightsProof": False,
        "excludedArchivesAccessed": False,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--current-facts", type=Path)
    source.add_argument("--private-manifest", type=Path)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if args.current_facts is not None:
        facts = json.loads(args.current_facts.read_text(encoding="utf-8"))
        preflight = summarize_current_facts(facts)
        if args.artifact_output is not None:
            raise RightsInputError("committed incomplete rights facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
