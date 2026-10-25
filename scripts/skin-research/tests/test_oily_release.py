import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_oily_release.py"
spec = importlib.util.spec_from_file_location("check_oily_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "oily-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class OilyReleaseTests(unittest.TestCase):
    def test_current_model_remains_research_only_without_erasing_working_output(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingAppearanceProxyPreserved"])
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["learnedRegionalMaskActivationAllowed"])

    def test_whole_face_class_cannot_be_copied_to_regions(self):
        receipt = _receipt()
        receipt["semanticContract"]["wholeFaceReplicationAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "whole-face"):
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

    def test_clinical_sebum_claim_is_rejected(self):
        receipt = _receipt()
        receipt["semanticContract"]["clinicalSebumDiagnosis"] = True
        with self.assertRaisesRegex(module.GateInputError, "clinical sebum"):
            module.evaluate_release(receipt)

    def test_exposed_small_test_cannot_become_untouched(self):
        receipt = _receipt()
        receipt["source"]["testAlreadyExposed"] = False
        with self.assertRaisesRegex(module.GateInputError, "cannot become untouched"):
            module.evaluate_release(receipt)

    def test_localization_failure_cannot_be_hidden(self):
        receipt = _receipt()
        receipt["model"]["validationMap75"] = 0.5
        with self.assertRaisesRegex(module.GateInputError, "validation map75"):
            module.evaluate_release(receipt)

    def test_evidence_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["inputBlobs"]["modelDiagnosis"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "input blobs changed"):
            module.evaluate_release(receipt)

    def test_complete_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        for field in (
            "rightsReviewed",
            "expertMaskNegativeAndAssessabilityProtocolComplete",
            "illuminationShineAndGlareProtocolComplete",
            "sourcePersonGroupSplitIndependent",
            "replacementSplitLocked",
            "newUntouchedFinalTestReserved",
            "independentCameraHoldoutReserved",
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
        self.assertTrue(result["learnedRegionalMaskActivationAllowed"])


if __name__ == "__main__":
    unittest.main()
