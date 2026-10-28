#!/usr/bin/env python3
"""Fail-closed provider dataset gate for the regional skin-map candidate.

The mutable Roboflow project is not itself an immutable training candidate.
This gate accepts only a version 2 or later that exactly reproduces the
reviewed, source/person-group-locked 337-record manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "regional-provider-dataset-release-receipt-v3"
PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
PROJECT_TYPE = "instance-segmentation"
MANIFEST_PATH = "docs/skin/evidence/regional-mask-group-locked-split-20261027-v1.json"
MANIFEST_BLOB_SHA = "088c38a2e8802fedc14486cf0b873225774b82f4"
MANIFEST_FILE_SHA256 = "d698580acae5c2987392e170bd408d626ad0ba685f4c49f5899c7bef46b967ce"
ASSIGNMENTS_SHA256 = "2a8608d2f74fbf3e64fca53b60334a64add9c47f0301766dc47c9ca2fe651e3c"
QUEUE_SHA256 = "f516efb71509111bd55e079bcbb8b2a897e5c00b5c8416668f18af3e247698a5"
DECISIONS_SHA256 = "41702f492a41c72e15764288c9c0da7b9a2c43cb2c619cdb851a5098fc67ced1"
AUDIT_SCHEMA = "regional-provider-version-export-audit-v1"
POST_UPLOAD_AUDIT_SCHEMA = "regional-post-upload-provenance-audit-v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TARGET_IMAGES = 337
TARGET_SPLITS = {"train": 236, "valid": 50, "test": 51}
TARGET_ANNOTATIONS = {
    "train": {"Oily": 719, "Redness": 394},
    "valid": {"Oily": 157, "Redness": 110},
    "test": {"Oily": 189, "Redness": 67},
}
TARGET_CLASS_TOTALS = {"Oily": 1065, "Redness": 571}


class GateInputError(ValueError):
    """Raised when provider observations or immutable bindings are invalid."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _load_evidence(identity: Any, label: str, evidence_root: Path) -> dict[str, Any]:
    if not isinstance(identity, dict):
        raise GateInputError(f"{label} evidence identity missing")
    path = identity.get("path")
    digest = identity.get("sha256")
    if not isinstance(path, str) or not path.startswith("docs/skin/evidence/"):
        raise GateInputError(f"{label} evidence path missing")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None or digest == "0" * 64:
        raise GateInputError(f"{label} evidence sha256 missing")
    file_path = evidence_root / path
    if not file_path.is_file():
        raise GateInputError(f"{label} evidence file missing")
    if hashlib.sha256(file_path.read_bytes()).hexdigest() != digest:
        raise GateInputError(f"{label} evidence digest mismatch")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateInputError(f"{label} evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GateInputError(f"{label} evidence must be a JSON object")
    return payload


def _validate_snapshot(receipt: dict[str, Any]) -> bool:
    project = receipt.get("providerProject", {})
    _require(project.get("id"), PROJECT_ID, "regional project identity changed")
    _require(project.get("type"), PROJECT_TYPE, "regional project type changed")
    _require(project.get("public"), False, "regional project must remain private")
    images = project.get("images")
    splits = project.get("splits")
    classes = project.get("classes")
    if not isinstance(images, int) or isinstance(images, bool) or images < 0:
        raise GateInputError("provider image count is invalid")
    if not isinstance(splits, dict) or sum(splits.values()) != images:
        raise GateInputError("provider split counts do not cover the project")
    if not isinstance(classes, dict) or set(classes) != set(TARGET_CLASS_TOTALS):
        raise GateInputError("provider class inventory is invalid")

    upload = receipt.get("upload", {})
    _require(upload.get("status"), "completed", "provider upload is not terminal")
    for field in ("uploaded", "duplicates", "annotated", "errors", "warnings", "failedChunks"):
        value = upload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise GateInputError(f"upload {field} is invalid")
    _require(upload["errors"], 0, "provider upload has errors")
    _require(upload["warnings"], 0, "provider upload has warnings")
    _require(upload["failedChunks"], 0, "provider upload has failed chunks")
    _require(upload["uploaded"] + upload["duplicates"], TARGET_IMAGES, "upload did not process 337 source records")
    _require(upload["annotated"], TARGET_IMAGES, "upload did not report 337 annotations")

    new_records = receipt.get("postUploadRecords", {})
    _require(new_records.get("records"), upload["uploaded"], "post-upload record count does not match upload")
    new_splits = new_records.get("splits")
    new_annotations = new_records.get("annotations")
    if not isinstance(new_splits, dict) or sum(new_splits.values()) != new_records["records"]:
        raise GateInputError("post-upload split counts are invalid")
    if not isinstance(new_annotations, dict) or set(new_annotations) != set(TARGET_CLASS_TOTALS):
        raise GateInputError("post-upload annotation counts are invalid")
    _require(project["images"], TARGET_IMAGES + new_records["records"], "project growth does not match post-upload records")
    return (
        project["images"] != TARGET_IMAGES
        or project["splits"] != TARGET_SPLITS
        or project["classes"] != TARGET_CLASS_TOTALS
    )


def _validate_post_upload_provenance(receipt: dict[str, Any], evidence_root: Path) -> None:
    audit = _load_evidence(
        receipt.get("postUploadProvenanceAudit"),
        "post-upload provenance audit",
        evidence_root,
    )
    expected = {
        "schemaVersion": POST_UPLOAD_AUDIT_SCHEMA,
        "project": PROJECT_ID,
        "uploadTaskId": receipt.get("upload", {}).get("taskId"),
        "selectedRecords": receipt.get("postUploadRecords", {}).get("records"),
        "membershipClassification": "unverified_until_exact_provider_export",
        "contentIdentityEstablished": False,
        "annotationIdentityEstablished": False,
        "tagEstablishesUnwantedMembership": False,
        "tagBasedDeletionOrVersionExclusionAllowed": False,
        "exactProviderExportAuditRequired": True,
        "containsFilenamesOrProviderImageIds": False,
    }
    if any(audit.get(field) != value for field, value in expected.items()):
        raise GateInputError("post-upload provenance audit mismatch")


def _candidate_version_ready(candidate: Any, evidence_root: Path) -> tuple[bool, list[str]]:
    if candidate is None:
        return False, ["provider_version_2_missing"]
    if not isinstance(candidate, dict):
        raise GateInputError("candidateVersion must be an object or null")
    blockers: list[str] = []
    version = candidate.get("versionNumber")
    if not isinstance(version, int) or isinstance(version, bool) or version < 2:
        blockers.append("provider_version_2_missing")
    expected = {
        "images": TARGET_IMAGES,
        "splits": TARGET_SPLITS,
        "annotations": TARGET_ANNOTATIONS,
        "classTotals": TARGET_CLASS_TOTALS,
    }
    if any(candidate.get(field) != value for field, value in expected.items()):
        blockers.append("exact_group_locked_provider_version_unconfirmed")
    audit = _load_evidence(candidate.get("exportAudit"), "provider version export audit", evidence_root)
    _require(audit.get("schemaVersion"), AUDIT_SCHEMA, "provider version export audit schema changed")
    audit_expected = {
        "project": PROJECT_ID,
        "projectType": PROJECT_TYPE,
        "public": False,
        "versionNumber": version,
        "images": TARGET_IMAGES,
        "splits": TARGET_SPLITS,
        "annotations": TARGET_ANNOTATIONS,
        "classTotals": TARGET_CLASS_TOTALS,
        "manifestFileSHA256": MANIFEST_FILE_SHA256,
        "assignmentsSHA256": ASSIGNMENTS_SHA256,
        "recordIdentityBasis": "image-content-sha256",
        "allProviderRecordsMatchedManifestOnce": True,
        "unexpectedProviderRecords": 0,
        "missingManifestRecords": 0,
        "crossSplitContentHashCount": 0,
        "sourcePersonCoverageComplete": True,
        "crossSplitGroupCount": 0,
        "finalTestUsedForSelectionOrThresholds": False,
        "containsFilenamesOrProviderImageIds": False,
    }
    if any(audit.get(field) != value for field, value in audit_expected.items()):
        blockers.append("provider_export_audit_mismatch")
    for field in ("exportArchiveSHA256",):
        digest = audit.get(field)
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None or digest == "0" * 64:
            blockers.append("provider_export_audit_mismatch")
    for field in ("splitImageContentSetSHA256", "splitRecordAnnotationSetSHA256"):
        split_digests = audit.get(field)
        if not isinstance(split_digests, dict) or set(split_digests) != set(TARGET_SPLITS):
            blockers.append("provider_export_audit_mismatch")
        elif any(
            not isinstance(value, str)
            or SHA256.fullmatch(value) is None
            or value == "0" * 64
            for value in split_digests.values()
        ):
            blockers.append("provider_export_audit_mismatch")
    return not blockers, blockers


def evaluate_release(receipt: dict[str, Any], evidence_root: Path = ROOT) -> dict[str, Any]:
    _require(receipt.get("schemaVersion"), SCHEMA, "receipt schema changed")
    manifest = receipt.get("groupLockedManifest", {})
    _require(manifest.get("path"), MANIFEST_PATH, "group-locked manifest path changed")
    _require(manifest.get("blobSHA"), MANIFEST_BLOB_SHA, "group-locked manifest changed")
    _require(manifest.get("sha256"), MANIFEST_FILE_SHA256, "group-locked manifest digest changed")
    _require(manifest.get("assignmentsSHA256"), ASSIGNMENTS_SHA256, "group-locked assignments changed")
    _require(manifest.get("queueItemsSHA256"), QUEUE_SHA256, "review queue binding changed")
    _require(manifest.get("reviewDecisionsSHA256"), DECISIONS_SHA256, "review decisions binding changed")
    _require(manifest.get("records"), TARGET_SPLITS, "group-locked record split changed")
    _require(manifest.get("annotations"), TARGET_ANNOTATIONS, "group-locked annotation split changed")
    _require(manifest.get("crossSplitGroupCount"), 0, "group-locked manifest contains split leakage")
    _require(manifest.get("allRecordsAssignedExactlyOnce"), True, "group-locked manifest is incomplete")

    _validate_post_upload_provenance(receipt, evidence_root)
    project_drift = _validate_snapshot(receipt)
    version_ready, blockers = _candidate_version_ready(receipt.get("candidateVersion"), evidence_root)
    if project_drift and not version_ready:
        blockers.extend([
            "mutable_provider_project_drifted_from_group_locked_candidate",
            "mutable_provider_membership_requires_exact_export_audit",
        ])

    prerequisites = receipt.get("releasePrerequisites", {})
    for field, reason in (
        ("rightsReviewed", "rights_review_missing"),
        ("expertSemanticMaskProtocolAccepted", "expert_semantic_mask_protocol_not_accepted"),
        ("independentPhysicalCameraHoldoutReserved", "independent_physical_camera_holdout_missing"),
    ):
        if prerequisites.get(field) is not True:
            blockers.append(reason)

    provider_dataset_ready = version_ready
    training_authorized = provider_dataset_ready and not blockers
    blockers = list(dict.fromkeys(blockers))
    return {
        "schemaVersion": 3,
        "methodVersion": "regional-provider-dataset-release-gate-v3",
        "project": PROJECT_ID,
        "mutableProjectDriftDetected": project_drift,
        "groupLockedManifestVerified": True,
        "postUploadProvenanceVerified": True,
        "tagBasedExclusionAuthorized": False,
        "providerVersionReady": provider_dataset_ready,
        "trainingAuthorized": training_authorized,
        "finalTestAuthorized": False,
        "activationAllowed": False,
        "roadmapAccepted": False,
        "blockers": blockers,
        "decision": "ready_for_one_preregistered_training" if training_authorized else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = evaluate_release(receipt, args.receipt.resolve().parents[3])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
