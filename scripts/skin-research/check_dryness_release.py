#!/usr/bin/env python3
"""Fail-closed release gate for regional dryness and visible flaking.

The current source pool mixes box-only, processed-image, broad dry-skin and
visible-flaking semantics. This gate preserves those distinctions: boxes are
localization proposals, never blue regional masks; missing labels are never
normal truth; and a generic Dryness label cannot silently become confirmed
facial flaking.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_INPUT_BLOBS = {
    "clean3": "11f300fe126246e65616cc22e7f2a43c0994f0a2",
    "merve": "0519d6e87d2206f0387f5c69784b42b52b960ca5",
    "sourceAcquisition": "632ab9084f71f8ea3019ec923f9ffd7bf2b42bf7",
    "sourceReviewChecks": "7318b1345ba67e606ae6ad4e68fab6d2c662fbdd",
    "skinTypeBoxes": "3c9114c9e7892f6ed03dfffb7eea92ce212bc408",
    "skinTypeGroupResolution": "4aec8f0657b7df8c958711f946baea8fd471bc3c",
    "mergedProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "unifiedResultReceipt": "aac52634eaba105cd1ccc86383b7665eca7b53eb",
}

EXPECTED_ARCHIVES = {
    "clean3": "461c70bb46307273af60334259bec685981e4fb99348fbeb0fc04e6102466fc3",
    "merve": "8fdf070c0cae65fd27ce0046c93393e0ac17e5282bf472097453c756481b831e",
    "drynessV1": "caa1d873d1c98a507ed37a31c42e2f7a0cd543d494e65d0be1f67f15b5b483f4",
    "faceV3": "7c06f1c48d049c1c419d909d488c6642465f0f57958a42eaa62569527ee3094c",
    "skinTypeBoxes": "4af7732298a0f54c3e1bd4aa68ca954429c39a19a832331a4ce542ae365fa228",
}
EXPECTED_PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"


class GateInputError(ValueError):
    """Raised when a frozen source fact or semantic boundary is contradicted."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _validate_candidate_identity(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    mode = candidate.get("mode")
    if mode not in {"not-trained", "new-model"}:
        raise GateInputError("unknown dryness candidate mode")
    project_id = candidate.get("projectId")
    model_id = candidate.get("modelId")
    training_id = candidate.get("trainingId")
    version = candidate.get("datasetVersion")
    if mode == "not-trained":
        if project_id is not None or model_id is not None or training_id is not None or version is not None:
            raise GateInputError("not-trained candidate cannot claim a model identity")
        return False, ["distinct_dryness_candidate_model_missing"]
    if project_id != EXPECTED_PROJECT_ID:
        raise GateInputError("candidate must belong to the frozen regional mask project")
    blockers: list[str] = []
    if not isinstance(version, int) or isinstance(version, bool) or version < 2:
        blockers.append("group_locked_candidate_dataset_version_missing")
    if not isinstance(model_id, str) or not isinstance(version, int) or not model_id.startswith(
        f"{EXPECTED_PROJECT_ID}-{version}-"
    ):
        blockers.append("distinct_dryness_candidate_model_missing")
    if not isinstance(training_id, str) or not training_id:
        blockers.append("distinct_dryness_candidate_training_missing")
    return not blockers, blockers


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "input evidence blobs changed")

    sources = receipt.get("sources", {})
    for name, sha in EXPECTED_ARCHIVES.items():
        _require(sources.get(name, {}).get("archiveSHA256"), sha, f"{name} archive identity changed")

    clean3 = sources["clean3"]
    _require(clean3.get("dryBoxes"), 2117, "Clean3 dry box inventory changed")
    _require(clean3.get("dryPolygons"), 6, "Clean3 dry polygon inventory changed")
    _require(clean3.get("dryPolygonSplits"), {"train": 3, "valid": 2, "test": 1}, "Clean3 dry polygon splits changed")
    _require(clean3.get("crossSplitExactGroups"), 9, "Clean3 leakage evidence changed")

    merve = sources["merve"]
    _require(merve.get("pulBoxes"), 2590, "Merve pul box inventory changed")
    _require(merve.get("pulPolygons"), 0, "Merve boxes must not become polygons")
    _require(merve.get("processedFilenameCount"), 3368, "Merve processed-image inventory changed")
    _require(merve.get("naturalCameraColourCalibrationAllowed"), False, "processed Merve images cannot calibrate natural camera colour")

    dryness = sources["drynessV1"]
    _require(dryness.get("boxOnlyAnnotations"), 6679, "Dryness v1 box inventory changed")
    _require(dryness.get("nonRectangularPolygons"), 61, "Dryness v1 polygon inventory changed")
    _require(dryness.get("rectanglePolygons"), 65, "Dryness v1 rectangle inventory changed")
    _require(dryness.get("geometryIssues"), 14, "Dryness v1 geometry issue inventory changed")
    _require(dryness.get("matchedExistingImages"), 700, "Dryness v1 overlap inventory changed")

    face = sources["faceV3"]
    _require(face.get("dryPolygons"), 48, "FACE v3 dry polygon inventory changed")
    _require(face.get("dryRectanglePolygons"), 24, "FACE v3 rectangle inventory changed")
    _require(face.get("normalPolygons"), 88, "FACE v3 normal polygon inventory changed")

    boxes = sources["skinTypeBoxes"]
    _require(boxes.get("dryBoxes"), 3648, "skin-type dry box inventory changed")
    _require(boxes.get("nonEmptySegmentations"), 0, "skin-type boxes cannot become masks")
    _require(boxes.get("normalClassPresent"), False, "skin-type box source has no normal class")
    _require(boxes.get("missingAnnotationMeansNormal"), False, "missing boxes cannot become normal truth")
    _require(boxes.get("confirmedCrossSplitPersonGroups"), 1, "skin-type leakage evidence changed")
    _require(boxes.get("fullPersonIdentityCoverage"), False, "unreviewed identities cannot become complete")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("blueOverlayMeaning"), "expert-supported-regional-dryness-or-flaking", "blue overlay semantics changed")
    _require(contract.get("boxesAsMasksAllowed"), False, "boxes cannot be rendered as blue masks")
    _require(contract.get("missingLabelMeansNormal"), False, "missing labels cannot mean normal")
    _require(contract.get("genericDrynessEqualsVisibleFlaking"), False, "generic dryness cannot silently become flaking")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model predictions cannot become expert truth")
    _require(contract.get("unknownColour"), "#D1D5DB", "unknown must remain light gray")
    _require(contract.get("dryColour"), "#2563EB", "dry must remain blue")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product result baseline was lost")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("dryAppearanceHeadingPresent"), True, "existing dry appearance heading was lost")
    _require(baseline.get("separateSkinTypePresent"), True, "separate skin type was lost")
    _require(baseline.get("regionalResultsPresent"), True, "existing regional results were lost")

    remote = receipt.get("currentRoboflowState", {})
    _require(remote.get("projectId"), EXPECTED_PROJECT_ID, "regional project identity changed")
    _require(remote.get("images"), 337, "regional project image inventory changed")
    _require(remote.get("latestVersion"), 1, "current regional project version changed")
    _require(remote.get("classes"), {"Oily": 1065, "Redness": 571}, "current regional class inventory changed")
    _require(remote.get("dryClassPresent"), False, "current project cannot gain Dry truth implicitly")
    _require(remote.get("runningTrainingFound"), False, "running-training state changed")
    _require(remote.get("knownVersionOneTrainingIds"), ["3485f8c67f957a1b850d", "af287a006e2e428f5ce4"], "known training identities changed")

    candidate = receipt.get("candidate", {})
    training_requirements = {
        "rightsReviewedNaturalCameraSources": "rights_reviewed_natural_camera_sources_missing",
        "expertSemanticPolicyComplete": "expert_dryness_flaking_semantic_policy_missing",
        "expertPolygonExtentReviewComplete": "expert_polygon_extent_review_missing",
        "evaluatedNegativeAndNormalRegionsComplete": "evaluated_negative_normal_regions_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "groupLockedReplacementSplitVerified": "group_locked_replacement_split_missing",
        "newUntouchedFinalTestReserved": "untouched_final_test_reservation_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
        "oneChangeValidationExperimentSpecified": "one_change_validation_experiment_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
    }
    training_blockers = [reason for field, reason in training_requirements.items() if candidate.get(field) is not True]
    training_allowed = not training_blockers

    distinct_candidate, identity_blockers = _validate_candidate_identity(candidate)
    test_blockers = list(training_blockers) + identity_blockers
    for field, reason in (
        ("trainedFromGroupLockedReplacementSplit", "candidate_not_trained_from_group_locked_split"),
        ("candidateChangeMatchesPreRegisteredExperiment", "candidate_change_not_pre_registered"),
        ("thresholdsLockedBeforeFinalTest", "thresholds_not_locked_before_final_test"),
        ("instanceSegmentationPolygonOutputVerified", "polygon_mask_output_verification_missing"),
        ("dryClassMetricReportedSeparately", "dry_class_metric_missing"),
    ):
        if candidate.get(field) is not True:
            test_blockers.append(reason)
    if candidate.get("validationPassed") is not True:
        test_blockers.append("validation_acceptance_missing")
    test_allowed = not test_blockers

    activation_blockers = list(test_blockers)
    for field, reason in (
        ("newUntouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("physicalCameraHoldoutPassed", "physical_camera_acceptance_missing"),
        ("lightingSkinTonePoseSlicesPassed", "lighting_skin_tone_pose_slices_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
        ("regionalCoverageOverlapAndUnavailableControlsPassed", "regional_overlap_unavailable_controls_missing"),
    ):
        if candidate.get(field) is not True:
            activation_blockers.append(reason)

    activation_allowed = distinct_candidate and not activation_blockers
    return {
        "schemaVersion": 2,
        "methodVersion": "regional-dryness-release-gate-v2",
        "existingDryAppearanceProxyPreserved": True,
        "existingConcreteResultFlowPreserved": True,
        "boxLocalizationResearchAllowed": True,
        "blueMaskFromBoxesAllowed": False,
        "missingLabelAsNormalAllowed": False,
        "processedMerveNaturalColourCalibrationAllowed": False,
        "knownVersionOneModelsAccepted": False,
        "blindRetrainingAllowed": False,
        "distinctCandidatePresent": distinct_candidate,
        "researchTrainingAuthorized": training_allowed,
        "finalTestEvaluationAuthorized": test_allowed,
        "learnedBlueRegionalMaskActivationAllowed": activation_allowed,
        "roadmapAccepted": activation_allowed,
        "trainingBlockers": training_blockers,
        "testBlockers": test_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if activation_allowed else "blocked",
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
