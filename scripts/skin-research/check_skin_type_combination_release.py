#!/usr/bin/env python3
"""Fail-closed gate for regional normal/dry/oily evidence and mixed skin.

The existing global three-class result is a functioning product baseline.  It
must not be removed while the regional evidence needed for a supported mixed
skin result is incomplete.  Conversely, whole-face argmaxes, detector boxes,
missing annotations and model proposals can never be copied into region truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_BLOBS = {
    "mainLocalSkinType": "8a89c9d89d2bc31cf934e5b2473a455193defa6b",
    "roadmapLocalSkinType": "806f6f8e236b3689cfd420ec07550813df4a7eff",
    "roadmapRegionalEvidence": "a8fbfefb613b01162df863614df5a91bf5a6f4f0",
    "boxAudit": "3c9114c9e7892f6ed03dfffb7eea92ce212bc408",
    "boxModelReceipt": "7d0817f9df9cb19d38830c7b5288ad7b93d4c934",
    "boxModelVerdict": "4d875dc9800b5b5f3504d2b27d7b42f873033d09",
    "sourceGroupResolution": "4aec8f0657b7df8c958711f946baea8fd471bc3c",
    "currentMergedCapability": "001a343c4ae2537a8b6b9e8ccc2621586ddf014e",
}
SOURCE_ARCHIVE = "4af7732298a0f54c3e1bd4aa68ca954429c39a19a832331a4ce542ae365fa228"


class GateInputError(ValueError):
    """Raised when a pinned identity or accepted semantic boundary drifts."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    baseline = receipt.get("currentProductBaseline", {})
    _require(baseline.get("commit"), "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285", "merged baseline identity changed")
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product baseline cannot be erased")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("appearanceCriteria"), 9, "existing appearance inventory changed")
    _require(baseline.get("separateSkinTypeResults"), 6, "existing skin-type replay changed")
    _require(baseline.get("regionalInventoriesComplete"), 6, "existing regional replay changed")

    implementation = receipt.get("roadmapImplementation", {})
    _require(implementation.get("globalClasses"), ["dry", "normal", "oily"], "global class contract changed")
    _require(implementation.get("globalPredictionPreserved"), True, "global prediction must be preserved")
    _require(implementation.get("tZone"), ["forehead", "nose", "chin"], "accepted T-zone changed")
    _require(implementation.get("outsideTZone"), ["leftCheek", "rightCheek"], "accepted outside-T zone changed")
    _require(implementation.get("combinationRequiresCompleteRegionalEvidence"), True, "combination cannot use incomplete evidence")
    _require(implementation.get("wholeFaceCopiedToRegionsAllowed"), False, "whole-face labels cannot become regional truth")
    _require(implementation.get("boxesAsRegionalTruthAllowed"), False, "boxes cannot become regional truth")
    _require(implementation.get("missingLabelMeansNormal"), False, "missing labels cannot become normal")
    _require(implementation.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(implementation.get("normalColour"), None, "evaluated normal must remain uncoloured")
    _require(implementation.get("unknownColour"), "#D1D5DB", "unknown must remain light gray")

    source = receipt.get("regionalBoxSource", {})
    _require(source.get("archiveSHA256"), SOURCE_ARCHIVE, "regional box archive changed")
    _require(source.get("images"), 1711, "regional box image inventory changed")
    _require(source.get("uniqueSourceIds"), 990, "regional source inventory changed")
    _require(source.get("dryBoxes"), 3648, "dry box inventory changed")
    _require(source.get("oilyBoxes"), 1604, "oily box inventory changed")
    _require(source.get("nonEmptySegmentations"), 0, "box source cannot become polygon truth")
    _require(source.get("normalClassPresent"), False, "box source has no normal truth")
    _require(source.get("confirmedCrossSplitGroups"), 1, "known leakage evidence changed")
    _require(source.get("unreviewedSingletonSources"), 986, "identity coverage changed")
    _require(source.get("testEligibleForFinalAcceptance"), False, "leaking exposed test cannot become final evidence")

    model = receipt.get("regionalBoxModel", {})
    _require(model.get("trainingId"), "a9e8b8a021825191cf5b", "box model identity changed")
    _require(model.get("thresholdsLockedBeforeTest"), False, "historical threshold status changed")
    _require(model.get("dryTestF1"), 0.215, "dry test metric changed")
    _require(model.get("oilyTestF1"), 0.279, "oily test metric changed")
    _require(model.get("accepted"), False, "rejected box model cannot become accepted")

    candidate = receipt.get("candidate", {})
    training_requirements = {
        "rightsReviewedRegionalSources": "rights_reviewed_regional_sources_missing",
        "expertRegionalPolygonProtocolComplete": "expert_regional_polygon_protocol_missing",
        "evaluatedNormalNegativeTruthComplete": "evaluated_normal_negative_truth_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "acceptedMethodRegistryPopulated": "accepted_regional_method_registry_empty",
    }
    training_blockers = [reason for field, reason in training_requirements.items() if candidate.get(field) is not True]
    training_allowed = not training_blockers

    evaluation_blockers = list(training_blockers)
    if candidate.get("validationPassed") is not True:
        evaluation_blockers.append("validation_acceptance_missing")
    if candidate.get("untouchedFinalTestReserved") is not True:
        evaluation_blockers.append("untouched_final_test_reservation_missing")
    evaluation_allowed = not evaluation_blockers

    activation_blockers = list(evaluation_blockers)
    for field, reason in (
        ("untouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("physicalCameraHoldoutPassed", "physical_camera_acceptance_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_acceptance_missing"),
    ):
        if candidate.get(field) is not True:
            activation_blockers.append(reason)

    activation_allowed = not activation_blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "skin-type-combination-release-gate-v1",
        "existingGlobalSkinTypeFlowPreserved": True,
        "combinationRuleImplementationReady": True,
        "wholeFaceToRegionalTruthAllowed": False,
        "boxToRegionalTruthAllowed": False,
        "missingLabelAsNormalAllowed": False,
        "researchTrainingAuthorized": training_allowed,
        "finalTestEvaluationAuthorized": evaluation_allowed,
        "combinationProductActivationAllowed": activation_allowed,
        "roadmapAccepted": activation_allowed,
        "trainingBlockers": training_blockers,
        "evaluationBlockers": evaluation_blockers,
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
