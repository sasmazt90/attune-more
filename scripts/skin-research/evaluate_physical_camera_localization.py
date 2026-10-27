#!/usr/bin/env python3
"""Evaluate locked polygon localization on independent physical-camera truth.

The evaluator computes class-level union-mask IoU/Dice and device, lighting,
skin-tone and pose slices with a locked pure-Python rasterization method.  It
never treats a box as polygon truth, never tunes on ``camera_final`` and never
turns model geometry into expert truth.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


RESOLUTION = 512
GEOMETRY_METHOD = "normalized-polygon-union-raster-iou-v1"
DECISIONS = {"positive", "negative", "unavailable"}
TRUTH_DECISIONS = {"positive", "evaluated_negative", "unknown", "unassessable"}
SLICE_FIELDS = ("deviceClass", "lightingBin", "skinToneBin", "pose")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "filepath", "path", "uri", "url", "email", "phone",
    "address", "rawimage", "imagebytes", "bytes", "confidence", "score",
    "probability", "thresholdcandidate", "suggestedthreshold", "bbox", "box",
    "rectangle",
}


class CameraLocalizationError(ValueError):
    """Raised when localization evidence is incomplete, mutable or unsafe."""


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise CameraLocalizationError(f"{field} must be an opaque reference")
    return value


def _assert_no_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in FORBIDDEN_KEYS:
                raise CameraLocalizationError(f"forbidden private/box/tuning field at {location}.{key}")
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


def _validate_polygons(value: Any, *, required: bool) -> list[list[list[float]]]:
    if not isinstance(value, list):
        raise CameraLocalizationError("polygons must be an array")
    if required and not value:
        raise CameraLocalizationError("positive localization requires polygon geometry")
    if not required and value:
        raise CameraLocalizationError("negative/unavailable localization cannot carry geometry")
    output: list[list[list[float]]] = []
    for polygon in value:
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise CameraLocalizationError("polygon requires at least three points")
        clean: list[list[float]] = []
        for point in polygon:
            if (
                not isinstance(point, list) or len(point) != 2
                or isinstance(point[0], bool) or isinstance(point[1], bool)
                or not isinstance(point[0], (int, float))
                or not isinstance(point[1], (int, float))
            ):
                raise CameraLocalizationError("polygon points must be numeric [x, y]")
            x, y = float(point[0]), float(point[1])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise CameraLocalizationError("polygon coordinates must be normalized to [0, 1]")
            clean.append([x, y])
        if _polygon_area(clean) <= 0:
            raise CameraLocalizationError("polygon must have non-zero area")
        output.append(clean)
    return output


def _rasterize(polygons: list[list[list[float]]]) -> bytearray:
    """Rasterize a polygon union at pixel centres with an even-odd scanline."""
    mask = bytearray(RESOLUTION * RESOLUTION)
    for polygon in polygons:
        scaled = [(x * RESOLUTION, y * RESOLUTION) for x, y in polygon]
        min_row = max(0, math.floor(min(y for _, y in scaled) - 0.5))
        max_row = min(RESOLUTION - 1, math.ceil(max(y for _, y in scaled) - 0.5))
        for row in range(min_row, max_row + 1):
            scan_y = row + 0.5
            intersections: list[float] = []
            for index, (x1, y1) in enumerate(scaled):
                x2, y2 = scaled[(index + 1) % len(scaled)]
                if (y1 <= scan_y < y2) or (y2 <= scan_y < y1):
                    intersections.append(x1 + (scan_y - y1) * (x2 - x1) / (y2 - y1))
            intersections.sort()
            for left, right in zip(intersections[0::2], intersections[1::2]):
                start = max(0, math.ceil(left - 0.5))
                stop = min(RESOLUTION - 1, math.ceil(right - 0.5) - 1)
                if stop >= start:
                    offset = row * RESOLUTION
                    mask[offset + start:offset + stop + 1] = b"\x01" * (stop - start + 1)
    return mask


def _overlap(truth_polygons: list[list[list[float]]], prediction_polygons: list[list[list[float]]]) -> dict[str, Any]:
    truth_mask = _rasterize(truth_polygons)
    prediction_mask = _rasterize(prediction_polygons)
    truth_area = sum(truth_mask)
    prediction_area = sum(prediction_mask)
    intersection = sum(1 for truth, predicted in zip(truth_mask, prediction_mask) if truth and predicted)
    union = truth_area + prediction_area - intersection
    return {
        "truthAreaPixels": truth_area,
        "predictionAreaPixels": prediction_area,
        "intersectionPixels": intersection,
        "unionPixels": union,
        "iou": intersection / union if union else None,
        "dice": (2 * intersection) / (truth_area + prediction_area) if truth_area + prediction_area else None,
    }


def _new_counts() -> dict[str, Any]:
    return {
        "eligibleTruthCaptures": 0,
        "availablePredictions": 0,
        "unavailablePredictions": 0,
        "positiveTruthCaptures": 0,
        "scoredPositiveCaptures": 0,
        "evaluatedNegativeCaptures": 0,
        "falsePositiveAreaCaptures": 0,
        "unknownTruthExcluded": 0,
        "unassessableTruthExcluded": 0,
        "sumIoU": 0.0,
        "sumDice": 0.0,
        "truthAreaPixels": 0,
        "predictionAreaPixelsOnPositiveTruth": 0,
        "intersectionPixels": 0,
        "unionPixels": 0,
        "falsePositiveAreaPixelsOnEvaluatedNegative": 0,
    }


def _update_counts(counts: dict[str, Any], truth: str, prediction: str, overlap: dict[str, Any] | None) -> None:
    if truth == "unknown":
        counts["unknownTruthExcluded"] += 1
        return
    if truth == "unassessable":
        counts["unassessableTruthExcluded"] += 1
        return
    counts["eligibleTruthCaptures"] += 1
    if prediction == "unavailable":
        counts["unavailablePredictions"] += 1
    else:
        counts["availablePredictions"] += 1
    if truth == "positive":
        counts["positiveTruthCaptures"] += 1
        if overlap is None:
            raise CameraLocalizationError("positive truth requires overlap accounting")
        counts["scoredPositiveCaptures"] += 1
        counts["sumIoU"] += overlap["iou"] or 0.0
        counts["sumDice"] += overlap["dice"] or 0.0
        counts["truthAreaPixels"] += overlap["truthAreaPixels"]
        counts["predictionAreaPixelsOnPositiveTruth"] += overlap["predictionAreaPixels"]
        counts["intersectionPixels"] += overlap["intersectionPixels"]
        counts["unionPixels"] += overlap["unionPixels"]
    elif truth == "evaluated_negative":
        counts["evaluatedNegativeCaptures"] += 1
        predicted_area = overlap["predictionAreaPixels"] if overlap is not None else 0
        if predicted_area:
            counts["falsePositiveAreaCaptures"] += 1
            counts["falsePositiveAreaPixelsOnEvaluatedNegative"] += predicted_area
    else:
        raise CameraLocalizationError("unexpected truth state")


def _metrics(counts: dict[str, Any]) -> dict[str, Any]:
    positive = counts["positiveTruthCaptures"]
    eligible = counts["eligibleTruthCaptures"]
    negatives = counts["evaluatedNegativeCaptures"]
    truth_plus_prediction = counts["truthAreaPixels"] + counts["predictionAreaPixelsOnPositiveTruth"]
    output = {key: value for key, value in counts.items() if key not in {"sumIoU", "sumDice"}}
    output.update({
        "availability": counts["availablePredictions"] / eligible if eligible else None,
        "meanPositiveIoU": counts["sumIoU"] / positive if positive else None,
        "meanPositiveDice": counts["sumDice"] / positive if positive else None,
        "microPositiveIoU": counts["intersectionPixels"] / counts["unionPixels"] if counts["unionPixels"] else None,
        "microPositiveDice": 2 * counts["intersectionPixels"] / truth_plus_prediction if truth_plus_prediction else None,
        "negativeFalsePositiveAreaCaptureRate": counts["falsePositiveAreaCaptures"] / negatives if negatives else None,
    })
    return output


def evaluate_localization(camera_manifest: dict[str, Any], expert_truth: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    _assert_no_forbidden_keys(camera_manifest, "cameraManifest")
    _assert_no_forbidden_keys(expert_truth, "expertTruth")
    _assert_no_forbidden_keys(receipt, "localizationReceipt")
    if camera_manifest.get("methodVersion") != "physical-camera-benchmark-manifest-v1":
        raise CameraLocalizationError("camera manifest method identity changed")
    if camera_manifest.get("sourceType") != "physical-camera" or camera_manifest.get("generated") is not False:
        raise CameraLocalizationError("localization evaluation requires physical captures")
    if camera_manifest.get("split") != "camera_final":
        raise CameraLocalizationError("localization evaluation requires camera_final")
    if expert_truth.get("methodVersion") != "physical-camera-expert-truth-v1":
        raise CameraLocalizationError("expert truth method identity changed")
    if expert_truth.get("modelProposalUsedAsTruth") is not False or expert_truth.get("missingTruthInterpretedAsNegative") is not False:
        raise CameraLocalizationError("expert truth provenance contract changed")

    method_ref = _opaque(receipt.get("methodRef"), "methodRef")
    threshold_lock_ref = _opaque(receipt.get("thresholdLockRef"), "thresholdLockRef")
    geometry_lock_ref = _opaque(receipt.get("geometryLockRef"), "geometryLockRef")
    method_version = receipt.get("methodVersion")
    if not isinstance(method_version, str) or not method_version.strip():
        raise CameraLocalizationError("methodVersion must be non-empty")
    if receipt.get("thresholdsLockedBeforeCameraFinal") is not True or receipt.get("cameraFinalUsedForThresholdSelection") is not False:
        raise CameraLocalizationError("thresholds must be locked outside camera_final")
    if receipt.get("geometryLockedBeforeCameraFinal") is not True or receipt.get("cameraFinalUsedForGeometrySelection") is not False:
        raise CameraLocalizationError("geometry method must be locked outside camera_final")
    if receipt.get("methodMutatedAfterLock") is not False or receipt.get("geometryMutatedAfterLock") is not False:
        raise CameraLocalizationError("method or geometry cannot change after lock")
    if receipt.get("geometryMethodVersion") != GEOMETRY_METHOD or receipt.get("rasterResolution") != RESOLUTION:
        raise CameraLocalizationError("localization raster method identity changed")

    captures = camera_manifest.get("captures")
    activated = expert_truth.get("activatedClasses")
    truth_rows = expert_truth.get("truth")
    if not isinstance(captures, list) or not captures or not isinstance(activated, list) or not activated or not isinstance(truth_rows, list):
        raise CameraLocalizationError("camera/expert inventory is invalid")
    capture_by_ref = {row.get("captureRef"): row for row in captures}
    if len(capture_by_ref) != len(captures) or None in capture_by_ref:
        raise CameraLocalizationError("camera capture references are invalid")
    expected = {(capture_ref, class_id) for capture_ref in capture_by_ref for class_id in activated}
    truth_by_key = {(row.get("captureRef"), row.get("classId")): row for row in truth_rows}
    if len(truth_by_key) != len(truth_rows) or set(truth_by_key) != expected:
        raise CameraLocalizationError("expert truth matrix is incomplete or duplicated")

    prediction_rows = receipt.get("records")
    if not isinstance(prediction_rows, list):
        raise CameraLocalizationError("localization records must be an array")
    prediction_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in prediction_rows:
        if not isinstance(row, dict):
            raise CameraLocalizationError("localization record must be an object")
        key = (row.get("captureRef"), row.get("classId"))
        if key not in expected:
            raise CameraLocalizationError("localization record is outside the camera/class matrix")
        if key in prediction_by_key:
            raise CameraLocalizationError("duplicate localization record")
        decision = row.get("decision")
        if decision not in DECISIONS:
            raise CameraLocalizationError("invalid localization decision")
        source = row.get("geometrySource")
        if decision == "positive" and source != "native-polygon-or-mask":
            raise CameraLocalizationError("positive geometry must originate from a native polygon or mask; boxes are forbidden")
        if decision != "positive" and source != "none":
            raise CameraLocalizationError("negative/unavailable geometrySource must be none")
        clean = dict(row)
        clean["polygons"] = _validate_polygons(row.get("polygons"), required=decision == "positive")
        prediction_by_key[key] = clean
    if set(prediction_by_key) != expected:
        raise CameraLocalizationError("every camera/class cell requires explicit localization")

    class_counts = {class_id: _new_counts() for class_id in activated}
    slice_counts: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
        field: defaultdict(lambda: {class_id: _new_counts() for class_id in activated})
        for field in SLICE_FIELDS
    }
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for capture_ref, class_id in sorted(expected):
        truth_row = truth_by_key[(capture_ref, class_id)]
        prediction_row = prediction_by_key[(capture_ref, class_id)]
        truth_decision = truth_row.get("decision")
        if truth_decision not in TRUTH_DECISIONS:
            raise CameraLocalizationError("invalid expert truth decision")
        truth_polygons = _validate_polygons(truth_row.get("polygons"), required=truth_decision == "positive")
        prediction_polygons = prediction_row["polygons"]
        if truth_decision == "positive":
            overlap = _overlap(truth_polygons, prediction_polygons)
        elif truth_decision == "evaluated_negative" and prediction_polygons:
            overlap = _overlap([], prediction_polygons)
        else:
            overlap = None
        _update_counts(class_counts[class_id], truth_decision, prediction_row["decision"], overlap)
        capture = capture_by_ref[capture_ref]
        for field in SLICE_FIELDS:
            value = capture.get(field)
            if not isinstance(value, str) or not value:
                raise CameraLocalizationError(f"camera manifest missing {field}")
            _update_counts(slice_counts[field][value][class_id], truth_decision, prediction_row["decision"], overlap)
        if truth_decision in {"positive", "evaluated_negative"}:
            case = {"captureRef": capture_ref, "classId": class_id, "truthDecision": truth_decision, "predictionDecision": prediction_row["decision"]}
            if overlap is not None:
                case.update(overlap)
            cases.append(case)
        if truth_decision == "positive" and prediction_row["decision"] != "positive":
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "missing_positive_geometry" if prediction_row["decision"] == "negative" else "unavailable_on_positive"})
        elif truth_decision == "positive" and overlap is not None and overlap["intersectionPixels"] == 0:
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "zero_overlap_positive_geometry"})
        elif truth_decision == "evaluated_negative" and overlap is not None and overlap["predictionAreaPixels"]:
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "false_positive_area_on_evaluated_negative", "predictionAreaPixels": overlap["predictionAreaPixels"]})

    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-localization-evaluation-v1",
        "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version,
        "thresholdLockRef": threshold_lock_ref,
        "geometryLockRef": geometry_lock_ref,
        "geometryMethodVersion": GEOMETRY_METHOD,
        "rasterResolution": RESOLUTION,
        "cameraFinalUsedForThresholdSelection": False,
        "cameraFinalUsedForGeometrySelection": False,
        "classMetrics": {class_id: _metrics(class_counts[class_id]) for class_id in sorted(activated)},
        "sliceMetrics": {
            field: {value: {class_id: _metrics(counts[class_id]) for class_id in sorted(activated)} for value, counts in sorted(values.items())}
            for field, values in slice_counts.items()
        },
        "localizationCases": cases,
        "failures": failures,
        "boxesAcceptedAsPolygons": False,
        "modelGeometryUsedAsExpertTruth": False,
        "unknownAndUnassessableExcludedNotNegative": True,
        "normalRequiresExplicitEvaluatedTruth": True,
        "rednessIndependentFromSensitivity": True,
        "mapContract": {"dry": "blue", "oily": "green", "redness": "red-independent", "normal": "uncoloured-evaluated-only", "unknown": "light-grey-never-normal"},
        "localizationMetricsComputed": True,
        "captureLevelClassificationMetricsComputed": False,
        "productReplayComputed": False,
        "acceptanceThresholdsApplied": False,
        "activationAllowed": False,
        "note": "Rasterized union-mask IoU/Dice and negative false-positive area are diagnostics only. Apply separately locked class thresholds and complete API/browser/map/history replay before activation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--expert-truth", type=Path, required=True)
    parser.add_argument("--localization-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_localization(
        json.loads(args.camera_manifest.read_text(encoding="utf-8")),
        json.loads(args.expert_truth.read_text(encoding="utf-8")),
        json.loads(args.localization_receipt.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
