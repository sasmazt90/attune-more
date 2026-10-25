#!/usr/bin/env python3
"""Fail-closed release gate for the independent regional redness layer."""

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
    "unifiedMapContract": "a1f26fa1b754bac84978936ef1a47eba62d5b898",
    "regionalImplementation": "a8fbfefb613b01162df863614df5a91bf5a6f4f0",
    "regionalImprovementGate": "a0539e644b302417a64c1336d13117a88caaeee3",
}
SOURCE_ARCHIVE = "a24793ca3490a48088abf47ba89fc9ab94e1c3a12c488ce52915e19b5bdf6fd6"
PROVIDER_EXPORT = "ba7aa450ee2e98af35dcb1b60f3f9673fc7a6ef6b7709e7b94e1df1d32bdab3a"


class GateInputError(ValueError):
    """Raised when immutable evidence or the accepted map semantics drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("className"), "Redness", "redness class identity changed")
    _require(contract.get("productHeading"), "kizariklik", "redness product heading changed")
    _require(contract.get("colour"), "#DC2626", "redness must remain red")
    _require(contract.get("style"), "contour-or-hatching", "redness must remain contour or hatching")
    _require(contract.get("independentLayer"), True, "redness must remain an independent layer")
    _require(contract.get("mayOverlapDryOrOily"), True, "redness overlap must remain supported")
    _require(contract.get("sensitivityInferred"), False, "redness cannot become sensitivity")
    _require(contract.get("missingMaskMeansNormal"), False, "missing redness masks cannot mean normal")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")

    source = receipt.get("source", {})
    _require(source.get("sourceArchiveSHA256"), SOURCE_ARCHIVE, "source archive changed")
    _require(source.get("providerExportSHA256"), PROVIDER_EXPORT, "provider export changed")
    _require(source.get("images"), 337, "source image inventory changed")
    _require(source.get("splits"), {"train": 244, "valid": 63, "test": 30}, "source splits changed")
    _require(source.get("rednessLabels"), {"train": 429, "valid": 105, "test": 37}, "redness label inventory changed")
    _require(source.get("polygonAnnotations"), 1636, "polygon inventory changed")
    _require(source.get("invalidPolygonAnnotations"), 0, "invalid polygon inventory changed")
    _require(source.get("completeReviewedPersonGroups"), 0, "person review coverage changed")
    _require(source.get("unreviewedSourceIds"), 337, "unreviewed identity coverage changed")
    _require(source.get("testImagesBelowMinimum"), True, "small test limitation changed")
    _require(source.get("testAlreadyExposed"), True, "exposed test cannot become untouched")

    model = receipt.get("model", {})
    _require(model.get("trainingId"), "af287a006e2e428f5ce4", "model training identity changed")
    _require(model.get("evalId"), "vsQ6klUgSohCdtLwNMJf", "model evaluation identity changed")
    _require(model.get("validationSelectedThreshold"), 0.39, "redness threshold changed")
    _require(model.get("validationF1"), 0.524, "redness validation F1 changed")
    _require(model.get("diagnosticTestF1"), 0.581, "redness diagnostic test F1 changed")
    _require(model.get("diagnosticTestMap75"), 0.18456227201667535, "redness map75 changed")
    _require(model.get("diagnosticSmallObjectMap50"), 0.0, "small redness diagnosis changed")
    _require(model.get("accepted"), False, "rejected redness model cannot become accepted")

    review = receipt.get("expertReview", {})
    _require(review.get("queueImages"), 81, "expert queue inventory changed")
    _require(review.get("rednessTrainItems"), 32, "redness train review inventory changed")
    _require(review.get("rednessValidItems"), 8, "redness validation review inventory changed")
    _require(review.get("testItems"), 0, "expert review must not consume test")
    _require(review.get("expertProtocolComplete"), False, "blank expert queue cannot become complete")

    candidate = receipt.get("candidate", {})
    training_requirements = {
        "rightsReviewed": "rights_review_missing",
        "expertMaskAndNegativeProtocolComplete": "expert_mask_negative_protocol_missing",
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
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
        ("overlapAndUnavailableControlsPassed", "overlap_unavailable_controls_missing"),
    ):
        if candidate.get(field) is not True:
            activation_blockers.append(reason)

    activation_allowed = not activation_blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "regional-redness-release-gate-v1",
        "researchVisualizationAllowed": True,
        "independentRedLayerRequired": True,
        "sensitivityInferenceAllowed": False,
        "missingMaskAsNormalAllowed": False,
        "researchTrainingAuthorized": training_allowed,
        "finalTestEvaluationAuthorized": test_allowed,
        "productActivationAllowed": activation_allowed,
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
