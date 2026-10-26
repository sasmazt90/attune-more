#!/usr/bin/env python3
"""Apply locked per-class camera thresholds and product replay evidence.

This final gate composes capture-level metrics, polygon localization metrics,
an acceptance policy locked before ``camera_final`` and a real-product replay
receipt.  Every class and every observed camera slice must pass independently;
macro averages, recommendation flags and finished-training status are never
accepted as substitutes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SLICE_FIELDS = ("deviceClass", "lightingBin", "skinToneBin", "pose")
CAPTURE_THRESHOLDS = {
    "precision": "minPrecision",
    "recall": "minRecall",
    "f1": "minF1",
    "availability": "minAvailability",
}
LOCALIZATION_THRESHOLDS = {
    "meanPositiveIoU": "minMeanPositiveIoU",
    "meanPositiveDice": "minMeanPositiveDice",
}
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "macroaverage", "macrof1", "overallscore", "recommended", "hardwarewinner",
    "confidence", "scorecandidate", "thresholdcandidate", "suggestedthreshold",
    "name", "filename", "filepath", "path", "uri", "url", "email", "phone",
    "address", "rawimage", "imagebytes", "bytes",
}


class CameraAcceptanceError(ValueError):
    """Raised when acceptance evidence is incomplete, mutable or unsafe."""


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise CameraAcceptanceError(f"{field} must be an opaque reference")
    return value


def _assert_no_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in FORBIDDEN_KEYS:
                raise CameraAcceptanceError(f"forbidden aggregate/private/tuning field at {location}.{key}")
            _assert_no_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, f"{location}[{index}]")


def _fraction(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CameraAcceptanceError(f"{field} must be numeric")
    number = float(value)
    if not 0 <= number <= 1:
        raise CameraAcceptanceError(f"{field} must be within [0, 1]")
    return number


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CameraAcceptanceError(f"{field} must be a positive integer")
    return value


def _metric_passes(value: Any, minimum: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= minimum


def _validate_metric_identity(capture: dict[str, Any], localization: dict[str, Any]) -> tuple[str, str, str, str]:
    if capture.get("methodVersion") != "physical-camera-capture-level-evaluation-v1":
        raise CameraAcceptanceError("capture evaluation method identity changed")
    if localization.get("methodVersion") != "physical-camera-localization-evaluation-v1":
        raise CameraAcceptanceError("localization evaluation method identity changed")
    if capture.get("captureLevelMetricsComputed") is not True or capture.get("activationAllowed") is not False:
        raise CameraAcceptanceError("capture evaluation provenance contract changed")
    if localization.get("localizationMetricsComputed") is not True or localization.get("activationAllowed") is not False:
        raise CameraAcceptanceError("localization evaluation provenance contract changed")
    method_ref = _opaque(capture.get("evaluatedMethodRef"), "evaluatedMethodRef")
    method_version = capture.get("evaluatedMethodVersion")
    threshold_ref = _opaque(capture.get("thresholdLockRef"), "thresholdLockRef")
    geometry_ref = _opaque(localization.get("geometryLockRef"), "geometryLockRef")
    if not isinstance(method_version, str) or not method_version:
        raise CameraAcceptanceError("evaluatedMethodVersion must be non-empty")
    if localization.get("evaluatedMethodRef") != method_ref or localization.get("evaluatedMethodVersion") != method_version:
        raise CameraAcceptanceError("capture and localization evaluations must bind the same method")
    if localization.get("thresholdLockRef") != threshold_ref:
        raise CameraAcceptanceError("capture and localization evaluations must bind the same thresholds")
    if capture.get("cameraFinalUsedForThresholdSelection") is not False or localization.get("cameraFinalUsedForThresholdSelection") is not False:
        raise CameraAcceptanceError("camera_final cannot select thresholds")
    if localization.get("cameraFinalUsedForGeometrySelection") is not False:
        raise CameraAcceptanceError("camera_final cannot select geometry method")
    if localization.get("boxesAcceptedAsPolygons") is not False or localization.get("modelGeometryUsedAsExpertTruth") is not False:
        raise CameraAcceptanceError("localization provenance contract changed")
    return method_ref, method_version, threshold_ref, geometry_ref


def _validate_policy(policy: dict[str, Any], classes: set[str], identity: tuple[str, str, str, str]) -> dict[str, dict[str, Any]]:
    method_ref, method_version, threshold_ref, geometry_ref = identity
    if policy.get("methodVersion") != "physical-camera-acceptance-policy-v1":
        raise CameraAcceptanceError("acceptance policy method identity changed")
    _opaque(policy.get("policyRef"), "policyRef")
    if policy.get("lockedBeforeCameraFinal") is not True or policy.get("cameraFinalUsedForPolicySelection") is not False:
        raise CameraAcceptanceError("acceptance policy must be locked outside camera_final")
    if policy.get("policyMutatedAfterLock") is not False:
        raise CameraAcceptanceError("acceptance policy cannot change after lock")
    expected = {
        "appliesToMethodRef": method_ref,
        "appliesToMethodVersion": method_version,
        "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref,
        "applyPerClassWithoutMacroAveraging": True,
        "applySameMinimumsToEveryObservedSlice": True,
    }
    for field, value in expected.items():
        if policy.get(field) != value:
            raise CameraAcceptanceError(f"acceptance policy {field} mismatch")
    rows = policy.get("classes")
    if not isinstance(rows, list):
        raise CameraAcceptanceError("policy classes must be an array")
    by_class: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("classId"), str):
            raise CameraAcceptanceError("policy class row is invalid")
        class_id = row["classId"]
        if class_id in by_class:
            raise CameraAcceptanceError("duplicate policy class")
        clean = dict(row)
        for field in CAPTURE_THRESHOLDS.values():
            clean[field] = _fraction(row.get(field), field)
        clean["minimumEligibleTruthPerSlice"] = _positive_int(row.get("minimumEligibleTruthPerSlice"), "minimumEligibleTruthPerSlice")
        clean["minimumPositiveTruthPerSlice"] = _positive_int(row.get("minimumPositiveTruthPerSlice"), "minimumPositiveTruthPerSlice")
        if not isinstance(row.get("localizationRequired"), bool):
            raise CameraAcceptanceError("localizationRequired must be boolean")
        if row["localizationRequired"]:
            for field in LOCALIZATION_THRESHOLDS.values():
                clean[field] = _fraction(row.get(field), field)
            clean["maxNegativeFalsePositiveAreaCaptureRate"] = _fraction(
                row.get("maxNegativeFalsePositiveAreaCaptureRate"),
                "maxNegativeFalsePositiveAreaCaptureRate",
            )
        by_class[class_id] = clean
    if set(by_class) != classes:
        raise CameraAcceptanceError("acceptance policy must cover every class exactly once")
    return by_class


def _validate_replay(replay: dict[str, Any], classes: set[str], identity: tuple[str, str, str, str]) -> dict[str, dict[str, Any]]:
    method_ref, method_version, threshold_ref, geometry_ref = identity
    if replay.get("methodVersion") != "physical-camera-product-replay-v1":
        raise CameraAcceptanceError("product replay method identity changed")
    _opaque(replay.get("replayRef"), "replayRef")
    expected = {
        "sourceType": "physical-camera",
        "generated": False,
        "split": "camera_final",
        "endpoint": "/api/local-health/skin",
        "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version,
        "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref,
        "realBrowser": True,
        "apiPassed": True,
        "overviewPassed": True,
        "everyRegionPassed": True,
        "mapPassed": True,
        "historyWriteReadPassed": True,
        "methodIncompatibleHistoryExcluded": True,
        "unavailableStatePassed": True,
        "retainedPhotoReplayPassed": True,
        "privacyRetentionDeletionPassed": True,
        "normalRequiresExplicitEvaluatedTruth": True,
        "unknownNeverRenderedAsNormal": True,
        "rednessIndependentFromSensitivity": True,
        "rednessOverlapAllowed": True,
    }
    for field, value in expected.items():
        if replay.get(field) != value:
            raise CameraAcceptanceError(f"product replay {field} mismatch")
    capture_count = replay.get("physicalCaptureCount")
    if isinstance(capture_count, bool) or not isinstance(capture_count, int) or capture_count < 1:
        raise CameraAcceptanceError("product replay requires physical captures")
    map_contract = replay.get("mapContract")
    if map_contract != {
        "dry": "blue",
        "oily": "green",
        "redness": "red-independent-contour-or-hatching",
        "normal": "uncoloured-explicitly-evaluated-only",
        "unknown": "light-grey-never-normal",
        "overlapAllowed": True,
    }:
        raise CameraAcceptanceError("product replay map contract mismatch")
    rows = replay.get("classes")
    if not isinstance(rows, list):
        raise CameraAcceptanceError("product replay classes must be an array")
    by_class: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("classId"), str):
            raise CameraAcceptanceError("product replay class row is invalid")
        class_id = row["classId"]
        if class_id in by_class:
            raise CameraAcceptanceError("duplicate product replay class")
        for field in ("headingRendered", "resultBoundToMethod", "unavailableStatePassed", "historyPassed"):
            if row.get(field) is not True:
                raise CameraAcceptanceError(f"product replay class {class_id} failed {field}")
        by_class[class_id] = row
    if set(by_class) != classes:
        raise CameraAcceptanceError("product replay must cover every class exactly once")
    return by_class


def _check_thresholds(metrics: dict[str, Any], policy: dict[str, Any], mappings: dict[str, str]) -> list[str]:
    failures = []
    for metric, threshold in mappings.items():
        if not _metric_passes(metrics.get(metric), policy[threshold]):
            failures.append(f"{metric}_below_{threshold}")
    return failures


def check_acceptance(capture: dict[str, Any], localization: dict[str, Any], policy: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    for name, value in (("capture", capture), ("localization", localization), ("policy", policy), ("replay", replay)):
        _assert_no_forbidden_keys(value, name)
    capture_metrics = capture.get("classMetrics")
    localization_metrics = localization.get("classMetrics")
    if not isinstance(capture_metrics, dict) or not capture_metrics or not isinstance(localization_metrics, dict):
        raise CameraAcceptanceError("class metrics are missing")
    classes = set(capture_metrics)
    if set(localization_metrics) != classes:
        raise CameraAcceptanceError("capture and localization class inventories differ")
    identity = _validate_metric_identity(capture, localization)
    class_policy = _validate_policy(policy, classes, identity)
    replay_classes = _validate_replay(replay, classes, identity)
    capture_slices = capture.get("sliceMetrics")
    localization_slices = localization.get("sliceMetrics")
    if not isinstance(capture_slices, dict) or not isinstance(localization_slices, dict):
        raise CameraAcceptanceError("slice metrics are missing")
    if set(capture_slices) != set(SLICE_FIELDS) or set(localization_slices) != set(SLICE_FIELDS):
        raise CameraAcceptanceError("all required slice dimensions must be present")

    verdicts: dict[str, dict[str, Any]] = {}
    for class_id in sorted(classes):
        rules = class_policy[class_id]
        failures = _check_thresholds(capture_metrics[class_id], rules, CAPTURE_THRESHOLDS)
        if rules["localizationRequired"]:
            failures.extend(_check_thresholds(localization_metrics[class_id], rules, LOCALIZATION_THRESHOLDS))
            fp_rate = localization_metrics[class_id].get("negativeFalsePositiveAreaCaptureRate")
            if not isinstance(fp_rate, (int, float)) or isinstance(fp_rate, bool) or fp_rate > rules["maxNegativeFalsePositiveAreaCaptureRate"]:
                failures.append("negativeFalsePositiveAreaCaptureRate_above_maximum")
        slice_failures: list[dict[str, str]] = []
        for field in SLICE_FIELDS:
            if set(capture_slices[field]) != set(localization_slices[field]) or not capture_slices[field]:
                raise CameraAcceptanceError(f"{field} slice inventories differ or are empty")
            for value in sorted(capture_slices[field]):
                capture_row = capture_slices[field][value].get(class_id)
                localization_row = localization_slices[field][value].get(class_id)
                if not isinstance(capture_row, dict) or not isinstance(localization_row, dict):
                    raise CameraAcceptanceError("slice class matrix is incomplete")
                local_failures = []
                if capture_row.get("eligibleTruth", 0) < rules["minimumEligibleTruthPerSlice"]:
                    local_failures.append("eligible_truth_below_minimum")
                truth_positives = capture_row.get("tp", 0) + capture_row.get("fn", 0)
                if truth_positives < rules["minimumPositiveTruthPerSlice"]:
                    local_failures.append("positive_truth_below_minimum")
                local_failures.extend(_check_thresholds(capture_row, rules, CAPTURE_THRESHOLDS))
                if rules["localizationRequired"]:
                    if localization_row.get("positiveTruthCaptures", 0) < rules["minimumPositiveTruthPerSlice"]:
                        local_failures.append("localization_positive_truth_below_minimum")
                    local_failures.extend(_check_thresholds(localization_row, rules, LOCALIZATION_THRESHOLDS))
                    slice_fp = localization_row.get("negativeFalsePositiveAreaCaptureRate")
                    if slice_fp is not None and (not isinstance(slice_fp, (int, float)) or isinstance(slice_fp, bool) or slice_fp > rules["maxNegativeFalsePositiveAreaCaptureRate"]):
                        local_failures.append("negative_false_positive_area_rate_above_maximum")
                for failure in local_failures:
                    slice_failures.append({"dimension": field, "value": value, "failure": failure})
        if slice_failures:
            failures.append("one_or_more_camera_slices_failed")
        verdicts[class_id] = {
            "passed": not failures,
            "failures": sorted(set(failures)),
            "sliceFailures": slice_failures,
            "localizationRequired": rules["localizationRequired"],
            "productReplayPassed": bool(replay_classes[class_id]),
        }

    accepted = all(row["passed"] for row in verdicts.values())
    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-acceptance-gate-v1",
        "policyRef": policy["policyRef"],
        "evaluatedMethodRef": identity[0],
        "evaluatedMethodVersion": identity[1],
        "thresholdLockRef": identity[2],
        "geometryLockRef": identity[3],
        "classVerdicts": verdicts,
        "everyClassPassedIndependently": accepted,
        "everyObservedSlicePassedIndependently": accepted,
        "macroAveragingUsed": False,
        "trainingFinishedOrRecommendedUsedAsAcceptance": False,
        "realProductReplayPassed": True,
        "mapContractPassed": True,
        "cameraAccepted": accepted,
        "activationAllowed": accepted,
        "note": "A true result requires every class, every observed camera slice and the real API/browser/map/history replay to pass the policy locked before camera_final.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-evaluation", type=Path, required=True)
    parser.add_argument("--localization-evaluation", type=Path, required=True)
    parser.add_argument("--acceptance-policy", type=Path, required=True)
    parser.add_argument("--product-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check_acceptance(*[
        json.loads(path.read_text(encoding="utf-8"))
        for path in (args.capture_evaluation, args.localization_evaluation, args.acceptance_policy, args.product_replay)
    ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
