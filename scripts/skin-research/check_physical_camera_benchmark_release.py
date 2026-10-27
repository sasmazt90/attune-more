#!/usr/bin/env python3
"""Fail-closed common gate for independent physical-camera acceptance.

The merged product already returns concrete skin results.  Generated triplets
remain useful integration smoke tests, but cannot be relabelled as physical
camera, expert truth, threshold calibration or accuracy evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_INPUT_BLOBS = {
    "scripts/skin-research/prepare_camera_triplet_benchmark.py": "b6294409b8421bf0e3f503f9112f14c7c180a057",
    "docs/skin/evidence/camera-triplet-generated-smoke-20261024-v1.json": "5b44b0b8c03096c8dab3afa01ae2f5235d65193c",
    "docs/skin/evidence/generated-front-roboflow-20261024-v1.json": "15ea84ab4d755b8027020dd5e8d39b2036563bef",
    "docs/skin/evidence/gate-pass-camera-package-audit-20261024-v1.json": "b4a8f279de93abb56bc8c5ebc589fd4a9e9a68b8",
    "docs/skin/evidence/attune-v5-results-package-audit-20261024-v1.json": "c57fee8bb2cfc3fc9edda01f625818371b244580",
    "docs/skin/evidence/original-photo-model-comparison-audit-20261024.json": "7308f5cc14d5c96fc0baaa4aa521cb2f3a990d03",
    "docs/skin/evidence/current-product-skin-contract-recheck-20261025-v1.json": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "scripts/skin-research/check_unified_skin_result_release.py": "c6304b0a5f303f50fbe22f0eb8dadbbd7c1a8b51",
}
EXPECTED_HEADINGS = [
    "tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags",
    "Post acne", "Pigmentation", "skinType",
]


class CameraGateError(ValueError):
    """Raised when immutable camera or product evidence changes."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise CameraGateError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
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
    accepted = not blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-benchmark-release-gate-v1",
        "workingBaselinePreserved": True,
        "generatedIntegrationSmokeAllowed": True,
        "generatedAccuracyEvidenceAllowed": False,
        "generatedPhysicalCameraAcceptanceAllowed": False,
        "physicalCameraBenchmarkAccepted": accepted,
        "roadmapCameraAcceptanceAllowed": accepted,
        "blockers": blockers,
        "decision": "ready" if accepted else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(json.loads(args.receipt.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
