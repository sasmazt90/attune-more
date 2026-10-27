#!/usr/bin/env python3
"""Identity-bound release gate for broad regional tone unevenness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SEPARATION_VERSION = "tone-localized-pigmentation-separation-v1"
TONE_MEANING = "broad-regional-chromatic-variation"
BASE_METHOD_ID = "regional-cielab-chromatic-variation-v1"
EXPECTED_CODE_BLOBS = {
    "services/core-api/skin_product_contract.py": "f152726978bee2eea36b0563d9ac36cbcf330c7b",
    "services/core-api/skin_general.py": "ef5869c6801d3845ec8424e17474b3a3e0fd665a",
    "services/core-api/appearance_analysis.py": "1ebb762a76865f4a33f7f0d5aadab36a5115d46e",
    "apps/vehicle-app/src/utils/skinIndicators.ts": "eeb3599bec0361bcca7298fc277fa53a32fc06d5",
    "apps/vehicle-app/src/utils/skinOverview.ts": "4d31010f82bfd5c42a49b46c20880630d57079dd",
}
EXPECTED_INPUT_BLOBS = {
    "contractEvidence": "2415926f1706a8a8991a5180fe338a01bd1391d8",
    "currentProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "cameraManifestBuilder": "455f8dcf377c45a5db2cdb637a81ea6f19fd5688",
    "cameraExpertTruthBuilder": "77bb863346c69f6838af091339f715f3f04424fd",
    "cameraPredictionEvaluator": "4ce05c088449adf0d61a801c18c2316787cd926a",
    "cameraBenchmarkReleaseGate": "53c3710166c2e5e43becd36234e10bafe68ac659",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GateInputError(ValueError):
    """Raised when a frozen product identity or semantic boundary drifts."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _require_evidence_identity(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise GateInputError(f"{label} evidence identity missing")
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path.startswith("docs/skin/evidence/"):
        raise GateInputError(f"{label} evidence path missing")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None or digest == "0" * 64:
        raise GateInputError(f"{label} evidence sha256 missing")


def _validate_calibrated_candidate(candidate: dict[str, Any]) -> tuple[bool, list[str], str | None]:
    mode = candidate.get("mode")
    if mode not in {"uncalibrated-proxy", "accepted-calibrated-proxy"}:
        raise GateInputError("unknown tone candidate mode")
    identity_fields = (
        "methodId",
        "calibrationReleaseId",
        "cameraBenchmarkId",
        "captureProtocolId",
        "lockedPolicyId",
    )
    if mode == "uncalibrated-proxy":
        if any(candidate.get(field) is not None for field in identity_fields) or candidate.get("acceptanceEvidence") is not None:
            raise GateInputError("uncalibrated proxy cannot claim accepted calibration identities")
        return False, ["accepted_calibrated_tone_method_missing"], None

    method_id = candidate.get("methodId")
    if not isinstance(method_id, str) or not method_id or method_id == BASE_METHOD_ID:
        raise GateInputError("distinct calibrated tone method identity missing")
    for field in identity_fields[1:]:
        value = candidate.get(field)
        if not isinstance(value, str) or not value:
            raise GateInputError(f"calibrated tone {field} missing")
    _require_evidence_identity(candidate.get("acceptanceEvidence"), "calibrated tone")
    _require(candidate.get("accepted"), True, "calibrated tone method is not accepted")
    _require(candidate.get("truthSource"), "adjudicated-physical-camera", "tone calibration requires camera expert truth")
    _require(candidate.get("thresholdSelectionSplit"), "validation", "tone policy must be selected on validation")
    _require(candidate.get("cameraFinalUsedForSelection"), False, "camera final cannot select the tone policy")
    return True, [], method_id


def _validate_localized_support(localized: dict[str, Any]) -> tuple[bool, list[str]]:
    mode = localized.get("mode")
    if mode not in {"unavailable", "accepted-localized-methods"}:
        raise GateInputError("unknown localized pigmentation support mode")
    if mode == "unavailable":
        if localized.get("methodIds") != [] or localized.get("acceptanceEvidence") is not None:
            raise GateInputError("unavailable localized support cannot claim accepted methods")
        return False, []

    method_ids = localized.get("methodIds")
    if not isinstance(method_ids, list) or not method_ids or any(not isinstance(value, str) or not value for value in method_ids):
        raise GateInputError("accepted localized method identities missing")
    if len(method_ids) != len(set(method_ids)):
        raise GateInputError("localized method identities must be distinct")
    _require_evidence_identity(localized.get("acceptanceEvidence"), "localized support")
    _require(localized.get("accepted"), True, "localized pigmentation support is not accepted")
    blockers = []
    if localized.get("excludedFromToneSampling") is not True:
        blockers.append("accepted_localized_support_not_excluded_from_tone")
    if localized.get("independentCameraCoReportingPassed") is not True:
        blockers.append("localized_tone_coreporting_camera_acceptance_missing")
    return True, blockers


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "input blobs changed")
    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "semantic implementation blobs changed")

    baseline = receipt.get("currentProductBaseline", {})
    _require(baseline.get("commit"), "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285", "merged baseline changed")
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product baseline cannot be erased")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("toneHeadingPresent"), True, "existing tone heading was lost")
    _require(baseline.get("regionalResultsPresent"), True, "existing regional result flow was lost")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("separationVersion"), SEPARATION_VERSION, "separation version changed")
    _require(contract.get("toneMeaning"), TONE_MEANING, "tone meaning changed")
    _require(contract.get("baseMethodId"), BASE_METHOD_ID, "base tone method identity changed")
    _require(contract.get("clinicalSeverity"), False, "tone cannot claim clinical severity")
    _require(contract.get("localizedPigmentationDetector"), False, "tone cannot become a localized pigmentation detector")
    _require(contract.get("toneCanSupplyPostAcne"), False, "tone cannot populate Post acne")
    _require(contract.get("toneCanSupplyPigmentation"), False, "tone cannot populate Pigmentation")
    _require(contract.get("missingLocalizedResultMeansZero"), False, "an unavailable localized result cannot become zero")
    _require(contract.get("localizedHeadingsSeparate"), True, "localized headings must remain separate")
    _require(contract.get("unknownOrUnassessableMeansNormal"), False, "unknown tone cannot become normal")

    current = receipt.get("currentProxy", {})
    _require(current.get("mode"), "regional-cielab-appearance-proxy", "current tone proxy changed")
    _require(current.get("methodId"), BASE_METHOD_ID, "current tone method identity changed")
    _require(current.get("clinicalClaimsDisabled"), True, "clinical tone claims must remain disabled")
    _require(current.get("localizedHeadingsDerivedFromTone"), False, "localized headings cannot be derived from tone")
    _require(current.get("calibrationAccepted"), False, "uncalibrated proxy cannot become accepted")

    preparation = receipt.get("preparation", {})
    calibration_requirements = {
        "cameraCalibrationProtocolComplete": "camera_calibration_protocol_missing",
        "sourcePersonIndependentCalibrationSplit": "calibration_source_person_independence_missing",
        "adjudicatedExpertToneTruthComplete": "adjudicated_tone_truth_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
        "untouchedPhysicalCameraFinalReserved": "untouched_physical_camera_final_missing",
    }
    preparation_blockers = [reason for field, reason in calibration_requirements.items() if preparation.get(field) is not True]
    calibration_evaluation_authorized = not preparation_blockers

    candidate = receipt.get("candidate", {})
    calibrated, identity_blockers, method_id = _validate_calibrated_candidate(candidate)
    validation = receipt.get("calibrationValidation", {})
    if calibrated:
        _require(validation.get("methodId"), method_id, "validation is not bound to the calibrated tone method")
    validation_blockers = list(preparation_blockers) + identity_blockers
    for field, reason in (
        ("illuminationShadowHairWhiteBalanceRobustnessPassed", "illumination_shadow_hair_white_balance_robustness_missing"),
        ("skinToneSubgroupCalibrationPassed", "skin_tone_subgroup_calibration_missing"),
        ("samePersonRepeatabilityPassed", "same_person_repeatability_missing"),
        ("policyLockedBeforeCameraFinal", "policy_not_locked_before_camera_final"),
        ("untouchedPhysicalCameraFinalPassed", "untouched_physical_camera_final_acceptance_missing"),
        ("deviceLightingSkinTonePoseSlicesPassed", "tone_camera_slices_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_replay_missing"),
        ("unknownUnavailableAndHistoryControlsPassed", "tone_unknown_unavailable_history_controls_missing"),
    ):
        if validation.get(field) is not True:
            validation_blockers.append(reason)
    if calibrated:
        _require_evidence_identity(validation.get("acceptanceEvidence"), "tone validation")

    localized_available, localized_blockers = _validate_localized_support(receipt.get("localizedSupport", {}))
    activation_blockers = list(validation_blockers) + localized_blockers
    calibrated_activation = calibrated and not activation_blockers
    localized_coreporting = localized_available and not localized_blockers and calibrated_activation
    return {
        "schemaVersion": 2,
        "methodVersion": "tone-unevenness-release-gate-v2",
        "existingConcreteResultFlowPreserved": True,
        "currentProxyPresentationAllowed": True,
        "currentProxyClaim": "broad regional chromatic-variation appearance only",
        "clinicalSeverityClaimAllowed": False,
        "toneCanSupplyPostAcne": False,
        "toneCanSupplyPigmentation": False,
        "acceptedCalibratedMethodPresent": calibrated,
        "acceptedCalibratedMethodId": method_id,
        "calibrationEvaluationAuthorized": calibration_evaluation_authorized,
        "calibratedToneActivationAllowed": calibrated_activation,
        "localizedCoReportingAllowed": localized_coreporting,
        "roadmapAccepted": calibrated_activation,
        "preparationBlockers": preparation_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if calibrated_activation else "blocked",
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
