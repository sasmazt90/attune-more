import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name):
    path = ROOT / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CAMERA = load("build_physical_camera_benchmark_manifest.py")
TRUTH = load("build_physical_camera_expert_truth.py")
MODULE = load("evaluate_physical_camera_predictions.py")
POLYGON = [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]]


def fixtures():
    raw = []
    for number, pose in enumerate(("front", "left", "right"), 1):
        raw.append({
            "subjectRef": "subject_0000000000000001", "captureRef": f"capture_{number:016x}",
            "consentRef": "consent_0000000000000001", "imageSha256": f"{number:064x}",
            "pose": pose, "deviceClass": "mobile-front", "lightingBin": "indoor-diffuse",
            "skinToneBin": "fitzpatrick-iii", "captureQualityGateRef": f"quality_{number:016x}",
            "captureQuality": "pass", "sourceType": "physical-camera", "generated": False,
            "split": "camera_final", "usedForTraining": False, "usedForValidation": False,
            "usedForThresholdSelection": False,
        })
    camera = CAMERA.build_manifest({"captures": raw})
    private = {"protocolRef": "protocol_0000000000000001", "activatedClasses": ["pimple", "redness"], "reviews": [], "adjudications": []}
    for capture_index, capture in enumerate(camera["captures"]):
        for class_id in private["activatedClasses"]:
            positive = (class_id == "redness") or (class_id == "pimple" and capture_index == 0)
            decision = "positive" if positive else "evaluated_negative"
            for reviewer in (1, 2):
                private["reviews"].append({
                    "captureRef": capture["captureRef"], "classId": class_id,
                    "reviewerRef": f"reviewer_{reviewer:016x}", "qualificationRef": f"qualification_{reviewer:016x}",
                    "decision": decision, "polygons": copy.deepcopy(POLYGON) if positive else [],
                    "humanAuthored": True, "modelProposalViewed": False,
                })
    truth = TRUTH.build_expert_truth(camera, private)
    receipt = {
        "methodRef": "method_0000000000000001", "methodVersion": "candidate-v1",
        "thresholdLockRef": "thresholds_0000000000000001",
        "thresholdsLockedBeforeCameraFinal": True, "cameraFinalUsedForThresholdSelection": False,
        "methodMutatedAfterLock": False, "records": [],
    }
    for row in truth["truth"]:
        receipt["records"].append({
            "captureRef": row["captureRef"], "classId": row["classId"],
            "decision": "positive" if row["decision"] == "positive" else "negative",
        })
    return camera, truth, receipt


class CameraPredictionEvaluationTest(unittest.TestCase):
    def test_perfect_fixture_scores_each_class_and_slice_separately(self):
        camera, truth, receipt = fixtures()
        result = MODULE.evaluate(camera, truth, receipt)
        self.assertEqual(result["classMetrics"]["pimple"]["f1"], 1.0)
        self.assertEqual(result["classMetrics"]["redness"]["f1"], 1.0)
        self.assertEqual(result["sliceMetrics"]["pose"]["front"]["pimple"]["tp"], 1)
        self.assertFalse(result["localizationMetricsComputed"])
        self.assertFalse(result["activationAllowed"])

    def test_missing_or_duplicate_prediction_fails_closed(self):
        camera, truth, receipt = fixtures()
        receipt["records"].pop()
        with self.assertRaisesRegex(MODULE.CameraEvaluationError, "every camera/class"):
            MODULE.evaluate(camera, truth, receipt)
        camera, truth, receipt = fixtures()
        receipt["records"].append(copy.deepcopy(receipt["records"][0]))
        with self.assertRaisesRegex(MODULE.CameraEvaluationError, "duplicate prediction"):
            MODULE.evaluate(camera, truth, receipt)

    def test_camera_final_cannot_tune_thresholds_or_mutate_method(self):
        for field, message in (("thresholdsLockedBeforeCameraFinal", "locked"), ("cameraFinalUsedForThresholdSelection", "cannot select"), ("methodMutatedAfterLock", "cannot change")):
            camera, truth, receipt = fixtures()
            receipt[field] = False if field == "thresholdsLockedBeforeCameraFinal" else True
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraEvaluationError, message):
                MODULE.evaluate(camera, truth, receipt)

    def test_unavailable_is_not_true_negative_and_positive_becomes_failure(self):
        camera, truth, receipt = fixtures()
        positive = next(row for row in receipt["records"] if row["classId"] == "pimple" and row["decision"] == "positive")
        positive["decision"] = "unavailable"
        negative = next(row for row in receipt["records"] if row["classId"] == "pimple" and row["decision"] == "negative")
        negative["decision"] = "unavailable"
        result = MODULE.evaluate(camera, truth, receipt)
        metrics = result["classMetrics"]["pimple"]
        self.assertEqual(metrics["fn"], 1)
        self.assertEqual(metrics["tn"], 1)
        self.assertEqual(metrics["unavailablePredictions"], 2)
        self.assertTrue(result["unavailableNeverCountsAsTrueNegative"])

    def test_unknown_and_unassessable_are_excluded_not_negative(self):
        camera, truth, receipt = fixtures()
        pimple_rows = [row for row in truth["truth"] if row["classId"] == "pimple"]
        pimple_rows[1]["decision"] = "unknown"
        pimple_rows[2]["decision"] = "unassessable"
        result = MODULE.evaluate(camera, truth, receipt)
        metrics = result["classMetrics"]["pimple"]
        self.assertEqual(metrics["eligibleTruth"], 1)
        self.assertEqual(metrics["unknownTruthExcluded"], 1)
        self.assertEqual(metrics["unassessableTruthExcluded"], 1)

    def test_class_failures_remain_separate(self):
        camera, truth, receipt = fixtures()
        pimple_positive = next(row for row in receipt["records"] if row["classId"] == "pimple" and row["decision"] == "positive")
        pimple_positive["decision"] = "negative"
        result = MODULE.evaluate(camera, truth, receipt)
        self.assertLess(result["classMetrics"]["pimple"]["f1"], 1.0)
        self.assertEqual(result["classMetrics"]["redness"]["f1"], 1.0)

    def test_scores_or_private_fields_are_rejected(self):
        for field in ("confidence", "score", "suggestedThreshold", "name", "email", "path"):
            camera, truth, receipt = fixtures()
            receipt["records"][0][field] = 0.9
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraEvaluationError, "forbidden"):
                MODULE.evaluate(camera, truth, receipt)

    def test_map_contract_and_redness_semantics_are_preserved(self):
        result = MODULE.evaluate(*fixtures())
        self.assertEqual(result["mapContract"]["dry"], "blue")
        self.assertEqual(result["mapContract"]["oily"], "green")
        self.assertEqual(result["mapContract"]["unknown"], "light-grey-never-normal")
        self.assertTrue(result["rednessIndependentFromSensitivity"])


if __name__ == "__main__":
    unittest.main()
