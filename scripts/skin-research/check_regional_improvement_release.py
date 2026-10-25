#!/usr/bin/env python3
"""Fail-closed authorization gate for one regional-mask improvement experiment.

The gate reads privacy-safe receipts only. It never changes annotations, creates
a dataset version, starts a training job, evaluates a test set, or activates a
model. A successful result authorizes one validation-only training experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_MODEL_ID = "tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-seg-small-t2"
EXPECTED_TRAINING_ID = "af287a006e2e428f5ce4"
EXPECTED_EVAL_ID = "vsQ6klUgSohCdtLwNMJf"
EXPECTED_ARCHIVE_SHA256 = "a24793ca3490a48088abf47ba89fc9ab94e1c3a12c488ce52915e19b5bdf6fd6"
EXPECTED_PROVIDER_EXPORT_SHA256 = "ba7aa450ee2e98af35dcb1b60f3f9673fc7a6ef6b7709e7b94e1df1d32bdab3a"
EXPECTED_IMAGES = 337
EXPECTED_ANNOTATIONS = 1636
CLASSES = ("Oily", "Redness")
ALLOWED_EXPERIMENT_CHANGES = {
    "face_aligned_higher_effective_resolution",
    "mask_extent_standardization",
}
MINIMUM_FINAL_TEST_IMAGES = 50


class GateError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc


def validate_diagnosis(value: dict[str, Any]) -> None:
    if value.get("schemaVersion") != "regional-mask-model-diagnosis-v1":
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
    if (
        dataset.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256
        or dataset.get("images") != EXPECTED_IMAGES
    ):
        raise GateError("diagnosis dataset binding does not match")
    privacy = value.get("privacy", {})
    required_false = (
        "containsImageBytes",
        "containsFilenames",
        "containsRawSourceNames",
        "containsProviderImageIds",
    )
    if any(privacy.get(key) is not False for key in required_false):
        raise GateError("diagnosis is not privacy safe")
    decision = value.get("decision", {})
    if (
        decision.get("modelAccepted") is not False
        or decision.get("activationAllowed") is not False
        or decision.get("rednessIndependentLayer") is not True
    ):
        raise GateError("diagnosis must preserve rejection and independent Redness semantics")
    if decision.get("nextExperimentPolicy") != "one_change_validation_only_after_release_gate":
        raise GateError("diagnosis experiment policy is invalid")


def validate_source_audit(value: dict[str, Any]) -> None:
    if value.get("schemaVersion") != "regional-mask-source-group-audit-v1":
        raise GateError("source audit schema is invalid")
    source = value.get("source", {})
    if (
        source.get("sourceArchiveSHA256") != EXPECTED_ARCHIVE_SHA256
        or source.get("providerExportSHA256") != EXPECTED_PROVIDER_EXPORT_SHA256
        or source.get("versionNumber") != 1
    ):
        raise GateError("source audit archive/export binding does not match")
    privacy = value.get("privacy", {})
    required_false = (
        "containsImageBytes",
        "containsFilenames",
        "containsRawSourceNames",
        "containsProviderImageIds",
        "resolverCommitted",
    )
    if any(privacy.get(key) is not False for key in required_false):
        raise GateError("source audit is not privacy safe")
    inventory = value.get("inventory", {})
    expected_inventory = {
        "images": EXPECTED_IMAGES,
        "uniqueSourceIds": EXPECTED_IMAGES,
        "annotations": EXPECTED_ANNOTATIONS,
        "polygonAnnotations": EXPECTED_ANNOTATIONS,
        "nonPolygonAnnotations": 0,
        "invalidPolygonAnnotations": 0,
    }
    if any(inventory.get(key) != expected for key, expected in expected_inventory.items()):
        raise GateError("source audit inventory or polygon geometry does not match")
    coverage = value.get("coverage", {})
    if coverage.get("allRecordsRepresented") is not True:
        raise GateError("source audit does not represent every source record")
    decision = value.get("decision", {})
    if (
        decision.get("trainingAuthorized") is not False
        or decision.get("replacementSplitReady") is not False
        or decision.get("testEligibleForFinalAcceptance") is not False
    ):
        raise GateError("source audit must preserve fail-closed decisions")


def group_split_ready(value: dict[str, Any] | None) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "regional-mask-group-split-v1":
        raise GateError("group split schema is invalid")
    source = value.get("source", {})
    if (
        source.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256
        or source.get("images") != EXPECTED_IMAGES
    ):
        raise GateError("group split source binding does not match")
    replacement_version = value.get("replacementDatasetVersion")
    if not isinstance(replacement_version, str) or not replacement_version or replacement_version == "1":
        return False, "REPLACEMENT_DATASET_VERSION_REQUIRED"
    if (
        value.get("complete") is not True
        or value.get("sourcePersonGroupingComplete") is not True
        or value.get("sourcePersonOverlapAcrossSplits") != 0
        or value.get("testUntouched") is not True
    ):
        return False, "SOURCE_PERSON_GROUP_LOCKED_REPLACEMENT_SPLIT_MISSING"
    return True, None


def mask_protocol_ready(value: dict[str, Any] | None) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "regional-mask-expert-protocol-v1":
        raise GateError("mask protocol schema is invalid")
    if value.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256:
        raise GateError("mask protocol archive binding does not match")
    if value.get("reviewer") != "expert_review":
        return False, "EXPERT_MASK_AND_NEGATIVE_PROTOCOL_MISSING"
    if (
        value.get("rednessIndependentLayer") is not True
        or value.get("missingMaskMeansNormal") is not False
        or value.get("modelPredictionAcceptedAsTruth") is not False
    ):
        return False, "REGIONAL_SEMANTIC_INVARIANTS_NOT_LOCKED"
    rows = value.get("classes")
    if not isinstance(rows, list):
        raise GateError("mask protocol classes are missing")
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("name") not in CLASSES:
            raise GateError("mask protocol class row is invalid")
        if row["name"] in by_name:
            raise GateError("mask protocol classes are duplicated")
        by_name[row["name"]] = row
    complete = all(
        name in by_name
        and by_name[name].get("expertReviewed") is True
        and by_name[name].get("maskExtentPolicyLocked") is True
        and by_name[name].get("hardNegativePolicyLocked") is True
        and by_name[name].get("ambiguousCasePolicyLocked") is True
        and isinstance(by_name[name].get("reviewedItemIds"), list)
        and len(by_name[name]["reviewedItemIds"]) > 0
        for name in CLASSES
    )
    return (complete, None if complete else "EXPERT_MASK_AND_NEGATIVE_PROTOCOL_MISSING")


def experiment_ready(value: dict[str, Any] | None) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "regional-mask-validation-experiment-v1":
        raise GateError("validation experiment schema is invalid")
    changes = value.get("changes")
    if not isinstance(changes, list) or len(changes) != 1:
        return False, "EXACTLY_ONE_EXPERIMENT_CHANGE_REQUIRED"
    change = changes[0]
    if not isinstance(change, dict) or change.get("type") not in ALLOWED_EXPERIMENT_CHANGES:
        return False, "EXPERIMENT_CHANGE_NOT_TARGETED_TO_CONFIRMED_PROBLEM"
    if value.get("selectionSplit") != "valid" or value.get("testUsedForSelection") is not False:
        return False, "EXPERIMENT_MUST_BE_VALIDATION_ONLY"
    if value.get("rednessIndependentLayer") is not True:
        return False, "REDNESS_INDEPENDENT_LAYER_REQUIRED"
    replacement_version = value.get("replacementDatasetVersion")
    if not isinstance(replacement_version, str) or not replacement_version or replacement_version == "1":
        return False, "REPLACEMENT_DATASET_VERSION_REQUIRED"
    return True, None


def final_test_ready(
    value: dict[str, Any] | None,
    group_split: dict[str, Any] | None,
    experiment: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    if value.get("schemaVersion") != "regional-mask-untouched-final-test-v1":
        raise GateError("final test schema is invalid")
    if value.get("archiveSHA256") != EXPECTED_ARCHIVE_SHA256:
        raise GateError("final test archive binding does not match")
    images = value.get("images")
    if not isinstance(images, int) or images < MINIMUM_FINAL_TEST_IMAGES:
        return False, "FINAL_TEST_BELOW_50_IMAGES"
    if (
        value.get("isUntouched") is not True
        or value.get("frozenBeforeTraining") is not True
        or value.get("sourcePersonGroupingComplete") is not True
        or value.get("overlapWithPreviouslyExposedTestImages") != 0
        or value.get("independentProductCameraHoldoutReserved") is not True
        or not isinstance(value.get("productCameraHoldoutImages"), int)
        or value.get("productCameraHoldoutImages") <= 0
    ):
        return False, "FINAL_TEST_NOT_UNTOUCHED_GROUP_SAFE_OR_CAMERA_RESERVED"
    dataset_version = value.get("replacementDatasetVersion")
    if not isinstance(dataset_version, str) or not dataset_version or dataset_version == "1":
        return False, "NEW_FINAL_TEST_VERSION_REQUIRED"
    for receipt in (group_split, experiment):
        if receipt is not None and receipt.get("replacementDatasetVersion") != dataset_version:
            return False, "REPLACEMENT_VERSION_MISMATCH"
    return True, None


def build_gate(
    diagnosis: dict[str, Any],
    source_audit: dict[str, Any] | None = None,
    group_split: dict[str, Any] | None = None,
    mask_protocol: dict[str, Any] | None = None,
    experiment: dict[str, Any] | None = None,
    final_test: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_diagnosis(diagnosis)
    if source_audit is not None:
        validate_source_audit(source_audit)
    source_audit_ok = source_audit is not None
    group_ok, group_reason = group_split_ready(group_split)
    protocol_ok, protocol_reason = mask_protocol_ready(mask_protocol)
    experiment_ok, experiment_reason = experiment_ready(experiment)
    final_test_ok, final_test_reason = final_test_ready(final_test, group_split, experiment)

    blockers: list[str] = []
    if source_audit is None:
        blockers.append("FROZEN_PROVIDER_EXPORT_AUDIT_MISSING")
    if group_split is None:
        blockers.append("SOURCE_PERSON_GROUP_LOCKED_REPLACEMENT_SPLIT_MISSING")
    elif not group_ok:
        blockers.append(group_reason or "GROUP_SPLIT_INVALID")
    if mask_protocol is None:
        blockers.append("EXPERT_MASK_AND_NEGATIVE_PROTOCOL_MISSING")
    elif not protocol_ok:
        blockers.append(protocol_reason or "MASK_PROTOCOL_INVALID")
    if experiment is None:
        blockers.append("VALIDATION_ONLY_ONE_CHANGE_EXPERIMENT_MISSING")
    elif not experiment_ok:
        blockers.append(experiment_reason or "VALIDATION_EXPERIMENT_INVALID")
    if final_test is None:
        blockers.append("NEW_UNTOUCHED_50_IMAGE_FINAL_TEST_AND_CAMERA_HOLDOUT_MISSING")
    elif not final_test_ok:
        blockers.append(final_test_reason or "FINAL_TEST_INVALID")

    authorized = not blockers
    return {
        "schemaVersion": "regional-mask-improvement-release-gate-v1",
        "modelIdentity": diagnosis["modelIdentity"],
        "checks": {
            "frozenProviderExportAuditBound": source_audit_ok,
            "sourcePersonGroupLockedReplacementSplit": group_ok,
            "expertMaskAndNegativeProtocol": protocol_ok,
            "rednessIndependentLayer": diagnosis["decision"]["rednessIndependentLayer"],
            "validationOnlyOneChangeExperiment": experiment_ok,
            "newUntouchedFinalTestAtLeast50AndCameraHoldout": final_test_ok,
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
    parser.add_argument("--source-audit", type=Path)
    parser.add_argument("--group-split", type=Path)
    parser.add_argument("--mask-protocol", type=Path)
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--final-test", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-authorized", action="store_true")
    args = parser.parse_args()
    result = build_gate(
        load_json(args.diagnosis),
        load_json(args.source_audit) if args.source_audit else None,
        load_json(args.group_split) if args.group_split else None,
        load_json(args.mask_protocol) if args.mask_protocol else None,
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
