#!/usr/bin/env python3
"""Prove that the pinned merged Attune skin baseline already emits results.

This consumes the previously source-bound Attune/Roboflow comparison receipt.
It does not rerun either system and makes no accuracy or camera claim.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CURRENT_PRODUCT_COMMIT = "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285"
CURRENT_ENDPOINT = "/api/local-health/skin"
CURRENT_CRITERIA = (
    "tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags",
)
REGIONS = ("forehead", "rightCheek", "leftCheek", "nose", "chin", "periorbital")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read receipt: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("receipt must be an object")
    return value


def summarize(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("comparisonReady") is not True:
        raise ContractError("source-bound comparison is not ready")
    if receipt.get("sourceCommit") != CURRENT_PRODUCT_COMMIT:
        raise ContractError("receipt is not pinned to the current merged commit")
    if receipt.get("endpoint") != CURRENT_ENDPOINT:
        raise ContractError("receipt endpoint mismatch")
    provenance = receipt.get("attuneExecutionProvenance")
    if (not isinstance(provenance, dict)
            or provenance.get("baseCommit") != CURRENT_PRODUCT_COMMIT
            or provenance.get("productOrModelOrThresholdChanges") is not False):
        raise ContractError("execution provenance changed product/model/threshold behavior")
    if not SHA256_RE.fullmatch(str(provenance.get("localRevisionSHA256", ""))):
        raise ContractError("execution revision is unidentified")
    claims = receipt.get("claims")
    if not isinstance(claims, dict) or any(claims.get(key) is not False for key in (
        "accuracyMeasured", "expertGroundTruth", "realCameraAcceptance",
        "thresholdCalibrationAuthorized", "productionActivationAuthorized",
    )):
        raise ContractError("upstream receipt overclaims its evidence")

    subjects = receipt.get("subjects")
    if not isinstance(subjects, list) or len(subjects) != 6:
        raise ContractError("exactly six source-bound FRONT subjects are required")
    seen: set[str] = set()
    valid_by_criterion = {criterion: 0 for criterion in CURRENT_CRITERIA}
    valid_values = 0
    valid_skin_types = 0
    subjects_with_maps = 0
    subjects_with_contours = 0
    rows = []
    for subject in subjects:
        if not isinstance(subject, dict) or not isinstance(subject.get("subjectKey"), str):
            raise ContractError("malformed subject")
        key = subject["subjectKey"]
        if key in seen:
            raise ContractError("duplicate subject")
        seen.add(key)
        attune = subject.get("attune")
        if not isinstance(attune, dict) or not SHA256_RE.fullmatch(str(attune.get("photoId", ""))):
            raise ContractError(f"missing source identity for {key}")
        criteria = attune.get("criteria")
        if not isinstance(criteria, dict) or set(criteria) != set(CURRENT_CRITERIA):
            raise ContractError(f"criterion inventory mismatch for {key}")
        subject_valid = 0
        for criterion in CURRENT_CRITERIA:
            row = criteria[criterion]
            if not isinstance(row, dict) or row.get("quality") not in ("valid", "insufficient"):
                raise ContractError(f"invalid criterion receipt for {key}/{criterion}")
            value = row.get("value")
            if row["quality"] == "valid":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ContractError(f"valid value missing for {key}/{criterion}")
                subject_valid += 1
                valid_by_criterion[criterion] += 1
            elif value is not None:
                raise ContractError(f"insufficient value must be null for {key}/{criterion}")
        valid_values += subject_valid
        skin_type = attune.get("skinType")
        if not isinstance(skin_type, dict) or skin_type.get("quality") not in ("valid", "insufficient"):
            raise ContractError(f"separate skin type missing for {key}")
        valid_skin_types += int(skin_type["quality"] == "valid")
        if attune.get("regionalInventory") != list(REGIONS):
            raise ContractError(f"regional inventory mismatch for {key}")
        map_count, contour_count = attune.get("mapCount"), attune.get("contourCount")
        if not isinstance(map_count, int) or map_count <= 0:
            raise ContractError(f"no concrete maps for {key}")
        if not isinstance(contour_count, int) or contour_count < 0:
            raise ContractError(f"invalid contour count for {key}")
        subjects_with_maps += 1
        subjects_with_contours += int(contour_count > 0)
        rows.append({
            "subjectKey": key,
            "validCriteria": subject_valid,
            "criterionSlots": len(CURRENT_CRITERIA),
            "skinTypeQuality": skin_type["quality"],
            "mapCount": map_count,
            "contourCount": contour_count,
        })
    if any(count == 0 for count in valid_by_criterion.values()):
        raise ContractError("at least one concrete value is required for every existing criterion")
    return {
        "schemaVersion": 1,
        "status": "verified-concrete-output",
        "productAlreadyProducesConcreteResults": True,
        "currentMergedBaseline": {"commit": CURRENT_PRODUCT_COMMIT, "endpoint": CURRENT_ENDPOINT},
        "subjects": len(subjects),
        "criterionInventory": list(CURRENT_CRITERIA),
        "criterionSlots": len(subjects) * len(CURRENT_CRITERIA),
        "validCriterionValues": valid_values,
        "validByCriterion": valid_by_criterion,
        "separateSkinTypeResults": len(subjects),
        "validSkinTypeResults": valid_skin_types,
        "regionalInventoriesComplete": len(subjects),
        "regions": list(REGIONS),
        "subjectsWithMaps": subjects_with_maps,
        "subjectsWithContours": subjects_with_contours,
        "subjectSummary": rows,
        "claims": {
            "accuracyMeasured": False,
            "expertGroundTruth": False,
            "physicalCameraAcceptance": False,
            "newLearnedModelActivated": False,
            "productionBehaviorChanged": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = summarize(load(args.comparison))
    except ContractError as exc:
        print(f"current-product capability blocked: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
