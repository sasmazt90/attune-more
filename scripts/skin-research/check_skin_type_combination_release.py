#!/usr/bin/env python3
"""Identity-bound release gate for regional skin type and combination.

The existing global dry/normal/oily output is a functioning product baseline.
Combination is a stricter regional claim: every T-zone region must have accepted
oily support and both cheeks must have accepted Dry or explicitly evaluated
Normal support. Detector boxes, absent labels and whole-face predictions cannot
be promoted into that truth.
"""

from __future__ import annotations

import argparse
import json
import re
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
    "oilyReleaseReceiptV2": "bf6f62b5a0c0cb03df484df24ce81ef46432de0a",
    "oilyReleaseGateV2": "0a8f8219af4bac33f2b9c35dca1d5d95f7cc969d",
    "drynessReleaseReceiptV2": "155351f3f6741ab91eeab1b8b20e59411933f9df",
    "drynessReleaseGateV2": "32b114c674ad47abeb8ed52eb5da96db64f8a694",
}
SOURCE_ARCHIVE = "4af7732298a0f54c3e1bd4aa68ca954429c39a19a832331a4ce542ae365fa228"
EXTERNAL_PROJECT_ID = "tolgar-sasmaz/attune-skin-type-regional-r1"
REGIONAL_PROJECT_ID = "tolgar-sasmaz/attune-skin-regional-skin-map"
REJECTED_BOX_MODEL_ID = "tolgar-sasmaz/attune-skin-type-regional-r1-2-rfdetr-small-t1"
REJECTED_REGIONAL_MODEL_ID = "tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-seg-small-t2"
T_ZONE = {"forehead", "nose", "chin"}
OUTSIDE_T_ZONE = {"leftCheek", "rightCheek"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GateInputError(ValueError):
    """Raised when a pinned identity or accepted semantic boundary drifts."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _require_evidence_identity(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise GateInputError(f"{label} evidence identity missing")
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path.startswith("docs/skin/evidence/"):
        raise GateInputError(f"{label} evidence path missing")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise GateInputError(f"{label} evidence sha256 missing")


def _validate_method(method: Any, role: str) -> tuple[str, set[str]]:
    if not isinstance(method, dict):
        raise GateInputError(f"{role} accepted method missing")
    _require(method.get("role"), role, f"{role} method role changed")
    _require(method.get("accepted"), True, f"{role} method is not accepted")
    _require(method.get("truthSource"), "expert-regional", f"{role} requires expert regional truth")
    _require(method.get("wholeFaceReplicationAllowed"), False, f"{role} cannot copy whole-face predictions")
    _require(method.get("missingLabelMeansNormal"), False, f"{role} cannot treat missing labels as normal")
    _require(method.get("modelPredictionIsExpertTruth"), False, f"{role} cannot use model proposals as expert truth")
    _require(method.get("sourcePersonGroupSplitIndependent"), True, f"{role} group independence missing")
    _require(method.get("thresholdsLockedBeforeFinalTest"), True, f"{role} thresholds were not locked")
    for field in ("validationPassed", "untouchedFinalTestPassed", "physicalCameraPassed", "workingProductIntegrationPassed"):
        _require(method.get(field), True, f"{role} {field} missing")

    method_id = method.get("methodId")
    if not isinstance(method_id, str) or not method_id.strip():
        raise GateInputError(f"{role} method identity missing")
    _require_evidence_identity(method.get("acceptanceEvidence"), role)

    regions = method.get("regions")
    if not isinstance(regions, list) or any(not isinstance(region, str) for region in regions):
        raise GateInputError(f"{role} regions missing")
    region_set = set(regions)
    expected_regions = T_ZONE if role == "oily_t_zone" else OUTSIDE_T_ZONE
    if not expected_regions.issubset(region_set):
        raise GateInputError(f"{role} coverage incomplete")

    geometry = method.get("geometry")
    if role in {"oily_t_zone", "outside_dry"}:
        _require(geometry, "polygon", f"{role} requires polygon support")
    else:
        _require(geometry, "evaluated-uncoloured-region", "Normal requires explicit evaluated uncoloured regions")

    kind = method.get("kind")
    if kind == "learned-mask":
        _require(method.get("projectId"), REGIONAL_PROJECT_ID, f"{role} learned method project changed")
        version = method.get("datasetVersion")
        if not isinstance(version, int) or isinstance(version, bool) or version < 2:
            raise GateInputError(f"{role} group-locked dataset version missing")
        training_id = method.get("trainingId")
        model_id = method.get("modelId")
        if not isinstance(training_id, str) or not training_id:
            raise GateInputError(f"{role} training identity missing")
        if not isinstance(model_id, str) or not model_id.startswith(f"{REGIONAL_PROJECT_ID}-{version}-"):
            raise GateInputError(f"{role} model identity missing")
        if model_id in {REJECTED_BOX_MODEL_ID, REJECTED_REGIONAL_MODEL_ID}:
            raise GateInputError("known rejected model cannot enter the accepted method registry")
    elif kind == "expert-rule":
        for field in ("protocolId", "datasetReleaseId", "sourceCollectionSHA256"):
            value = method.get(field)
            if not isinstance(value, str) or not value:
                raise GateInputError(f"{role} expert-rule {field} missing")
        if SHA256.fullmatch(method["sourceCollectionSHA256"]) is None:
            raise GateInputError(f"{role} source collection sha256 missing")
        if any(method.get(field) is not None for field in ("projectId", "datasetVersion", "trainingId", "modelId")):
            raise GateInputError(f"{role} expert-rule cannot claim a model identity")
    else:
        raise GateInputError(f"{role} method kind unsupported")
    return method_id, region_set


def _validate_registry(candidate: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    mode = candidate.get("mode")
    methods = candidate.get("methods")
    if mode not in {"not-populated", "accepted-registry"}:
        raise GateInputError("unknown combination candidate mode")
    if mode == "not-populated":
        if candidate.get("registryId") is not None or candidate.get("registryEvidence") is not None or methods != []:
            raise GateInputError("not-populated registry cannot claim accepted method identities")
        return False, ["accepted_regional_method_registry_empty"], []

    registry_id = candidate.get("registryId")
    if not isinstance(registry_id, str) or not registry_id:
        raise GateInputError("accepted registry identity missing")
    _require_evidence_identity(candidate.get("registryEvidence"), "registry")
    if not isinstance(methods, list):
        raise GateInputError("accepted registry methods missing")
    by_role: dict[str, dict[str, Any]] = {}
    for method in methods:
        if not isinstance(method, dict) or method.get("role") not in {"oily_t_zone", "outside_dry", "outside_normal"}:
            raise GateInputError("accepted registry contains an unsupported method role")
        role = method["role"]
        if role in by_role:
            raise GateInputError("accepted registry contains a duplicate method role")
        by_role[role] = method
    if "oily_t_zone" not in by_role:
        return False, ["accepted_oily_t_zone_method_missing"], []
    outside_roles = [role for role in ("outside_dry", "outside_normal") if role in by_role]
    if not outside_roles:
        return False, ["accepted_outside_t_dry_or_normal_method_missing"], []

    method_ids: list[str] = []
    method_id, _ = _validate_method(by_role["oily_t_zone"], "oily_t_zone")
    method_ids.append(method_id)
    for role in outside_roles:
        method_id, _ = _validate_method(by_role[role], role)
        method_ids.append(method_id)
    if len(method_ids) != len(set(method_ids)):
        raise GateInputError("accepted methods must have distinct identities")
    return True, [], sorted(method_ids)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")

    baseline = receipt.get("currentProductBaseline", {})
    _require(baseline.get("commit"), "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285", "merged baseline identity changed")
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product baseline cannot be erased")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("globalSkinTypePreserved"), True, "existing global skin type must be preserved")
    _require(baseline.get("regionalResultsPresent"), True, "existing regional result flow was lost")

    contract = receipt.get("combinationContract", {})
    _require(contract.get("tZone"), ["forehead", "nose", "chin"], "accepted T-zone changed")
    _require(contract.get("outsideTZone"), ["leftCheek", "rightCheek"], "accepted outside-T zone changed")
    _require(contract.get("requiresOilyAllTZoneRegions"), True, "combination requires complete oily T-zone evidence")
    _require(contract.get("requiresDryOrNormalBothCheeks"), True, "combination requires complete outside-T evidence")
    _require(contract.get("wholeFaceCopiedToRegionsAllowed"), False, "whole-face labels cannot become regional truth")
    _require(contract.get("boxesAsRegionalTruthAllowed"), False, "boxes cannot become regional truth")
    _require(contract.get("missingLabelMeansNormal"), False, "missing labels cannot become normal")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model proposals cannot become expert truth")
    _require(contract.get("dryColour"), "#2563EB", "Dry must remain blue")
    _require(contract.get("oilyColour"), "#16A34A", "Oily must remain green")
    _require(contract.get("normalColour"), None, "Normal must remain uncoloured")
    _require(contract.get("unknownColour"), "#D1D5DB", "Unknown must remain light gray")
    _require(contract.get("rednessIndependentOverlapAllowed"), True, "Redness overlap must remain independent")
    _require(contract.get("rednessMeansSensitivity"), False, "Redness cannot become sensitivity")

    source = receipt.get("rejectedBoxSource", {})
    _require(source.get("archiveSHA256"), SOURCE_ARCHIVE, "regional box archive changed")
    _require(source.get("projectId"), EXTERNAL_PROJECT_ID, "regional box project changed")
    _require(source.get("projectImages"), 991, "regional box project inventory changed")
    _require(source.get("version"), 2, "regional box version changed")
    _require(source.get("versionImages"), 1711, "regional box version inventory changed")
    _require(source.get("splits"), {"train": 1442, "valid": 150, "test": 119}, "regional box splits changed")
    _require(source.get("uniqueSourceIds"), 990, "regional source inventory changed")
    _require(source.get("nonEmptySegmentations"), 0, "box source cannot become polygon truth")
    _require(source.get("normalClassPresent"), False, "box source has no normal truth")
    _require(source.get("confirmedCrossSplitGroups"), 1, "known leakage evidence changed")
    _require(source.get("unreviewedSingletonSources"), 986, "identity coverage changed")
    _require(source.get("testEligibleForFinalAcceptance"), False, "leaking exposed test cannot become final evidence")

    model = receipt.get("rejectedBoxModel", {})
    _require(model.get("trainingId"), "a9e8b8a021825191cf5b", "box model training identity changed")
    _require(model.get("modelId"), REJECTED_BOX_MODEL_ID, "box model identity changed")
    _require(model.get("dryTestF1"), 0.215, "dry test metric changed")
    _require(model.get("oilyTestF1"), 0.279, "oily test metric changed")
    _require(model.get("thresholdsLockedBeforeTest"), False, "historical threshold status changed")
    _require(model.get("accepted"), False, "rejected box model cannot become accepted")

    regional = receipt.get("currentRegionalMaskProject", {})
    _require(regional.get("projectId"), REGIONAL_PROJECT_ID, "regional mask project changed")
    _require(regional.get("images"), 337, "regional mask inventory changed")
    _require(regional.get("latestVersion"), 1, "regional mask version changed")
    _require(regional.get("classes"), {"Oily": 1065, "Redness": 571}, "regional mask classes changed")
    _require(regional.get("knownTrainingIds"), ["3485f8c67f957a1b850d", "af287a006e2e428f5ce4"], "regional training identities changed")
    _require(regional.get("dryTruth"), False, "regional source cannot gain Dry truth implicitly")
    _require(regional.get("evaluatedNormalTruth"), False, "missing regional labels cannot become Normal")
    _require(regional.get("combinationTruth"), False, "regional source cannot gain combination truth implicitly")
    _require(regional.get("runningTrainingFound"), False, "running-training state changed")

    preparation = receipt.get("preparation", {})
    training_requirements = {
        "rightsReviewedRegionalSources": "rights_reviewed_regional_sources_missing",
        "expertRegionalPolygonProtocolComplete": "expert_regional_polygon_protocol_missing",
        "evaluatedNormalNegativeTruthComplete": "evaluated_normal_negative_truth_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "groupLockedReplacementSplitVerified": "group_locked_replacement_split_missing",
        "newUntouchedFinalTestReserved": "untouched_final_test_reservation_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
        "oneChangeValidationExperimentSpecified": "one_change_validation_experiment_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
    }
    training_blockers = [reason for field, reason in training_requirements.items() if preparation.get(field) is not True]
    training_allowed = not training_blockers

    candidate = receipt.get("candidate", {})
    registry_complete, registry_blockers, method_ids = _validate_registry(candidate)
    validation = receipt.get("combinationValidation", {})
    test_blockers = list(registry_blockers)
    if registry_complete:
        _require(validation.get("methodIds"), method_ids, "combination validation is not bound to accepted methods")
    for field, reason in (
        ("policyLockedBeforeFinalTest", "combination_policy_not_locked_before_final_test"),
        ("validationPassed", "combination_validation_missing"),
        ("untouchedFinalTestPassed", "combination_untouched_final_test_missing"),
    ):
        if validation.get(field) is not True:
            test_blockers.append(reason)
    test_allowed = registry_complete and not test_blockers

    activation_blockers = list(test_blockers)
    for field, reason in (
        ("physicalCameraPassed", "combination_physical_camera_acceptance_missing"),
        ("lightingSkinTonePoseSlicesPassed", "combination_slice_acceptance_missing"),
        ("workingProductIntegrationPassed", "combination_product_integration_missing"),
        ("coverageOverlapAndUnavailableControlsPassed", "combination_coverage_overlap_unavailable_controls_missing"),
        ("historyWriteReadPassed", "combination_history_write_read_missing"),
    ):
        if validation.get(field) is not True:
            activation_blockers.append(reason)
    if registry_complete:
        _require_evidence_identity(validation.get("acceptanceEvidence"), "combination validation")

    activation_allowed = registry_complete and not activation_blockers
    return {
        "schemaVersion": 2,
        "methodVersion": "skin-type-combination-release-gate-v2",
        "existingGlobalSkinTypeFlowPreserved": True,
        "existingConcreteResultFlowPreserved": True,
        "combinationRuleImplementationReady": True,
        "wholeFaceToRegionalTruthAllowed": False,
        "boxToRegionalTruthAllowed": False,
        "missingLabelAsNormalAllowed": False,
        "knownBoxModelAccepted": False,
        "knownVersionOneRegionalModelsAccepted": False,
        "blindRetrainingAllowed": False,
        "acceptedRegistryPresent": registry_complete,
        "acceptedMethodIds": method_ids,
        "researchTrainingAuthorized": training_allowed,
        "finalTestEvaluationAuthorized": test_allowed,
        "combinationProductActivationAllowed": activation_allowed,
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
