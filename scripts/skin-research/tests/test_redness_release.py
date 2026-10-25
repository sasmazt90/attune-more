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
    path = ROOT / "docs" / "skin" / "evidence" / "redness-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class RednessReleaseTests(unittest.TestCase):
    def test_current_model_remains_research_only(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["researchVisualizationAllowed"])
        self.assertTrue(result["independentRedLayerRequired"])
        self.assertFalse(result["sensitivityInferenceAllowed"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["productActivationAllowed"])

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

    def test_complete_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        for field in (
            "rightsReviewed",
            "expertMaskAndNegativeProtocolComplete",
            "sourcePersonGroupSplitIndependent",
            "replacementSplitLocked",
            "newUntouchedFinalTestReserved",
            "independentCameraHoldoutReserved",
            "validationPassed",
            "newUntouchedFinalTestPassed",
            "physicalCameraHoldoutPassed",
            "workingProductIntegrationPassed",
            "overlapAndUnavailableControlsPassed",
        ):
            receipt["candidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["productActivationAllowed"])


if __name__ == "__main__":
    unittest.main()
