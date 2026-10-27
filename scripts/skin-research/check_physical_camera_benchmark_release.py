#!/usr/bin/env python3
"""Fail-closed common gate for independent physical-camera acceptance.

Generated triplets remain useful integration smoke tests, but cannot be
relabelled as physical camera, expert truth, threshold calibration or accuracy
evidence. A physical-camera release requires seven real pipeline artifacts,
each bound by a file SHA-256 and shared benchmark/method identity. Receipt
booleans alone can never make the gate ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_RECEIPT_SCHEMA = 2
EXPECTED_INPUT_BLOBS = {
    "scripts/skin-research/prepare_camera_triplet_benchmark.py": "b6294409b8421bf0e3f503f9112f14c7c180a057",
    "docs/skin/evidence/camera-triplet-generated-smoke-20261024-v1.json": "5b44b0b8c03096c8dab3afa01ae2f5235d65193c",
    "docs/skin/evidence/generated-front-roboflow-20261024-v1.json": "15ea84ab4d755b8027020dd5e8d39b2036563bef",
    "docs/skin/evidence/gate-pass-camera-package-audit-20261024-v1.json": "b4a8f279de93abb56bc8c5ebc589fd4a9e9a68b8",
    "docs/skin/evidence/attune-v5-results-package-audit-20261024-v1.json": "c57fee8bb2cfc3fc9edda01f625818371b244580",
    "docs/skin/evidence/original-photo-model-comparison-audit-20261024.json": "7308f5cc14d5c96fc0baaa4aa521cb2f3a990d03",
    "docs/skin/evidence/current-product-skin-contract-recheck-20261025-v1.json": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
}
EXPECTED_HEADINGS = [
    "tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags",
    "Post acne", "Pigmentation", "skinType",
]
EXPECTED_ARTIFACT_METHODS = {
    "cameraManifest": "physical-camera-benchmark-manifest-v1",
    "expertTruth": "physical-camera-expert-truth-v1",
    "captureEvaluation": "physical-camera-capture-level-evaluation-v1",
    "localizationEvaluation": "physical-camera-localization-evaluation-v1",
    "acceptancePolicy": "physical-camera-acceptance-policy-v1",
    "productReplay": "physical-camera-product-replay-v1",
    "acceptanceGate": "physical-camera-acceptance-gate-v1",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")


class CameraGateError(ValueError):
    """Raised when immutable camera or product evidence changes."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise CameraGateError(message)


def _positive_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CameraGateError(message)
    return value


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise CameraGateError(f"{field} must be an opaque reference")
    return value


def _load_artifact(identity: Any, label: str, evidence_root: Path) -> dict[str, Any]:
    if not isinstance(identity, dict) or set(identity) != {"path", "sha256"}:
        raise CameraGateError(f"{label} evidence identity is incomplete")
    path = identity.get("path")
    digest = identity.get("sha256")
    if not isinstance(path, str):
        raise CameraGateError(f"{label} evidence path is invalid")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not path.startswith("docs/skin/evidence/physical-camera-"):
        raise CameraGateError(f"{label} evidence path is outside the physical-camera evidence registry")
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None or digest == "0" * 64:
        raise CameraGateError(f"{label} evidence sha256 is invalid")
    file_path = evidence_root / path
    if not file_path.is_file():
        raise CameraGateError(f"{label} evidence file is missing")
    raw = file_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise CameraGateError(f"{label} evidence digest mismatch")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CameraGateError(f"{label} evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CameraGateError(f"{label} evidence must be a JSON object")
    return payload


def _validate_artifacts(candidate: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    registry = candidate.get("artifacts")
    if not isinstance(registry, dict) or set(registry) != set(EXPECTED_ARTIFACT_METHODS):
        raise CameraGateError("physical-camera artifact registry is incomplete")
    artifacts = {
        name: _load_artifact(registry[name], name, evidence_root)
        for name in EXPECTED_ARTIFACT_METHODS
    }
    for name, expected_method in EXPECTED_ARTIFACT_METHODS.items():
        _require(artifacts[name].get("methodVersion"), expected_method, f"{name} method identity changed")

    manifest = artifacts["cameraManifest"]
    _require(manifest.get("sourceType"), "physical-camera", "camera manifest source changed")
    _require(manifest.get("generated"), False, "generated evidence cannot enter camera manifest")
    _require(manifest.get("split"), "camera_final", "camera manifest split changed")
    _require(manifest.get("completeThreePoseTriplets"), True, "camera triplets are incomplete")
    _require(
        manifest.get("subjectIndependentFromTrainingValidationThresholdSelection"), True,
        "camera subject independence is not established",
    )
    _require(manifest.get("containsImageBytesOrPaths"), False, "camera manifest privacy contract changed")
    _require(manifest.get("containsModelPredictions"), False, "camera manifest cannot contain predictions")
    _require(manifest.get("containsExpertTruth"), False, "camera manifest must keep expert truth separate")
    subject_count = _positive_int(manifest.get("subjectCount"), "camera manifest requires subjects")
    capture_count = _positive_int(manifest.get("captureCount"), "camera manifest requires captures")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or len(captures) != capture_count or capture_count != subject_count * 3:
        raise CameraGateError("camera manifest counts do not describe exact three-pose triplets")
    capture_refs = {row.get("captureRef") for row in captures if isinstance(row, dict)}
    if len(capture_refs) != capture_count or None in capture_refs:
        raise CameraGateError("camera manifest capture references are invalid")

    truth = artifacts["expertTruth"]
    _require(truth.get("cameraManifestMethodVersion"), manifest["methodVersion"], "expert truth manifest identity changed")
    _require(truth.get("captureCount"), capture_count, "expert truth capture count changed")
    classes = truth.get("activatedClasses")
    if not isinstance(classes, list) or not classes or len(classes) != len(set(classes)):
        raise CameraGateError("expert truth activated classes are invalid")
    _require(truth.get("truthCellCount"), capture_count * len(classes), "expert truth matrix is incomplete")
    for field, expected in {
        "twoIndependentHumanReviewsPerCell": True,
        "modelProposalUsedAsTruth": False,
        "missingTruthInterpretedAsNegative": False,
        "unknownInterpretedAsNormal": False,
        "rednessIndependentFromSensitivity": True,
        "rednessOverlapAllowed": True,
        "normalRequiresExplicitEvaluatedTruth": True,
    }.items():
        _require(truth.get(field), expected, f"expert truth {field} changed")

    capture_eval = artifacts["captureEvaluation"]
    localization = artifacts["localizationEvaluation"]
    method_ref = _opaque(capture_eval.get("evaluatedMethodRef"), "evaluatedMethodRef")
    method_version = capture_eval.get("evaluatedMethodVersion")
    if not isinstance(method_version, str) or not method_version:
        raise CameraGateError("evaluatedMethodVersion is missing")
    threshold_ref = _opaque(capture_eval.get("thresholdLockRef"), "thresholdLockRef")
    geometry_ref = _opaque(localization.get("geometryLockRef"), "geometryLockRef")
    for payload, label in ((capture_eval, "capture evaluation"), (localization, "localization evaluation")):
        _require(payload.get("evaluatedMethodRef"), method_ref, f"{label} method ref changed")
        _require(payload.get("evaluatedMethodVersion"), method_version, f"{label} method version changed")
        _require(payload.get("thresholdLockRef"), threshold_ref, f"{label} threshold lock changed")
        _require(payload.get("cameraFinalUsedForThresholdSelection"), False, f"{label} leaked camera_final into threshold selection")
        metrics = payload.get("classMetrics")
        if not isinstance(metrics, dict) or set(metrics) != set(classes):
            raise CameraGateError(f"{label} class inventory changed")
    _require(capture_eval.get("captureLevelMetricsComputed"), True, "capture metrics are missing")
    _require(capture_eval.get("activationAllowed"), False, "capture evaluator cannot activate a method")
    _require(localization.get("localizationMetricsComputed"), True, "localization metrics are missing")
    _require(localization.get("activationAllowed"), False, "localization evaluator cannot activate a method")
    _require(localization.get("cameraFinalUsedForGeometrySelection"), False, "camera_final selected geometry")
    _require(localization.get("boxesAcceptedAsPolygons"), False, "boxes cannot become polygons")
    _require(localization.get("modelGeometryUsedAsExpertTruth"), False, "model geometry cannot become expert truth")

    policy = artifacts["acceptancePolicy"]
    policy_ref = _opaque(policy.get("policyRef"), "policyRef")
    for field, expected in {
        "lockedBeforeCameraFinal": True,
        "cameraFinalUsedForPolicySelection": False,
        "policyMutatedAfterLock": False,
        "appliesToMethodRef": method_ref,
        "appliesToMethodVersion": method_version,
        "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref,
        "applyPerClassWithoutMacroAveraging": True,
        "applySameMinimumsToEveryObservedSlice": True,
    }.items():
        _require(policy.get(field), expected, f"acceptance policy {field} changed")
    policy_classes = policy.get("classes")
    if not isinstance(policy_classes, list) or {row.get("classId") for row in policy_classes if isinstance(row, dict)} != set(classes):
        raise CameraGateError("acceptance policy class inventory changed")

    replay = artifacts["productReplay"]
    replay_ref = _opaque(replay.get("replayRef"), "replayRef")
    replay_expected = {
        "sourceType": "physical-camera", "generated": False, "split": "camera_final",
        "endpoint": "/api/local-health/skin", "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version, "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref, "realBrowser": True, "apiPassed": True,
        "overviewPassed": True, "everyRegionPassed": True, "mapPassed": True,
        "historyWriteReadPassed": True, "methodIncompatibleHistoryExcluded": True,
        "unavailableStatePassed": True, "retainedPhotoReplayPassed": True,
        "privacyRetentionDeletionPassed": True, "normalRequiresExplicitEvaluatedTruth": True,
        "unknownNeverRenderedAsNormal": True, "rednessIndependentFromSensitivity": True,
        "rednessOverlapAllowed": True, "physicalCaptureCount": capture_count,
    }
    for field, expected in replay_expected.items():
        _require(replay.get(field), expected, f"product replay {field} changed")
    replay_classes = replay.get("classes")
    if not isinstance(replay_classes, list) or {row.get("classId") for row in replay_classes if isinstance(row, dict)} != set(classes):
        raise CameraGateError("product replay class inventory changed")

    gate = artifacts["acceptanceGate"]
    for field, expected in {
        "policyRef": policy_ref, "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version, "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref, "everyClassPassedIndependently": True,
        "everyObservedSlicePassedIndependently": True, "macroAveragingUsed": False,
        "trainingFinishedOrRecommendedUsedAsAcceptance": False,
        "realProductReplayPassed": True, "mapContractPassed": True,
        "cameraAccepted": True, "activationAllowed": True,
    }.items():
        _require(gate.get(field), expected, f"acceptance gate {field} changed")
    verdicts = gate.get("classVerdicts")
    if not isinstance(verdicts, dict) or set(verdicts) != set(classes):
        raise CameraGateError("acceptance gate class inventory changed")
    if any(not isinstance(row, dict) or row.get("passed") is not True for row in verdicts.values()):
        raise CameraGateError("every activated class must pass independently")

    manifest_sha = registry["cameraManifest"]["sha256"]
    _require(candidate.get("benchmarkId"), f"camera_benchmark_{manifest_sha[:16]}", "camera benchmark identity changed")
    for field, expected in {
        "evaluatedMethodRef": method_ref, "evaluatedMethodVersion": method_version,
        "thresholdLockRef": threshold_ref, "geometryLockRef": geometry_ref,
        "policyRef": policy_ref, "replayRef": replay_ref,
    }.items():
        _require(candidate.get(field), expected, f"physical-camera candidate {field} changed")
    return {
        "benchmarkId": candidate["benchmarkId"],
        "subjectCount": subject_count,
        "captureCount": capture_count,
        "activatedClasses": sorted(classes),
        "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version,
        "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref,
        "policyRef": policy_ref,
        "replayRef": replay_ref,
        "artifactSha256": {name: registry[name]["sha256"] for name in EXPECTED_ARTIFACT_METHODS},
    }


def evaluate_release(receipt: dict[str, Any], evidence_root: Path = ROOT) -> dict[str, Any]:
    _require(receipt.get("schemaVersion"), EXPECTED_RECEIPT_SCHEMA, "physical-camera receipt schema changed")
    _require(receipt.get("methodVersion"), "physical-camera-benchmark-release-receipt-v2", "physical-camera receipt method changed")
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "camera evidence blobs changed")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working output cannot become missing")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("headings"), EXPECTED_HEADINGS, "product heading inventory changed")
    _require(baseline.get("regionalResults"), True, "regional result flow changed")
    _require(baseline.get("overviewAndHistory"), True, "overview/history flow changed")

    generated = receipt.get("generatedEvidence", {})
    _require(generated.get("declaredGenerated"), True, "generated source identity changed")
    _require(generated.get("subjects"), 6, "generated subject count changed")
    _require(generated.get("images"), 18, "generated image count changed")
    _require(generated.get("completeThreePoseTriplets"), True, "generated triplets changed")
    _require(generated.get("rawImagesCommitted"), False, "generated image privacy changed")
    _require(generated.get("realCameraCapture"), False, "generated images cannot become physical camera")
    _require(generated.get("expertGroundTruth"), False, "generated images cannot become expert truth")
    _require(generated.get("precisionRecallF1Eligible"), False, "generated images cannot become metric truth")
    _require(generated.get("thresholdCalibrationEligible"), False, "generated images cannot calibrate thresholds")
    _require(generated.get("integrationSmokeAllowed"), True, "generated integration smoke changed")

    contract = receipt.get("acceptanceContract", {})
    _require(contract.get("generatedMaySatisfyPhysicalCamera"), False, "generated images cannot satisfy camera acceptance")
    _require(contract.get("modelPredictionMayServeAsExpertTruth"), False, "model predictions cannot serve as expert truth")
    _require(contract.get("sameSubjectMayCrossTrainingOrThresholdSets"), False, "camera identities must remain independent")
    _require(contract.get("thresholdsMayBeFitOnCameraFinal"), False, "final camera data cannot fit thresholds")
    _require(contract.get("missingClassTruthMeansNegative"), False, "missing class truth cannot become negative")
    _require(contract.get("unknownCountsAsNormal"), False, "unknown cannot count as normal")
    _require(contract.get("rednessIsIndependentLayer"), True, "redness must remain independent")

    candidate = receipt.get("physicalCameraCandidate", {})
    requirements = {
        "consentedPhysicalCaptures": "consented_physical_captures_missing",
        "immutableCaptureHashes": "immutable_capture_hashes_missing",
        "subjectIdentityIndependent": "subject_independence_missing",
        "notUsedForTrainingValidationOrThresholdSelection": "camera_final_set_not_locked",
        "expertTruthPerActivatedClass": "expert_truth_per_activated_class_missing",
        "evaluatedNegativeAndUnknownPolicy": "evaluated_negative_unknown_policy_missing",
        "deviceLightingSkinTonePoseSlices": "camera_slice_coverage_missing",
        "captureQualityGateRecorded": "capture_quality_gate_evidence_missing",
        "lockedThresholdsAndMethodIdentity": "locked_threshold_method_identity_missing",
        "perClassMetricsAndFailuresRecorded": "per_class_camera_metrics_missing",
        "apiBrowserMapHistoryReplayPassed": "working_product_camera_replay_missing",
        "privacyRetentionDeletionPassed": "camera_privacy_lifecycle_missing",
    }
    blockers = [reason for field, reason in requirements.items() if candidate.get(field) is not True]
    registry = candidate.get("artifacts")
    if not isinstance(registry, dict) or set(registry) != set(EXPECTED_ARTIFACT_METHODS):
        blockers.append("physical_camera_artifact_registry_missing")
        identity = None
    else:
        missing = [name for name in EXPECTED_ARTIFACT_METHODS if not isinstance(registry.get(name), dict)]
        blockers.extend(f"{name}_evidence_missing" for name in missing)
        identity = None if missing else _validate_artifacts(candidate, evidence_root)
    accepted = not blockers and identity is not None
    return {
        "schemaVersion": 2,
        "methodVersion": "physical-camera-benchmark-release-gate-v2",
        "workingBaselinePreserved": True,
        "generatedIntegrationSmokeAllowed": True,
        "generatedAccuracyEvidenceAllowed": False,
        "generatedPhysicalCameraAcceptanceAllowed": False,
        "evidenceRegistryRequired": True,
        "evidenceRegistryComplete": identity is not None,
        "physicalCameraBenchmarkIdentity": identity,
        "physicalCameraBenchmarkAccepted": accepted,
        "roadmapCameraAcceptanceAllowed": accepted,
        "blockers": blockers,
        "decision": "ready" if accepted else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = evaluate_release(json.loads(args.receipt.read_text(encoding="utf-8")), args.evidence_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
