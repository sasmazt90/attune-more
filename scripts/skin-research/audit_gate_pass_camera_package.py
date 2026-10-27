#!/usr/bin/env python3
"""Audit the privacy-safe evidence contract of a gate-pass camera ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


POSES = ("FRONT", "RIGHT", "LEFT")
CAPTURE_CHECK_ENDPOINT = "http://127.0.0.1:8311/api/local-health/skin/capture-check"
CAPTURE_CHECK_VERSION = "glasses-free-skin-capture-v1"
SHA256_LENGTH = 64


class AuditError(ValueError):
    pass


def _json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON in {label}: {exc}") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _jpeg_size(raw: bytes) -> tuple[int, int]:
    if len(raw) < 4 or raw[:2] != b"\xff\xd8":
        raise AuditError("invalid JPEG signature")
    offset = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 4 <= len(raw):
        if raw[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(raw) and raw[offset] == 0xFF:
            offset += 1
        if offset >= len(raw):
            break
        marker = raw[offset]
        offset += 1
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(raw):
            break
        length = int.from_bytes(raw[offset : offset + 2], "big")
        if length < 2 or offset + length > len(raw):
            raise AuditError("invalid JPEG segment")
        if marker in sof:
            if length < 7:
                raise AuditError("invalid JPEG SOF")
            height = int.from_bytes(raw[offset + 3 : offset + 5], "big")
            width = int.from_bytes(raw[offset + 5 : offset + 7], "big")
            return width, height
        offset += length
    raise AuditError("JPEG dimensions not found")


def _image_size(raw: bytes, path: str) -> tuple[int, int]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(raw) < 24 or raw[12:16] != b"IHDR":
            raise AuditError(f"invalid PNG header for {path}")
        return struct.unpack(">II", raw[16:24])
    if raw.startswith(b"\xff\xd8"):
        return _jpeg_size(raw)
    raise AuditError(f"unsupported image format for {path}")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len({member.filename for member in members}) != len(members):
        raise AuditError("ZIP contains duplicate paths")
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise AuditError(f"unsafe ZIP path: {member.filename}")
        mode = member.external_attr >> 16
        if mode & 0o170000 == 0o120000:
            raise AuditError(f"ZIP symlink is not allowed: {member.filename}")
        if member.is_dir():
            raise AuditError(f"explicit ZIP directory is not expected: {member.filename}")
    return members


def _previous_front_hashes(previous: dict[str, Any]) -> set[str]:
    values = set()
    for subject in previous.get("subjects", []):
        try:
            value = subject["poses"]["front"]["sha256"]
        except (KeyError, TypeError) as exc:
            raise AuditError("previous FRONT manifest is malformed") from exc
        if not isinstance(value, str) or len(value) != SHA256_LENGTH:
            raise AuditError("previous FRONT hash is malformed")
        values.add(value)
    if len(values) != 6:
        raise AuditError("previous manifest must contain six unique FRONT hashes")
    return values


def audit(zip_path: Path, previous: dict[str, Any], library_file_id: str | None = None) -> dict[str, Any]:
    archive_bytes = zip_path.read_bytes()
    with zipfile.ZipFile(zip_path) as archive:
        members = _safe_members(archive)
        names = {member.filename for member in members}
        required_root = {"checksums.json", "manifest.json", "README.txt"}
        if not required_root.issubset(names):
            raise AuditError("ZIP is missing required root files")

        checksum_rows = _json(archive.read("checksums.json"), "checksums.json")
        if not isinstance(checksum_rows, list):
            raise AuditError("checksums.json must be an array")
        checksums = {}
        for row in checksum_rows:
            if not isinstance(row, dict) or not isinstance(row.get("file"), str):
                raise AuditError("malformed checksum row")
            name = row["file"]
            if name in checksums:
                raise AuditError(f"duplicate checksum row for {name}")
            checksums[name] = row
        expected_checksum_names = names - {"checksums.json"}
        if set(checksums) != expected_checksum_names:
            raise AuditError("checksum coverage does not equal all non-index members")
        for name, row in checksums.items():
            raw = archive.read(name)
            if row.get("bytes") != len(raw) or row.get("sha256") != _sha(raw):
                raise AuditError(f"checksum mismatch for {name}")

        manifest_raw = archive.read("manifest.json")
        manifest = _json(manifest_raw, "manifest.json")
        if not isinstance(manifest, dict):
            raise AuditError("manifest.json must be an object")
        if manifest.get("personCount") != 6 or manifest.get("imageCount") != 18:
            raise AuditError("manifest must declare six people and eighteen images")
        if manifest.get("staticGatePassedCount") != 18:
            raise AuditError("manifest does not declare 18/18 static gate passes")
        if manifest.get("physicalCameraAcceptance") is not False:
            raise AuditError("generated still package must not claim physical-camera acceptance")
        if manifest.get("fullV5SkinAnalysisCompletedForThisSet") is not False:
            raise AuditError("gate package must not claim full V5 skin analysis")

        files = manifest.get("files")
        if not isinstance(files, list) or len(files) != 18:
            raise AuditError("manifest files must contain eighteen rows")
        seen_pairs: set[tuple[str, str]] = set()
        seen_hashes: set[str] = set()
        seen_photo_ids: set[str] = set()
        people: defaultdict[str, set[str]] = defaultdict(set)
        source_kinds: Counter[str] = Counter()
        dimensions: Counter[tuple[int, int]] = Counter()
        extensions: Counter[str] = Counter()
        rows_out = []
        front_hashes = set()
        capture_model_hashes = set()

        for row in files:
            if not isinstance(row, dict):
                raise AuditError("manifest image row is malformed")
            person = row.get("personId")
            pose = row.get("pose")
            image_path = row.get("file")
            if not isinstance(person, str) or pose not in POSES or not isinstance(image_path, str):
                raise AuditError("manifest person/pose/file is malformed")
            pair = (person, pose)
            if pair in seen_pairs:
                raise AuditError(f"duplicate person/pose: {person}/{pose}")
            seen_pairs.add(pair)
            people[person].add(pose)
            if image_path not in names:
                raise AuditError(f"manifest image is absent: {image_path}")
            raw = archive.read(image_path)
            digest = _sha(raw)
            if digest != row.get("sha256") or len(raw) != row.get("bytes"):
                raise AuditError(f"manifest identity mismatch for {image_path}")
            if digest in seen_hashes:
                raise AuditError("image bytes are duplicated")
            seen_hashes.add(digest)
            width, height = _image_size(raw, image_path)
            if (width, height) != (row.get("width"), row.get("height")):
                raise AuditError(f"decoded dimensions mismatch for {image_path}")
            dimensions[(width, height)] += 1
            extensions[PurePosixPath(image_path).suffix.lower()] += 1
            source_kinds[str(row.get("sourceKind"))] += 1
            if row.get("staticPreflightAccepted") is not True:
                raise AuditError(f"manifest gate is not accepted for {image_path}")
            if pose == "FRONT":
                front_hashes.add(digest)

            evidence_root = row.get("gateEvidence")
            if not isinstance(evidence_root, str):
                raise AuditError(f"gate evidence path missing for {image_path}")
            preflight_path = f"{evidence_root}/preflight.json"
            capture_path = f"{evidence_root}/capture-check-response.json"
            if preflight_path not in names or capture_path not in names:
                raise AuditError(f"gate evidence files missing for {image_path}")
            preflight = _json(archive.read(preflight_path), preflight_path)
            if not isinstance(preflight, dict):
                raise AuditError(f"preflight is not an object for {image_path}")
            measured_person = preflight.get("personId")
            allowed_measured_people = {person, f"{person}_replacement", f"{person}_revised"}
            if measured_person not in allowed_measured_people or preflight.get("pose") != pose:
                raise AuditError(f"preflight identity mismatch for {image_path}")
            if (preflight.get("sourceWidth"), preflight.get("sourceHeight")) != (width, height):
                raise AuditError(f"preflight dimensions mismatch for {image_path}")
            alignment = preflight.get("acquisitionAlignment", {})
            landmarks = alignment.get("landmarks") if isinstance(alignment, dict) else None
            quality = preflight.get("quality", {})
            if not isinstance(landmarks, list) or len(landmarks) != 478:
                raise AuditError(f"preflight must contain 478 landmarks for {image_path}")
            if not isinstance(quality, dict) or quality.get("isValid") is not True or quality.get("status") != "OPTIMAL":
                raise AuditError(f"preflight quality is not OPTIMAL for {image_path}")
            if preflight.get("staticPreflightAccepted") is not True or preflight.get("matchesSkinAngle") is not True:
                raise AuditError(f"preflight pose gate failed for {image_path}")
            if preflight.get("reasons") != [] or preflight.get("geometryError") is not None:
                raise AuditError(f"preflight contains a failure reason for {image_path}")
            if preflight.get("physicalCameraAcceptance") is not False:
                raise AuditError(f"preflight overclaims camera acceptance for {image_path}")
            if preflight.get("temporalStabilityStatus") != "not_measured_still_image":
                raise AuditError(f"unexpected temporal status for {image_path}")
            photo_id = preflight.get("photoId")
            if photo_id != row.get("measuredPhotoId") or not isinstance(photo_id, str) or len(photo_id) != SHA256_LENGTH:
                raise AuditError(f"preflight photoId mismatch for {image_path}")
            if photo_id in seen_photo_ids:
                raise AuditError("preflight photoIds are not unique")
            seen_photo_ids.add(photo_id)

            capture = _json(archive.read(capture_path), capture_path)
            if not isinstance(capture, dict):
                raise AuditError(f"capture check is not an object for {image_path}")
            if "body" in capture:
                if capture.get("httpStatus") != 200 or capture.get("url") != CAPTURE_CHECK_ENDPOINT:
                    raise AuditError(f"wrapped capture check failed for {image_path}")
                capture = capture.get("body")
            if not isinstance(capture, dict):
                raise AuditError(f"capture check body is malformed for {image_path}")
            if capture.get("status") != "CLEAR" or capture.get("version") != CAPTURE_CHECK_VERSION:
                raise AuditError(f"capture check is not CLEAR for {image_path}")
            probability = capture.get("probability")
            model_hash = capture.get("modelHash")
            if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
                raise AuditError(f"capture probability is invalid for {image_path}")
            if not isinstance(model_hash, str) or len(model_hash) != SHA256_LENGTH:
                raise AuditError(f"capture model hash is invalid for {image_path}")
            capture_model_hashes.add(model_hash)
            rows_out.append(
                {
                    "personId": person,
                    "measurementPersonId": measured_person,
                    "pose": pose,
                    "file": image_path,
                    "sha256": digest,
                    "photoId": photo_id,
                    "width": width,
                    "height": height,
                    "sourceKind": row.get("sourceKind"),
                    "quality": quality.get("status"),
                    "captureStatus": capture.get("status"),
                }
            )

        if len(people) != 6 or any(poses != set(POSES) for poses in people.values()):
            raise AuditError("each of six people must have FRONT, RIGHT, and LEFT")
        if len(capture_model_hashes) != 1:
            raise AuditError("capture checks do not share one immutable model hash")
        previous_fronts = _previous_front_hashes(previous)
        if front_hashes != previous_fronts:
            raise AuditError("FRONT image set changed from the saved Roboflow evidence source")

    return {
        "schemaVersion": 1,
        "source": {
            "libraryFileId": library_file_id,
            "archiveFilename": zip_path.name,
            "archiveBytes": len(archive_bytes),
            "archiveSHA256": _sha(archive_bytes),
            "rawImagesCommitted": False,
        },
        "integrity": {
            "zipMembers": len(members),
            "checksumRows": len(checksums),
            "checksumCoverageComplete": True,
            "safePaths": True,
            "uniqueImageBytes": True,
            "uniquePhotoIds": True,
            "manifestSHA256": _sha(manifest_raw),
        },
        "gate": {
            "people": len(people),
            "images": len(rows_out),
            "posesPerPerson": list(POSES),
            "staticPreflightAccepted": len(rows_out),
            "optimalQuality": len(rows_out),
            "clearCaptureCheck": len(rows_out),
            "landmarksPerImage": 478,
            "captureCheckVersion": CAPTURE_CHECK_VERSION,
            "captureModelHash": next(iter(capture_model_hashes)),
            "dimensions": [
                {"width": width, "height": height, "count": count}
                for (width, height), count in sorted(dimensions.items())
            ],
            "formats": dict(sorted(extensions.items())),
            "sourceKinds": dict(sorted(source_kinds.items())),
        },
        "reuseDecision": {
            "frontHashSetMatchesSavedRoboflowInputs": True,
            "frontImages": len(front_hashes),
            "repeatRoboflowInferenceRequired": False,
            "savedRoboflowEvidence": "docs/skin/evidence/generated-front-roboflow-20261024-v1.json",
        },
        "acceptance": {
            "staticGeneratedReplayGate": True,
            "fullV5SkinAnalysisCompleted": False,
            "physicalCameraAcceptance": False,
            "temporalStabilityMeasured": False,
            "expertGroundTruth": False,
            "precisionRecallF1Eligible": False,
        },
        "files": rows_out,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--previous-manifest", type=Path, required=True)
    parser.add_argument("--library-file-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        previous = json.loads(args.previous_manifest.read_text(encoding="utf-8"))
        result = audit(args.zip, previous, args.library_file_id)
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, AuditError) as exc:
        print(f"gate package audit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
