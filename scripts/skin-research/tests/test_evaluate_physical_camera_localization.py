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
MODULE = load("evaluate_physical_camera_localization.py")
POLYGON = [[[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]]


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
        "geometryLockRef": "geometry_0000000000000001",
        "thresholdsLockedBeforeCameraFinal": True, "cameraFinalUsedForThresholdSelection": False,
        "geometryLockedBeforeCameraFinal": True, "cameraFinalUsedForGeometrySelection": False,
        "methodMutatedAfterLock": False, "geometryMutatedAfterLock": False,
        "geometryMethodVersion": MODULE.GEOMETRY_METHOD, "rasterResolution": MODULE.RESOLUTION,
        "records": [],
    }
    for row in truth["truth"]:
        positive = row["decision"] == "positive"
        receipt["records"].append({
            "captureRef": row["captureRef"], "classId": row["classId"],
            "decision": "positive" if positive else "negative",
            "geometrySource": "native-polygon-or-mask" if positive else "none",
            "polygons": copy.deepcopy(row["polygons"]),
        })
    return camera, truth, receipt


class CameraLocalizationEvaluationTest(unittest.TestCase):
    def test_perfect_union_masks_score_each_class_and_slice(self):
        result = MODULE.evaluate_localization(*fixtures())
        self.assertEqual(result["classMetrics"]["pimple"]["meanPositiveIoU"], 1.0)
        self.assertEqual(result["classMetrics"]["redness"]["microPositiveDice"], 1.0)
        self.assertEqual(result["sliceMetrics"]["pose"]["front"]["pimple"]["meanPositiveIoU"], 1.0)
        self.assertTrue(result["localizationMetricsComputed"])
        self.assertFalse(result["activationAllowed"])

    def test_partial_overlap_is_measured_without_acceptance_claim(self):
        camera, truth, receipt = fixtures()
        row = next(item for item in receipt["records"] if item["classId"] == "pimple" and item["decision"] == "positive")
        row["polygons"] = [[[0.2, 0.1], [0.4, 0.1], [0.4, 0.3], [0.2, 0.3]]]
        result = MODULE.evaluate_localization(camera, truth, receipt)
        self.assertGreater(result["classMetrics"]["pimple"]["meanPositiveIoU"], 0)
        self.assertLess(result["classMetrics"]["pimple"]["meanPositiveIoU"], 1)
        self.assertFalse(result["acceptanceThresholdsApplied"])

    def test_missing_positive_geometry_scores_zero_and_is_a_failure(self):
        camera, truth, receipt = fixtures()
        row = next(item for item in receipt["records"] if item["classId"] == "pimple" and item["decision"] == "positive")
        row.update({"decision": "negative", "geometrySource": "none", "polygons": []})
        result = MODULE.evaluate_localization(camera, truth, receipt)
        self.assertEqual(result["classMetrics"]["pimple"]["meanPositiveIoU"], 0)
        self.assertIn("missing_positive_geometry", {item["failure"] for item in result["failures"]})

    def test_false_positive_area_on_evaluated_negative_is_separate(self):
        camera, truth, receipt = fixtures()
        row = next(item for item in receipt["records"] if item["classId"] == "pimple" and item["decision"] == "negative")
        row.update({"decision": "positive", "geometrySource": "native-polygon-or-mask", "polygons": copy.deepcopy(POLYGON)})
        result = MODULE.evaluate_localization(camera, truth, receipt)
        metrics = result["classMetrics"]["pimple"]
        self.assertEqual(metrics["falsePositiveAreaCaptures"], 1)
        self.assertGreater(metrics["falsePositiveAreaPixelsOnEvaluatedNegative"], 0)
        self.assertEqual(result["classMetrics"]["redness"]["falsePositiveAreaCaptures"], 0)

    def test_box_geometry_and_box_fields_are_rejected(self):
        camera, truth, receipt = fixtures()
        positive = next(item for item in receipt["records"] if item["decision"] == "positive")
        positive["geometrySource"] = "box"
        with self.assertRaisesRegex(MODULE.CameraLocalizationError, "native polygon or mask"):
            MODULE.evaluate_localization(camera, truth, receipt)
        camera, truth, receipt = fixtures()
        receipt["records"][0]["bbox"] = [0.1, 0.1, 0.2, 0.2]
        with self.assertRaisesRegex(MODULE.CameraLocalizationError, "forbidden"):
            MODULE.evaluate_localization(camera, truth, receipt)

    def test_camera_final_cannot_select_or_mutate_geometry(self):
        cases = (
            ("geometryLockedBeforeCameraFinal", False, "locked"),
            ("cameraFinalUsedForGeometrySelection", True, "locked"),
            ("geometryMutatedAfterLock", True, "cannot change"),
            ("rasterResolution", 256, "identity changed"),
        )
        for field, value, message in cases:
            camera, truth, receipt = fixtures()
            receipt[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraLocalizationError, message):
                MODULE.evaluate_localization(camera, truth, receipt)

    def test_unknown_and_unassessable_are_excluded_not_negative(self):
        camera, truth, receipt = fixtures()
        pimple_rows = [row for row in truth["truth"] if row["classId"] == "pimple" and row["decision"] != "positive"]
        pimple_rows[0]["decision"] = "unknown"
        pimple_rows[1]["decision"] = "unassessable"
        result = MODULE.evaluate_localization(camera, truth, receipt)
        metrics = result["classMetrics"]["pimple"]
        self.assertEqual(metrics["eligibleTruthCaptures"], 1)
        self.assertEqual(metrics["unknownTruthExcluded"], 1)
        self.assertEqual(metrics["unassessableTruthExcluded"], 1)

    def test_missing_duplicate_and_private_tuning_fields_fail_closed(self):
        camera, truth, receipt = fixtures()
        receipt["records"].pop()
        with self.assertRaisesRegex(MODULE.CameraLocalizationError, "every camera/class"):
            MODULE.evaluate_localization(camera, truth, receipt)
        camera, truth, receipt = fixtures()
        receipt["records"].append(copy.deepcopy(receipt["records"][0]))
        with self.assertRaisesRegex(MODULE.CameraLocalizationError, "duplicate"):
            MODULE.evaluate_localization(camera, truth, receipt)
        for field in ("confidence", "score", "suggestedThreshold", "path", "email"):
            camera, truth, receipt = fixtures()
            receipt["records"][0][field] = 0.9
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraLocalizationError, "forbidden"):
                MODULE.evaluate_localization(camera, truth, receipt)

    def test_map_contract_and_truth_provenance_are_preserved(self):
        result = MODULE.evaluate_localization(*fixtures())
        self.assertEqual(result["mapContract"]["dry"], "blue")
        self.assertEqual(result["mapContract"]["oily"], "green")
        self.assertEqual(result["mapContract"]["unknown"], "light-grey-never-normal")
        self.assertTrue(result["rednessIndependentFromSensitivity"])
        self.assertFalse(result["modelGeometryUsedAsExpertTruth"])
        self.assertFalse(result["boxesAcceptedAsPolygons"])


if __name__ == "__main__":
    unittest.main()
