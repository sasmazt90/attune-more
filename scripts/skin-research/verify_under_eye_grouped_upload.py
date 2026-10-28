#!/usr/bin/env python3
"""Verify the exact grouped under-eye archive before a provider upload.

This preflight is deliberately side-effect free. It proves that one local ZIP
matches the exact archive, destination and post-upload contract already
authorized by repository evidence. It never uploads, creates a version,
starts training or reads image members from the archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class UploadPreflightError(ValueError):
    """Raised when the local archive cannot satisfy the upload contract."""


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise UploadPreflightError(f"{Path(path).name} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UploadPreflightError(message)


def verify_upload_preflight(
    archive: str | Path,
    reproduction_receipt: str | Path,
    authorization_receipt: str | Path,
    grouped_gate: str | Path,
    *,
    observed_at: str,
) -> dict[str, Any]:
    archive_path = Path(archive)
    _require(archive_path.is_file(), "archive is missing")
    reproduction = _load(reproduction_receipt)
    authorization = _load(authorization_receipt)
    gate = _load(grouped_gate)

    archive_sha = _sha256(archive_path)
    archive_bytes = archive_path.stat().st_size
    source_sha = authorization.get("sourceArchiveSHA256")
    authorized_sha = authorization.get("authorizedArchiveSHA256")
    revoked_sha = authorization.get("revokedArchiveSHA256")
    policy = authorization.get("authorization", {})
    required = authorization.get("requiredPostUploadVerification", {})

    _require(authorization.get("methodVersion") == "under-eye-grouped-archive-authorization-v3", "unexpected authorization method")
    _require(reproduction.get("methodVersion") == "under-eye-grouped-archive-v2", "unexpected reproduction method")
    _require(gate.get("methodVersion") == "under-eye-grouped-release-gate-v3", "unexpected grouped gate method")
    _require(isinstance(authorized_sha, str) and len(authorized_sha) == 64, "authorized archive SHA256 is invalid")
    _require(archive_sha == authorized_sha, "local archive does not match the authorized SHA256")
    _require(archive_sha != revoked_sha, "local archive is explicitly revoked")
    _require(reproduction.get("sourceArchiveSHA256") == source_sha, "reproduction source SHA256 disagrees with authorization")
    _require(reproduction.get("outputArchiveSHA256") == archive_sha, "reproduction output SHA256 disagrees with archive")
    _require(reproduction.get("outputArchiveBytes") == archive_bytes, "reproduction byte count disagrees with archive")
    _require(reproduction.get("output") == {
        "images": required.get("images"),
        "annotations": required.get("annotations"),
        "splits": required.get("splits"),
        "classCounts": required.get("classCounts"),
    }, "reproduction output counts disagree with post-upload contract")
    _require(reproduction.get("imageBytesChanged") == 0, "image bytes changed during regrouping")
    _require(reproduction.get("annotationPayloadsChanged") == 0, "annotation payloads changed during regrouping")
    _require(reproduction.get("trainingAuthorized") is False, "reproduction must not authorize training")
    _require(reproduction.get("activationAllowed") is False, "reproduction must not authorize activation")

    destination = policy.get("destinationProject")
    _require(destination == "tolgar-sasmaz/attune-skin-under-eye-grouped-research", "unexpected destination project")
    _require(policy.get("destinationMustRemainPrivate") is True, "destination privacy is not required")
    _require(policy.get("destinationMustBeEmpty") is True, "destination emptiness is not required")
    _require(policy.get("freshDirectArchiveUpload") is True, "fresh direct upload is not required")
    _require(policy.get("reuseExistingCreatedTask") is False, "stale upload task reuse is not forbidden")
    for key in ("versionGeneration", "researchTraining", "testEvaluation", "productActivation"):
        _require(policy.get(key) is False, f"authorization unexpectedly enables {key}")

    _require(gate.get("archiveUploadAuthorized") is True, "grouped gate does not authorize archive upload")
    _require(gate.get("exactArchiveAuthorized") is True, "grouped gate does not authorize the exact archive")
    _require(gate.get("authorizedArchiveSHA256") == archive_sha, "grouped gate SHA256 disagrees with archive")
    _require(gate.get("candidateArchiveSHA256") == archive_sha, "grouped candidate SHA256 disagrees with archive")
    _require(gate.get("sourceArchiveSHA256") == source_sha, "grouped gate source SHA256 disagrees with authorization")
    _require(gate.get("freshDirectUploadRequired") is True, "grouped gate does not require a fresh direct upload")
    _require(gate.get("existingUploadTaskReusable") is False, "grouped gate permits stale task reuse")
    for key in ("versionGenerationAuthorized", "researchTrainingAuthorized", "testEvaluationAuthorized", "productActivationAllowed", "roadmapAccepted"):
        _require(gate.get(key) is False, f"grouped gate unexpectedly enables {key}")

    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-upload-preflight-v1",
        "observedAt": observed_at,
        "archiveSHA256": archive_sha,
        "archiveBytes": archive_bytes,
        "sourceArchiveSHA256": source_sha,
        "destinationProject": destination,
        "destinationMustRemainPrivate": True,
        "destinationMustBeEmpty": True,
        "freshDirectUploadRequired": True,
        "existingUploadTaskReusable": False,
        "expectedPostUploadVerification": required,
        "archiveUploadAuthorized": True,
        "uploadPerformed": False,
        "providerTaskId": None,
        "versionGenerationAuthorized": False,
        "researchTrainingAuthorized": False,
        "testEvaluationAuthorized": False,
        "productActivationAllowed": False,
        "roadmapAccepted": False,
        "decision": "ready_for_exact_authorized_upload",
        "privacySafe": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--reproduction", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = verify_upload_preflight(
        args.archive,
        args.reproduction,
        args.authorization,
        args.gate,
        observed_at=args.observed_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
