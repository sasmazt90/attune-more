#!/usr/bin/env python3
"""Build a privacy-safe selected-source archive hash registry.

The private input stays outside Git.  It contains only opaque archive IDs,
immutable SHA-256 values, and SHA-256 values for previously-authorized hash
evidence.  The public artifact contains no archive names, paths, URLs, or raw
archive hashes.  An incomplete manifest produces a blocked preflight, never a
release artifact.

This tool intentionally does not open or hash excluded archives.  Their only
allowed relationship to this registry is a reviewed, empty overlap list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "source-archive-hash-registry-input-v1"
PREFLIGHT_METHOD = "source-archive-hash-registry-preflight-v1"
ARTIFACT_METHOD = "source-archive-hash-registry-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEY_PARTS = (
    "name",
    "filename",
    "path",
    "uri",
    "url",
    "bucket",
    "objectkey",
    "object_key",
    "localfile",
    "local_file",
)
SAFE_POLICY_KEYS = {"publicNamesOrPathsAllowed"}


class RegistryInputError(ValueError):
    """Raised when private input violates preservation or privacy policy."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _reject_forbidden_keys(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "").replace(" ", "")
            if key not in SAFE_POLICY_KEYS and any(
                part.replace("_", "") in normalized for part in FORBIDDEN_KEY_PARTS
            ):
                raise RegistryInputError(f"{location} contains a forbidden name/path/URL field")
            _reject_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{location}[{index}]")


def _policy_guard(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["policy_missing"]
    required = {
        "privateManifestOutsideGit": True,
        "publicNamesOrPathsAllowed": False,
        "excludedArchiveAccessAllowed": False,
        "excludedArchiveHashRecomputationAllowed": False,
    }
    blockers: list[str] = []
    for field, expected in required.items():
        value = policy.get(field)
        if value is None:
            blockers.append(f"policy_{field}_missing")
        elif value != expected:
            raise RegistryInputError(f"unsafe policy value: {field}")
    return blockers


def evaluate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a private manifest and return a blocked-or-ready preflight."""
    if not isinstance(manifest, dict):
        raise RegistryInputError("manifest must be a JSON object")
    _reject_forbidden_keys(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise RegistryInputError("manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise RegistryInputError("input method changed")

    blockers = _policy_guard(manifest.get("policy"))
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    if not _is_opaque(registry_ref):
        blockers.append("source_registry_ref_missing_or_invalid")

    review = manifest.get("review")
    expected_count: int | None = None
    if not isinstance(review, dict):
        blockers.append("review_missing")
    else:
        raw_count = review.get("selectedArchiveCountExpected")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 1:
            blockers.append("selected_archive_count_expected_missing")
        else:
            expected_count = raw_count
        if review.get("allSelectedArchivesEnumerated") is not True:
            blockers.append("selected_archive_inventory_incomplete")
        if review.get("reviewerAuthorizationConfirmed") is not True:
            blockers.append("authorized_hash_review_incomplete")

    entries = manifest.get("selectedArchives", [])
    if not isinstance(entries, list):
        raise RegistryInputError("selectedArchives must be a list")
    if not entries:
        blockers.append("selected_archive_registry_empty")

    opaque_ids: list[str] = []
    archive_hashes: list[str] = []
    evidence_hashes: list[str] = []
    canonical_entries: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RegistryInputError(f"selected archive {index} must be an object")
        allowed = {
            "opaqueId",
            "archiveSHA256",
            "authorizedPriorHashEvidenceSHA256",
            "hashVerifiedAgainstAuthorizedPriorEvidence",
            "selectedForResearch",
            "excludedArchive",
        }
        if set(entry) - allowed:
            raise RegistryInputError(f"selected archive {index} contains unsupported fields")
        opaque_id = entry.get("opaqueId")
        archive_hash = entry.get("archiveSHA256")
        evidence_hash = entry.get("authorizedPriorHashEvidenceSHA256")
        if not _is_opaque(opaque_id):
            blockers.append(f"selected_archive_{index}_opaque_id_invalid")
        if not _is_sha256(archive_hash):
            blockers.append(f"selected_archive_{index}_sha256_invalid")
        if not _is_sha256(evidence_hash):
            blockers.append(f"selected_archive_{index}_evidence_sha256_invalid")
        if entry.get("hashVerifiedAgainstAuthorizedPriorEvidence") is not True:
            blockers.append(f"selected_archive_{index}_hash_unverified")
        if entry.get("selectedForResearch") is not True:
            blockers.append(f"selected_archive_{index}_not_selected")
        if entry.get("excludedArchive") is not False:
            raise RegistryInputError("an excluded archive cannot enter the selected-source registry")
        if _is_opaque(opaque_id):
            opaque_ids.append(opaque_id)
        if _is_sha256(archive_hash):
            archive_hashes.append(archive_hash)
        if _is_sha256(evidence_hash):
            evidence_hashes.append(evidence_hash)
        if _is_opaque(opaque_id) and _is_sha256(archive_hash) and _is_sha256(evidence_hash):
            canonical_entries.append({
                "opaqueId": opaque_id,
                "archiveSHA256": archive_hash,
                "authorizedPriorHashEvidenceSHA256": evidence_hash,
            })

    if len(opaque_ids) != len(set(opaque_ids)):
        raise RegistryInputError("selected archive opaque IDs must be unique")
    if len(archive_hashes) != len(set(archive_hashes)):
        raise RegistryInputError("selected archive hashes must be unique")
    if len(evidence_hashes) != len(set(evidence_hashes)):
        raise RegistryInputError("authorized prior evidence hashes must be unique")
    if expected_count is not None and len(entries) != expected_count:
        blockers.append("selected_archive_count_mismatch")

    overlap = manifest.get("excludedArchiveHashOverlap")
    if overlap is None:
        blockers.append("excluded_archive_overlap_review_missing")
    elif not isinstance(overlap, list):
        raise RegistryInputError("excludedArchiveHashOverlap must be a list")
    elif overlap:
        raise RegistryInputError("selected-source hashes overlap an excluded archive")

    blockers = sorted(set(blockers))
    ready = not blockers
    registry_digest = None
    if canonical_entries:
        registry_digest = hashlib.sha256(
            _canonical_bytes(sorted(canonical_entries, key=lambda item: item["opaqueId"]))
        ).hexdigest()
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "selectedArchiveCount": len(entries),
        "registryDigest": registry_digest,
        "containsArchiveNamesOrPaths": False,
        "excludedArchivesPresent": False,
        "excludedArchiveHashesRecomputed": False,
        "readyForReleaseArtifact": ready,
        "decision": "ready" if ready else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the exact public v1 artifact only for a complete safe manifest."""
    preflight = evaluate_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise RegistryInputError("hash registry is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "selectedArchiveCount": preflight["selectedArchiveCount"],
        "registryDigest": preflight["registryDigest"],
        "allArchiveHashesVerified": True,
        "containsArchiveNamesOrPaths": False,
        "excludedArchivesPresent": False,
        "excludedArchiveHashesRecomputed": False,
        "verificationBasis": "authorized-prior-hash-evidence",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True, help="private input; keep outside Git")
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    preflight = evaluate_manifest(manifest)
    _write_json(args.preflight_output, preflight)
    if args.artifact_output is not None:
        artifact = build_release_artifact(manifest)
        _write_json(args.artifact_output, artifact)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
