#!/usr/bin/env python3
"""Audit post-upload regional records without treating tags as identity truth.

The upload receipt proves transport counts, while the workspace observation
proves only which records were selected by the prior post-upload tag operation.
Neither proves that those records are unwanted.  This audit deliberately keeps
cleanup blocked until an immutable provider export matches the group-locked
archive by image bytes and canonical annotations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "regional-post-upload-provenance-observation-v1"
OUTPUT_SCHEMA = "regional-post-upload-provenance-audit-v1"
PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
UPLOAD_TASK_ID = "RzTdxfpBr9REzkke1mPp"
SELECTION_TAG = "provider-drift-rztdxfpbr9rezkke1mpp"


class AuditError(ValueError):
    """Raised when the aggregate observation is incomplete or inconsistent."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise AuditError(message)


def build_audit(observation: dict[str, Any]) -> dict[str, Any]:
    _require(observation.get("schemaVersion"), SCHEMA, "observation schema changed")
    _require(observation.get("project"), PROJECT_ID, "project identity changed")
    upload = observation.get("upload", {})
    _require(upload.get("taskId"), UPLOAD_TASK_ID, "upload task changed")
    _require(upload.get("status"), "completed", "upload is not complete")
    expected = {
        "total": 337,
        "uploaded": 139,
        "duplicates": 198,
        "annotated": 337,
        "errors": 0,
        "warnings": 0,
        "failedChunks": 0,
    }
    for field, value in expected.items():
        _require(upload.get(field), value, f"upload {field} changed")

    selected = observation.get("selectedRecords", {})
    _require(selected.get("tag"), SELECTION_TAG, "selection tag changed")
    _require(selected.get("records"), upload["uploaded"], "selected record count changed")
    _require(selected.get("allSelectedRecordsCarryTag"), True, "tag coverage incomplete")
    _require(selected.get("selectionWasCreatedAfterUpload"), True, "selection provenance missing")
    _require(selected.get("contentOrAnnotationIdentityCompared"), False,
             "aggregate observation must not claim content identity")
    privacy = observation.get("privacy", {})
    for field in ("containsFilenames", "containsProviderImageIds", "containsImageBytes"):
        _require(privacy.get(field), False, f"privacy field {field} must be false")

    return {
        "schemaVersion": OUTPUT_SCHEMA,
        "project": PROJECT_ID,
        "uploadTaskId": UPLOAD_TASK_ID,
        "uploadTransport": expected,
        "selectedRecords": upload["uploaded"],
        "selectionTag": SELECTION_TAG,
        "selectionBasis": "post-upload provider record selection",
        "membershipClassification": "unverified_until_exact_provider_export",
        "contentIdentityEstablished": False,
        "annotationIdentityEstablished": False,
        "tagEstablishesUnwantedMembership": False,
        "tagBasedDeletionOrVersionExclusionAllowed": False,
        "exactProviderExportAuditRequired": True,
        "safeNextStep": "compare immutable provider export to group-locked archive by image sha256 and canonical annotations",
        "containsFilenamesOrProviderImageIds": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observation = json.loads(args.observation.read_text(encoding="utf-8"))
    result = build_audit(observation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
