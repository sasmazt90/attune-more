#!/usr/bin/env python3
"""Audit an Attune V5 replay ZIP and export a source-bound FRONT bundle.

Raw photos and map payloads remain in the local ZIP.  The evidence output is
privacy-safe; the optional bundle retains full responses only for a local
comparison run and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


BASE_COMMIT = "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285"
ENDPOINT = "/api/local-health/skin"
PEOPLE = tuple(f"{i:02d}_{name}" for i, name in enumerate(
    ("england", "germany", "kenya", "scotland", "turkey", "usa"), 1
))
POSES = ("FRONT", "RIGHT", "LEFT")
CRITERIA = {"tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags"}
REGIONS = {"forehead", "rightCheek", "leftCheek", "nose", "chin", "periorbital"}


class AuditError(ValueError):
    pass


def _json(zf: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(zf.read(name))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuditError(f"cannot read {name}: {exc}") from exc


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_members(zf: zipfile.ZipFile) -> set[str]:
    names: set[str] = set()
    for info in zf.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or info.filename in names:
            raise AuditError(f"unsafe or duplicate ZIP member: {info.filename}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise AuditError(f"symlink ZIP member: {info.filename}")
        names.add(info.filename)
    return names


def audit(path: Path, expected_sha256: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    archive_sha = _sha(path)
    if expected_sha256 and archive_sha != expected_sha256:
        raise AuditError("archive SHA-256 mismatch")
    with zipfile.ZipFile(path) as zf:
        names = _safe_members(zf)
        bad_member = zf.testzip()
        if bad_member:
            raise AuditError(f"ZIP CRC failure: {bad_member}")

        run = _json(zf, "run-manifest.json")
        source = _json(zf, "input-manifest.json")
        summary = _json(zf, "summary.json")
        verified = _json(zf, "artifact-verification.json")
        checksums = _json(zf, "checksums.json")

        required_run = {
            "status": "finished",
            "sourceType": "generated-still-image-replay",
            "physicalCameraAcceptance": False,
            "temporalSamples": 0,
            "temporalStability": "not_measured",
            "productOrModelOrThresholdChanges": False,
            "protectedFilesUnchanged": True,
        }
        for key, value in required_run.items():
            if run.get(key) != value:
                raise AuditError(f"run-manifest {key} mismatch")
        git = run.get("git", {})
        if git.get("baseCommit") != BASE_COMMIT:
            raise AuditError("unexpected Attune base commit")
        if not isinstance(git.get("localRevisionSHA256"), str):
            raise AuditError("local execution revision is not identified")
        if run.get("counts", {}).get("completed") != 18 or run["counts"].get("failed") != 0:
            raise AuditError("run did not complete all 18 inputs")
        if source.get("personCount") != 6 or source.get("imageCount") != 18:
            raise AuditError("input manifest is not six triplets")
        if source.get("physicalCameraAcceptance") is not False:
            raise AuditError("generated replay cannot claim physical camera acceptance")
        if summary.get("expectedInputs") != 18 or summary.get("completedInputs") != 18:
            raise AuditError("summary is incomplete")
        if verified.get("passed") is not True or verified.get("verifiedInputs") != 18:
            raise AuditError("artifact verification did not pass")

        checks = verified.get("inputChecks")
        if not isinstance(checks, list) or len(checks) != 18:
            raise AuditError("artifact input checks are incomplete")
        for row in checks:
            flags = row.get("checks") if isinstance(row, dict) else None
            if not isinstance(flags, dict) or not flags or any(value is not True for value in flags.values()):
                raise AuditError("one or more artifact verification flags failed")

        if not isinstance(checksums, list) or not checksums:
            raise AuditError("checksums.json is missing rows")
        checksum_names: set[str] = set()
        for row in checksums:
            name = row.get("file") if isinstance(row, dict) else None
            if not isinstance(name, str) or name in checksum_names or name not in names:
                raise AuditError("checksum inventory is malformed")
            payload = zf.read(name)
            if len(payload) != row.get("bytes") or hashlib.sha256(payload).hexdigest() != row.get("sha256"):
                raise AuditError(f"checksum mismatch: {name}")
            checksum_names.add(name)
        if names - {"checksums.json"} != checksum_names:
            raise AuditError("checksum inventory does not cover every payload")

        source_rows = source.get("files")
        summary_rows = summary.get("inputs")
        if not isinstance(source_rows, list) or not isinstance(summary_rows, list):
            raise AuditError("input rows missing")
        source_by_key = {(row.get("personId"), row.get("pose")): row for row in source_rows}
        summary_by_key = {(row.get("personId"), row.get("pose")): row for row in summary_rows}
        expected_keys = {(person, pose) for person in PEOPLE for pose in POSES}
        if set(source_by_key) != expected_keys or set(summary_by_key) != expected_keys:
            raise AuditError("person/pose inventory mismatch")

        captures: list[dict[str, Any]] = []
        evidence_rows: list[dict[str, Any]] = []
        for person, pose in sorted(expected_keys):
            src = source_by_key[(person, pose)]
            item = summary_by_key[(person, pose)]
            if src.get("sourceType") != "generated-still-image-replay" or src.get("staticPreflightAccepted") is not True:
                raise AuditError(f"source gate mismatch for {person}/{pose}")
            if item.get("inputSHA256") != src.get("sha256") or item.get("analysisStatus") != "completed":
                raise AuditError(f"summary identity/status mismatch for {person}/{pose}")
            if item.get("httpStatus") != 200 or item.get("productAttachmentSucceeded") is not True:
                raise AuditError(f"HTTP/product attachment failure for {person}/{pose}")

            prefix = f"{person}/{pose}"
            response = _json(zf, f"{prefix}/response.json")
            request_meta = _json(zf, f"{prefix}/request-metadata.json")
            http = _json(zf, f"{prefix}/http.json")
            transport = _json(zf, f"{prefix}/request-transport.json")
            photo_id = src.get("measuredPhotoId")
            if not isinstance(photo_id, str) or response.get("photoId") != photo_id or request_meta.get("photoId") != photo_id:
                raise AuditError(f"photo identity mismatch for {person}/{pose}")
            if (response.get("sourceWidth"), response.get("sourceHeight")) != (src.get("width"), src.get("height")):
                raise AuditError(f"dimensions mismatch for {person}/{pose}")
            if response.get("storage") != "volatile-memory-only":
                raise AuditError(f"storage receipt mismatch for {person}/{pose}")
            if not str(http.get("url", "")).endswith(ENDPOINT) or http.get("httpStatus") != 200:
                raise AuditError(f"HTTP endpoint mismatch for {person}/{pose}")
            if transport.get("method") != "POST" or not str(transport.get("url", "")).endswith(ENDPOINT):
                raise AuditError(f"request transport mismatch for {person}/{pose}")
            if not REGIONS.issuperset(response.get("measurements", {}).keys()):
                raise AuditError(f"unknown region for {person}/{pose}")

            criteria = response.get("general", {}).get("measurements")
            if pose == "FRONT":
                if set(response.get("measurements", {})) != REGIONS:
                    raise AuditError(f"FRONT regional inventory incomplete for {person}")
                if not isinstance(criteria, list) or {row.get("id") for row in criteria} != CRITERIA:
                    raise AuditError(f"FRONT criteria inventory mismatch for {person}")
                skin_type = response.get("general", {}).get("skinType")
                if not isinstance(skin_type, dict) or skin_type.get("quality") not in {"valid", "insufficient"}:
                    raise AuditError(f"FRONT skin type missing for {person}")
                captures.append({
                    "subjectKey": person,
                    "pose": pose,
                    "input": {
                        "filename": src.get("file"),
                        "jpegSha256": src.get("sha256"),
                        "decodedRgbaSha256": photo_id,
                    },
                    "response": response,
                })
            evidence_rows.append({
                "personId": person,
                "pose": pose,
                "inputSHA256": src.get("sha256"),
                "photoId": photo_id,
                "httpStatus": item.get("httpStatus"),
                "measurementCount": item.get("measurementCount"),
                "measured": item.get("measured"),
                "unavailable": item.get("unavailable"),
            })

    bundle = {
        "sourceCommit": BASE_COMMIT,
        "endpoint": ENDPOINT,
        "provenance": {
            "sourceType": run["sourceType"],
            "baseCommit": git["baseCommit"],
            "gitCheckoutPresent": git.get("gitCheckoutPresent"),
            "localRevision": git.get("localRevision"),
            "localRevisionSHA256": git["localRevisionSHA256"],
            "productOrModelOrThresholdChanges": run["productOrModelOrThresholdChanges"],
        },
        "captures": captures,
    }
    evidence = {
        "schemaVersion": 1,
        "archive": {"name": path.name, "sha256": archive_sha, "bytes": path.stat().st_size},
        "libraryFileId": "libfile_389b88645f7c8191bb2facb26572b452",
        "integrity": {"zipCrcPassed": True, "checksummedFiles": len(checksum_names), "artifactVerificationPassed": True},
        "execution": bundle["provenance"],
        "endpoint": ENDPOINT,
        "completedInputs": 18,
        "frontResponses": 6,
        "rows": evidence_rows,
        "claims": {
            "generatedReplay": True,
            "physicalCameraAcceptance": False,
            "temporalStabilityMeasured": False,
            "expertGroundTruth": False,
            "accuracyMeasured": False,
        },
    }
    return bundle, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output-bundle", type=Path, required=True)
    parser.add_argument("--output-evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle, evidence = audit(args.archive, args.expected_sha256)
    except (AuditError, OSError, zipfile.BadZipFile) as exc:
        print(f"audit blocked: {exc}")
        return 2
    for output, value in ((args.output_bundle, bundle), (args.output_evidence, evidence)):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
