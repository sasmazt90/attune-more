#!/usr/bin/env python3
"""Fail-closed task-00 gate for source mappings and release evidence.

The selected/expanded mapping tables are research routing hints. A release
requires eight immutable, SHA-256-bound artifacts with a shared release
identity; receipt booleans alone can never turn mappings into expert truth,
pixel masks, negatives, product Pigmentation or a frozen dataset release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_RECEIPT_SCHEMA = 2
EXPECTED_INPUT_BLOBS = {
    "scripts/skin-research/selected_sources.py": "cfd24d16f86f3437dd3b1d925053cc7ebe543399",
    "scripts/skin-research/expanded_sources.py": "8771f1aed674f1c7f554dcb6fa539b20c7696f38",
    "docs/skin/evidence/source-review-checks-20261023-v1.json": "6feddd434914c1f6d0b1cccf3cb0221ef35213f7",
    "docs/skin/evidence/source-visual-inspection-20261023-v1.json": "641ace42509141e8a70cd675130179376fe98070",
    "docs/skin/evidence/source-acquisition-summary-20261023-v1.json": "18370bbbb536dc2562726ae0b686a66bc741a331",
    "docs/skin/evidence/clean3-source-summary-20261023-v1.json": "ddf96001096c606ad51e0792fa3496132f3d1eb1",
    "docs/skin/evidence/regional-mask-source-group-audit-20261025-v1.json": "29314becfb5fd8c6f77e389036e2afa152aa56cb",
    "docs/skin/evidence/under-eye-provider-v2-grouped-reproduction-20261025-v1.json": "b835168ebee70699236c4748fa8fc39e4c5168ba",
}
EXPECTED_CLEAN3_GEOMETRY = {
    "Dry-Skin": {"box": 2117, "validPolygon": 6},
    "Oily-Skin": {"box": 889, "validPolygon": 10},
    "Skin-Redness": {"box": 123, "validPolygon": 0},
}
EXPECTED_ACQUISITION = {
    "images": 4226,
    "crossSplitExactGroups": 57,
    "crossSplitPerceptualCandidatePairs": 1301,
    "crossSplitFilenameCandidateGroups": 286,
    "geometryIssueCount": 57,
    "face": {"images": 408, "geometryIssueCount": 39},
    "redness": {"images": 1746, "validPolygon": 2150, "rectanglePolygon": 1067},
}
TARGETS = ("acne", "oil", "dry", "redness", "tone", "lines", "dark", "bags", "type", "sag")
EXPECTED_ARTIFACT_METHODS = {
    "excludedArchiveInventory": "excluded-archive-inventory-reconciliation-v1",
    "archiveHashRegistry": "source-archive-hash-registry-v1",
    "rightsReview": "source-rights-review-v1",
    "expertSemantics": "skin-source-expert-semantics-v1",
    "geometryAudit": "skin-source-geometry-audit-v1",
    "sourcePersonGrouping": "skin-source-person-grouping-v1",
    "lockedSplit": "skin-source-group-locked-split-v1",
    "cameraReservation": "skin-source-independent-camera-reservation-v1",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")


class GateInputError(ValueError):
    """Raised when immutable evidence or safety semantics change."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _positive_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GateInputError(message)
    return value


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise GateInputError(f"{field} must be an opaque reference")
    return value


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def validate_repo_inputs(repo_root: Path) -> None:
    for relative, expected in EXPECTED_INPUT_BLOBS.items():
        path = repo_root / relative
        if not path.is_file():
            raise GateInputError(f"pinned input missing: {relative}")
        _require(git_blob_sha1(path), expected, f"pinned input changed: {relative}")


def _load_artifact(identity: Any, label: str, evidence_root: Path) -> dict[str, Any]:
    if not isinstance(identity, dict) or set(identity) != {"path", "sha256"}:
        raise GateInputError(f"{label} evidence identity is incomplete")
    path = identity.get("path")
    digest = identity.get("sha256")
    if not isinstance(path, str):
        raise GateInputError(f"{label} evidence path is invalid")
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or not path.startswith("docs/skin/evidence/")
        or not pure.name.endswith(".json")
    ):
        raise GateInputError(f"{label} evidence path is outside the source evidence registry")
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None or digest == "0" * 64:
        raise GateInputError(f"{label} evidence sha256 is invalid")
    file_path = evidence_root / path
    if not file_path.is_file():
        raise GateInputError(f"{label} evidence file is missing")
    raw = file_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise GateInputError(f"{label} evidence digest mismatch")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateInputError(f"{label} evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GateInputError(f"{label} evidence must be a JSON object")
    return payload


def _validate_artifacts(candidate: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    registry = candidate.get("artifacts")
    if not isinstance(registry, dict) or set(registry) != set(EXPECTED_ARTIFACT_METHODS):
        raise GateInputError("source release artifact registry is incomplete")
    artifacts = {
        name: _load_artifact(registry[name], name, evidence_root)
        for name in EXPECTED_ARTIFACT_METHODS
    }
    for name, method in EXPECTED_ARTIFACT_METHODS.items():
        _require(artifacts[name].get("methodVersion"), method, f"{name} method identity changed")

    release_ref = _opaque(candidate.get("releaseRef"), "releaseRef")
    for name, payload in artifacts.items():
        _require(payload.get("releaseRef"), release_ref, f"{name} release identity changed")

    excluded = artifacts["excludedArchiveInventory"]
    for field, expected in {
        "requiredArchiveCount": 4,
        "inventoryReconciled": True,
        "preservationPolicyEnforced": True,
        "containsPublicNamesOrPaths": False,
        "excludedArchivesAccessed": False,
        "mutationPerformed": False,
        "uploadPerformed": False,
        "trainingUsePerformed": False,
        "productUsePerformed": False,
        "sourceReleaseContributionAllowed": False,
    }.items():
        _require(excluded.get(field), expected, f"excluded archive inventory {field} changed")

    hashes = artifacts["archiveHashRegistry"]
    registry_ref = _opaque(hashes.get("sourceRegistryRef"), "sourceRegistryRef")
    archive_count = _positive_int(hashes.get("selectedArchiveCount"), "selected archive registry is empty")
    for field, expected in {
        "allArchiveHashesVerified": True,
        "containsArchiveNamesOrPaths": False,
        "excludedArchivesPresent": False,
        "excludedArchiveHashesRecomputed": False,
    }.items():
        _require(hashes.get(field), expected, f"archive hash registry {field} changed")

    rights = artifacts["rightsReview"]
    _require(rights.get("sourceRegistryRef"), registry_ref, "rights review registry identity changed")
    _require(rights.get("selectedArchiveCount"), archive_count, "rights review archive count changed")
    for field, expected in {
        "allSelectedArchivesReviewed": True,
        "allIndividualImageRightsReviewed": True,
        "unresolvedRightsCount": 0,
        "excludedArchivesAccessed": False,
    }.items():
        _require(rights.get(field), expected, f"rights review {field} changed")

    semantics = artifacts["expertSemantics"]
    _require(semantics.get("sourceRegistryRef"), registry_ref, "expert semantics registry identity changed")
    _require(semantics.get("targets"), list(TARGETS), "expert semantic target inventory changed")
    for field, expected in {
        "perClassExpertSemanticsLocked": True,
        "mappingUsedAsExpertTruth": False,
        "boxesUsedAsPixelTruth": False,
        "rectanglePolygonsUsedAsPixelTruth": False,
        "missingLabelMeansNegativeOrNormal": False,
        "toneUsedAsLocalizedPigmentation": False,
        "pulUsedAsBroadRegionalDryness": False,
        "wholeFaceClassReplicatedIntoRegions": False,
        "modelPredictionUsedAsExpertTruth": False,
    }.items():
        _require(semantics.get(field), expected, f"expert semantics {field} changed")

    geometry = artifacts["geometryAudit"]
    _require(geometry.get("sourceRegistryRef"), registry_ref, "geometry audit registry identity changed")
    _require(geometry.get("selectedArchiveCount"), archive_count, "geometry audit archive count changed")
    for field, expected in {
        "allGeometryAudited": True,
        "invalidGeometryIssueCount": 0,
        "boxesAcceptedAsPixelTruth": False,
        "rectanglePolygonsAcceptedAsPixelTruth": False,
        "modelGeometryAcceptedAsExpertTruth": False,
    }.items():
        _require(geometry.get(field), expected, f"geometry audit {field} changed")

    grouping = artifacts["sourcePersonGrouping"]
    _require(grouping.get("sourceRegistryRef"), registry_ref, "grouping registry identity changed")
    _positive_int(grouping.get("recordCount"), "source/person grouping is empty")
    for field, expected in {
        "sourcePersonGroupingComplete": True,
        "crossSplitGroupCount": 0,
        "singletonAssignmentAcceptedAsIdentity": False,
        "similarityCandidateAcceptedAsIdentity": False,
    }.items():
        _require(grouping.get(field), expected, f"source/person grouping {field} changed")

    split = artifacts["lockedSplit"]
    split_ref = _opaque(split.get("splitRef"), "splitRef")
    _require(split.get("sourceRegistryRef"), registry_ref, "locked split registry identity changed")
    counts = split.get("counts")
    if not isinstance(counts, dict) or set(counts) != {"train", "validation", "final_test"}:
        raise GateInputError("locked split counts are incomplete")
    for name, value in counts.items():
        _positive_int(value, f"locked split {name} is empty")
    for field, expected in {
        "groupLocked": True,
        "allRecordsAssignedExactlyOnce": True,
        "crossSplitGroupCount": 0,
        "finalTestUsedForSelection": False,
        "finalTestUsedForThresholds": False,
        "cameraSubjectsIncluded": False,
    }.items():
        _require(split.get(field), expected, f"locked split {field} changed")

    camera = artifacts["cameraReservation"]
    camera_ref = _opaque(camera.get("cameraReservationRef"), "cameraReservationRef")
    _require(camera.get("sourceRegistryRef"), registry_ref, "camera reservation registry identity changed")
    for field, expected in {
        "reserved": True,
        "sourceType": "physical-camera",
        "generated": False,
        "consentRequired": True,
        "subjectIndependentFromSourceRegistry": True,
        "usedForTrainingValidationOrThresholdSelection": False,
    }.items():
        _require(camera.get(field), expected, f"camera reservation {field} changed")

    for field, expected in {
        "sourceRegistryRef": registry_ref,
        "splitRef": split_ref,
        "cameraReservationRef": camera_ref,
    }.items():
        _require(candidate.get(field), expected, f"source release candidate {field} changed")
    return {
        "releaseRef": release_ref,
        "sourceRegistryRef": registry_ref,
        "splitRef": split_ref,
        "cameraReservationRef": camera_ref,
        "selectedArchiveCount": archive_count,
        "artifactSha256": {name: registry[name]["sha256"] for name in EXPECTED_ARTIFACT_METHODS},
    }


def _validate_current_facts(receipt: dict[str, Any]) -> None:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "source evidence blobs changed")
    contract = receipt.get("mappingContract", {})
    for field, expected, message in (
        ("mappingIsCandidateSemanticRoutingOnly", True, "mapping cannot become expert truth"),
        ("boxesArePixelTruth", False, "boxes cannot become pixel truth"),
        ("rectanglePolygonsArePixelTruth", False, "rectangle-polygons cannot become pixel truth"),
        ("missingLabelMeansNegativeOrNormal", False, "missing labels cannot become negative or normal"),
        ("modelPredictionMeansExpertTruth", False, "predictions cannot become expert truth"),
        ("toneMayBecomeProductPigmentation", False, "tone cannot become product Pigmentation"),
        ("pulMayBecomeBroadRegionalDryness", False, "pul cannot become broad regional dryness"),
        ("wholeFaceClassReplicationAllowed", False, "whole-face labels cannot become regional truth"),
        ("unknownCountsAsNormal", False, "unknown cannot count as normal"),
    ):
        _require(contract.get(field), expected, message)
    facts = receipt.get("auditFacts", {})
    review = facts.get("sourceReview", {})
    for field, expected in {
        "selectedPairsVerified": 120, "imageByteEquality": True,
        "annotationStructuralEquality": True, "sourceTrainOnly": True,
        "expertReviewed": False, "productAccepted": False,
    }.items():
        _require(review.get(field), expected, f"source review {field} changed")
    clean3 = facts.get("clean3", {})
    _require(clean3.get("actualImages"), 3240, "Clean3 export count changed")
    _require(clean3.get("apiImages"), 3261, "Clean3 API count changed")
    _require(clean3.get("apiExportCountDiscrepancyUnresolved"), True, "Clean3 discrepancy was erased")
    _require(clean3.get("geometry"), EXPECTED_CLEAN3_GEOMETRY, "Clean3 geometry inventory changed")
    _require(clean3.get("crossSplitExactGroups"), 9, "Clean3 cross-split exact groups changed")
    _require(facts.get("acquisition"), EXPECTED_ACQUISITION, "acquisition geometry/leakage audit changed")
    under_eye = facts.get("underEye", {})
    for field, expected in {
        "images": 399, "darkcirclePolygons": 382, "eyebagPolygons": 487,
        "reviewedCrossSplitGroups": 3, "sourcePersonCoverageComplete": False,
    }.items():
        _require(under_eye.get(field), expected, f"under-eye {field} changed")
    excluded = facts.get("excludedArchives", {})
    for field, expected in {
        "requiredPreservedCount": 4, "mappingScriptListedCount": 3,
        "fullInventoryReconciled": False, "mutationPerformed": False,
    }.items():
        _require(excluded.get(field), expected, f"excluded archive fact {field} changed")
    decisions = receipt.get("targetDecisions", {})
    _require(tuple(decisions), TARGETS, "target decision inventory changed")
    for target, decision in decisions.items():
        for field, expected in {
            "researchRoutingAllowed": True, "expertTruthAuthorized": False,
            "trainingDataReleaseAuthorized": False, "productTruthAuthorized": False,
        }.items():
            _require(decision.get(field), expected, f"{target}: {field} changed")


def evaluate_release(receipt: dict[str, Any], evidence_root: Path = ROOT) -> dict[str, Any]:
    _require(receipt.get("schemaVersion"), EXPECTED_RECEIPT_SCHEMA, "source receipt schema changed")
    _require(receipt.get("methodVersion"), "source-mapping-release-receipt-v2", "source receipt method changed")
    _validate_current_facts(receipt)
    candidate = receipt.get("acceptanceCandidate", {})
    requirements = {
        "allFourExcludedArchivesReconciled": "four_excluded_archive_inventory_not_reconciled",
        "allArchiveHashesVerified": "all_archive_hashes_not_verified",
        "allRightsReviewed": "rights_review_incomplete",
        "perClassExpertSemanticsLocked": "expert_semantics_incomplete",
        "allGeometryAudited": "geometry_audit_incomplete",
        "sourcePersonGroupingComplete": "source_person_grouping_incomplete",
        "lockedTrainValidationFinalTestSplit": "locked_group_split_missing",
        "independentCameraReserved": "independent_camera_holdout_missing",
    }
    blockers = [reason for field, reason in requirements.items() if candidate.get(field) is not True]
    registry = candidate.get("artifacts")
    if not isinstance(registry, dict) or set(registry) != set(EXPECTED_ARTIFACT_METHODS):
        blockers.append("source_release_artifact_registry_missing")
        identity = None
    else:
        missing = [name for name in EXPECTED_ARTIFACT_METHODS if not isinstance(registry.get(name), dict)]
        blockers.extend(f"{name}_evidence_missing" for name in missing)
        identity = None if missing else _validate_artifacts(candidate, evidence_root)
    released = not blockers and identity is not None
    return {
        "schemaVersion": 2,
        "methodVersion": "source-mapping-release-gate-v2",
        "sourceMappingsAreExpertTruth": False,
        "boxToMaskConversionAllowed": False,
        "missingLabelToNormalAllowed": False,
        "toneToProductPigmentationAllowed": False,
        "researchRoutingAllowed": True,
        "evidenceRegistryRequired": True,
        "evidenceRegistryComplete": identity is not None,
        "sourceReleaseIdentity": identity,
        "trainingDataReleaseAuthorized": released,
        "productTruthAuthorized": released,
        "blockers": blockers,
        "decision": "ready" if released else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.repo_root is not None:
        validate_repo_inputs(args.repo_root)
    result = evaluate_release(json.loads(args.receipt.read_text(encoding="utf-8")), args.evidence_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
