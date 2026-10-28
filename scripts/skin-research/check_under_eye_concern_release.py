#!/usr/bin/env python3
"""Fail-closed, per-class release gate for dark circles and under-eye bags.

Archive/import/version/training claims are derived from the independently
evaluated grouped-dataset gate.  Mutable booleans in this receipt cannot
promote the stale upload task or the revoked three-group archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_BLOBS = {
    "ungroupedModelReceipt": "6b50743ad404024ab33a6dfb536424de9324e5bb",
    "ungroupedModelVerdict": "437c97d23f6163ecc12c40dc52e4f12d60a840d9",
    "sourcePhotoReview": "80dbf3d4d89ec089a72db54a40b497d836b20fc7",
    "providerGroupedReproduction": "12d3bc76bdc41482828932e401d3df9738a6ace8",
    "providerState": "e56d27cd2e51f3fd06eb116d723b8924e89f8a00",
    "groupedArchiveAuthorization": "24aff0aaa21026523b32ce257ec00725b3b25861",
    "groupedReleaseGate": "213837262f0e729efb102330c81d33e5d5d74782",
    "mergedProductRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "expertReviewQueue": "bf4e5ab3e8d8462894b91133b514e968b238a448",
    "expertReviewDecisionsTemplate": "169b32cf4e83359dbb2ed5a72430999768819be1",
}
REJECTED_UNGROUPED_MODEL_ID = "tolgar-sasmaz/attune-skin-under-eye-pilot-1-rfdetr-seg-small-t1"
EXPECTED_GROUPED_PROJECT_ID = "tolgar-sasmaz/attune-skin-under-eye-grouped-research"
KNOWN_INELIGIBLE_MODEL_IDS = {REJECTED_UNGROUPED_MODEL_ID}
EXPECTED_GROUPED_ARCHIVE_SHA256 = "8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"
REVOKED_GROUPED_ARCHIVE_SHA256 = "41985daef4e2ba6336be5b67ada1c0001cd188a930df6ce29ef67cdf2999fbc8"
EXPECTED_SOURCE_ARCHIVE_SHA256 = "6bff63b27720f2c1a9796b641b60879dbefcfde033b3515658cb91cbd4e32b99"
EXPECTED_GROUPED_GATE_CANONICAL_SHA256 = "b24dda0a3c1ac46c650c111855ecac5ef4a014f67e6ab96d633ccac776d7d127"
EXPECTED_REVIEW_QUEUE_CANONICAL_SHA256 = "8784366d14ac86d6472f87c4f14ae7940e5c9344f2cfceeb30ef24b3f116c38d"


class GateInputError(ValueError):
    """Raised when immutable evidence or class semantics drift."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _validate_review_queue(queue: dict[str, Any] | None) -> bool:
    if queue is None:
        return False
    _require(queue.get("schemaVersion"), "under-eye-expert-review-queue-v1", "expert review queue schema changed")
    _require(_canonical_sha(queue), EXPECTED_REVIEW_QUEUE_CANONICAL_SHA256, "expert review queue content changed")
    dataset = queue.get("dataset", {})
    _require(dataset.get("candidateArchiveSHA256"), EXPECTED_GROUPED_ARCHIVE_SHA256, "expert review archive changed")
    _require(dataset.get("project"), EXPECTED_GROUPED_PROJECT_ID, "expert review project changed")
    _require(dataset.get("reviewSplits"), ["train", "valid"], "expert review splits changed")
    _require(dataset.get("lockedTestImages"), 38, "locked expert-review test inventory changed")
    _require(dataset.get("testAnnotationPayloadRead"), False, "locked test annotations cannot be read for expert review")
    _require(dataset.get("testImageBytesRead"), False, "locked test images cannot be read for expert review")
    _require(dataset.get("testSelectedForReview"), 0, "locked test cannot enter expert review selection")
    _require(dataset.get("personIndependent"), False, "review queue cannot claim person independence")
    _require(queue.get("classes"), ["darkcircle", "eyebag"], "expert review classes changed")
    selection = queue.get("selection", {})
    _require(selection.get("items"), 88, "expert review item inventory changed")
    _require(selection.get("uniqueImages"), 59, "expert review image inventory changed")
    _require(selection.get("candidateGeometryOnly"), True, "source candidates cannot become expert truth")
    policy = queue.get("reviewPolicy", {})
    _require(policy.get("expertReviewerRequired"), True, "expert reviewer requirement changed")
    _require(policy.get("darkCircleAndEyeBagIndependent"), True, "under-eye class review cannot be collapsed")
    _require(policy.get("missingTargetAnnotationIsNegative"), False, "missing labels cannot become negatives")
    _require(policy.get("sourceAnnotationIsExpertTruth"), False, "source proposals cannot become expert truth")
    _require(policy.get("modelPredictionAcceptedAsTruth"), False, "model proposals cannot become expert truth")
    _require(policy.get("boxAcceptedAsPolygon"), False, "boxes cannot become expert polygons")
    _require(policy.get("ambiguousOrUnassessableBecomesNormal"), False, "unknown review items cannot become normal")
    return True


def _validate_expert_protocol(queue: dict[str, Any], protocol: dict[str, Any] | None) -> bool:
    if protocol is None:
        return False
    _require(protocol.get("schemaVersion"), "under-eye-expert-semantic-protocol-v1", "expert protocol schema changed")
    _require(protocol.get("candidateArchiveSHA256"), EXPECTED_GROUPED_ARCHIVE_SHA256, "expert protocol archive changed")
    _require(protocol.get("reviewQueueCanonicalSHA256"), EXPECTED_REVIEW_QUEUE_CANONICAL_SHA256, "expert protocol queue binding changed")
    _require(protocol.get("reviewerRole"), "expert_review", "expert reviewer confirmation is missing")
    _require(protocol.get("semanticInvariants"), queue.get("reviewPolicy"), "expert protocol semantic invariants changed")
    queue_by_class = {
        name: sorted(row["reviewItemId"] for row in queue["items"] if row.get("targetClass") == name)
        for name in ("darkcircle", "eyebag")
    }
    classes = protocol.get("classes")
    if not isinstance(classes, list) or len(classes) != 2:
        raise GateInputError("expert protocol per-class inventory is incomplete")
    seen: set[str] = set()
    for row in classes:
        if not isinstance(row, dict) or row.get("name") not in queue_by_class or row["name"] in seen:
            raise GateInputError("expert protocol per-class record is invalid")
        if not all(row.get(field) is True for field in (
            "expertReviewed", "positiveDefinitionLocked", "maskExtentPolicyLocked",
            "hardNegativePolicyLocked", "ambiguousCasePolicyLocked",
        )):
            raise GateInputError("expert protocol class policy is incomplete")
        _require(sorted(row.get("reviewedItemIds", [])), queue_by_class[row["name"]], "expert protocol does not cover the frozen queue")
        seen.add(row["name"])
    _require(seen, {"darkcircle", "eyebag"}, "expert protocol classes are incomplete")
    decision = protocol.get("decision", {})
    _require(decision.get("expertReviewComplete"), True, "expert review is incomplete")
    _require(decision.get("semanticProtocolReady"), True, "expert semantic protocol is incomplete")
    _require(decision.get("personIndependentSplitReady"), False, "semantic review cannot claim person independence")
    _require(decision.get("trainingAuthorized"), False, "semantic review alone cannot authorize training")
    _require(decision.get("testEvaluationAuthorized"), False, "semantic review alone cannot authorize final-test use")
    _require(decision.get("activationAllowed"), False, "semantic review alone cannot authorize activation")
    return True


def _validate_grouped_release_gate(gate: dict[str, Any] | None) -> dict[str, bool]:
    if gate is None:
        raise GateInputError("grouped release gate evidence is required")
    _require(
        _canonical_sha(gate),
        EXPECTED_GROUPED_GATE_CANONICAL_SHA256,
        "grouped release gate content changed",
    )
    _require(gate.get("schemaVersion"), 1, "grouped release gate schema changed")
    _require(
        gate.get("methodVersion"),
        "under-eye-grouped-release-gate-v3",
        "grouped release gate method changed",
    )
    _require(
        gate.get("sourceArchiveSHA256"),
        EXPECTED_SOURCE_ARCHIVE_SHA256,
        "grouped release source archive changed",
    )
    _require(
        gate.get("revokedArchiveSHA256"),
        REVOKED_GROUPED_ARCHIVE_SHA256,
        "revoked grouped archive boundary changed",
    )
    _require(
        gate.get("authorizedArchiveSHA256"),
        EXPECTED_GROUPED_ARCHIVE_SHA256,
        "authorized grouped archive changed",
    )
    _require(
        gate.get("candidateArchiveSHA256"),
        EXPECTED_GROUPED_ARCHIVE_SHA256,
        "candidate grouped archive changed",
    )
    _require(gate.get("exactArchiveAuthorized"), True, "exact grouped archive is not authorized")
    _require(gate.get("existingUploadTaskReusable"), False, "stale grouped upload task cannot be reused")
    _require(gate.get("freshDirectUploadRequired"), True, "fresh direct grouped upload requirement changed")
    _require(gate.get("testEvaluationAuthorized"), False, "grouped dataset gate cannot authorize final-test use")
    _require(gate.get("productActivationAllowed"), False, "grouped dataset gate cannot activate product output")
    _require(gate.get("roadmapAccepted"), False, "grouped dataset gate cannot accept the roadmap")
    flags = {
        "archive": gate.get("exactArchiveAuthorized") is True,
        "import": gate.get("versionGenerationAuthorized") is True,
        "version": gate.get("researchTrainingAuthorized") is True,
        "training": gate.get("researchTrainingAuthorized") is True,
    }
    if flags["version"] and not flags["import"]:
        raise GateInputError("grouped training authorization requires a verified import and version")
    return flags


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


def _validate_candidate_identity(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    mode = candidate.get("mode")
    if mode not in {"not-trained", "new-model"}:
        raise GateInputError("unknown under-eye candidate mode")
    project_id = candidate.get("projectId")
    model_id = candidate.get("modelId")
    training_id = candidate.get("trainingId")
    version = candidate.get("datasetVersion")
    if mode == "not-trained":
        if project_id is not None or model_id is not None or training_id is not None or version is not None:
            raise GateInputError("not-trained candidate cannot claim a model identity")
        return False, ["distinct_grouped_candidate_model_missing"]
    if model_id in KNOWN_INELIGIBLE_MODEL_IDS:
        raise GateInputError("known ungrouped model cannot be relabelled as a grouped candidate")
    if project_id != EXPECTED_GROUPED_PROJECT_ID:
        raise GateInputError("candidate must belong to the frozen grouped research project")
    blockers: list[str] = []
    if not isinstance(model_id, str) or not model_id.startswith(f"{EXPECTED_GROUPED_PROJECT_ID}-"):
        blockers.append("distinct_grouped_candidate_model_missing")
    if not isinstance(training_id, str) or not training_id:
        blockers.append("distinct_grouped_candidate_training_missing")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        blockers.append("authorized_grouped_candidate_version_missing")
    return not blockers, blockers


def evaluate_release(
    receipt: dict[str, Any],
    grouped_release_gate: dict[str, Any] | None = None,
    review_queue: dict[str, Any] | None = None,
    expert_protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_BLOBS, "input blobs changed")
    grouped_flags = _validate_grouped_release_gate(grouped_release_gate)

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
    _require(source.get("groupedSplits"), {"train": 284, "valid": 77, "test": 38}, "grouped splits changed")
    _require(source.get("reviewedCrossSplitGroups"), 4, "reviewed cross-split groups changed")
    _require(source.get("movedImages"), 5, "grouped moved-image inventory changed")
    _require(source.get("imageBytesChanged"), 0, "grouped image bytes changed")
    _require(source.get("annotationPayloadsChanged"), 0, "grouped annotations changed")
    _require(source.get("personIndependent"), False, "partial grouping cannot become person-independent")
    _require(source.get("groupedProjectImages"), 0, "empty grouped project state changed")
    _require(source.get("uploadStatus"), "created", "grouped upload status changed")
    _require(source.get("uploadProgress"), None, "grouped upload progress changed")
    _require(source.get("candidateArchiveMatchesAuthorizedArchive"), True, "archive authorization boundary changed")
    _require(source.get("existingUploadTaskReusable"), False, "stale upload task cannot be reused")
    _require(source.get("freshDirectUploadRequired"), True, "fresh direct upload requirement changed")

    model = receipt.get("ungroupedModel", {})
    _require(model.get("trainingId"), "d194569acd3ebe7cf8b7", "model training identity changed")
    _require(model.get("modelId"), REJECTED_UNGROUPED_MODEL_ID, "model identity changed")
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

    queue_verified = _validate_review_queue(review_queue)
    protocol_verified = queue_verified and _validate_expert_protocol(review_queue, expert_protocol)

    candidate = receipt.get("candidate", {})
    for field, grouped_field in (
        ("exactArchiveAuthorized", "archive"),
        ("groupedImportVerified", "import"),
        ("augmentationFreeGroupedVersionVerified", "version"),
    ):
        if candidate.get(field) is not grouped_flags[grouped_field]:
            raise GateInputError(f"{field} claim is not bound to grouped release gate evidence")
    if candidate.get("expertPerClassMaskNegativeAndAmbiguityProtocolComplete") is not protocol_verified:
        raise GateInputError("expert protocol claim is not bound to the frozen queue and protocol")
    shared_requirements = {
        "rightsReviewed": "rights_review_missing",
        "personIndependentGroupedSplitLocked": "person_independent_grouped_split_missing",
        "newUntouchedFinalTestReserved": "new_untouched_final_test_missing",
        "independentCameraHoldoutReserved": "independent_camera_holdout_missing",
        "qualityPolicyLockedBeforeValidation": "quality_policy_not_locked_before_validation",
    }
    shared_training_blockers = [reason for field, reason in shared_requirements.items() if candidate.get(field) is not True]
    if not grouped_flags["archive"]:
        shared_training_blockers.append("exact_archive_authorization_missing")
    if not grouped_flags["import"]:
        shared_training_blockers.append("grouped_import_verification_missing")
    if not grouped_flags["version"]:
        shared_training_blockers.append("grouped_version_verification_missing")
    if not grouped_flags["training"]:
        shared_training_blockers.append("grouped_release_gate_training_authorization_missing")
    if not queue_verified:
        shared_training_blockers.append("expert_review_queue_verification_missing")
    if not protocol_verified:
        shared_training_blockers.append("expert_per_class_protocol_missing")
    distinct_candidate, identity_blockers = _validate_candidate_identity(candidate)
    shared_test_blockers = list(shared_training_blockers) + identity_blockers
    if candidate.get("trainedFromAuthorizedGroupedArchive") is not True:
        shared_test_blockers.append("candidate_not_trained_from_authorized_grouped_archive")
    if candidate.get("candidateChangeMatchesPreRegisteredExperiment") is not True:
        shared_test_blockers.append("candidate_change_not_pre_registered")
    if candidate.get("thresholdsLockedBeforeFinalTest") is not True:
        shared_test_blockers.append("thresholds_not_locked_before_final_test")
    classes = candidate.get("classes")
    if not isinstance(classes, dict) or set(classes) != {"darkcircle", "eyebag"}:
        raise GateInputError("both per-class candidate records are required")
    class_decisions = {
        class_name: _class_decision(shared_test_blockers, candidate, class_name)
        for class_name in ("darkcircle", "eyebag")
    }
    roadmap_accepted = distinct_candidate and all(item["productActivationAllowed"] for item in class_decisions.values())
    return {
        "schemaVersion": 4,
        "methodVersion": "under-eye-per-class-release-gate-v4",
        "existingConcreteResultFlowPreserved": True,
        "classesRemainSeparate": True,
        "ungroupedModelAccepted": False,
        "distinctGroupedCandidatePresent": distinct_candidate,
        "researchTrainingAuthorized": not shared_training_blockers,
        "expertReviewQueueVerified": queue_verified,
        "expertSemanticProtocolVerified": protocol_verified,
        "groupedReleaseGateVerified": True,
        "blindRetrainingAllowed": False,
        "classDecisions": class_decisions,
        "roadmapAccepted": roadmap_accepted,
        "sharedTrainingBlockers": shared_training_blockers,
        "decision": "ready" if roadmap_accepted else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--grouped-release-gate", type=Path, required=True)
    parser.add_argument("--review-queue", type=Path, required=True)
    parser.add_argument("--expert-protocol", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(
        json.loads(args.receipt.read_text(encoding="utf-8")),
        json.loads(args.grouped_release_gate.read_text(encoding="utf-8")),
        json.loads(args.review_queue.read_text(encoding="utf-8")),
        json.loads(args.expert_protocol.read_text(encoding="utf-8")) if args.expert_protocol else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

