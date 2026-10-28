#!/usr/bin/env python3
"""Build a fail-closed acne remediation diagnosis from privacy-safe live eval facts.

This tool deliberately cannot authorize training, final-test use, or product
activation.  It compares only evaluations that actually exist, keeps provider
``recommended`` flags non-semantic, and turns class-specific failures into a
targeted review plan.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


PROJECT = "attune-skin-acne-marks-pigmentation"
VERSION = 1
TRAINING_ID = "5b632a5c12b76fcfe703"
CLASSES = ("Pimple", "Post acne", "Pigmentation")
CONFUSION_CLASSES = ("Pigmentation", "Pimple", "Post acne", "background")
REQUIRED_EVAL_IDS = {"7s06OfIzx78XzATqr5oA", "0xMgfVLFzMyNEOhN1baC"}


class DiagnosisError(ValueError):
    """Raised when a supposedly live fact receipt is incomplete or inconsistent."""


def _metric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DiagnosisError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise DiagnosisError(f"{label} must be finite and between 0 and 1")
    return result


def _validate_confusion(value: dict[str, Any], eval_id: str) -> list[list[int]]:
    if tuple(value.get("classes", ())) != CONFUSION_CLASSES:
        raise DiagnosisError(f"{eval_id} confusion classes changed")
    if value.get("split") != "test" or value.get("confidenceThreshold") != 0.2:
        raise DiagnosisError(f"{eval_id} confusion slice must be test@0.20")
    matrix = value.get("matrix")
    if not isinstance(matrix, list) or len(matrix) != 4:
        raise DiagnosisError(f"{eval_id} confusion matrix must be 4x4")
    for row in matrix:
        if not isinstance(row, list) or len(row) != 4:
            raise DiagnosisError(f"{eval_id} confusion matrix must be 4x4")
        if any(isinstance(cell, bool) or not isinstance(cell, int) or cell < 0 for cell in row):
            raise DiagnosisError(f"{eval_id} confusion counts must be non-negative integers")
    return matrix


def _validate_eval(value: dict[str, Any]) -> dict[str, Any]:
    eval_id = value.get("evalId")
    if eval_id not in REQUIRED_EVAL_IDS:
        raise DiagnosisError("unexpected evaluation identity")
    if value.get("status") != "done" or value.get("project") != PROJECT or value.get("version") != VERSION:
        raise DiagnosisError(f"{eval_id} evaluation binding is invalid")
    summary = value.get("summary", {})
    summary_metrics = {name: _metric(summary.get(name), f"{eval_id}.{name}") for name in ("map50", "map50_95", "precision", "recall", "f1")}
    splits = value.get("perClass", {})
    normalized: dict[str, dict[str, dict[str, float]]] = {}
    for split in ("valid", "test"):
        rows = splits.get(split)
        if not isinstance(rows, list) or {row.get("className") for row in rows if isinstance(row, dict)} != set(CLASSES):
            raise DiagnosisError(f"{eval_id} {split} must contain all three classes exactly once")
        if len(rows) != len(CLASSES):
            raise DiagnosisError(f"{eval_id} {split} classes are duplicated")
        normalized[split] = {}
        for row in rows:
            name = row["className"]
            normalized[split][name] = {field: _metric(row.get(field), f"{eval_id}.{split}.{name}.{field}") for field in ("map50", "map50_95", "precision", "recall", "f1", "optimalThreshold")}
    return {
        "evalId": eval_id,
        "modelId": value.get("modelId"),
        "providerRecommended": value.get("providerRecommended") is True,
        "summary": summary_metrics,
        "perClass": normalized,
        "confusion": _validate_confusion(value.get("confusion", {}), eval_id),
    }


def build_diagnosis(facts: dict[str, Any]) -> dict[str, Any]:
    if facts.get("schemaVersion") != "acne-live-evaluation-facts-v1":
        raise DiagnosisError("facts schema is invalid")
    project = facts.get("project", {})
    if project.get("id") != PROJECT or project.get("version") != VERSION or project.get("images") != 800:
        raise DiagnosisError("project binding changed")
    if project.get("splits") != {"train": 553, "valid": 165, "test": 82}:
        raise DiagnosisError("dataset split inventory changed")
    if project.get("classes") != {"Pimple": 3640, "Post acne": 32123, "Pigmentation": 1579}:
        raise DiagnosisError("class inventory changed")
    training = facts.get("training", {})
    if training.get("trainingId") != TRAINING_ID or training.get("status") != "finished" or training.get("nasChildren") != 89:
        raise DiagnosisError("NAS training identity or completion changed")
    rows = facts.get("evaluations")
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_EVAL_IDS):
        raise DiagnosisError("both known evaluations are required")
    evaluations = [_validate_eval(row) for row in rows]
    if {row["evalId"] for row in evaluations} != REQUIRED_EVAL_IDS:
        raise DiagnosisError("known evaluation set is incomplete")

    expected_models = training["nasChildren"] + 1
    evaluated_models = len(evaluations)
    missing_evaluations = expected_models - evaluated_models
    leader = max(evaluations, key=lambda row: row["summary"]["map50_95"])
    recommended = next((row for row in evaluations if row["providerRecommended"]), None)

    class_actions = {
        "Pimple": [
            "expert-review Pimple versus Post acne boundary and hard negatives",
            "review missed small lesions and false-positive objectness before any resolution experiment",
        ],
        "Post acne": [
            "expert-review dense Post acne labels and Pimple/Pigmentation confusions",
            "define sampling policy only after group locking; do not treat class prevalence as truth quality",
        ],
        "Pigmentation": [
            "expert-adjudicate Pigmentation versus Post acne, freckles, moles, shadow, and tone variation",
            "collect/review targeted positives and hard negatives; never populate from a tone proxy",
        ],
    }
    class_findings: dict[str, Any] = {}
    for class_name in CLASSES:
        best = max(evaluations, key=lambda row: row["perClass"]["test"][class_name]["map50_95"])
        idx = CONFUSION_CLASSES.index(class_name)
        matrix = best["confusion"]
        class_findings[class_name] = {
            "bestObservedEvalId": best["evalId"],
            "validation": best["perClass"]["valid"][class_name],
            "diagnosticTest": best["perClass"]["test"][class_name],
            "testAtConfidence020": {
                "truePositive": matrix[idx][idx],
                "missedToBackground": matrix[idx][3],
                "crossClassPredictions": sum(matrix[idx][j] for j in range(3) if j != idx),
                "falsePositiveFromBackground": matrix[3][idx],
            },
            "accepted": False,
            "actions": class_actions[class_name],
        }

    controls = facts.get("releaseControls", {})
    blockers = []
    for field, reason in (
        ("expertSemanticReviewComplete", "expert_semantic_review_incomplete"),
        ("personIndependentGroupingComplete", "person_independent_grouping_incomplete"),
        ("groupLockedReplacementSplitReady", "group_locked_replacement_split_missing"),
        ("newUntouchedFinalTestReserved", "new_untouched_final_test_missing"),
        ("physicalCameraHoldoutReserved", "physical_camera_holdout_missing"),
    ):
        if controls.get(field) is not True:
            blockers.append(reason)
    if controls.get("existingTestExposed") is not True:
        raise DiagnosisError("current test exposure fact cannot be cleared by this receipt")
    blockers.extend(["current_test_is_diagnostic_only", "evaluated_model_coverage_incomplete", "all_three_classes_below_release_quality"])

    return {
        "schemaVersion": "acne-live-evaluation-diagnosis-v1",
        "observedAt": facts.get("observedAt"),
        "project": {"id": PROJECT, "version": VERSION},
        "evaluationCoverage": {
            "expectedModels": expected_models,
            "evaluatedModels": evaluated_models,
            "missingEvaluations": missing_evaluations,
            "complete": missing_evaluations == 0,
        },
        "observedMetricLeader": {
            "evalId": leader["evalId"],
            "modelId": leader["modelId"],
            "testMap50_95": leader["summary"]["map50_95"],
            "isReleaseWinner": False,
        },
        "providerRecommendedFlag": {
            "evalId": recommended["evalId"] if recommended else None,
            "usedAsAccuracyOrHardwareWinner": False,
            "overridesPerClassEvidence": False,
        },
        "classes": class_findings,
        "targetedNextExperiment": {
            "type": "face_aligned_single_roi_or_higher_effective_resolution",
            "validationOnly": True,
            "authorizedNow": False,
            "prerequisites": blockers[:5],
        },
        "decision": {
            "trainingAuthorized": False,
            "finalTestEvaluationAuthorized": False,
            "productActivationAllowed": False,
            "blindRetrainingAllowed": False,
            "reason": "TARGETED_DATA_AND_SEMANTIC_REMEDIATION_REQUIRED",
            "blockers": blockers,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsProviderImageIds": False,
            "containsExcludedArchiveDetails": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_diagnosis(json.loads(args.facts.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
