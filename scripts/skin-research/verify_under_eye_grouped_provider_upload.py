#!/usr/bin/env python3
"""Verify a completed grouped under-eye provider upload without opening media.

The verifier consumes a privacy-safe aggregate facts document produced from the
Roboflow upload receipt, annotation board and fully paginated RoboQL counts.  It
never treats a completed upload as version, training, evaluation or product
authorization.  Provider project-summary counters may lag, but the exact upload,
board and paginated Dataset counts must all agree with the authorized archive.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_PROJECT = "tolgar-sasmaz/attune-skin-under-eye-grouped-research"
EXPECTED_ARCHIVE_SHA256 = "8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"
EXPECTED_ARCHIVE_BYTES = 15_086_760
EXPECTED_IMAGES = 399
EXPECTED_ANNOTATIONS = 869
EXPECTED_SPLITS = {"train": 284, "valid": 77, "test": 38}
EXPECTED_CLASSES = {"darkcircle": 382, "eyebag": 487}


class ProviderUploadVerificationError(ValueError):
    """Raised when provider aggregates cannot prove the exact upload."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProviderUploadVerificationError(message)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "facts must be a JSON object")
    return value


def verify_provider_upload(
    facts: dict[str, Any], *, expected_task_id: str
) -> dict[str, Any]:
    _require(facts.get("schemaVersion") == 1, "facts schema changed")
    _require(
        facts.get("methodVersion") == "under-eye-grouped-provider-upload-facts-v1",
        "facts method changed",
    )
    _require(facts.get("project") == EXPECTED_PROJECT, "destination project changed")
    _require(facts.get("private") is True, "destination project is not private")
    _require(facts.get("archiveSHA256") == EXPECTED_ARCHIVE_SHA256, "archive SHA256 changed")
    _require(facts.get("archiveBytes") == EXPECTED_ARCHIVE_BYTES, "archive byte count changed")

    upload = facts.get("upload")
    _require(isinstance(upload, dict), "upload receipt is missing")
    _require(upload.get("taskId") == expected_task_id, "provider task identity changed")
    _require(upload.get("status") == "completed", "provider upload is not completed")
    _require(upload.get("progress") == {"current": EXPECTED_IMAGES, "total": EXPECTED_IMAGES}, "upload progress is incomplete")
    result = upload.get("result")
    _require(isinstance(result, dict), "provider upload result is missing")
    _require(result.get("uploaded") == EXPECTED_IMAGES, "uploaded image count changed")
    _require(result.get("duplicates") == 0, "provider reported duplicate images")
    _require(result.get("annotated") == EXPECTED_IMAGES, "annotated image count changed")
    _require(result.get("videosStaged") == 0 and result.get("videoIds") == [], "unexpected video payload")
    _require(result.get("failedChunks") == 0, "provider upload has failed chunks")
    _require(result.get("chunkCount") == 4, "provider upload chunk count changed")
    _require(result.get("uploadErrors") == [], "provider upload errors are present")
    _require(result.get("annotationErrors") == [], "provider annotation errors are present")
    warnings = result.get("warnings")
    _require(isinstance(warnings, list), "provider warnings are missing")
    _require(
        all(
            isinstance(item, dict)
            and item.get("type") == "ignored"
            and item.get("reason") == "readme"
            and item.get("path") == "README.roboflow.txt"
            for item in warnings
        ),
        "provider returned an unexpected warning",
    )

    board = facts.get("annotationBoard")
    _require(isinstance(board, dict), "annotation board facts are missing")
    _require(board.get("datasetImages") == EXPECTED_IMAGES, "annotation board image count changed")
    _require(board.get("datasetAnnotated") == EXPECTED_IMAGES, "annotation board annotated count changed")
    _require(board.get("datasetUnannotated") == 0, "annotation board has unannotated images")
    _require(board.get("percentLabeled") == 100, "annotation board is not fully labeled")
    _require(board.get("uploadJobStatus") == "complete", "annotation board upload job is incomplete")

    search = facts.get("paginatedDatasetSearch")
    _require(isinstance(search, dict), "paginated Dataset facts are missing")
    _require(search.get("complete") is True, "Dataset search is not complete")
    _require(search.get("pages") == 5, "Dataset pagination changed")
    _require(search.get("images") == EXPECTED_IMAGES, "Dataset image count changed")
    _require(search.get("splits") == EXPECTED_SPLITS, "Dataset split counts changed")
    _require(search.get("classAnnotationCounts") == EXPECTED_CLASSES, "Dataset class counts changed")

    versions = facts.get("versions")
    trainings = facts.get("trainings")
    _require(versions == [], "a provider version exists before authorization")
    _require(trainings == [], "provider training exists before authorization")

    provider_summary_images = facts.get("providerProjectSummaryImages")
    _require(isinstance(provider_summary_images, int) and provider_summary_images >= 0, "provider summary count is invalid")
    summary_consistent = provider_summary_images == EXPECTED_IMAGES

    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-provider-upload-verification-v1",
        "observedAt": facts.get("observedAt"),
        "project": EXPECTED_PROJECT,
        "private": True,
        "archiveSHA256": EXPECTED_ARCHIVE_SHA256,
        "archiveBytes": EXPECTED_ARCHIVE_BYTES,
        "providerTaskId": expected_task_id,
        "uploadCompleted": True,
        "uploadedImages": EXPECTED_IMAGES,
        "annotatedImages": EXPECTED_IMAGES,
        "duplicates": 0,
        "uploadErrors": 0,
        "annotationErrors": 0,
        "datasetSearchComplete": True,
        "datasetSearchPages": 5,
        "splits": EXPECTED_SPLITS,
        "classAnnotationCounts": EXPECTED_CLASSES,
        "providerProjectSummaryImages": provider_summary_images,
        "providerProjectSummaryConsistent": summary_consistent,
        "providerProjectSummaryLagObserved": not summary_consistent,
        "versionPresent": False,
        "trainingPresent": False,
        "versionGenerationAuthorized": False,
        "researchTrainingAuthorized": False,
        "testEvaluationAuthorized": False,
        "productActivationAllowed": False,
        "roadmapAccepted": False,
        "decision": "UPLOAD_VERIFIED_VERSION_EXPERT_PROVIDER_EXPORT_AND_CAMERA_GATES_PENDING",
        "privacySafe": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--expected-task-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = verify_provider_upload(_load(args.facts), expected_task_id=args.expected_task_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
