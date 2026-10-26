import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_redness_release.py"
spec = importlib.util.spec_from_file_location("check_redness_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "redness-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_training_prerequisites(receipt):
    for field in (
        "rightsReviewed",
        "expertMaskNegativeAmbiguityAndAssessabilityProtocolComplete",
        "illuminationWhiteBalanceMakeupAndAcneProtocolComplete",
        "personIndependentGroupingComplete",
        "groupLockedReplacementSplitVerified",
        "newUntouchedFinalTestAtLeast50Reserved",
        "independentCameraHoldoutReserved",
        "oneChangeValidationExperimentSpecified",
        "qualityPolicyLockedBeforeValidation",
    ):
        receipt["candidate"][field] = True


def _install_distinct_candidate(receipt):
    candidate = receipt["candidate"]
    candidate["mode"] = "new-model"
    candidate["projectId"] = module.EXPECTED_PROJECT_ID
    candidate["modelId"] = f"{module.EXPECTED_PROJECT_ID}-2-rfdetr-seg-small-t1"
    candidate["trainingId"] = "future-group-locked-redness-training"
    candidate["datasetVersion"] = 2
    candidate["trainedFromGroupLockedReplacementSplit"] = True
    candidate["candidateChangeMatchesPreRegisteredExperiment"] = True
    candidate["thresholdsLockedBeforeFinalTest"] = True
    candidate["instanceSegmentationPolygonOutputVerified"] = True
    candidate["separateRednessMetricsPassed"] = True


class RednessReleaseTests(unittest.TestCase):
    def test_current_model_remains_research_only_without_erasing_working_output(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertTrue(result["independentRedLayerRequired"])
        self.assertFalse(result["sensitivityInferenceAllowed"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertFalse(result["blindRetrainingAllowed"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["learnedRednessLayerActivationAllowed"])

    def test_redness_cannot_become_sensitivity(self):
        receipt = _receipt()
        receipt["semanticContract"]["sensitivityInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become sensitivity"):
            module.evaluate_release(receipt)

    def test_redness_must_remain_independent_overlap_layer(self):
        receipt = _receipt()
        receipt["semanticContract"]["independentLayer"] = False
        with self.assertRaisesRegex(module.GateInputError, "independent layer"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["semanticContract"]["mayOverlapDryOrOily"] = False
        with self.assertRaisesRegex(module.GateInputError, "overlap"):
            module.evaluate_release(receipt)

    def test_boxes_and_missing_masks_cannot_become_polygon_or_normal_truth(self):
        receipt = _receipt()
        receipt["semanticContract"]["boxAcceptedAsPolygon"] = True
        with self.assertRaisesRegex(module.GateInputError, "boxes"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["semanticContract"]["missingMaskMeansNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot mean normal"):
            module.evaluate_release(receipt)

    def test_exposed_small_test_cannot_become_untouched(self):
        receipt = _receipt()
        receipt["source"]["testAlreadyExposed"] = False
        with self.assertRaisesRegex(module.GateInputError, "cannot become untouched"):
            module.evaluate_release(receipt)

    def test_small_redness_failure_cannot_be_hidden(self):
        receipt = _receipt()
        receipt["model"]["diagnosticSmallObjectMap50"] = 0.5
        with self.assertRaisesRegex(module.GateInputError, "small redness diagnosis"):
            module.evaluate_release(receipt)

    def test_evidence_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["inputBlobs"]["modelDiagnosis"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "input blobs changed"):
            module.evaluate_release(receipt)

    def test_known_rejected_model_cannot_be_relabelled_as_candidate(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": module.EXPECTED_PROJECT_ID,
            "modelId": module.REJECTED_RESEARCH_MODEL_ID,
            "trainingId": "fake-new-training",
            "datasetVersion": 2,
        })
        with self.assertRaisesRegex(module.GateInputError, "cannot be relabelled"):
            module.evaluate_release(receipt)

    def test_version_one_nas_child_cannot_be_relabelled_as_version_two(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": module.EXPECTED_PROJECT_ID,
            "modelId": f"{module.EXPECTED_PROJECT_ID}-1-rfdetr-nas-seg-t1--2c07ef",
            "trainingId": "fake-new-training",
            "datasetVersion": 2,
        })
        result = module.evaluate_release(receipt)
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertIn("distinct_new_candidate_model_missing", result["testBlockers"])

    def test_candidate_must_belong_to_frozen_regional_project(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": "tolgar-sasmaz/other-redness-project",
            "modelId": "tolgar-sasmaz/other-redness-project-2-rfdetr-seg-small-t1",
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
            "lightingWhiteBalanceSkinTonePoseMakeupSlicesPassed",
            "workingProductIntegrationPassed",
            "overlapUnavailableAndHistoryControlsPassed",
        ):
            receipt["candidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["learnedRednessLayerActivationAllowed"])


if __name__ == "__main__":
    unittest.main()
