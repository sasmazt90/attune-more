#!/usr/bin/env python3
"""Fail-closed release gate for externally trained wrinkle models.

Provider metrics are diagnostic evidence, not product authorization.  The
gate keeps the crows-feet candidate separate from an unrelated wrinkle
dataset whose lineage and cross-split independence are known to be invalid.
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
REQUIRED_METRICS = ("map50", "map50_95", "map75", "precision", "recall", "f1")


class GateInputError(ValueError):
    """Raised when immutable provider evidence is malformed or substituted."""


def _require_identity(receipt: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    actual = {key: receipt.get(key) for key in expected}
    if actual != expected:
        raise GateInputError(f"{label} identity does not match the frozen provider run")


def _metrics(receipt: dict[str, Any], split: str, class_name: str) -> dict[str, float]:
    classes = receipt.get("perClass", {}).get(split)
    if not isinstance(classes, dict) or class_name not in classes:
        raise GateInputError(f"missing {split}/{class_name} metrics")
    values = classes[class_name]
    if not isinstance(values, dict):
        raise GateInputError(f"invalid {split}/{class_name} metrics")
    result: dict[str, float] = {}
    for key in REQUIRED_METRICS:
        value = values.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise GateInputError(f"invalid {split}/{class_name}/{key}")
        result[key] = float(value)
    return result


def _quality_policy_passes(receipt: dict[str, Any], valid: dict[str, float], test: dict[str, float]) -> bool:
    policy = receipt.get("releasePolicy")
    if not isinstance(policy, dict) or policy.get("expertApproved") is not True:
        return False
    minimums = policy.get("minimums")
    if not isinstance(minimums, dict):
        return False
    for key in REQUIRED_METRICS:
        minimum = minimums.get(key)
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool) or not 0 <= minimum <= 1:
            raise GateInputError(f"invalid release minimum {key}")
        if valid[key] < minimum or test[key] < minimum:
            return False
    return True


def evaluate_release(crows: dict[str, Any], unrelated: dict[str, Any]) -> dict[str, Any]:
    """Evaluate research, test and activation eligibility without mutations."""

    _require_identity(crows, CROWS_IDENTITY, "crows-feet")
    _require_identity(unrelated, UNRELATED_IDENTITY, "unrelated wrinkle")
    if crows.get("trainingStatus") != "finished" or crows.get("evalStatus") != "done":
        raise GateInputError("crows-feet provider run is not complete")
    if unrelated.get("trainingStatus") != "finished" or unrelated.get("evalStatus") != "done":
        raise GateInputError("unrelated provider run is not complete")

    valid = _metrics(crows, "valid", "crows_feet")
    test = _metrics(crows, "test", "crows_feet")
    unrelated_valid = _metrics(unrelated, "valid", "wrinkles")
    unrelated_test = _metrics(unrelated, "test", "wrinkles")

    if unrelated.get("exactSelectedDataset") is not False:
        raise GateInputError("unrelated model must remain marked as a non-selected dataset")
    leakage = unrelated.get("crossSplitCandidates")
    if not isinstance(leakage, dict) or leakage.get("filename", 0) <= 0 or leakage.get("perceptual", 0) <= 0:
        raise GateInputError("known unrelated split-leakage evidence was removed")

    blockers: list[str] = []
    boolean_requirements = {
        "expertNegativeProtocolComplete": "expert_evaluated_negative_protocol_missing",
        "sourceGroupSplitIndependent": "source_group_split_independence_missing",
        "untouchedFinalTest": "untouched_final_test_missing",
        "cameraHoldoutAccepted": "independent_camera_holdout_missing",
        "productIntegrationAccepted": "working_product_integration_evidence_missing",
    }
    for field, blocker in boolean_requirements.items():
        if crows.get(field) is not True:
            blockers.append(blocker)
    if not _quality_policy_passes(crows, valid, test):
        blockers.append("expert_approved_quality_policy_missing_or_not_met")
    current_external_model_accepted = not blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "wrinkle-external-release-gate-v1",
        "crowsFeet": {
            "valid": valid,
            "test": test,
            "modelAccepted": current_external_model_accepted,
        },
        "unrelatedWrinkle": {
            "valid": unrelated_valid,
            "test": unrelated_test,
            "diagnosticOnly": True,
            "substitutionAllowed": False,
            "activationAllowed": False,
        },
        "researchTrainingAuthorized": False,
        "testEvaluationAuthorized": False,
        "productActivationAllowed": current_external_model_accepted,
        "roadmapAccepted": current_external_model_accepted,
        "blockers": blockers,
        "excludedAlternatives": [
            "unrelated_wrinkle_model_dataset_lineage_mismatch",
            "unrelated_wrinkle_model_cross_split_leakage_candidates",
        ],
        "decision": "blocked" if blockers else "ready",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crows", type=Path, required=True)
    parser.add_argument("--unrelated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(
        json.loads(args.crows.read_text(encoding="utf-8")),
        json.loads(args.unrelated.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
