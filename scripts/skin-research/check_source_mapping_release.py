#!/usr/bin/env python3
"""Fail-closed release gate for source-label mappings and geometry evidence.

The selected/expanded source maps are research routing hints.  This gate
prevents them from silently becoming expert labels, pixel masks, negatives,
product Pigmentation truth or a released train/validation/test corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


class GateInputError(ValueError):
    """Raised when immutable evidence or safety semantics change."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


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


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "source evidence blobs changed")

    contract = receipt.get("mappingContract", {})
    _require(contract.get("mappingIsCandidateSemanticRoutingOnly"), True, "mapping cannot become expert truth")
    _require(contract.get("boxesArePixelTruth"), False, "boxes cannot become pixel truth")
    _require(contract.get("rectanglePolygonsArePixelTruth"), False, "rectangle-polygons cannot become pixel truth")
    _require(contract.get("missingLabelMeansNegativeOrNormal"), False, "missing labels cannot become negative or normal")
    _require(contract.get("modelPredictionMeansExpertTruth"), False, "predictions cannot become expert truth")
    _require(contract.get("toneMayBecomeProductPigmentation"), False, "tone cannot become product Pigmentation")
    _require(contract.get("pulMayBecomeBroadRegionalDryness"), False, "pul cannot become broad regional dryness")
    _require(contract.get("wholeFaceClassReplicationAllowed"), False, "whole-face labels cannot become regional truth")
    _require(contract.get("unknownCountsAsNormal"), False, "unknown cannot count as normal")

    facts = receipt.get("auditFacts", {})
    review = facts.get("sourceReview", {})
    _require(review.get("selectedPairsVerified"), 120, "selected source-pair audit changed")
    _require(review.get("imageByteEquality"), True, "selected source bytes are not verified")
    _require(review.get("annotationStructuralEquality"), True, "selected source annotations are not verified")
    _require(review.get("sourceTrainOnly"), True, "selected source review test lock changed")
    _require(review.get("expertReviewed"), False, "assistant review cannot become expert review")
    _require(review.get("productAccepted"), False, "source review cannot become product acceptance")

    clean3 = facts.get("clean3", {})
    _require(clean3.get("actualImages"), 3240, "Clean3 export count changed")
    _require(clean3.get("apiImages"), 3261, "Clean3 API count changed")
    _require(clean3.get("apiExportCountDiscrepancyUnresolved"), True, "Clean3 discrepancy was erased")
    _require(clean3.get("geometry"), EXPECTED_CLEAN3_GEOMETRY, "Clean3 geometry inventory changed")
    _require(clean3.get("crossSplitExactGroups"), 9, "Clean3 cross-split exact groups changed")

    _require(facts.get("acquisition"), EXPECTED_ACQUISITION, "acquisition geometry/leakage audit changed")
    under_eye = facts.get("underEye", {})
    _require(under_eye.get("images"), 399, "under-eye image count changed")
    _require(under_eye.get("darkcirclePolygons"), 382, "under-eye darkcircle count changed")
    _require(under_eye.get("eyebagPolygons"), 487, "under-eye eyebag count changed")
    _require(under_eye.get("reviewedCrossSplitGroups"), 3, "under-eye group review changed")
    _require(under_eye.get("sourcePersonCoverageComplete"), False, "partial under-eye grouping cannot become complete")

    excluded = facts.get("excludedArchives", {})
    _require(excluded.get("requiredPreservedCount"), 4, "four excluded archives must remain preserved")
    _require(excluded.get("mappingScriptListedCount"), 3, "mapping-script archive inventory changed")
    _require(excluded.get("fullInventoryReconciled"), False, "excluded archive inventory cannot be inferred complete")
    _require(excluded.get("mutationPerformed"), False, "excluded archives must not be mutated")

    decisions = receipt.get("targetDecisions", {})
    _require(tuple(decisions), TARGETS, "target decision inventory changed")
    for target, decision in decisions.items():
        _require(decision.get("researchRoutingAllowed"), True, f"{target}: research routing changed")
        _require(decision.get("expertTruthAuthorized"), False, f"{target}: expert truth cannot be inferred")
        _require(decision.get("trainingDataReleaseAuthorized"), False, f"{target}: training release cannot be inferred")
        _require(decision.get("productTruthAuthorized"), False, f"{target}: product truth cannot be inferred")

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
    released = not blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "source-mapping-release-gate-v1",
        "sourceMappingsAreExpertTruth": False,
        "boxToMaskConversionAllowed": False,
        "missingLabelToNormalAllowed": False,
        "toneToProductPigmentationAllowed": False,
        "researchRoutingAllowed": True,
        "trainingDataReleaseAuthorized": released,
        "productTruthAuthorized": released,
        "blockers": blockers,
        "decision": "ready" if released else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="optional checked-out repository root; verifies every pinned Git blob on disk",
    )
    args = parser.parse_args()
    if args.repo_root is not None:
        validate_repo_inputs(args.repo_root)
    result = evaluate_release(json.loads(args.receipt.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
