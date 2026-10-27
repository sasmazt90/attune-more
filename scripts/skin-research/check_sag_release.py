#!/usr/bin/env python3
"""Identity-bound release gate for the sag appearance roadmap target.

The merged product already emits a useful lower-face contour/fold appearance
result. That result may remain visible under its narrow semantics. A future
localized learned method is a separate release and must prove immutable data,
model, expert-truth, final-test, camera and integration identities before it
can replace or extend the current result.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SOURCE_ARCHIVE_SHA256 = "8f2bebd6b97bdd3acd06a42798babbd377b7937db362a734586ff5fb3d0ea4a1"
SEMANTICS = "visible-lower-face-contour-fold-appearance-v1"
BASE_METHOD_ID = "analytic-lower-face-contour-fold-v1"
COMPARISON_MODE = "same-person-compatible-capture-only"
WHOLE_FACE_BLOCK = "WHOLE_FACE_ORDINAL_CANNOT_REPLACE_LOCAL_SAG"
EXPECTED_CODE_BLOBS = {
    "services/core-api/skin_product_contract.py": "f152726978bee2eea36b0563d9ac36cbcf330c7b",
    "services/core-api/instant_appearance.py": "fcbf26c8685123177fde7516ca113ee2d87c116f",
    "services/core-api/skin_general.py": "ef5869c6801d3845ec8424e17474b3a3e0fd665a",
    "services/core-api/contour_appearance.py": "748bef67cc59857b2e12e5c48211db973bf29d22",
    "apps/vehicle-app/src/utils/appearanceMeasurements.ts": "45b056e1aff9ce2fb7791995134ad7b5f4a9a57e",
}
EXPECTED_INPUT_BLOBS = {
    "sagAppearanceSemantics": "6a09dea4c2d66c683ea3b9185f0780a7708e6827",
    "ordinalLocalSeparation": "0bd86545886e87c515be73b46775b9b32c7dde66",
    "ordinalSourceAudit": "2a50defa37e8708b656db624e7dbed787b531cb3",
    "currentProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "cameraManifestBuilder": "455f8dcf377c45a5db2cdb637a81ea6f19fd5688",
    "cameraExpertTruthBuilder": "77bb863346c69f6838af091339f715f3f04424fd",
    "cameraPredictionEvaluator": "4ce05c088449adf0d61a801c18c2316787cd926a",
    "cameraLocalizationEvaluator": "a05e1950f58076535bdc1545dbc00d3c357c31f7",
    "cameraBenchmarkReleaseGate": "53c3710166c2e5e43becd36234e10bafe68ac659",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GateInputError(ValueError):
    """Raised when immutable identity or sag semantics are contradicted."""


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
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None or digest == "0" * 64:
        raise GateInputError(f"{label} evidence sha256 missing")


def _validate_candidate(candidate: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any] | None]:
    mode = candidate.get("mode")
    identity_fields = (
        "methodId",
        "datasetReleaseId",
        "projectId",
        "datasetVersion",
        "trainingId",
        "modelId",
        "captureProtocolId",
        "lockedPolicyId",
    )
    if mode == "no-localized-candidate":
        if any(candidate.get(field) is not None for field in identity_fields) or candidate.get("acceptanceEvidence") is not None:
            raise GateInputError("missing localized candidate cannot claim release identities")
        return False, ["accepted_localized_sag_method_missing"], None
    if mode == "whole-face-ordinal":
        raise GateInputError("whole-face ordinal sag is not a localized appearance target")
    if mode != "accepted-localized-sag-method":
        raise GateInputError("unknown sag candidate mode")

    method_id = candidate.get("methodId")
    if not isinstance(method_id, str) or not method_id or method_id == BASE_METHOD_ID:
        raise GateInputError("distinct localized sag method identity missing")
    for field in ("datasetReleaseId", "projectId", "trainingId", "modelId", "captureProtocolId", "lockedPolicyId"):
        value = candidate.get(field)
        if not isinstance(value, str) or not value:
            raise GateInputError(f"localized sag {field} missing")
    version = candidate.get("datasetVersion")
    if not isinstance(version, int) or version < 2:
        raise GateInputError("localized sag requires a group-locked dataset version 2 or later")
    _require_evidence_identity(candidate.get("acceptanceEvidence"), "localized sag candidate")
    _require(candidate.get("accepted"), True, "localized sag candidate is not accepted")
    _require(candidate.get("truthSource"), "adjudicated-localized-expert-polygons", "localized sag requires adjudicated polygon truth")
    _require(candidate.get("outputGeometry"), "polygon", "localized sag output must be polygon geometry")
    _require(candidate.get("thresholdSelectionSplit"), "validation", "sag policy must be selected on validation")
    _require(candidate.get("finalTestUsedForSelection"), False, "final test cannot select the sag policy")
    _require(candidate.get("clinicalClaimsDisabled"), True, "clinical sag claims must remain disabled")
    _require(candidate.get("elasticityClaimsDisabled"), True, "elasticity claims must remain disabled")
    identity = {
        "methodId": method_id,
        "projectId": candidate["projectId"],
        "datasetVersion": version,
        "trainingId": candidate["trainingId"],
        "modelId": candidate["modelId"],
    }
    return True, [], identity


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "input blobs changed")
    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "semantic implementation blobs changed")

    baseline = receipt.get("currentProductBaseline", {})
    _require(baseline.get("commit"), "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285", "merged baseline changed")
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product baseline cannot be erased")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    _require(baseline.get("sagHeadingPresent"), True, "existing sag heading was lost")
    _require(baseline.get("regionalResultsPresent"), True, "existing regional result flow was lost")

    source = receipt.get("sourceAudit", {})
    _require(source.get("archiveSHA256"), SOURCE_ARCHIVE_SHA256, "source archive identity changed")
    _require(source.get("containsSagTarget"), False, "18-criterion source must not be relabelled as sag")
    _require(source.get("nearestButNonEquivalentTarget"), "elasticity", "elasticity boundary changed")
    _require(source.get("personIndependent"), False, "unreviewed source cannot become person-independent")
    _require(source.get("expertProtocolVerified"), False, "unreviewed source cannot gain expert status")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("appearanceSemantics"), SEMANTICS, "appearance semantics changed")
    _require(contract.get("baseMethodId"), BASE_METHOD_ID, "base sag method identity changed")
    _require(contract.get("comparisonMode"), COMPARISON_MODE, "comparison mode changed")
    _require(contract.get("clinicalSeverity"), False, "clinical severity claim is forbidden")
    _require(contract.get("elasticity"), False, "elasticity claim is forbidden")
    _require(contract.get("crossPersonComparison"), False, "cross-person comparison is forbidden")
    _require(contract.get("wholeFaceOrdinalReplacementAllowed"), False, "whole-face ordinal replacement is forbidden")
    _require(contract.get("wholeFaceBlockReason"), WHOLE_FACE_BLOCK, "whole-face block reason changed")
    _require(contract.get("unknownOrUnassessableMeansNormal"), False, "unknown sag cannot become normal")

    current = receipt.get("currentProxy", {})
    _require(current.get("mode"), "visible-contour-fold-proxy", "current sag proxy changed")
    _require(current.get("methodId"), BASE_METHOD_ID, "current sag method identity changed")
    _require(current.get("productSemanticsIntegrated"), True, "current sag result was removed from the product")
    _require(current.get("clinicalClaimsDisabled"), True, "clinical sag claims must remain disabled")
    _require(current.get("elasticityClaimsDisabled"), True, "elasticity claims must remain disabled")
    _require(current.get("acceptedAsLocalizedLearnedMethod"), False, "analytic proxy cannot become a learned localized method")

    preparation = receipt.get("preparation", {})
    preparation_requirements = {
        "sourceRightsAndScopeReviewed": "source_rights_scope_review_missing",
        "localizedExpertPolygonProtocolComplete": "localized_expert_polygon_protocol_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "poseExpressionProtocolComplete": "pose_expression_protocol_missing",
        "samePersonCaptureProtocolComplete": "same_person_capture_protocol_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
        "untouchedFinalTestReserved": "untouched_final_test_missing",
        "physicalCameraHoldoutReserved": "physical_camera_holdout_missing",
    }
    preparation_blockers = [reason for field, reason in preparation_requirements.items() if preparation.get(field) is not True]
    research_training_authorized = not preparation_blockers

    candidate_present, identity_blockers, identity = _validate_candidate(receipt.get("candidate", {}))
    validation = receipt.get("validation", {})
    if candidate_present:
        for field in ("methodId", "projectId", "datasetVersion", "trainingId", "modelId"):
            _require(validation.get(field), identity[field], f"validation is not bound to candidate {field}")
        _require_evidence_identity(validation.get("acceptanceEvidence"), "localized sag validation")

    activation_blockers = list(preparation_blockers) + identity_blockers
    for field, reason in (
        ("validationPerClassPassed", "validation_per_class_acceptance_missing"),
        ("policyLockedBeforeFinalTest", "policy_not_locked_before_final_test"),
        ("untouchedFinalTestPassed", "untouched_final_test_acceptance_missing"),
        ("independentPhysicalCameraPassed", "independent_camera_acceptance_missing"),
        ("poseExpressionRobustnessPassed", "pose_expression_robustness_missing"),
        ("samePersonRepeatabilityPassed", "same_person_repeatability_missing"),
        ("deviceLightingSkinTonePoseSlicesPassed", "sag_camera_slices_missing"),
        ("localizedPolygonGeometryPassed", "localized_polygon_geometry_acceptance_missing"),
        ("workingProductIntegrationPassed", "working_product_integration_replay_missing"),
        ("unknownUnavailableAndHistoryControlsPassed", "sag_unknown_unavailable_history_controls_missing"),
    ):
        if validation.get(field) is not True:
            activation_blockers.append(reason)

    final_test_authorized = bool(
        candidate_present
        and research_training_authorized
        and validation.get("validationPerClassPassed") is True
        and validation.get("policyLockedBeforeFinalTest") is True
        and preparation.get("untouchedFinalTestReserved") is True
    )
    activation = candidate_present and not activation_blockers
    return {
        "schemaVersion": 2,
        "methodVersion": "sag-appearance-release-gate-v2",
        "existingConcreteResultFlowPreserved": True,
        "currentProxyPresentationAllowed": True,
        "currentProxyClaim": "visible lower-face contour/fold appearance only",
        "crossPersonComparisonAllowed": False,
        "clinicalSeverityClaimAllowed": False,
        "elasticityClaimAllowed": False,
        "acceptedLocalizedMethodPresent": candidate_present,
        "acceptedLocalizedMethodIdentity": identity,
        "researchTrainingAuthorized": research_training_authorized,
        "finalTestEvaluationAuthorized": final_test_authorized,
        "localizedSagActivationAllowed": activation,
        "roadmapAccepted": activation,
        "preparationBlockers": preparation_blockers,
        "activationBlockers": activation_blockers,
        "decision": "ready" if activation else "blocked",
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
