import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_wrinkle_release.py"
spec = importlib.util.spec_from_file_location("check_wrinkle_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _load(name):
    return json.loads((ROOT / "docs" / "skin" / "evidence" / name).read_text(encoding="utf-8"))


def _inputs():
    return (
        _load("skin-face-crows-feet-external-model-receipt-20261025-v1.json"),
        _load("unrelated-wrinkles-external-model-receipt-20261025-v1.json"),
        _load("wrinkle-per-class-release-receipt-20261026-v1.json"),
    )


class WrinkleReleaseTests(unittest.TestCase):
    def test_current_external_models_and_candidate_fail_closed(self):
        result = module.evaluate_release(*_inputs())
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["roadmapAccepted"])
        self.assertFalse(result["currentExternalCrowsFeet"]["modelAccepted"])
        self.assertTrue(result["currentExternalCrowsFeet"]["diagnosticOnly"])
        self.assertFalse(result["unrelatedWrinkle"]["substitutionAllowed"])
        self.assertIn("expert_per_class_protocol_missing", result["researchTrainingBlockers"])
        self.assertAlmostEqual(result["currentExternalCrowsFeet"]["metrics"]["test"]["f1"], 0.017)

    def test_rejected_external_model_cannot_be_rewritten_as_accepted(self):
        crows, unrelated, candidate = _inputs()
        crows["activationAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become activated"):
            module.evaluate_release(crows, unrelated, candidate)

    def test_external_metrics_cannot_be_rewritten_post_hoc(self):
        crows, unrelated, candidate = _inputs()
        crows["perClass"]["test"]["crows_feet"]["f1"] = 0.9
        with self.assertRaisesRegex(module.GateInputError, "diagnostic metrics changed"):
            module.evaluate_release(crows, unrelated, candidate)

    def test_missing_label_cannot_become_negative_truth(self):
        crows, unrelated, candidate = _inputs()
        candidate["semanticContract"]["missingLabelMeansNegative"] = True
        with self.assertRaisesRegex(module.GateInputError, "negative truth"):
            module.evaluate_release(crows, unrelated, candidate)

    def test_known_external_model_cannot_be_relabelled_as_new_candidate(self):
        crows, unrelated, candidate = _inputs()
        candidate["candidate"]["mode"] = "new-model"
        candidate["candidate"]["modelId"] = module.CROWS_IDENTITY["modelId"]
        with self.assertRaisesRegex(module.GateInputError, "cannot be relabelled"):
            module.evaluate_release(crows, unrelated, candidate)

    def test_completed_pre_model_evidence_can_authorize_one_targeted_training(self):
        crows, unrelated, candidate = copy.deepcopy(_inputs())
        for field in (
            "selectedDatasetIdentityVerified",
            "rightsReviewed",
            "expertPerClassPositiveNegativeAmbiguityProtocolComplete",
            "sourcePersonGroupedSplitLocked",
            "poseExpressionProtocolComplete",
            "newUntouchedFinalTestReserved",
            "independentCameraHoldoutReserved",
            "qualityPolicyLockedBeforeValidation",
        ):
            candidate["candidate"][field] = True
        result = module.evaluate_release(crows, unrelated, candidate)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["classDecisions"]["crows_feet"]["finalTestEvaluationAuthorized"])
        self.assertFalse(result["roadmapAccepted"])

    def test_complete_distinct_crows_feet_candidate_can_pass(self):
        crows, unrelated, candidate = copy.deepcopy(_inputs())
        next_candidate = candidate["candidate"]
        next_candidate["mode"] = "new-model"
        next_candidate["modelId"] = "tolgar-sasmaz/future-crows-feet-2-rfdetr-seg-small-t1"
        for field in (
            "selectedDatasetIdentityVerified",
            "rightsReviewed",
            "expertPerClassPositiveNegativeAmbiguityProtocolComplete",
            "sourcePersonGroupedSplitLocked",
            "poseExpressionProtocolComplete",
            "newUntouchedFinalTestReserved",
            "independentCameraHoldoutReserved",
            "qualityPolicyLockedBeforeValidation",
            "thresholdsLockedBeforeFinalTest",
        ):
            next_candidate[field] = True
        for field in next_candidate["classes"]["crows_feet"]:
            next_candidate["classes"]["crows_feet"][field] = True
        result = module.evaluate_release(crows, unrelated, candidate)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["classDecisions"]["crows_feet"]["productActivationAllowed"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["decision"], "ready")

    def test_supported_optional_class_must_pass_independently(self):
        crows, unrelated, candidate = copy.deepcopy(_inputs())
        next_candidate = candidate["candidate"]
        next_candidate["classes"]["forehead"] = {
            "labelSupported": True,
            "validationPassed": False,
            "newUntouchedFinalTestPassed": False,
            "physicalCameraHoldoutPassed": False,
            "skinToneLightingPoseSlicesPassed": False,
            "workingProductIntegrationPassed": False,
            "unavailableAndHistoryControlsPassed": False,
        }
        result = module.evaluate_release(crows, unrelated, candidate)
        self.assertEqual(result["classDecisions"]["forehead"]["decision"], "blocked")
        self.assertFalse(result["classDecisions"]["crows_feet"]["productActivationAllowed"])
        self.assertFalse(result["roadmapAccepted"])


if __name__ == "__main__":
    unittest.main()
