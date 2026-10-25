#!/usr/bin/env python3
"""Fail-closed release gate for the regional oily-appearance layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_BLOBS = {
    "modelReceipt": "f3fc4bb10530393ac5df31d17dba423f5bfb5287",
    "modelVerdict": "9aed72c0f5a3851c0e6a02f5cd6982739bfaaaaa",
    "modelDiagnosis": "5a31af138324100bfd10ba9a00da58611d75839b",
    "sourceGroupAudit": "29314becfb5fd8c6f77e389036e2afa152aa56cb",
    "expertReviewQueue": "31cc224918c58f07d3185e3aeeff298c4114f004",
    "regionalImprovementGate": "b55ef75ba61c6e0f7411aa4c67e7440f9168adc0",
    "mergedProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "unifiedResultReceipt": "aac52634eaba105cd1ccc86383b7665eca7b53eb",
}
SOURCE_ARCHIVE = "a24793ca3490a48088abf47ba89fc9ab94e1c3a12c488ce52915e19b5bdf6fd6"
PROVIDER_EXPORT = "ba7aa450ee2e98af35dcb1b60f3f9673fc7a6ef6b7709e7b94e1df1d32bdab3a"


class GateInputError(ValueError):
    """Raised when immutable evidence or accepted product semantics drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("className"), "Oily", "oily class identity changed")
    _require(contract.get("productHeading"), "oil", "oily product heading changed")
    _require(contract.get("colour"), "#16A34A", "oily layer must remain green")
    _require(contract.get("measuredRegionalSupportRequired"), True, "oily layer requires measured regional support")
    _require(contract.get("wholeFaceReplicationAllowed"), False, "whole-face class cannot become regional truth")
    _require(contract.get("missingMaskMeansNormal"), False, "missing oily masks cannot mean normal")
    _require(contract.get("boxAcceptedAsPolygon"), False, "boxes cannot become oily polygons")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(contract.get("clinicalSebumDiagnosis"), False, "appearance output cannot become a clinical sebum diagnosis")
    _require(contract.get("rednessMayOverlap"), True, "independent redness overlap must remain supported")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product result baseline was lost")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("oilAppearanceHeadingPresent"), True, "existing oil appearance heading was lost")
    _require(baseline.get("separateSkinTypePresent"), True, "separate skin type was lost")
    _require(baseline.get("regionalResultsPresent"), True, "existing regional results were lost")

    source = receipt.get("source", {})
    _require(source.get("sourceArchiveSHA256"), SOURCE_ARCHIVE, "source archive changed")
    _require(source.get("providerExportSHA256"), PROVIDER_EXPORT, "provider export changed")
    _require(source.get("images"), 337, "source image inventory changed")
    _require(source.get("splits"), {"train": 244, "valid": 63, "test": 30}, "source splits changed")
    _require(source.get("oilyLabels"), {"train": 780, "valid": 195, "test": 90}, "oily label inventory changed")
    _require(source.get("polygonAnnotations"), 1636, "polygon inventory changed")
    _require(source.get("invalidPolygonAnnotations"), 0, "invalid polygon inventory changed")
    _require(source.get("completeReviewedPersonGroups"), 0, "person review coverage changed")
    _require(source.get("unreviewedSourceIds"), 337, "unreviewed identity coverage changed")
    _require(source.get("testImagesBelowMinimum"), True, "small test limitation changed")
    _require(source.get("testAlreadyExposed"), True, "exposed test cannot become untouched")
    _require(source.get("dryTruth"), False, "regional source cannot gain dry truth implicitly")
    _require(source.get("evaluatedNormalTruth"), False, "missing labels cannot become evaluated normal")

    model = receipt.get("model", {})
    _require(model.get("trainingId"), "af287a006e2e428f5ce4", "model training identity changed")
    _require(model.get("evalId"), "vsQ6klUgSohCdtLwNMJf", "model evaluation identity changed")
    _require(model.get("validationSelectedThreshold"), 0.38, "oily threshold changed")
    _require(model.get("validationF1"), 0.571, "oily validation F1 changed")
    _require(model.get("diagnosticTestF1"), 0.475, "oily diagnostic test F1 changed")
    _require(model.get("validationMap75"), 0.027941856492013268, "oily validation map75 changed")
    _require(model.get("diagnosticTestMap75"), 0.040226982580142956, "oily diagnostic map75 changed")
    _require(model.get("validationFalsePositivesAtPoint2"), 386, "validation false-positive diagnosis changed")
    _require(model.get("diagnosticTestFalsePositivesAtPoint2"), 213, "test false-positive diagnosis changed")
    _require(model.get("accepted"), False, "rejected oily model cannot become accepted")

    review = receipt.get("expertReview", {})
    _require(review.get("queueImages"), 81, "expert queue inventory changed")
    _require(review.get("oilyTrainItems"), 32, "oily train review inventory changed")
    _require(review.get("oilyValidItems"), 8, "oily validation review inventory changed")
    _require(review.get("testItems"), 0, "expert review must not consume test")
    _require(review.get("expertProtocolComplete"), False, "blank expert queue cannot become complete")

    candidate = receipt.get("candidate", {})
    training_requirements = {
        "rightsReviewed": "rights_review_missing",
        "expertMaskNegativeAndAssessabilityProtocolComplete": "expert_mask_negative_protocol_missing",
        "illuminationShineAndGlareProtocolComplete": "illumination_shine_glare_protocol_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "replacementSplitLocked": "replacement_split_missing",
        "newUntouchedFinalTestReserved": "new_untouched_final_test_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
    }
    training_blockers = [reason for field, reason in training_requirements.items() if candidate.get(field) is not True]
    training_allowed = not training_blockers

    test_blockers = list(training_blockers)
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

    activation_allowed = not activation_blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "regional-oily-appearance-release-gate-v1",
        "existingAppearanceProxyPreserved": True,
        "existingConcreteResultFlowPreserved": True,
        "greenRegionalLayerRequired": True,
        "wholeFaceReplicationAllowed": False,
        "missingMaskAsNormalAllowed": False,
        "clinicalSebumDiagnosisAllowed": False,
        "researchTrainingAuthorized": training_allowed,
        "finalTestEvaluationAuthorized": test_allowed,
        "learnedRegionalMaskActivationAllowed": activation_allowed,
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
