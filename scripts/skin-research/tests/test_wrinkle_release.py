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


class WrinkleReleaseTests(unittest.TestCase):
    def test_current_external_models_fail_closed(self):
        result = module.evaluate_release(
            _load("skin-face-crows-feet-external-model-receipt-20261025-v1.json"),
            _load("unrelated-wrinkles-external-model-receipt-20261025-v1.json"),
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["productActivationAllowed"])
        self.assertTrue(result["unrelatedWrinkle"]["diagnosticOnly"])
        self.assertFalse(result["unrelatedWrinkle"]["substitutionAllowed"])
        self.assertIn("expert_evaluated_negative_protocol_missing", result["blockers"])
        self.assertAlmostEqual(result["crowsFeet"]["test"]["f1"], 0.017)

    def test_identity_substitution_is_rejected(self):
        crows = _load("skin-face-crows-feet-external-model-receipt-20261025-v1.json")
        crows["modelId"] = "another-model"
        with self.assertRaisesRegex(module.GateInputError, "identity"):
            module.evaluate_release(crows, _load("unrelated-wrinkles-external-model-receipt-20261025-v1.json"))

    def test_known_unrelated_leakage_cannot_be_erased(self):
        unrelated = _load("unrelated-wrinkles-external-model-receipt-20261025-v1.json")
        unrelated["crossSplitCandidates"]["filename"] = 0
        with self.assertRaisesRegex(module.GateInputError, "leakage"):
            module.evaluate_release(_load("skin-face-crows-feet-external-model-receipt-20261025-v1.json"), unrelated)

    def test_complete_synthetic_crows_candidate_can_pass_gate(self):
        crows = copy.deepcopy(_load("skin-face-crows-feet-external-model-receipt-20261025-v1.json"))
        for field in (
            "expertNegativeProtocolComplete",
            "sourceGroupSplitIndependent",
            "untouchedFinalTest",
            "cameraHoldoutAccepted",
            "productIntegrationAccepted",
        ):
            crows[field] = True
        for split in ("valid", "test"):
            crows["perClass"][split]["crows_feet"] = {
                "map50": 0.8,
                "map50_95": 0.6,
                "map75": 0.5,
                "precision": 0.85,
                "recall": 0.75,
                "f1": 0.79,
            }
        crows["releasePolicy"] = {
            "expertApproved": True,
            "minimums": {key: 0.5 for key in module.REQUIRED_METRICS},
        }
        result = module.evaluate_release(crows, _load("unrelated-wrinkles-external-model-receipt-20261025-v1.json"))
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["productActivationAllowed"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["excludedAlternatives"], [
            "unrelated_wrinkle_model_dataset_lineage_mismatch",
            "unrelated_wrinkle_model_cross_split_leakage_candidates",
        ])


if __name__ == "__main__":
    unittest.main()
