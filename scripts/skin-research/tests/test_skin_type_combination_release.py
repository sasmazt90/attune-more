import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_skin_type_combination_release.py"
spec = importlib.util.spec_from_file_location("check_skin_type_combination_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "skin-type-combination-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class SkinTypeCombinationReleaseTests(unittest.TestCase):
    def test_current_product_is_preserved_while_combination_fails_closed(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingGlobalSkinTypeFlowPreserved"])
        self.assertTrue(result["combinationRuleImplementationReady"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["combinationProductActivationAllowed"])
        self.assertIn("accepted_regional_method_registry_empty", result["trainingBlockers"])

    def test_whole_face_class_cannot_become_regional_truth(self):
        receipt = _receipt()
        receipt["roadmapImplementation"]["wholeFaceCopiedToRegionsAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "whole-face labels"):
            module.evaluate_release(receipt)

    def test_box_source_cannot_gain_polygon_or_normal_truth(self):
        receipt = _receipt()
        receipt["regionalBoxSource"]["nonEmptySegmentations"] = 5252
        with self.assertRaisesRegex(module.GateInputError, "cannot become polygon"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["regionalBoxSource"]["normalClassPresent"] = True
        with self.assertRaisesRegex(module.GateInputError, "no normal truth"):
            module.evaluate_release(receipt)

    def test_known_leaking_test_cannot_become_final_acceptance(self):
        receipt = _receipt()
        receipt["regionalBoxSource"]["testEligibleForFinalAcceptance"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become final"):
            module.evaluate_release(receipt)

    def test_t_zone_must_include_chin(self):
        receipt = _receipt()
        receipt["roadmapImplementation"]["tZone"] = ["forehead", "nose"]
        with self.assertRaisesRegex(module.GateInputError, "T-zone changed"):
            module.evaluate_release(receipt)

    def test_evidence_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["inputBlobs"]["roadmapLocalSkinType"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "input blobs changed"):
            module.evaluate_release(receipt)

    def test_complete_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        for field in (
            "rightsReviewedRegionalSources",
            "expertRegionalPolygonProtocolComplete",
            "evaluatedNormalNegativeTruthComplete",
            "sourcePersonGroupSplitIndependent",
            "acceptedMethodRegistryPopulated",
            "validationPassed",
            "untouchedFinalTestReserved",
            "untouchedFinalTestPassed",
            "physicalCameraHoldoutPassed",
            "workingProductIntegrationPassed",
        ):
            receipt["candidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["combinationProductActivationAllowed"])


if __name__ == "__main__":
    unittest.main()
