import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PATH = ROOT / "check_physical_camera_acceptance.py"
SPEC = importlib.util.spec_from_file_location(PATH.stem, PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


CLASSES = ("pimple", "redness")


def capture_row():
    return {
        "tp": 3, "fp": 0, "fn": 0, "tn": 2,
        "eligibleTruth": 5, "scorablePredictions": 5,
        "unavailablePredictions": 0, "unknownTruthExcluded": 0,
        "unassessableTruthExcluded": 0, "precision": 0.9,
        "recall": 0.9, "f1": 0.9, "availability": 1.0,
    }


def localization_row():
    return {
        "eligibleTruthCaptures": 5, "availablePredictions": 5,
        "unavailablePredictions": 0, "positiveTruthCaptures": 3,
        "scoredPositiveCaptures": 3, "evaluatedNegativeCaptures": 2,
        "falsePositiveAreaCaptures": 0, "unknownTruthExcluded": 0,
        "unassessableTruthExcluded": 0, "truthAreaPixels": 300,
        "predictionAreaPixelsOnPositiveTruth": 300, "intersectionPixels": 270,
        "unionPixels": 330, "falsePositiveAreaPixelsOnEvaluatedNegative": 0,
        "availability": 1.0, "meanPositiveIoU": 0.85,
        "meanPositiveDice": 0.9, "microPositiveIoU": 0.82,
        "microPositiveDice": 0.9, "negativeFalsePositiveAreaCaptureRate": 0.0,
    }


def fixtures():
    capture = {
        "methodVersion": "physical-camera-capture-level-evaluation-v1",
        "evaluatedMethodRef": "method_0000000000000001",
        "evaluatedMethodVersion": "candidate-v1",
        "thresholdLockRef": "thresholds_0000000000000001",
        "cameraFinalUsedForThresholdSelection": False,
        "captureLevelMetricsComputed": True,
        "activationAllowed": False,
        "classMetrics": {class_id: capture_row() for class_id in CLASSES},
        "sliceMetrics": {},
    }
    localization = {
        "methodVersion": "physical-camera-localization-evaluation-v1",
        "evaluatedMethodRef": "method_0000000000000001",
        "evaluatedMethodVersion": "candidate-v1",
        "thresholdLockRef": "thresholds_0000000000000001",
        "geometryLockRef": "geometry_0000000000000001",
        "cameraFinalUsedForThresholdSelection": False,
        "cameraFinalUsedForGeometrySelection": False,
        "boxesAcceptedAsPolygons": False,
        "modelGeometryUsedAsExpertTruth": False,
        "localizationMetricsComputed": True,
        "activationAllowed": False,
        "classMetrics": {class_id: localization_row() for class_id in CLASSES},
        "sliceMetrics": {},
    }
    for field, value in zip(MODULE.SLICE_FIELDS, ("mobile-front", "indoor-diffuse", "fitzpatrick-iii", "front")):
        capture["sliceMetrics"][field] = {value: {class_id: capture_row() for class_id in CLASSES}}
        localization["sliceMetrics"][field] = {value: {class_id: localization_row() for class_id in CLASSES}}
    policy = {
        "methodVersion": "physical-camera-acceptance-policy-v1",
        "policyRef": "policy_0000000000000001",
        "lockedBeforeCameraFinal": True,
        "cameraFinalUsedForPolicySelection": False,
        "policyMutatedAfterLock": False,
        "appliesToMethodRef": "method_0000000000000001",
        "appliesToMethodVersion": "candidate-v1",
        "thresholdLockRef": "thresholds_0000000000000001",
        "geometryLockRef": "geometry_0000000000000001",
        "applyPerClassWithoutMacroAveraging": True,
        "applySameMinimumsToEveryObservedSlice": True,
        "classes": [],
    }
    for class_id in CLASSES:
        policy["classes"].append({
            "classId": class_id, "minPrecision": 0.8, "minRecall": 0.8,
            "minF1": 0.8, "minAvailability": 0.9,
            "minimumEligibleTruthPerSlice": 1, "minimumPositiveTruthPerSlice": 1,
            "localizationRequired": True, "minMeanPositiveIoU": 0.8,
            "minMeanPositiveDice": 0.85,
            "maxNegativeFalsePositiveAreaCaptureRate": 0.1,
        })
    replay = {
        "methodVersion": "physical-camera-product-replay-v1",
        "replayRef": "replay_0000000000000001",
        "sourceType": "physical-camera", "generated": False, "split": "camera_final",
        "endpoint": "/api/local-health/skin",
        "evaluatedMethodRef": "method_0000000000000001",
        "evaluatedMethodVersion": "candidate-v1",
        "thresholdLockRef": "thresholds_0000000000000001",
        "geometryLockRef": "geometry_0000000000000001",
        "realBrowser": True, "apiPassed": True, "overviewPassed": True,
        "everyRegionPassed": True, "mapPassed": True, "historyWriteReadPassed": True,
        "methodIncompatibleHistoryExcluded": True, "unavailableStatePassed": True,
        "retainedPhotoReplayPassed": True, "privacyRetentionDeletionPassed": True,
        "normalRequiresExplicitEvaluatedTruth": True, "unknownNeverRenderedAsNormal": True,
        "rednessIndependentFromSensitivity": True, "rednessOverlapAllowed": True,
        "physicalCaptureCount": 3,
        "mapContract": {
            "dry": "blue", "oily": "green",
            "redness": "red-independent-contour-or-hatching",
            "normal": "uncoloured-explicitly-evaluated-only",
            "unknown": "light-grey-never-normal", "overlapAllowed": True,
        },
        "classes": [
            {"classId": class_id, "headingRendered": True, "resultBoundToMethod": True,
             "unavailableStatePassed": True, "historyPassed": True}
            for class_id in CLASSES
        ],
    }
    return capture, localization, policy, replay


class PhysicalCameraAcceptanceTest(unittest.TestCase):
    def test_complete_per_class_and_slice_evidence_passes(self):
        result = MODULE.check_acceptance(*fixtures())
        self.assertTrue(result["cameraAccepted"])
        self.assertTrue(result["activationAllowed"])
        self.assertFalse(result["macroAveragingUsed"])
        self.assertTrue(all(row["passed"] for row in result["classVerdicts"].values()))

    def test_weak_class_cannot_be_hidden_by_another_class(self):
        capture, localization, policy, replay = fixtures()
        capture["classMetrics"]["pimple"]["f1"] = 0.5
        result = MODULE.check_acceptance(capture, localization, policy, replay)
        self.assertFalse(result["classVerdicts"]["pimple"]["passed"])
        self.assertTrue(result["classVerdicts"]["redness"]["passed"])
        self.assertFalse(result["cameraAccepted"])

    def test_policy_must_cover_every_class_exactly_once(self):
        capture, localization, policy, replay = fixtures()
        policy["classes"].pop()
        with self.assertRaisesRegex(MODULE.CameraAcceptanceError, "every class"):
            MODULE.check_acceptance(capture, localization, policy, replay)
        capture, localization, policy, replay = fixtures()
        policy["classes"].append(copy.deepcopy(policy["classes"][0]))
        with self.assertRaisesRegex(MODULE.CameraAcceptanceError, "duplicate"):
            MODULE.check_acceptance(capture, localization, policy, replay)

    def test_policy_cannot_be_selected_on_camera_final_or_mutated(self):
        for field, value, message in (
            ("lockedBeforeCameraFinal", False, "locked"),
            ("cameraFinalUsedForPolicySelection", True, "locked"),
            ("policyMutatedAfterLock", True, "cannot change"),
        ):
            capture, localization, policy, replay = fixtures()
            policy[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraAcceptanceError, message):
                MODULE.check_acceptance(capture, localization, policy, replay)

    def test_method_threshold_and_geometry_identity_must_match(self):
        for document, field in ((1, "evaluatedMethodRef"), (1, "thresholdLockRef"), (2, "geometryLockRef"), (3, "evaluatedMethodVersion")):
            values = list(fixtures())
            values[document][field] = "method_ffffffffffffffff" if "Ref" in field else "other-v1"
            with self.subTest(document=document, field=field), self.assertRaises(MODULE.CameraAcceptanceError):
                MODULE.check_acceptance(*values)

    def test_localization_failure_blocks_only_affected_class(self):
        capture, localization, policy, replay = fixtures()
        localization["classMetrics"]["pimple"]["meanPositiveIoU"] = 0.2
        result = MODULE.check_acceptance(capture, localization, policy, replay)
        self.assertFalse(result["classVerdicts"]["pimple"]["passed"])
        self.assertTrue(result["classVerdicts"]["redness"]["passed"])
        self.assertIn("meanPositiveIoU_below_minMeanPositiveIoU", result["classVerdicts"]["pimple"]["failures"])

    def test_slice_failure_blocks_even_when_aggregate_passes(self):
        capture, localization, policy, replay = fixtures()
        capture["sliceMetrics"]["pose"]["front"]["pimple"]["recall"] = 0.1
        result = MODULE.check_acceptance(capture, localization, policy, replay)
        self.assertFalse(result["classVerdicts"]["pimple"]["passed"])
        self.assertIn("one_or_more_camera_slices_failed", result["classVerdicts"]["pimple"]["failures"])
        self.assertTrue(any(row["dimension"] == "pose" for row in result["classVerdicts"]["pimple"]["sliceFailures"]))

    def test_product_replay_and_map_semantics_fail_closed(self):
        for field in ("realBrowser", "apiPassed", "historyWriteReadPassed", "privacyRetentionDeletionPassed", "rednessIndependentFromSensitivity"):
            capture, localization, policy, replay = fixtures()
            replay[field] = False
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraAcceptanceError, "product replay"):
                MODULE.check_acceptance(capture, localization, policy, replay)
        capture, localization, policy, replay = fixtures()
        replay["mapContract"]["unknown"] = "normal"
        with self.assertRaisesRegex(MODULE.CameraAcceptanceError, "map contract"):
            MODULE.check_acceptance(capture, localization, policy, replay)

    def test_product_replay_must_cover_every_class_and_unavailable_state(self):
        capture, localization, policy, replay = fixtures()
        replay["classes"].pop()
        with self.assertRaisesRegex(MODULE.CameraAcceptanceError, "every class"):
            MODULE.check_acceptance(capture, localization, policy, replay)
        capture, localization, policy, replay = fixtures()
        replay["classes"][0]["unavailableStatePassed"] = False
        with self.assertRaisesRegex(MODULE.CameraAcceptanceError, "unavailableStatePassed"):
            MODULE.check_acceptance(capture, localization, policy, replay)

    def test_macro_recommendation_and_private_fields_are_rejected(self):
        for field in ("macroAverage", "recommended", "hardwareWinner", "confidence", "path", "email"):
            values = list(fixtures())
            values[0][field] = 0.99
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraAcceptanceError, "forbidden"):
                MODULE.check_acceptance(*values)


if __name__ == "__main__":
    unittest.main()
