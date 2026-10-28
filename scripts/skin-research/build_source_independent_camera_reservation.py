#!/usr/bin/env python3
"""Build the independent physical-camera reservation artifact.

Reservation is deliberately weaker than camera acceptance: it only proves
that consented, source-independent physical-camera sessions are reserved by a
locked protocol.  Generated media, controlled fixtures, existing source
records and model predictions cannot satisfy this contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "skin-source-independent-camera-reservation-input-v1"
PREFLIGHT_METHOD = "skin-source-independent-camera-reservation-preflight-v1"
ARTIFACT_METHOD = "skin-source-independent-camera-reservation-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
REQUIRED_VIEWS = ("front", "left", "right")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "path", "url", "uri", "filename", "image", "images",
    "subject", "subjectId", "subjectIds", "person", "personId",
    "record", "recordId", "recordIds", "reviewer", "reviewerId",
    "email", "phone", "address", "demographics", "biometrics",
    "capture", "captures", "prediction", "predictions", "annotation",
    "annotations",
}
SAFE_POLICY = {
    "reserved": True,
    "sourceType": "physical-camera",
    "generated": False,
    "controlledFixture": False,
    "syntheticOrRenderedMediaAllowed": False,
    "consentRequired": True,
    "consentObtainedBeforeCaptureRequired": True,
    "subjectIndependentFromSourceRegistry": True,
    "usedForTrainingValidationOrThresholdSelection": False,
    "usedForModelSelection": False,
    "usedForTestThresholdRetuning": False,
    "captureDeviceIsPhysicalCameraRequired": True,
    "expertGroundTruthRequiredForAcceptance": True,
    "reservationIsNotAcceptanceEvidence": True,
    "excludedArchivesUsed": False,
}


class CameraReservationInputError(ValueError):
    """Raised when camera reservation evidence is incomplete or unsafe."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CameraReservationInputError(f"{field} must be a nonnegative integer")
    return value


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise CameraReservationInputError(f"{location} contains private identity, media or model payload")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_committed_facts(receipt: dict[str, Any]) -> dict[str, Any]:
    """Replay current facts while keeping independent-camera reservation blocked."""
    if receipt.get("schemaVersion") != 2 or receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise CameraReservationInputError("source mapping receipt identity changed")
    candidate = receipt.get("acceptanceCandidate")
    if not isinstance(candidate, dict):
        raise CameraReservationInputError("source mapping acceptance candidate is missing")
    if candidate.get("independentCameraReserved") is not False:
        raise CameraReservationInputError("independent camera reservation fact changed")
    if candidate.get("cameraReservationRef") is not None:
        raise CameraReservationInputError("unexpected camera reservation identity present")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "sourceFactsMethodVersion": SOURCE_RECEIPT_METHOD,
        "releaseRef": None,
        "sourceRegistryRef": None,
        "cameraReservationRef": None,
        "reservedSubjectCount": 0,
        "reservedSessionCount": 0,
        "expectedCaptureCount": 0,
        "requiredViews": list(REQUIRED_VIEWS),
        **SAFE_POLICY,
        "reserved": False,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "physical_camera_reservation_missing",
            "source_independent_subject_reservation_missing",
            "pre_capture_consent_protocol_missing",
            "physical_camera_capture_protocol_missing",
            "privacy_retention_policy_missing",
            "front_left_right_session_plan_missing",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque physical-camera reservation manifest."""
    if not isinstance(manifest, dict):
        raise CameraReservationInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise CameraReservationInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise CameraReservationInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    reservation_ref = manifest.get("cameraReservationRef")
    for value, blocker in (
        (release_ref, "release_ref_missing_or_invalid"),
        (registry_ref, "source_registry_ref_missing_or_invalid"),
        (reservation_ref, "camera_reservation_ref_missing_or_invalid"),
    ):
        if not _is_opaque(value):
            blockers.append(blocker)
    policy = manifest.get("cameraPolicy")
    if not isinstance(policy, dict):
        blockers.append("camera_policy_missing")
    elif set(policy) != set(SAFE_POLICY):
        raise CameraReservationInputError("camera policy fields changed")
    else:
        for field, expected in SAFE_POLICY.items():
            if policy.get(field) != expected:
                raise CameraReservationInputError(f"unsafe camera reservation policy: {field}")
    if manifest.get("requiredViews") != list(REQUIRED_VIEWS):
        raise CameraReservationInputError("required physical-camera view contract changed")
    subject_count = _count(manifest.get("reservedSubjectCount"), "reservedSubjectCount")
    session_count = _count(manifest.get("reservedSessionCount"), "reservedSessionCount")
    expected_captures = _count(manifest.get("expectedCaptureCount"), "expectedCaptureCount")
    if subject_count == 0:
        blockers.append("reserved_subject_count_empty")
    if session_count == 0:
        blockers.append("reserved_session_count_empty")
    if expected_captures == 0:
        blockers.append("expected_capture_count_empty")
    if subject_count and session_count != subject_count:
        blockers.append("one_session_per_subject_contract_mismatch")
    if subject_count and expected_captures != subject_count * len(REQUIRED_VIEWS):
        blockers.append("front_left_right_capture_count_mismatch")
    hashes: dict[str, str | None] = {}
    for field in (
        "reservationEvidenceSHA256", "captureProtocolSHA256",
        "consentProtocolSHA256", "privacyRetentionPolicySHA256",
    ):
        value = manifest.get(field)
        if not _is_sha256(value):
            blockers.append(f"{field}_missing_or_invalid")
            hashes[field] = None
        else:
            hashes[field] = value
    valid_hashes = [value for value in hashes.values() if value is not None]
    if len(valid_hashes) != len(set(valid_hashes)):
        raise CameraReservationInputError("camera reservation evidence hashes must be unique")
    independence = manifest.get("independenceVerification")
    if not isinstance(independence, dict):
        blockers.append("independence_verification_missing")
    else:
        allowed = {
            "sourceRegistryCompared", "noSubjectOverlapFound",
            "comparisonEvidenceSHA256", "humanConfirmationRequired",
            "similarityAloneAcceptedAsIdentity",
        }
        if set(independence) - allowed:
            raise CameraReservationInputError("independence verification fields changed")
        for field in ("sourceRegistryCompared", "noSubjectOverlapFound", "humanConfirmationRequired"):
            if independence.get(field) is not True:
                blockers.append(f"independence_{field}_incomplete")
        if independence.get("similarityAloneAcceptedAsIdentity") is not False:
            raise CameraReservationInputError("similarity alone cannot establish subject independence")
        if not _is_sha256(independence.get("comparisonEvidenceSHA256")):
            blockers.append("independence_comparison_evidence_missing_or_invalid")
    canonical = {
        "releaseRef": release_ref,
        "sourceRegistryRef": registry_ref,
        "cameraReservationRef": reservation_ref,
        "reservedSubjectCount": subject_count,
        "reservedSessionCount": session_count,
        "expectedCaptureCount": expected_captures,
        "requiredViews": list(REQUIRED_VIEWS),
        "evidence": hashes,
        "independenceComparisonSHA256": independence.get("comparisonEvidenceSHA256") if isinstance(independence, dict) else None,
        "cameraPolicy": policy,
    }
    blockers = sorted(set(blockers))
    digest = hashlib.sha256(_canonical_bytes(canonical)).hexdigest()
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "cameraReservationRef": reservation_ref if _is_opaque(reservation_ref) else None,
        "reservedSubjectCount": subject_count,
        "reservedSessionCount": session_count,
        "expectedCaptureCount": expected_captures,
        "requiredViews": list(REQUIRED_VIEWS),
        "cameraReservationDigest": digest,
        **SAFE_POLICY,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise CameraReservationInputError("independent camera reservation is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "cameraReservationRef": preflight["cameraReservationRef"],
        "reservedSubjectCount": preflight["reservedSubjectCount"],
        "reservedSessionCount": preflight["reservedSessionCount"],
        "expectedCaptureCount": preflight["expectedCaptureCount"],
        "requiredViews": list(REQUIRED_VIEWS),
        "cameraReservationDigest": preflight["cameraReservationDigest"],
        **SAFE_POLICY,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-mapping-receipt", type=Path)
    source.add_argument("--private-manifest", type=Path)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if args.source_mapping_receipt is not None:
        receipt = json.loads(args.source_mapping_receipt.read_text(encoding="utf-8"))
        preflight = summarize_committed_facts(receipt)
        if args.artifact_output is not None:
            raise CameraReservationInputError("committed partial facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
