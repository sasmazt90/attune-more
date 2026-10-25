import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_dryness_release.py"
spec = importlib.util.spec_from_file_location("check_dryness_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "dryness-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class DrynessReleaseTests(unittest.TestCase):
    def test_current_sources_remain_research_only(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["boxLocalizationResearchAllowed"])
        self.assertFalse(result["blueMaskFromBoxesAllowed"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["testEvaluationAuthorized"])
        self.assertFalse(result["productActivationAllowed"])
        self.assertIn("expert_dryness_flaking_semantic_policy_missing", result["trainingBlockers"])

    def test_box_counts_cannot_be_relabelled_as_polygons(self):
        receipt = _receipt()
        receipt["sources"]["merve"]["pulPolygons"] = 2590
        with self.assertRaisesRegex(module.GateInputError, "must not become polygons"):
            module.evaluate_release(receipt)

    def test_processed_images_cannot_become_natural_camera_calibration(self):
        receipt = _receipt()
        receipt["sources"]["merve"]["naturalCameraColourCalibrationAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "natural camera colour"):
            module.evaluate_release(receipt)

    def test_missing_annotations_cannot_become_normal(self):
        receipt = _receipt()
        receipt["sources"]["skinTypeBoxes"]["missingAnnotationMeansNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become normal"):
            module.evaluate_release(receipt)

    def test_evidence_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["inputBlobs"]["clean3"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "blobs changed"):
            module.evaluate_release(receipt)

    def test_complete_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        for field in (
            "rightsReviewedNaturalCameraSources",
            "expertSemanticPolicyComplete",
            "expertPolygonExtentReviewComplete",
            "evaluatedNegativeAndNormalRegionsComplete",
            "sourcePersonGroupSplitIndependent",
            "untouchedFinalTestReserved",
            "validationPassed",
            "untouchedFinalTestPassed",
            "physicalCameraHoldoutPassed",
            "workingProductIntegrationPassed",
        ):
            receipt["candidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["testEvaluationAuthorized"])
        self.assertTrue(result["productActivationAllowed"])
        self.assertEqual(result["activationBlockers"], [])


if __name__ == "__main__":
    unittest.main()
