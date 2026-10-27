#!/usr/bin/env python3
"""Privacy-safe, fail-closed reconciliation for four user-excluded archives.

The public receipt never needs archive names or paths.  A private reviewer can
provide four opaque IDs plus immutable SHA-256 values; the gate only confirms
that all four remain excluded, unaccessed, unmodified, unuploaded and unused.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_ARCHIVES = 4
EXPECTED_INPUT_BLOBS = {
    "scripts/skin-research/selected_sources.py": "cfd24d16f86f3437dd3b1d925053cc7ebe543399",
    "scripts/skin-research/expanded_sources.py": "8771f1aed674f1c7f554dcb6fa539b20c7696f38",
    "scripts/skin-research/audit_roadmap_archives.py": "1881a2eeda8601f9412b11f030cd91ad795c8c3d",
    "docs/skin/evidence/archive-audit-20261023-v2.json": "3ed68674ccbab66cd7e7116c2f553535e4312a42",
    "docs/skin/archive-audit-20261023.md": "1a353acfbdda52416c69c0c3f63a9f1ac224b73e",
    "docs/skin/evidence/source-mapping-release-receipt-20261025-v1.json": "4dac40cb1bcc0d99e5dc2dff88566b9609070567",
    "docs/skin/evidence/source-mapping-release-gate-20261025-v1.json": "30db08a5d2c3db9bdeb22ea8996c806c8ffcbed6",
}
OPAQUE_ID = re.compile(r"excluded-[0-9a-f]{12}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN_ENTRY_KEYS = {"name", "filename", "path", "uri", "url", "archive"}


class ReconciliationError(ValueError):
    """Raised when an inventory violates privacy or preservation policy."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise ReconciliationError(message)


def evaluate_inventory(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "pinned source evidence changed")
    policy = receipt.get("policy", {})
    _require(policy.get("requiredArchiveCount"), REQUIRED_ARCHIVES, "exactly four excluded archives are required")
    _require(policy.get("publicNamesOrPathsAllowed"), False, "archive names or paths must remain private")
    _require(policy.get("archiveAccessAllowed"), False, "excluded archives cannot be accessed")
    _require(policy.get("archiveMutationAllowed"), False, "excluded archives cannot be mutated")
    _require(policy.get("uploadAllowed"), False, "excluded archives cannot be uploaded")
    _require(policy.get("trainingUseAllowed"), False, "excluded archives cannot be used for training")
    _require(policy.get("productTruthUseAllowed"), False, "excluded archives cannot become product truth")

    public = receipt.get("publicReference", {})
    _require(public.get("mappingScriptReferenceCount"), 3, "mapping-script reference count changed")
    _require(public.get("requiredArchiveCount"), REQUIRED_ARCHIVES, "public required count changed")
    _require(public.get("publicReferenceIsCompleteInventory"), False, "three references cannot become four-archive proof")

    candidate = receipt.get("privateInventoryCandidate", {})
    entries = candidate.get("entries", [])
    if not isinstance(entries, list):
        raise ReconciliationError("inventory entries must be a list")
    ids: list[str] = []
    hashes: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReconciliationError("inventory entry must be an object")
        forbidden = FORBIDDEN_ENTRY_KEYS.intersection(entry)
        if forbidden:
            raise ReconciliationError("public inventory cannot contain archive names, paths or URLs")
        opaque_id = entry.get("opaqueId")
        digest = entry.get("archiveSHA256")
        if not isinstance(opaque_id, str) or not OPAQUE_ID.fullmatch(opaque_id):
            raise ReconciliationError("opaque archive ID is invalid")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ReconciliationError("archive SHA-256 is invalid")
        _require(entry.get("disposition"), "user_excluded", "archive disposition changed")
        for field in ("accessed", "mutated", "uploaded", "usedForTraining", "usedForProductTruth"):
            _require(entry.get(field), False, f"excluded archive {field} must remain false")
        ids.append(opaque_id)
        hashes.append(digest)
    if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
        raise ReconciliationError("excluded archive identities and hashes must be unique")

    overlap = candidate.get("selectedSourceHashOverlap", [])
    if overlap:
        raise ReconciliationError("excluded archive hash overlaps a selected source")
    complete = candidate.get("completePrivateInventoryReviewed") is True
    count_ok = len(entries) == REQUIRED_ARCHIVES
    blockers = []
    if not count_ok:
        blockers.append("four_opaque_archive_hashes_not_recorded")
    if not complete:
        blockers.append("private_inventory_review_incomplete")
    reconciled = count_ok and complete
    return {
        "schemaVersion": 1,
        "methodVersion": "excluded-archive-inventory-reconciliation-v1",
        "requiredArchiveCount": REQUIRED_ARCHIVES,
        "candidateArchiveCount": len(entries),
        "publicNamesOrPathsStored": False,
        "preservationPolicyEnforced": True,
        "inventoryReconciled": reconciled,
        "sourceReleaseContributionAllowed": reconciled,
        "blockers": blockers,
        "decision": "ready" if reconciled else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_inventory(json.loads(args.receipt.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
