#!/usr/bin/env python3
"""Fail-closed, per-class release gate for dark circles and under-eye bags."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_BLOBS = {
    "ungroupedModelReceipt": "6b50743ad404024ab33a6dfb536424de9324e5bb",
    "ungroupedModelVerdict": "437c97d23f6163ecc12c40dc52e4f12d60a840d9",
    "sourceGroupSplit": "1e6ab8d942de0b50e54016ff24518cf7dc3ca3b6",
    "providerGroupedReproduction": "b835168ebee70699236c4748fa8fc39e4c5168ba",
    "providerState": "7bf6041f507f616d8e4d7ef3bc77b6f054a4a67f",
    "groupedReleaseGate": "d0b3062be1c9a946740bcc7bd2a42da1c21c92b2",
    "mergedProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "unifiedResultReceipt": "aac52634eaba105cd1ccc86383b7665eca7b53eb",
}


class GateInputError(ValueError):
    """Raised when immutable evidence or class semantics drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _class_decision(shared_blockers: list[str], candidate: dict[str, Any], class_name: str) -> dict[str, Any]:
    class_candidate = candidate.get("classes", {}).get(class_name, {})
    test_blockers = list(shared_blockers)
    if class_candidate.get("validationPassed") is not True:
        test_blockers.append(f"{class_name}_validation_acceptance_missing")
    test_allowed = not test_blockers

    activation_blockers = list(test_blockers)
    for field, suffix in (
        ("newUntouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("physicalCameraHoldoutPassed", "physical_camera_acceptance_missing"),
        ("skinToneLightingPoseSlicesPassed", "skin_tone_lighting_pose_slices_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
        ("unavailableAndHistoryControlsPassed", "unavailable_history_controls_missing"),
    ):
        if class_candidate.get(field) is not True:
            activation_blockers.append(f"{class_name}_{suffix}")
    activation_allowed = not activation_blockers
    return {
        "finalTestEvaluationAuthorized": test_allowed,
        "productActivationAllowed": activation_allowed,
        "testBlockers": test_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if activation_allowed else "blocked",
    }


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("classes"), {"darkcircle": "dark", "eyebag": "bags"}, "under-eye class headings changed")
    _require(contract.get("classesRemainSeparate"), True, "dark circles and bags must remain separate")
    _require(contract.get("mayCoexist"), True, "dark circles and bags may coexist")
    _require(contract.get("missingClassMeansNegative"), False, "missing under-eye labels cannot become negative truth")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(contract.get("darkcircleMedicalCauseInferred"), False, "dark-circle medical causes cannot be inferred")
    _require(contract.get("eyebagEdemaOrFluidRetentionInferred"), False, "eyebag cannot imply edema or fluid retention")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product result baseline was lost")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("darkHeadingPresent"), True, "dark-circle heading was lost")
    _require(baseline.get("bagsHeadingPresent"), True, "under-eye bags heading was lost")

    source = receipt.get("source", {})
    _require(source.get("providerSourceVersion"), 2, "provider source version changed")
    _require(source.get("images"), 399, "source image inventory changed")
    _require(source.get("classCounts"), {"darkcircle": 382, "eyebag": 487}, "class inventory changed")
    _require(source.get("sourceSplits"), {"train": 279, "valid": 81, "test": 39}, "source splits changed")
    _require(source.get("groupedSplits"), {"train": 283, "valid": 78, "test": 38}, "grouped splits changed")
    _require(source.get("reviewedCrossSplitGroups"), 3, "reviewed cross-split groups changed")
    _require(source.get("movedImages"), 4, "grouped moved-image inventory changed")
    _require(source.get("imageBytesChanged"), 0, "grouped image bytes changed")
    _require(source.get("annotationPayloadsChanged"), 0, "grouped annotations changed")
    _require(source.get("personIndependent"), False, "partial grouping cannot become person-independent")
    _require(source.get("groupedProjectImages"), 0, "empty grouped project state changed")
    _require(source.get("uploadStatus"), "created", "grouped upload status changed")
    _require(source.get("uploadProgress"), None, "grouped upload progress changed")
    _require(source.get("candidateArchiveMatchesAuthorizedArchive"), False, "archive authorization boundary changed")

    model = receipt.get("ungroupedModel", {})
    _require(model.get("trainingId"), "d194569acd3ebe7cf8b7", "model training identity changed")
    _require(model.get("evalId"), "ntJE3M4iMTVBPCg2HwIb", "model evaluation identity changed")
    _require(model.get("generatedImages"), 952, "ungrouped generated-image inventory changed")
    _require(model.get("thresholdsLockedBeforeTest"), False, "exposed test cannot become pre-locked")
    _require(model.get("accepted"), False, "rejected ungrouped model cannot become accepted")
    expected_metrics = {
        "darkcircle": {
            "threshold": 0.32,
            "validation": {"precision": 0.5, "recall": 0.597, "f1": 0.544},
            "diagnosticTest": {"precision": 0.5, "recall": 0.61, "f1": 0.549},
            "providerTestMap50": 0.6100278019619981,
            "providerTestMap50_95": 0.22253903692392357,
            "passed": False,
        },
        "eyebag": {
            "threshold": 0.49,
            "validation": {"precision": 0.75, "recall": 0.6, "f1": 0.667},
            "diagnosticTest": {"precision": 0.697, "recall": 0.479, "f1": 0.568},
            "providerTestMap50": 0.6263657136973713,
            "providerTestMap50_95": 0.2371280819762581,
            "passed": False,
        },
    }
    _require(model.get("classMetrics"), expected_metrics, "per-class under-eye metrics changed")

    candidate = receipt.get("candidate", {})
    shared_requirements = {
        "exactArchiveAuthorized": "exact_archive_authorization_missing",
        "groupedImportVerified": "grouped_import_verification_missing",
        "augmentationFreeGroupedVersionVerified": "grouped_version_verification_missing",
        "rightsReviewed": "rights_review_missing",
        "expertPerClassMaskNegativeAndAmbiguityProtocolComplete": "expert_per_class_protocol_missing",
        "personIndependentGroupedSplitLocked": "person_independent_grouped_split_missing",
        "newUntouchedFinalTestReserved": "new_untouched_final_test_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
    }
    shared_blockers = [reason for field, reason in shared_requirements.items() if candidate.get(field) is not True]
    training_allowed = not shared_blockers
    class_decisions = {
        class_name: _class_decision(shared_blockers, candidate, class_name)
        for class_name in ("darkcircle", "eyebag")
    }
    roadmap_accepted = all(item["productActivationAllowed"] for item in class_decisions.values())
    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-per-class-release-gate-v1",
        "existingConcreteResultFlowPreserved": True,
        "classesRemainSeparate": True,
        "ungroupedModelAccepted": False,
        "researchTrainingAuthorized": training_allowed,
        "classDecisions": class_decisions,
        "roadmapAccepted": roadmap_accepted,
        "sharedTrainingBlockers": shared_blockers,
        "decision": "ready" if roadmap_accepted else "blocked",
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
