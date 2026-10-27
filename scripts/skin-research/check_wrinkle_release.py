#!/usr/bin/env python3
"""Fail-closed, per-class release gate for crows-feet and wrinkle research.

The two provider runs captured on 2026-10-25 are immutable diagnostics.  The
very weak crows-feet model cannot be rehabilitated by editing its receipt, and
the unrelated generic-wrinkle model cannot substitute for the selected source.
Only a separately identified candidate with pre-locked policy, untouched final
test, physical-camera evidence, and working-product evidence can activate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CROWS_IDENTITY = {
    "project": "tolgar-sasmaz/skin_face_detection-emora",
    "version": 1,
    "trainingId": "d74d5d927dbbe97574bc",
    "modelId": "tolgar-sasmaz/skin_face_detection-emora-1-rfdetr-seg-small-t1",
    "evalId": "g4rZij16YyDRIqJucTKM",
}
UNRELATED_IDENTITY = {
    "project": "tolgar-sasmaz/wrinkles-79rrf-t7kyp",
    "version": 1,
    "trainingId": "342657886079e855c017",
    "modelId": "tolgar-sasmaz/wrinkles-79rrf-t7kyp-1-rfdetr-seg-small-t1",
    "evalId": "vrgoNtXQJSRl0kHo0ahf",
}
EVIDENCE_BLOBS = {
    "crowsFeetExternalReceipt": "2546b986d2675dc9dc78896ff0b8614b86b09351",
    "unrelatedWrinkleExternalReceipt": "6725340478514cbd58651fa0ed7afc2fe86213b7",
}
CURRENT_CROWS_METRICS = {
    "valid": {"map50": 0.005415421147257854, "map50_95": 0.0009904147136091453, "map75": 0.0, "precision": 0.035, "recall": 0.107, "f1": 0.053},
    "test": {"map50": 0.0010211828139297429, "map50_95": 0.0002746943792401853, "map75": 0.0, "precision": 0.01, "recall": 0.048, "f1": 0.017},
}
CURRENT_UNRELATED_METRICS = {
    "valid": {"map50": 0.5994696691583155, "map50_95": 0.2105946586582374, "map75": 0.09009791117999257, "precision": 0.779, "recall": 0.611, "f1": 0.685},
    "test": {"map50": 0.6440890457494266, "map50_95": 0.22789575695408526, "map75": 0.10173694020272453, "precision": 0.811, "recall": 0.658, "f1": 0.727},
}
OPTIONAL_CLASSES = {
    "forehead",
    "frown",
    "nasolabial_fold",
    "marionette_line",
    "bunny_line",
    "vertical_lips_lines",
    "mental_crease",
}


class GateInputError(ValueError):
    """Raised when frozen evidence or semantic boundaries drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _metrics(receipt: dict[str, Any], split: str, class_name: str) -> dict[str, float]:
    values = receipt.get("perClass", {}).get(split, {}).get(class_name)
    if not isinstance(values, dict):
        raise GateInputError(f"missing {split}/{class_name} metrics")
    required = ("map50", "map50_95", "map75", "precision", "recall", "f1")
    if set(values) != set(required):
        raise GateInputError(f"unexpected {split}/{class_name} metric keys")
    if any(isinstance(values[key], bool) or not isinstance(values[key], (int, float)) for key in required):
        raise GateInputError(f"invalid {split}/{class_name} metrics")
    return {key: float(values[key]) for key in required}


def _freeze_external_evidence(crows: dict[str, Any], unrelated: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _require({key: crows.get(key) for key in CROWS_IDENTITY}, CROWS_IDENTITY, "crows-feet identity changed")
    _require({key: unrelated.get(key) for key in UNRELATED_IDENTITY}, UNRELATED_IDENTITY, "unrelated wrinkle identity changed")
    _require(crows.get("trainingStatus"), "finished", "crows-feet training state changed")
    _require(crows.get("evalStatus"), "done", "crows-feet evaluation state changed")
    _require(crows.get("modelPredictionIsExpertTruth"), False, "model prediction cannot become expert truth")
    _require(crows.get("activationAllowed"), False, "rejected external model cannot become activated")
    _require(crows.get("releasePolicy"), {"expertApproved": False, "minimums": None}, "external release policy changed post hoc")
    crows_metrics = {
        "valid": _metrics(crows, "valid", "crows_feet"),
        "test": _metrics(crows, "test", "crows_feet"),
    }
    _require(crows_metrics, CURRENT_CROWS_METRICS, "crows-feet diagnostic metrics changed")

    _require(unrelated.get("trainingStatus"), "finished", "unrelated training state changed")
    _require(unrelated.get("evalStatus"), "done", "unrelated evaluation state changed")
    _require(unrelated.get("exactSelectedDataset"), False, "unrelated dataset cannot become selected source")
    _require(unrelated.get("diagnosticOnly"), True, "unrelated model must remain diagnostic-only")
    _require(unrelated.get("substitutionAllowed"), False, "unrelated model cannot substitute for crows-feet")
    _require(unrelated.get("activationAllowed"), False, "unrelated model cannot become activated")
    _require(unrelated.get("crossSplitCandidates"), {"filename": 65, "perceptual": 202}, "known cross-split evidence changed")
    unrelated_metrics = {
        "valid": _metrics(unrelated, "valid", "wrinkles"),
        "test": _metrics(unrelated, "test", "wrinkles"),
    }
    _require(unrelated_metrics, CURRENT_UNRELATED_METRICS, "unrelated wrinkle diagnostic metrics changed")
    return crows_metrics, unrelated_metrics


def _class_decision(shared_test_blockers: list[str], class_name: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if evidence.get("labelSupported") is not True:
        return {
            "labelSupported": False,
            "finalTestEvaluationAuthorized": False,
            "productActivationAllowed": False,
            "testBlockers": [f"{class_name}_label_support_missing"],
            "activationBlockers": [f"{class_name}_label_support_missing"],
            "decision": "not_eligible",
        }
    test_blockers = list(shared_test_blockers)
    if evidence.get("validationPassed") is not True:
        test_blockers.append(f"{class_name}_validation_acceptance_missing")
    activation_blockers = list(test_blockers)
    for field, suffix in (
        ("newUntouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("physicalCameraHoldoutPassed", "physical_camera_acceptance_missing"),
        ("skinToneLightingPoseSlicesPassed", "skin_tone_lighting_pose_slices_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
        ("unavailableAndHistoryControlsPassed", "unavailable_history_controls_missing"),
    ):
        if evidence.get(field) is not True:
            activation_blockers.append(f"{class_name}_{suffix}")
    return {
        "labelSupported": True,
        "finalTestEvaluationAuthorized": not test_blockers,
        "productActivationAllowed": not activation_blockers,
        "testBlockers": test_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if not activation_blockers else "blocked",
    }


def evaluate_release(crows: dict[str, Any], unrelated: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    crows_metrics, unrelated_metrics = _freeze_external_evidence(crows, unrelated)
    _require(candidate.get("evidenceBlobs"), EVIDENCE_BLOBS, "external evidence blobs changed")
    contract = candidate.get("semanticContract", {})
    _require(contract.get("primaryClass"), "crows_feet", "primary wrinkle class changed")
    _require(contract.get("otherClassesRequireExplicitLabelSupport"), True, "optional wrinkle label boundary changed")
    _require(contract.get("missingLabelMeansNegative"), False, "missing wrinkle labels cannot become negative truth")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(contract.get("clinicalDiagnosisInferred"), False, "wrinkle appearance cannot become clinical diagnosis")
    _require(contract.get("unrelatedModelSubstitutionAllowed"), False, "unrelated model substitution is forbidden")
    baseline = candidate.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product baseline was lost")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("linesHeadingPresent"), True, "existing lines heading was lost")

    next_candidate = candidate.get("candidate", {})
    _require(next_candidate.get("knownRejectedModelId"), CROWS_IDENTITY["modelId"], "known rejected model boundary changed")
    mode = next_candidate.get("mode")
    if mode not in {"not-trained", "new-model"}:
        raise GateInputError("unknown wrinkle candidate mode")
    model_id = next_candidate.get("modelId")
    distinct_model = mode == "new-model" and isinstance(model_id, str) and bool(model_id) and model_id != CROWS_IDENTITY["modelId"]
    if mode == "not-trained" and model_id is not None:
        raise GateInputError("not-trained candidate cannot have a model id")
    if model_id in {CROWS_IDENTITY["modelId"], UNRELATED_IDENTITY["modelId"]}:
        raise GateInputError("known external model cannot be relabelled as a new candidate")

    research_requirements = {
        "selectedDatasetIdentityVerified": "selected_dataset_identity_missing",
        "rightsReviewed": "rights_review_missing",
        "expertPerClassPositiveNegativeAmbiguityProtocolComplete": "expert_per_class_protocol_missing",
        "sourcePersonGroupedSplitLocked": "source_person_grouped_split_missing",
        "poseExpressionProtocolComplete": "pose_expression_protocol_missing",
        "newUntouchedFinalTestReserved": "new_untouched_final_test_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
    }
    research_blockers = [reason for field, reason in research_requirements.items() if next_candidate.get(field) is not True]
    shared_test_blockers = list(research_blockers)
    if not distinct_model:
        shared_test_blockers.append("distinct_new_candidate_model_missing")
    if next_candidate.get("thresholdsLockedBeforeFinalTest") is not True:
        shared_test_blockers.append("thresholds_not_locked_before_final_test")

    classes = next_candidate.get("classes")
    if not isinstance(classes, dict) or "crows_feet" not in classes:
        raise GateInputError("crows-feet class evidence is required")
    unknown_classes = set(classes) - OPTIONAL_CLASSES - {"crows_feet"}
    if unknown_classes:
        raise GateInputError("unknown wrinkle class evidence")
    decisions = {name: _class_decision(shared_test_blockers, name, evidence) for name, evidence in classes.items()}
    if decisions["crows_feet"]["labelSupported"] is not True:
        raise GateInputError("crows-feet must remain the supported primary class")
    supported_classes = [name for name, item in decisions.items() if item["labelSupported"]]
    excluded_optional = sorted(OPTIONAL_CLASSES - set(supported_classes))
    roadmap_accepted = bool(supported_classes) and all(decisions[name]["productActivationAllowed"] for name in supported_classes)
    return {
        "schemaVersion": 2,
        "methodVersion": "wrinkle-per-class-release-gate-v2",
        "existingConcreteResultFlowPreserved": True,
        "currentExternalCrowsFeet": {"metrics": crows_metrics, "modelAccepted": False, "diagnosticOnly": True},
        "unrelatedWrinkle": {"metrics": unrelated_metrics, "diagnosticOnly": True, "substitutionAllowed": False, "activationAllowed": False},
        "researchTrainingAuthorized": not research_blockers,
        "researchTrainingBlockers": research_blockers,
        "classDecisions": decisions,
        "supportedClasses": supported_classes,
        "excludedOptionalClasses": excluded_optional,
        "roadmapAccepted": roadmap_accepted,
        "decision": "ready" if roadmap_accepted else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crows", type=Path, required=True)
    parser.add_argument("--unrelated", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(
        json.loads(args.crows.read_text(encoding="utf-8")),
        json.loads(args.unrelated.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
