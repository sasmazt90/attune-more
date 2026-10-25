#!/usr/bin/env python3
"""Fail-closed release gate for regional dryness and visible flaking.

The current source pool mixes box-only, processed-image, broad dry-skin and
visible-flaking semantics. This gate preserves those distinctions: boxes are
localization proposals, never blue regional masks; missing labels are never
normal truth; and a generic Dryness label cannot silently become confirmed
facial flaking.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_INPUT_BLOBS = {
    "clean3": "11f300fe126246e65616cc22e7f2a43c0994f0a2",
    "merve": "0519d6e87d2206f0387f5c69784b42b52b960ca5",
    "sourceAcquisition": "632ab9084f71f8ea3019ec923f9ffd7bf2b42bf7",
    "sourceReviewChecks": "7318b1345ba67e606ae6ad4e68fab6d2c662fbdd",
    "skinTypeBoxes": "3c9114c9e7892f6ed03dfffb7eea92ce212bc408",
    "skinTypeGroupResolution": "4aec8f0657b7df8c958711f946baea8fd471bc3c",
}

EXPECTED_ARCHIVES = {
    "clean3": "461c70bb46307273af60334259bec685981e4fb99348fbeb0fc04e6102466fc3",
    "merve": "8fdf070c0cae65fd27ce0046c93393e0ac17e5282bf472097453c756481b831e",
    "drynessV1": "caa1d873d1c98a507ed37a31c42e2f7a0cd543d494e65d0be1f67f15b5b483f4",
    "faceV3": "7c06f1c48d049c1c419d909d488c6642465f0f57958a42eaa62569527ee3094c",
    "skinTypeBoxes": "4af7732298a0f54c3e1bd4aa68ca954429c39a19a832331a4ce542ae365fa228",
}


class GateInputError(ValueError):
    """Raised when a frozen source fact or semantic boundary is contradicted."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("inputBlobs"), EXPECTED_INPUT_BLOBS, "input evidence blobs changed")

    sources = receipt.get("sources", {})
    for name, sha in EXPECTED_ARCHIVES.items():
        _require(sources.get(name, {}).get("archiveSHA256"), sha, f"{name} archive identity changed")

    clean3 = sources["clean3"]
    _require(clean3.get("dryBoxes"), 2117, "Clean3 dry box inventory changed")
    _require(clean3.get("dryPolygons"), 6, "Clean3 dry polygon inventory changed")
    _require(clean3.get("dryPolygonSplits"), {"train": 3, "valid": 2, "test": 1}, "Clean3 dry polygon splits changed")
    _require(clean3.get("crossSplitExactGroups"), 9, "Clean3 leakage evidence changed")

    merve = sources["merve"]
    _require(merve.get("pulBoxes"), 2590, "Merve pul box inventory changed")
    _require(merve.get("pulPolygons"), 0, "Merve boxes must not become polygons")
    _require(merve.get("processedFilenameCount"), 3368, "Merve processed-image inventory changed")
    _require(merve.get("naturalCameraColourCalibrationAllowed"), False, "processed Merve images cannot calibrate natural camera colour")

    dryness = sources["drynessV1"]
    _require(dryness.get("boxOnlyAnnotations"), 6679, "Dryness v1 box inventory changed")
    _require(dryness.get("nonRectangularPolygons"), 61, "Dryness v1 polygon inventory changed")
    _require(dryness.get("rectanglePolygons"), 65, "Dryness v1 rectangle inventory changed")
    _require(dryness.get("geometryIssues"), 14, "Dryness v1 geometry issue inventory changed")
    _require(dryness.get("matchedExistingImages"), 700, "Dryness v1 overlap inventory changed")

    face = sources["faceV3"]
    _require(face.get("dryPolygons"), 48, "FACE v3 dry polygon inventory changed")
    _require(face.get("dryRectanglePolygons"), 24, "FACE v3 rectangle inventory changed")
    _require(face.get("normalPolygons"), 88, "FACE v3 normal polygon inventory changed")

    boxes = sources["skinTypeBoxes"]
    _require(boxes.get("dryBoxes"), 3648, "skin-type dry box inventory changed")
    _require(boxes.get("nonEmptySegmentations"), 0, "skin-type boxes cannot become masks")
    _require(boxes.get("normalClassPresent"), False, "skin-type box source has no normal class")
    _require(boxes.get("missingAnnotationMeansNormal"), False, "missing boxes cannot become normal truth")
    _require(boxes.get("confirmedCrossSplitPersonGroups"), 1, "skin-type leakage evidence changed")
    _require(boxes.get("fullPersonIdentityCoverage"), False, "unreviewed identities cannot become complete")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("blueOverlayMeaning"), "expert-supported-regional-dryness-or-flaking", "blue overlay semantics changed")
    _require(contract.get("boxesAsMasksAllowed"), False, "boxes cannot be rendered as blue masks")
    _require(contract.get("missingLabelMeansNormal"), False, "missing labels cannot mean normal")
    _require(contract.get("genericDrynessEqualsVisibleFlaking"), False, "generic dryness cannot silently become flaking")
    _require(contract.get("modelPredictionIsExpertTruth"), False, "model predictions cannot become expert truth")
    _require(contract.get("unknownColour"), "#D1D5DB", "unknown must remain light gray")
    _require(contract.get("dryColour"), "#2563EB", "dry must remain blue")

    candidate = receipt.get("candidate", {})
    requirements = {
        "rightsReviewedNaturalCameraSources": "rights_reviewed_natural_camera_sources_missing",
        "expertSemanticPolicyComplete": "expert_dryness_flaking_semantic_policy_missing",
        "expertPolygonExtentReviewComplete": "expert_polygon_extent_review_missing",
        "evaluatedNegativeAndNormalRegionsComplete": "evaluated_negative_normal_regions_missing",
        "sourcePersonGroupSplitIndependent": "source_person_group_split_independence_missing",
        "untouchedFinalTestReserved": "untouched_final_test_reservation_missing",
    }
    training_blockers = [reason for field, reason in requirements.items() if candidate.get(field) is not True]
    training_allowed = not training_blockers

    test_blockers = list(training_blockers)
    if candidate.get("validationPassed") is not True:
        test_blockers.append("validation_acceptance_missing")
    test_allowed = not test_blockers

    activation_blockers = list(test_blockers)
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
        "methodVersion": "regional-dryness-release-gate-v1",
        "boxLocalizationResearchAllowed": True,
        "blueMaskFromBoxesAllowed": False,
        "missingLabelAsNormalAllowed": False,
        "processedMerveNaturalColourCalibrationAllowed": False,
        "researchTrainingAuthorized": training_allowed,
        "testEvaluationAuthorized": test_allowed,
        "productActivationAllowed": activation_allowed,
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
