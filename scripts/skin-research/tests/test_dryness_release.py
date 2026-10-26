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
    path = ROOT / "docs" / "skin" / "evidence" / "dryness-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_training_prerequisites(receipt):
    for field in (
        "rightsReviewedNaturalCameraSources",
        "expertSemanticPolicyComplete",
        "expertPolygonExtentReviewComplete",
        "evaluatedNegativeAndNormalRegionsComplete",
        "sourcePersonGroupSplitIndependent",
        "groupLockedReplacementSplitVerified",
        "newUntouchedFinalTestReserved",
        "independentCameraHoldoutReserved",
        "oneChangeValidationExperimentSpecified",
        "qualityPolicyLockedBeforeValidation",
    ):
        receipt["candidate"][field] = True


def _install_distinct_candidate(receipt):
    candidate = receipt["candidate"]
    candidate["mode"] = "new-model"
    candidate["projectId"] = module.EXPECTED_PROJECT_ID
    candidate["modelId"] = f"{module.EXPECTED_PROJECT_ID}-2-rfdetr-seg-small-t3"
    candidate["trainingId"] = "future-group-locked-dryness-training"
    candidate["datasetVersion"] = 2
    candidate["trainedFromGroupLockedReplacementSplit"] = True
    candidate["candidateChangeMatchesPreRegisteredExperiment"] = True
    candidate["thresholdsLockedBeforeFinalTest"] = True
    candidate["instanceSegmentationPolygonOutputVerified"] = True
    candidate["dryClassMetricReportedSeparately"] = True


class DrynessReleaseTests(unittest.TestCase):
    def test_current_sources_remain_research_only(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["boxLocalizationResearchAllowed"])
        self.assertFalse(result["blueMaskFromBoxesAllowed"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertFalse(result["blindRetrainingAllowed"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["learnedBlueRegionalMaskActivationAllowed"])
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

    def test_working_concrete_result_baseline_cannot_be_erased(self):
        receipt = _receipt()
        receipt["workingBaseline"]["productAlreadyProducesConcreteResults"] = False
        with self.assertRaisesRegex(module.GateInputError, "working product result baseline"):
            module.evaluate_release(receipt)

    def test_current_oily_redness_project_cannot_gain_dry_truth_implicitly(self):
        receipt = _receipt()
        receipt["currentRoboflowState"]["dryClassPresent"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot gain Dry truth"):
            module.evaluate_release(receipt)

    def test_not_trained_candidate_cannot_claim_identity(self):
        receipt = _receipt()
        receipt["candidate"]["modelId"] = "fabricated-model"
        with self.assertRaisesRegex(module.GateInputError, "cannot claim a model identity"):
            module.evaluate_release(receipt)

    def test_version_one_model_cannot_be_relabelled_as_version_two(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": module.EXPECTED_PROJECT_ID,
            "modelId": f"{module.EXPECTED_PROJECT_ID}-1-rfdetr-seg-small-t2",
            "trainingId": "fake-new-training",
            "datasetVersion": 2,
        })
        result = module.evaluate_release(receipt)
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertIn("distinct_dryness_candidate_model_missing", result["testBlockers"])

    def test_candidate_must_belong_to_frozen_regional_project(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": "tolgar-sasmaz/attune-skin-type-regional-r1",
            "modelId": "tolgar-sasmaz/attune-skin-type-regional-r1-2-rfdetr-small-t3",
            "trainingId": "future-training",
            "datasetVersion": 2,
        })
        with self.assertRaisesRegex(module.GateInputError, "frozen regional mask project"):
            module.evaluate_release(receipt)

    def test_completed_pre_model_evidence_authorizes_only_targeted_training(self):
        receipt = _receipt()
        _complete_training_prerequisites(receipt)
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["roadmapAccepted"])

    def test_box_output_cannot_pass_as_polygon_candidate(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        receipt["candidate"]["instanceSegmentationPolygonOutputVerified"] = False
        result = module.evaluate_release(receipt)
        self.assertIn("polygon_mask_output_verification_missing", result["testBlockers"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])

    def test_complete_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for field in (
            "validationPassed",
            "newUntouchedFinalTestPassed",
            "physicalCameraHoldoutPassed",
            "lightingSkinTonePoseSlicesPassed",
            "workingProductIntegrationPassed",
            "regionalCoverageOverlapAndUnavailableControlsPassed",
        ):
            receipt["candidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["learnedBlueRegionalMaskActivationAllowed"])
        self.assertEqual(result["activationBlockers"], [])


if __name__ == "__main__":
    unittest.main()
