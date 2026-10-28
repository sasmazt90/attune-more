#!/usr/bin/env python3
"""Assemble and validate the eight-artifact source-mapping release candidate.

This tool removes manual receipt editing from the release path.  It binds each
public release artifact by repository path and SHA-256, derives the shared
opaque identities, and delegates the final decision to the existing fail-closed
source-mapping gate.  Missing or inconsistent evidence cannot emit a receipt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = Path(__file__).with_name("check_source_mapping_release.py")
GATE_SPEC = importlib.util.spec_from_file_location("source_mapping_release_gate_for_builder", GATE_PATH)
GATE = importlib.util.module_from_spec(GATE_SPEC)
sys.modules[GATE_SPEC.name] = GATE
GATE_SPEC.loader.exec_module(GATE)

INPUT_METHOD = "skin-source-mapping-release-candidate-input-v1"
PREFLIGHT_METHOD = "skin-source-mapping-release-candidate-preflight-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
ARTIFACT_NAMES = tuple(GATE.EXPECTED_ARTIFACT_METHODS)
ACCEPTANCE_FLAGS = (
    "allFourExcludedArchivesReconciled",
    "allArchiveHashesVerified",
    "allRightsReviewed",
    "perClassExpertSemanticsLocked",
    "allGeometryAudited",
    "sourcePersonGroupingComplete",
    "lockedTrainValidationFinalTestSplit",
    "independentCameraReserved",
)


class SourceMappingCandidateInputError(ValueError):
    """Raised when evidence identities or release semantics are unsafe."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_evidence_path(value: Any) -> str:
    if not isinstance(value, str):
        raise SourceMappingCandidateInputError("artifact path must be a string")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or not value.startswith("docs/skin/evidence/")
        or not pure.name.endswith(".json")
    ):
        raise SourceMappingCandidateInputError("artifact path is outside the public source evidence registry")
    return value


def _read_artifact(path: str, evidence_root: Path) -> tuple[dict[str, Any], str]:
    file_path = evidence_root / path
    if not file_path.is_file():
        raise SourceMappingCandidateInputError(f"artifact file is missing: {path}")
    raw = file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceMappingCandidateInputError(f"artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SourceMappingCandidateInputError(f"artifact must be a JSON object: {path}")
    return payload, digest


def _validate_inputs(base_receipt: dict[str, Any], manifest: dict[str, Any]) -> None:
    if base_receipt.get("schemaVersion") != 2 or base_receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise SourceMappingCandidateInputError("base source-mapping receipt identity changed")
    if manifest.get("schemaVersion") not in (None, 1) or manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise SourceMappingCandidateInputError("artifact manifest identity changed")
    if set(manifest) - {"schemaVersion", "methodVersion", "artifacts"}:
        raise SourceMappingCandidateInputError("artifact manifest fields changed")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_NAMES):
        raise SourceMappingCandidateInputError("artifact manifest inventory is incomplete")


def _assemble(
    base_receipt: dict[str, Any],
    manifest: dict[str, Any],
    evidence_root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    _validate_inputs(base_receipt, manifest)
    blockers: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, str]] = {}
    for name in ARTIFACT_NAMES:
        path_value = manifest["artifacts"].get(name)
        if path_value is None:
            blockers.append(f"{name}_evidence_missing")
            continue
        path = _safe_evidence_path(path_value)
        payload, digest = _read_artifact(path, evidence_root)
        expected_method = GATE.EXPECTED_ARTIFACT_METHODS[name]
        if payload.get("methodVersion") != expected_method:
            raise SourceMappingCandidateInputError(f"{name} method identity changed")
        payloads[name] = payload
        identities[name] = {"path": path, "sha256": digest}

    if blockers:
        preflight = {
            "schemaVersion": 1,
            "methodVersion": PREFLIGHT_METHOD,
            "artifactCount": len(identities),
            "requiredArtifactCount": len(ARTIFACT_NAMES),
            "evidenceRegistryComplete": False,
            "trainingDataReleaseAuthorized": False,
            "productTruthAuthorized": False,
            "readyToEmitReceipt": False,
            "decision": "blocked",
            "blockers": sorted(blockers),
        }
        return preflight, None, None

    release_refs = {payload.get("releaseRef") for payload in payloads.values()}
    if len(release_refs) != 1:
        raise SourceMappingCandidateInputError("artifact release identities disagree")
    release_ref = next(iter(release_refs))
    if not isinstance(release_ref, str) or OPAQUE_RE.fullmatch(release_ref) is None:
        raise SourceMappingCandidateInputError("artifact release identity is not opaque")

    registry_ref = payloads["archiveHashRegistry"].get("sourceRegistryRef")
    split_ref = payloads["lockedSplit"].get("splitRef")
    camera_ref = payloads["cameraReservation"].get("cameraReservationRef")
    for label, value in (
        ("source registry", registry_ref),
        ("split", split_ref),
        ("camera reservation", camera_ref),
    ):
        if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
            raise SourceMappingCandidateInputError(f"{label} identity is not opaque")

    candidate_receipt = copy.deepcopy(base_receipt)
    acceptance = candidate_receipt.get("acceptanceCandidate")
    if not isinstance(acceptance, dict):
        raise SourceMappingCandidateInputError("base receipt acceptance candidate is missing")
    acceptance.update({
        "releaseRef": release_ref,
        "sourceRegistryRef": registry_ref,
        "splitRef": split_ref,
        "cameraReservationRef": camera_ref,
        "artifacts": identities,
    })
    for field in ACCEPTANCE_FLAGS:
        acceptance[field] = True

    gate = GATE.evaluate_release(candidate_receipt, evidence_root)
    ready = bool(
        gate.get("evidenceRegistryComplete")
        and gate.get("trainingDataReleaseAuthorized")
        and gate.get("productTruthAuthorized")
    )
    if not ready:
        raise SourceMappingCandidateInputError(
            "complete artifact registry was rejected by the source-mapping release gate"
        )
    registry_digest = hashlib.sha256(_canonical_bytes(identities)).hexdigest()
    receipt_digest = hashlib.sha256(_canonical_bytes(candidate_receipt)).hexdigest()
    preflight = {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref,
        "sourceRegistryRef": registry_ref,
        "splitRef": split_ref,
        "cameraReservationRef": camera_ref,
        "artifactCount": len(identities),
        "requiredArtifactCount": len(ARTIFACT_NAMES),
        "artifactRegistrySHA256": registry_digest,
        "candidateReceiptSHA256": receipt_digest,
        "evidenceRegistryComplete": True,
        "trainingDataReleaseAuthorized": True,
        "productTruthAuthorized": True,
        "readyToEmitReceipt": True,
        "decision": "ready",
        "blockers": [],
    }
    return preflight, candidate_receipt, gate


def evaluate_manifest(
    base_receipt: dict[str, Any],
    manifest: dict[str, Any],
    evidence_root: Path = ROOT,
) -> dict[str, Any]:
    return _assemble(base_receipt, manifest, evidence_root)[0]


def build_candidate_receipt(
    base_receipt: dict[str, Any],
    manifest: dict[str, Any],
    evidence_root: Path = ROOT,
) -> dict[str, Any]:
    preflight, receipt, _ = _assemble(base_receipt, manifest, evidence_root)
    if not preflight["readyToEmitReceipt"] or receipt is None:
        raise SourceMappingCandidateInputError("source-mapping release candidate is incomplete")
    return receipt


def build_gate_output(
    base_receipt: dict[str, Any],
    manifest: dict[str, Any],
    evidence_root: Path = ROOT,
) -> dict[str, Any]:
    preflight, _, gate = _assemble(base_receipt, manifest, evidence_root)
    if not preflight["readyToEmitReceipt"] or gate is None:
        raise SourceMappingCandidateInputError("source-mapping release candidate is incomplete")
    return gate


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-receipt", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path)
    parser.add_argument("--gate-output", type=Path)
    args = parser.parse_args()
    base_receipt = json.loads(args.base_receipt.read_text(encoding="utf-8"))
    manifest = json.loads(args.artifact_manifest.read_text(encoding="utf-8"))
    preflight, receipt, gate = _assemble(base_receipt, manifest)
    if args.receipt_output is not None or args.gate_output is not None:
        if not preflight["readyToEmitReceipt"] or receipt is None or gate is None:
            raise SourceMappingCandidateInputError("source-mapping release candidate is incomplete")
        if args.receipt_output is not None:
            _write_json(args.receipt_output, receipt)
        if args.gate_output is not None:
            _write_json(args.gate_output, gate)
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyToEmitReceipt"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
