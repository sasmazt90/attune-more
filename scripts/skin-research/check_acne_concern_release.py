#!/usr/bin/env python3
"""Fail-closed, per-class release gate for acne, post-acne and pigmentation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_BLOBS = {
    "modelReceipt": "030a58e09d36e441ce28eb5143ff776f250c5670",
    "modelVerdict": "97cf68fc45cd5a54755123015ea45d6783f7bde2",
    "modelDiagnosis": "b74b8edc14e7599907452d2ad8c08ce805601242",
    "improvementGate": "6ba318be04faca5bc64b0f8ba42da922172750f6",
    "splitGate": "e70effad23a5994892344ae13126b5049afdacf8",
    "semanticReview": "2b27d4da61d6d422789c19436133816e1fa859f9",
    "groupCoverage": "1d63ec4e1369e6f9021c63dde2ab7914e4e2e56d",
    "mergedProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "unifiedResultReceipt": "aac52634eaba105cd1ccc86383b7665eca7b53eb",
}
REJECTED_RESEARCH_MODEL_ID = "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-small-t2"
KNOWN_INELIGIBLE_MODEL_IDS = {
    REJECTED_RESEARCH_MODEL_ID,
    "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-nas-t1--a5e262",
    "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-nas-t1--929397",
}


class GateInputError(ValueError):
    """Raised when immutable evidence or concern semantics drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _class_decision(shared_test_blockers: list[str], candidate: dict[str, Any], class_name: str) -> dict[str, Any]:
    class_candidate = candidate.get("classes", {}).get(class_name, {})
    test_blockers = list(shared_test_blockers)
    if class_candidate.get("validationPassed") is not True:
        test_blockers.append(f"{class_name}_validation_acceptance_missing")
    activation_blockers = list(test_blockers)
    for field, suffix in (
        ("newUntouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("physicalCameraHoldoutPassed", "physical_camera_acceptance_missing"),
        ("skinToneLightingPoseSlicesPassed", "skin_tone_lighting_pose_slices_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
        ("unavailableHistoryAndDedupControlsPassed", "unavailable_history_dedup_controls_missing"),
    ):
        if class_candidate.get(field) is not True:
            activation_blockers.append(f"{class_name}_{suffix}")
    return {
        "finalTestEvaluationAuthorized": not test_blockers,
        "productActivationAllowed": not activation_blockers,
        "testBlockers": test_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if not activation_blockers else "blocked",
    }


def _validate_candidate_identity(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    mode = candidate.get("mode")
    if mode not in {"not-trained", "new-model"}:
        raise GateInputError("unknown acne candidate mode")
    model_id = candidate.get("modelId")
    training_id = candidate.get("trainingId")
    version = candidate.get("datasetVersion")
    if mode == "not-trained":
        if model_id is not None or training_id is not None or version is not None:
            raise GateInputError("not-trained candidate cannot claim a model identity")
        return False, ["distinct_new_candidate_model_missing"]
    if model_id in KNOWN_INELIGIBLE_MODEL_IDS:
        raise GateInputError("known ineligible model cannot be relabelled as a new candidate")
    blockers: list[str] = []
    if not isinstance(model_id, str) or not model_id:
        blockers.append("distinct_new_candidate_model_missing")
    if not isinstance(training_id, str) or not training_id:
        blockers.append("distinct_new_candidate_training_missing")
    if not isinstance(version, int) or isinstance(version, bool) or version < 2:
        blockers.append("group_locked_candidate_dataset_version_missing")
    return not blockers, blockers


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("classes"), {"Pimple": "acne", "Post acne": "Post acne", "Pigmentation": "Pigmentation"}, "concern headings changed")
    _require(contract.get("classesRemainSeparate"), True, "Pimple, Post acne and Pigmentation must remain separate")
    _require(contract.get("mayCoexist"), True, "the three findings may coexist")
    _require(contract.get("missingClassMeansNegative"), False, "missing labels cannot become negative truth")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(contract.get("medicalDiagnosisInferred"), False, "appearance findings cannot become medical diagnoses")
    _require(contract.get("postAcneCollapsedIntoActiveAcne"), False, "Post acne cannot collapse into active acne")
    _require(contract.get("pigmentationPopulatedByToneProxy"), False, "tone cannot populate localized Pigmentation")
    _require(contract.get("pigmentationIncludesFrecklesMolesOrShadowByDefault"), False, "Pigmentation boundaries must not absorb freckles, moles or shadow")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product result baseline was lost")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("acneHeadingPresent"), True, "existing acne heading was lost")
    _require(baseline.get("postAcneHeadingExplicitlyUnavailable"), True, "Post acne unavailable control was lost")
    _require(baseline.get("pigmentationHeadingExplicitlyUnavailable"), True, "Pigmentation unavailable control was lost")

    source = receipt.get("source", {})
    _require(source.get("archiveSHA256"), "29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2", "source archive changed")
    _require(source.get("images"), 800, "source image inventory changed")
    _require(source.get("labels"), 37342, "source label inventory changed")
    _require(source.get("splits"), {"train": 553, "valid": 165, "test": 82}, "source splits changed")
    _require(source.get("classLabels"), {"Pimple": 3640, "Post acne": 32123, "Pigmentation": 1579}, "class inventory changed")
    _require(source.get("classImageCoverage"), {"Pimple": 0.113, "Post acne": 1.0, "Pigmentation": 0.049}, "class image coverage changed")
    _require(source.get("confirmedCrossSplitGroups"), 16, "cross-split group count changed")
    _require(source.get("confirmedCrossSplitMembers"), 37, "cross-split member count changed")
    _require(source.get("reviewedGroupRecords"), 71, "reviewed group coverage changed")
    _require(source.get("unreviewedSingletonRecords"), 729, "unreviewed group coverage changed")
    _require(source.get("personIndependent"), False, "partial grouping cannot become person-independent")
    _require(source.get("existingTestExposed"), True, "exposed test cannot become untouched")

    model = receipt.get("researchModel", {})
    _require(model.get("trainingId"), "49ee6204cf069198bbfa", "model training identity changed")
    _require(model.get("modelId"), REJECTED_RESEARCH_MODEL_ID, "model identity changed")
    _require(model.get("evalId"), "7s06OfIzx78XzATqr5oA", "evaluation identity changed")
    _require(model.get("thresholdsLockedBeforeTest"), False, "exposed thresholds cannot become pre-locked")
    _require(model.get("accepted"), False, "rejected research model cannot become accepted")
    expected_metrics = {
        "Pimple": {"threshold": 0.35, "validation": {"precision": 0.291, "recall": 0.234, "f1": 0.26}, "diagnosticTest": {"precision": 0.272, "recall": 0.308, "f1": 0.289}, "providerTestMap50": 0.18178170442428168, "providerTestMap50_95": 0.04993333620656488, "passed": False},
        "Post acne": {"threshold": 0.31, "validation": {"precision": 0.359, "recall": 0.29, "f1": 0.321}, "diagnosticTest": {"precision": 0.34, "recall": 0.305, "f1": 0.322}, "providerTestMap50": 0.1848325895833806, "providerTestMap50_95": 0.04456150310173727, "passed": False},
        "Pigmentation": {"threshold": 0.15, "validation": {"precision": 0.115, "recall": 0.081, "f1": 0.095}, "diagnosticTest": {"precision": 0.132, "recall": 0.055, "f1": 0.077}, "providerTestMap50": 0.032430325837992775, "providerTestMap50_95": 0.008183552543335268, "passed": False},
    }
    _require(model.get("classMetrics"), expected_metrics, "per-class acne concern metrics changed")

    candidate = receipt.get("candidate", {})
    shared_requirements = {
        "rightsReviewed": "rights_review_missing",
        "expertPerClassPositiveNegativeAndAmbiguityProtocolComplete": "expert_per_class_protocol_missing",
        "personIndependentGroupingComplete": "person_independent_grouping_missing",
        "groupLockedReplacementSplitVerified": "group_locked_replacement_split_missing",
        "newUntouchedFinalTestReserved": "new_untouched_final_test_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
        "oneChangeValidationExperimentSpecified": "one_change_validation_experiment_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
    }
    shared_training_blockers = [reason for field, reason in shared_requirements.items() if candidate.get(field) is not True]
    distinct_candidate, identity_blockers = _validate_candidate_identity(candidate)
    shared_test_blockers = list(shared_training_blockers) + identity_blockers
    if candidate.get("trainedFromGroupLockedReplacementSplit") is not True:
        shared_test_blockers.append("candidate_not_trained_from_group_locked_split")
    if candidate.get("candidateChangeMatchesPreRegisteredExperiment") is not True:
        shared_test_blockers.append("candidate_change_not_pre_registered")
    if candidate.get("thresholdsLockedBeforeFinalTest") is not True:
        shared_test_blockers.append("thresholds_not_locked_before_final_test")

    classes = candidate.get("classes")
    if not isinstance(classes, dict) or set(classes) != {"Pimple", "Post acne", "Pigmentation"}:
        raise GateInputError("all three per-class candidate records are required")
    class_decisions = {name: _class_decision(shared_test_blockers, candidate, name) for name in ("Pimple", "Post acne", "Pigmentation")}
    roadmap_accepted = distinct_candidate and all(item["productActivationAllowed"] for item in class_decisions.values())
    return {
        "schemaVersion": 2,
        "methodVersion": "acne-concerns-per-class-release-gate-v2",
        "existingConcreteResultFlowPreserved": True,
        "classesRemainSeparate": True,
        "researchModelAccepted": False,
        "knownNasChildrenAccepted": False,
        "blindRetrainingAllowed": False,
        "distinctCandidatePresent": distinct_candidate,
        "researchTrainingAuthorized": not shared_training_blockers,
        "classDecisions": class_decisions,
        "roadmapAccepted": roadmap_accepted,
        "sharedTrainingBlockers": shared_training_blockers,
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
