#!/usr/bin/env python3
"""Fail-closed authorization gate for the next acne improvement experiment.

This gate consumes privacy-safe receipts. It does not change labels, generate a
dataset version, start training, evaluate a test set, or activate a model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_MODEL_ID = "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-small-t2"
EXPECTED_TRAINING_ID = "49ee6204cf069198bbfa"
EXPECTED_EVAL_ID = "7s06OfIzx78XzATqr5oA"
EXPECTED_ARCHIVE_SHA256 = "29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2"
CLASSES = ("Pimple", "Post acne", "Pigmentation")
ALLOWED_EXPERIMENT_CHANGE = "face_aligned_single_roi_or_higher_effective_resolution"


class GateError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc


def validate_diagnosis(value: dict[str, Any]) -> None:
    if value.get("schemaVersion") != "acne-model-diagnosis-v1":
        raise GateError("diagnosis schema is invalid")
    identity = value.get("modelIdentity", {})
    expected = {
        "modelId": EXPECTED_MODEL_ID,
        "trainingId": EXPECTED_TRAINING_ID,
        "evalId": EXPECTED_EVAL_ID,
        "versionNumber": 1,
    }
    if any(identity.get(key) != expected_value for key, expected_value in expected.items()):
        raise GateError("diagnosis model/evaluation binding does not match")
    dataset = value.get("dataset", {})
    if dataset.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256:
        raise GateError("diagnosis archive binding does not match")
    privacy = value.get("privacy", {})
    required_false = (
        "containsImageBytes", "containsFilenames", "containsRawSourceNames",
        "containsProviderImageIds",
    )
    if any(privacy.get(key) is not False for key in required_false):
        raise GateError("diagnosis is not privacy safe")
    decision = value.get("decision", {})
    if decision.get("modelAccepted") is not False or decision.get("activationAllowed") is not False:
        raise GateError("diagnosis must preserve the rejected model decision")
    if decision.get("nextExperimentPolicy") != "one_change_validation_only_after_release_gate":
        raise GateError("diagnosis experiment policy is invalid")


def semantic_complete(value: dict[str, Any] | None) -> bool:
    if value is None:
        return False
    if value.get("schemaVersion") != "acne-semantic-negative-review-v1":
        raise GateError("semantic review schema is invalid")
    if value.get("datasetArchiveSHA256") != EXPECTED_ARCHIVE_SHA256:
        raise GateError("semantic review archive binding does not match")
    if value.get("reviewer") != "expert_review":
        return False
    rows = value.get("classes")
    if not isinstance(rows, list):
        raise GateError("semantic review classes are missing")
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("name") not in CLASSES:
            raise GateError("semantic review class row is invalid")
        if row["name"] in by_name:
            raise GateError("semantic review classes are duplicated")
        by_name[row["name"]] = row
    return all(
        name in by_name
        and by_name[name].get("expertReviewed") is True
        and by_name[name].get("positiveDefinitionLocked") is True
        and by_name[name].get("hardNegativePolicyLocked") is True
        and by_name[name].get("ambiguousCasePolicyLocked") is True
        and isinstance(by_name[name].get("reviewedItemIds"), list)
        and len(by_name[name]["reviewedItemIds"]) > 0
        for name in CLASSES
    )


def split_ready(value: dict[str, Any]) -> bool:
    if value.get("schemaVersion") != "acne-split-release-gate-v1":
        raise GateError("split gate schema is invalid")
    dataset = value.get("dataset", {})
    if dataset.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256 or dataset.get("records") != 800:
        raise GateError("split gate dataset binding does not match")
    return (
        value.get("decision", {}).get("readyToGenerateReplacementSplit") is True
        and value.get("replacementSplit", {}).get("complete") is True
        and value.get("semanticNegativeReview", {}).get("complete") is True
    )


def experiment_ready(value: dict[str, Any] | None) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "acne-validation-experiment-v1":
        raise GateError("validation experiment schema is invalid")
    changes = value.get("changes")
    if not isinstance(changes, list) or len(changes) != 1:
        return False, "EXACTLY_ONE_EXPERIMENT_CHANGE_REQUIRED"
    change = changes[0]
    if not isinstance(change, dict) or change.get("type") != ALLOWED_EXPERIMENT_CHANGE:
        return False, "EXPERIMENT_CHANGE_NOT_TARGETED_TO_CONFIRMED_PROBLEM"
    if value.get("selectionSplit") != "valid" or value.get("testUsedForSelection") is not False:
        return False, "EXPERIMENT_MUST_BE_VALIDATION_ONLY"
    replacement_version = value.get("replacementDatasetVersion")
    if not isinstance(replacement_version, str) or not replacement_version or replacement_version == "1":
        return False, "REPLACEMENT_DATASET_VERSION_REQUIRED"
    return True, None


def final_test_ready(value: dict[str, Any] | None, experiment: dict[str, Any] | None) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "acne-untouched-final-test-v1":
        raise GateError("final test schema is invalid")
    if value.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256:
        raise GateError("final test archive binding does not match")
    if (
        value.get("isUntouched") is not True
        or value.get("frozenBeforeTraining") is not True
        or value.get("sourcePersonGroupingComplete") is not True
        or value.get("overlapWithPreviouslyExposedTestImages") != 0
        or not isinstance(value.get("images"), int)
        or value.get("images") <= 0
    ):
        return False, "FINAL_TEST_NOT_UNTOUCHED_OR_GROUP_SAFE"
    dataset_version = value.get("replacementDatasetVersion")
    if dataset_version == "1" or not isinstance(dataset_version, str) or not dataset_version:
        return False, "NEW_FINAL_TEST_VERSION_REQUIRED"
    if experiment is not None and experiment.get("replacementDatasetVersion") != dataset_version:
        return False, "EXPERIMENT_FINAL_TEST_VERSION_MISMATCH"
    return True, None


def build_gate(
    diagnosis: dict[str, Any],
    split_gate: dict[str, Any],
    semantic_review: dict[str, Any] | None = None,
    experiment: dict[str, Any] | None = None,
    final_test: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_diagnosis(diagnosis)
    split_ok = split_ready(split_gate)
    semantic_ok = semantic_complete(semantic_review)
    experiment_ok, experiment_reason = experiment_ready(experiment)
    final_test_ok, final_test_reason = final_test_ready(final_test, experiment)

    blockers: list[str] = []
    if not split_ok:
        blockers.append("SOURCE_PERSON_GROUP_LOCKED_REPLACEMENT_SPLIT_MISSING")
    if not semantic_ok:
        blockers.append("EXPERT_SEMANTIC_NEGATIVE_POLICY_MISSING")
    if experiment is None:
        blockers.append("VALIDATION_ONLY_ONE_CHANGE_EXPERIMENT_MISSING")
    elif not experiment_ok:
        blockers.append(experiment_reason or "VALIDATION_EXPERIMENT_INVALID")
    if final_test is None:
        blockers.append("NEW_UNTOUCHED_FINAL_TEST_MISSING")
    elif not final_test_ok:
        blockers.append(final_test_reason or "FINAL_TEST_INVALID")

    authorized = not blockers
    return {
        "schemaVersion": "acne-improvement-release-gate-v1",
        "modelIdentity": diagnosis["modelIdentity"],
        "checks": {
            "sourcePersonGroupLockedReplacementSplit": split_ok,
            "expertSemanticNegativePolicy": semantic_ok,
            "validationOnlyOneChangeExperiment": experiment_ok,
            "newUntouchedFinalTest": final_test_ok,
        },
        "decision": {
            "trainingAuthorized": authorized,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
            "blockedReasons": blockers,
            "note": (
                "Authorization permits one validation-only training experiment. "
                "It never permits test evaluation or activation; those require later receipts."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--split-gate", type=Path, required=True)
    parser.add_argument("--semantic-review", type=Path)
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--final-test", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-authorized", action="store_true")
    args = parser.parse_args()
    result = build_gate(
        load_json(args.diagnosis),
        load_json(args.split_gate),
        load_json(args.semantic_review) if args.semantic_review else None,
        load_json(args.experiment) if args.experiment else None,
        load_json(args.final_test) if args.final_test else None,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return int(args.require_authorized and not result["decision"]["trainingAuthorized"])


if __name__ == "__main__":
    raise SystemExit(main())
