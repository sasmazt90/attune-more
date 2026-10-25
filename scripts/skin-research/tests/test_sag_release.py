import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_sag_release.py"
spec = importlib.util.spec_from_file_location("check_sag_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "sag-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class SagReleaseTests(unittest.TestCase):
    def test_current_proxy_is_presented_narrowly_but_not_accepted_as_model(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["currentProxyPresentationAllowed"])
        self.assertEqual(result["currentProxyClaim"], "visible lower-face contour/fold appearance only")
        self.assertFalse(result["crossPersonComparisonAllowed"])
        self.assertFalse(result["productActivationAllowed"])
        self.assertIn("localized_learned_model_missing", result["blockers"])

    def test_elasticity_cannot_be_substituted_for_sag(self):
        receipt = _receipt()
        receipt["sourceAudit"]["containsSagTarget"] = True
        with self.assertRaisesRegex(module.GateInputError, "relabelled"):
            module.evaluate_release(receipt)

    def test_whole_face_ordinal_candidate_is_rejected(self):
        receipt = _receipt()
        receipt["candidate"]["mode"] = "whole-face-ordinal"
        with self.assertRaisesRegex(module.GateInputError, "whole-face ordinal"):
            module.evaluate_release(receipt)

    def test_code_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["services/core-api/skin_product_contract.py"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "blobs"):
            module.evaluate_release(receipt)

    def test_complete_future_localized_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        candidate = receipt["candidate"]
        candidate["mode"] = "localized-sag-appearance-model"
        for field in (
            "localizedExpertTruthComplete",
            "sourceGroupSplitIndependent",
            "poseExpressionProtocolComplete",
            "samePersonCaptureProtocolComplete",
            "validationPassed",
            "untouchedTestPassed",
            "cameraHoldoutPassed",
            "productIntegrationPassed",
        ):
            candidate[field] = True
        candidate["untouchedTestReserved"] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["testEvaluationAuthorized"])
        self.assertTrue(result["productActivationAllowed"])
        self.assertEqual(result["blockers"], [])


if __name__ == "__main__":
    unittest.main()
