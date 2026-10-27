#!/usr/bin/env python3
"""Build adjudicated expert truth for an independent camera manifest.

This tool never reads image bytes and never accepts model output as truth.  It
requires two independent human reviews for every activated class on every
capture.  Missing, unknown, unassessable and explicitly evaluated negative
remain distinct states.  Discordant reviews require a third expert decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ALLOWED_CLASSES = {
    "pimple", "post_acne", "pigmentation", "oily", "dry", "normal",
    "redness", "tone_unevenness", "darkcircle", "eyebag", "crows_feet", "sag",
}
DECISIONS = {"positive", "evaluated_negative", "unknown", "unassessable"}
GEOMETRY_REQUIRED_FOR_POSITIVE = ALLOWED_CLASSES - {"tone_unevenness"}
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "filepath", "path", "uri", "url", "email", "phone",
    "address", "rawimage", "imagebytes", "bytes", "prediction", "predictions",
    "modeloutput", "modelscore", "confidence",
}


class ExpertTruthError(ValueError):
    """Raised when private data, incomplete review or semantic drift is found."""


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise ExpertTruthError(f"{field} must be an opaque reference")
    return value


def _assert_no_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in FORBIDDEN_KEYS:
                raise ExpertTruthError(f"forbidden private/model field at {location}.{key}")
            _assert_no_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, f"{location}[{index}]")


def _polygon_area(points: list[list[float]]) -> float:
    return abs(sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )) / 2


def _validate_polygons(value: Any, required: bool) -> list[list[list[float]]]:
    if not isinstance(value, list):
        raise ExpertTruthError("polygons must be an array")
    if required and not value:
        raise ExpertTruthError("positive localized truth requires polygon geometry")
    if not required and value:
        raise ExpertTruthError("non-positive truth cannot carry polygon geometry")
    normalized: list[list[list[float]]] = []
    for polygon in value:
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ExpertTruthError("polygon requires at least three points")
        clean: list[list[float]] = []
        for point in polygon:
            if (
                not isinstance(point, list) or len(point) != 2
                or isinstance(point[0], bool) or isinstance(point[1], bool)
                or not isinstance(point[0], (int, float))
                or not isinstance(point[1], (int, float))
            ):
                raise ExpertTruthError("polygon points must be numeric [x, y]")
            x, y = float(point[0]), float(point[1])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ExpertTruthError("polygon coordinates must be normalized to [0, 1]")
            clean.append([x, y])
        if _polygon_area(clean) <= 0:
            raise ExpertTruthError("polygon must have non-zero area")
        normalized.append(clean)
    return normalized


def _normalize_decision(record: dict[str, Any], *, adjudication: bool = False) -> dict[str, Any]:
    role = "adjudicator" if adjudication else "reviewer"
    person_ref = _opaque(record.get(f"{role}Ref"), f"{role}Ref")
    qualification_ref = _opaque(record.get("qualificationRef"), "qualificationRef")
    if record.get("humanAuthored") is not True:
        raise ExpertTruthError("expert truth must be human-authored")
    if record.get("modelProposalViewed") is not False:
        raise ExpertTruthError("expert truth must be blinded to model proposals")
    decision = record.get("decision")
    if decision not in DECISIONS:
        raise ExpertTruthError("invalid expert decision")
    class_id = record.get("classId")
    if class_id not in ALLOWED_CLASSES:
        raise ExpertTruthError("unsupported classId")
    required = decision == "positive" and class_id in GEOMETRY_REQUIRED_FOR_POSITIVE
    polygons = _validate_polygons(record.get("polygons"), required)
    if decision == "positive" and class_id == "tone_unevenness" and polygons:
        raise ExpertTruthError("tone_unevenness truth is capture-level, not polygon truth")
    return {
        "captureRef": _opaque(record.get("captureRef"), "captureRef"),
        "classId": class_id,
        f"{role}Ref": person_ref,
        "qualificationRef": qualification_ref,
        "decision": decision,
        "polygons": polygons,
        "humanAuthored": True,
        "modelProposalViewed": False,
    }


def _decision_fingerprint(record: dict[str, Any]) -> str:
    payload = {"decision": record["decision"], "polygons": record["polygons"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_expert_truth(camera_manifest: dict[str, Any], private_reviews: dict[str, Any]) -> dict[str, Any]:
    _assert_no_forbidden_keys(camera_manifest, "cameraManifest")
    _assert_no_forbidden_keys(private_reviews, "privateReviews")
    if camera_manifest.get("methodVersion") != "physical-camera-benchmark-manifest-v1":
        raise ExpertTruthError("camera manifest method identity changed")
    if camera_manifest.get("sourceType") != "physical-camera" or camera_manifest.get("generated") is not False:
        raise ExpertTruthError("expert truth requires a physical-camera manifest")
    if camera_manifest.get("split") != "camera_final":
        raise ExpertTruthError("expert truth requires camera_final")
    if camera_manifest.get("containsImageBytesOrPaths") is not False:
        raise ExpertTruthError("camera manifest privacy contract changed")
    if camera_manifest.get("containsModelPredictions") is not False:
        raise ExpertTruthError("camera manifest cannot contain model predictions")
    if camera_manifest.get("subjectIndependentFromTrainingValidationThresholdSelection") is not True:
        raise ExpertTruthError("camera manifest independence is not established")

    captures = camera_manifest.get("captures")
    if not isinstance(captures, list) or not captures:
        raise ExpertTruthError("camera manifest has no captures")
    capture_refs = {record.get("captureRef") for record in captures}
    if len(capture_refs) != len(captures) or None in capture_refs:
        raise ExpertTruthError("camera manifest capture references are invalid")

    activated = private_reviews.get("activatedClasses")
    if not isinstance(activated, list) or not activated or len(set(activated)) != len(activated):
        raise ExpertTruthError("activatedClasses must be a unique non-empty array")
    if any(class_id not in ALLOWED_CLASSES for class_id in activated):
        raise ExpertTruthError("activatedClasses contains an unsupported class")
    protocol_ref = _opaque(private_reviews.get("protocolRef"), "protocolRef")

    reviews_raw = private_reviews.get("reviews")
    if not isinstance(reviews_raw, list):
        raise ExpertTruthError("reviews must be an array")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in reviews_raw:
        if not isinstance(raw, dict):
            raise ExpertTruthError("review must be an object")
        review = _normalize_decision(raw)
        key = (review["captureRef"], review["classId"])
        if key[0] not in capture_refs or key[1] not in activated:
            raise ExpertTruthError("review is outside the camera/class matrix")
        grouped[key].append(review)

    expected = {(capture_ref, class_id) for capture_ref in capture_refs for class_id in activated}
    if set(grouped) != expected:
        raise ExpertTruthError("every camera/class cell requires explicit reviews; missing is not negative")
    for key, pair in grouped.items():
        if len(pair) != 2:
            raise ExpertTruthError("every camera/class cell requires exactly two reviews")
        if pair[0]["reviewerRef"] == pair[1]["reviewerRef"]:
            raise ExpertTruthError("the two reviews must come from independent experts")

    adjudications_raw = private_reviews.get("adjudications", [])
    if not isinstance(adjudications_raw, list):
        raise ExpertTruthError("adjudications must be an array")
    adjudications: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in adjudications_raw:
        if not isinstance(raw, dict):
            raise ExpertTruthError("adjudication must be an object")
        decision = _normalize_decision(raw, adjudication=True)
        key = (decision["captureRef"], decision["classId"])
        if key in adjudications:
            raise ExpertTruthError("duplicate adjudication")
        if key not in expected:
            raise ExpertTruthError("adjudication is outside the camera/class matrix")
        adjudications[key] = decision

    truths: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    disagreement_count = 0
    for capture_ref, class_id in sorted(expected):
        pair = grouped[(capture_ref, class_id)]
        fingerprints = {_decision_fingerprint(item) for item in pair}
        if len(fingerprints) == 1:
            if (capture_ref, class_id) in adjudications:
                raise ExpertTruthError("agreed reviews must not be overwritten by adjudication")
            final = pair[0]
            resolution = "dual-review-agreement"
        else:
            disagreement_count += 1
            final = adjudications.get((capture_ref, class_id))
            if final is None:
                raise ExpertTruthError("discordant reviews require third-expert adjudication")
            if final["adjudicatorRef"] in {pair[0]["reviewerRef"], pair[1]["reviewerRef"]}:
                raise ExpertTruthError("adjudicator must be independent of both reviewers")
            resolution = "third-expert-adjudication"
        decision_counts[final["decision"]] += 1
        truths.append({
            "captureRef": capture_ref,
            "classId": class_id,
            "decision": final["decision"],
            "polygons": final["polygons"],
            "resolution": resolution,
        })

    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-expert-truth-v1",
        "cameraManifestMethodVersion": camera_manifest["methodVersion"],
        "protocolRef": protocol_ref,
        "activatedClasses": sorted(activated),
        "captureCount": len(capture_refs),
        "truthCellCount": len(truths),
        "twoIndependentHumanReviewsPerCell": True,
        "modelProposalUsedAsTruth": False,
        "missingTruthInterpretedAsNegative": False,
        "unknownInterpretedAsNormal": False,
        "rednessIndependentFromSensitivity": True,
        "rednessOverlapAllowed": True,
        "normalRequiresExplicitEvaluatedTruth": True,
        "disagreementCount": disagreement_count,
        "decisionCounts": dict(sorted(decision_counts.items())),
        "truth": truths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--private-reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_expert_truth(
        json.loads(args.camera_manifest.read_text(encoding="utf-8")),
        json.loads(args.private_reviews.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
