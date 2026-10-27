#!/usr/bin/env python3
"""Fail-closed provider dataset gate for the regional skin-map candidate.

The mutable Roboflow project is not itself an immutable training candidate.
This gate accepts only a version 2 or later that exactly reproduces the
reviewed, source/person-group-locked 337-record manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "regional-provider-dataset-release-receipt-v1"
PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
PROJECT_TYPE = "instance-segmentation"
MANIFEST_BLOB_SHA = "088c38a2e8802fedc14486cf0b873225774b82f4"
QUEUE_SHA256 = "f516efb71509111bd55e079bcbb8b2a897e5c00b5c8416668f18af3e247698a5"
DECISIONS_SHA256 = "41702f492a41c72e15764288c9c0da7b9a2c43cb2c619cdb851a5098fc67ced1"
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


def _candidate_version_ready(candidate: Any) -> tuple[bool, list[str]]:
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
        "manifestBlobSHA": MANIFEST_BLOB_SHA,
        "queueItemsSHA256": QUEUE_SHA256,
        "reviewDecisionsSHA256": DECISIONS_SHA256,
        "sourcePersonCoverageComplete": True,
        "crossSplitGroupCount": 0,
        "allRecordsAssignedExactlyOnce": True,
        "finalTestUsedForSelectionOrThresholds": False,
    }
    if any(candidate.get(field) != value for field, value in expected.items()):
        blockers.append("exact_group_locked_provider_version_unconfirmed")
    return not blockers, blockers


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("schemaVersion"), SCHEMA, "receipt schema changed")
    manifest = receipt.get("groupLockedManifest", {})
    _require(manifest.get("blobSHA"), MANIFEST_BLOB_SHA, "group-locked manifest changed")
    _require(manifest.get("queueItemsSHA256"), QUEUE_SHA256, "review queue binding changed")
    _require(manifest.get("reviewDecisionsSHA256"), DECISIONS_SHA256, "review decisions binding changed")
    _require(manifest.get("records"), TARGET_SPLITS, "group-locked record split changed")
    _require(manifest.get("annotations"), TARGET_ANNOTATIONS, "group-locked annotation split changed")
    _require(manifest.get("crossSplitGroupCount"), 0, "group-locked manifest contains split leakage")
    _require(manifest.get("allRecordsAssignedExactlyOnce"), True, "group-locked manifest is incomplete")

    project_drift = _validate_snapshot(receipt)
    version_ready, blockers = _candidate_version_ready(receipt.get("candidateVersion"))
    if project_drift and not version_ready:
        blockers.extend([
            "mutable_provider_project_drifted_from_group_locked_candidate",
            "post_upload_records_require_quarantine_or_verified_version_exclusion",
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
        "schemaVersion": 1,
        "methodVersion": "regional-provider-dataset-release-gate-v1",
        "project": PROJECT_ID,
        "mutableProjectDriftDetected": project_drift,
        "groupLockedManifestVerified": True,
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
    result = evaluate_release(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
