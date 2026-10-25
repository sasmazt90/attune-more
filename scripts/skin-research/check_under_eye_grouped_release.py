#!/usr/bin/env python3
"""Fail-closed release gate for the grouped under-eye research dataset.

The gate separates four operations that must never be conflated:
archive upload, dataset-version generation, research training and product
activation. A locally reproducible archive is not upload authorization when
its digest differs from the explicitly authorized digest. An empty project is
not a generated dataset, and a finished research model is not product proof.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_SOURCE = {
    "images": 399,
    "annotations": 869,
    "splits": {"train": 279, "valid": 81, "test": 39},
    "classCounts": {"darkcircle": 382, "eyebag": 487},
}
EXPECTED_GROUPED = {
    "images": 399,
    "annotations": 869,
    "splits": {"train": 283, "valid": 78, "test": 38},
    "classCounts": {"darkcircle": 382, "eyebag": 487},
}


class GateInputError(ValueError):
    """Raised when a receipt is malformed or contradicts immutable facts."""


def _exact_mapping(actual: Any, expected: dict[str, Any], label: str) -> None:
    if actual != expected:
        raise GateInputError(f"{label} does not match the frozen contract")


def evaluate_release(
    reproduction: dict[str, Any],
    remote: dict[str, Any],
    *,
    authorized_archive_sha256: str,
) -> dict[str, Any]:
    """Return operation-level authorization without mutating either system."""

    if reproduction.get("methodVersion") != "under-eye-grouped-archive-v1":
        raise GateInputError("unexpected reproduction method")
    _exact_mapping(reproduction.get("source"), EXPECTED_SOURCE, "source export")
    _exact_mapping(reproduction.get("output"), EXPECTED_GROUPED, "grouped output")
    if reproduction.get("reviewedCrossSplitGroups") != 3 or reproduction.get("movedImages") != 4:
        raise GateInputError("reviewed source-photo grouping contract changed")
    if reproduction.get("imageBytesChanged") != 0:
        raise GateInputError("image bytes changed")
    if reproduction.get("annotationPayloadsChanged") != 0:
        raise GateInputError("annotation payloads changed")
    candidate_sha = reproduction.get("outputArchiveSHA256")
    if not isinstance(candidate_sha, str) or len(candidate_sha) != 64:
        raise GateInputError("missing output archive SHA256")

    pilot = remote.get("pilotVersion", {})
    if pilot.get("version") != 2:
        raise GateInputError("provider pilot version 2 is not bound")
    if pilot.get("preprocessing") != {} or pilot.get("augmentation") != {}:
        raise GateInputError("provider source version must remain augmentation-free")
    _exact_mapping(
        {
            "images": pilot.get("images"),
            "annotations": pilot.get("annotations"),
            "splits": pilot.get("splits"),
            "classCounts": pilot.get("classCounts"),
        },
        EXPECTED_SOURCE,
        "provider pilot version",
    )

    grouped = remote.get("groupedProject", {})
    upload = grouped.get("upload", {})
    project_empty = grouped.get("images") == 0 and grouped.get("versions") == []
    upload_has_no_bytes = upload.get("status") == "created" and upload.get("progress") is None
    exact_archive_authorized = candidate_sha == authorized_archive_sha256
    archive_upload_authorized = bool(
        exact_archive_authorized
        and project_empty
        and upload_has_no_bytes
        and upload.get("taskId")
    )

    imported = grouped.get("importedDataset")
    import_verified = imported == EXPECTED_GROUPED and upload.get("status") == "completed"
    generated_version = grouped.get("generatedVersion")
    version_verified = bool(
        import_verified
        and isinstance(generated_version, dict)
        and generated_version.get("ready") is True
        and generated_version.get("splits") == EXPECTED_GROUPED["splits"]
        and generated_version.get("augmentation") == {}
    )

    blockers: list[str] = []
    if not exact_archive_authorized:
        blockers.append("candidate_archive_sha256_does_not_match_authorized_archive")
    if not project_empty and not import_verified:
        blockers.append("grouped_project_is_partially_populated_or_unverified")
    if project_empty:
        blockers.append("grouped_project_is_empty")
    if upload_has_no_bytes:
        blockers.append("existing_upload_task_has_no_processed_bytes")
    if not import_verified:
        blockers.append("grouped_import_counts_and_splits_not_verified")
    if not version_verified:
        blockers.append("augmentation_free_grouped_version_not_verified")
    blockers.extend([
        "independent_camera_holdout_missing",
        "working_product_integration_evidence_missing",
    ])

    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-release-gate-v1",
        "authorizedArchiveSHA256": authorized_archive_sha256,
        "candidateArchiveSHA256": candidate_sha,
        "exactArchiveAuthorized": exact_archive_authorized,
        "existingUploadTaskReusable": bool(project_empty and upload_has_no_bytes and upload.get("taskId")),
        "archiveUploadAuthorized": archive_upload_authorized,
        "versionGenerationAuthorized": import_verified,
        "researchTrainingAuthorized": version_verified,
        "testEvaluationAuthorized": False,
        "productActivationAllowed": False,
        "roadmapAccepted": False,
        "blockers": list(dict.fromkeys(blockers)),
        "decision": "blocked" if blockers else "ready",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reproduction", type=Path, required=True)
    parser.add_argument("--remote", type=Path, required=True)
    parser.add_argument("--authorized-archive-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(
        json.loads(args.reproduction.read_text(encoding="utf-8")),
        json.loads(args.remote.read_text(encoding="utf-8")),
        authorized_archive_sha256=args.authorized_archive_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
