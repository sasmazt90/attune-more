import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = ROOT / "scripts/skin-research/skin_model_acceptance_gate.py"
SPEC = importlib.util.spec_from_file_location("skin_model_acceptance_gate", GATE_PATH)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ProviderFinishedTrainingReceiptsTest(unittest.TestCase):
    def test_all_new_candidates_fail_closed(self):
        names = (
            "acne-rfdetr-small-t2-model-receipt-20261025-v1.json",
            "regional-rfdetr-seg-small-t2-model-receipt-20261025-v1.json",
            "under-eye-ungrouped-rfdetr-seg-small-t1-model-receipt-20261025-v1.json",
        )
        for name in names:
            with self.subTest(name=name):
                receipt = json.loads((ROOT / "docs/skin/evidence" / name).read_text("utf8"))
                verdict = GATE.evaluate(receipt)
                verdict_name = name.replace("-model-receipt-", "-model-verdict-")
                persisted = json.loads((ROOT / "docs/skin/evidence" / verdict_name).read_text("utf8"))
                self.assertFalse(receipt["evaluation"]["thresholdsLockedBeforeTest"])
                self.assertFalse(verdict["accepted"])
                self.assertFalse(verdict["activationAllowed"])
                self.assertIn("THRESHOLDS_NOT_LOCKED_BEFORE_TEST", verdict["reasons"])
                self.assertEqual(persisted, verdict)

    def test_provider_receipt_binds_exact_evaluations(self):
        evidence = json.loads((ROOT / "docs/skin/evidence/provider-finished-trainings-20261025-v1.json").read_text("utf8"))
        evaluated = evidence["evaluatedInThisReceipt"]
        self.assertEqual(evaluated["acneMarksPigmentation"]["evaluationId"], "7s06OfIzx78XzATqr5oA")
        self.assertEqual(evaluated["regionalOilyRedness"]["evaluationId"], "vsQ6klUgSohCdtLwNMJf")
        self.assertEqual(evaluated["underEyePilotUngrouped"]["evaluationId"], "ntJE3M4iMTVBPCg2HwIb")
        self.assertFalse(evidence["testExposure"]["thresholdsLockedBeforeThisIndependentTestRead"])
        self.assertFalse(any(evidence["actions"].values()))


if __name__ == "__main__":
    unittest.main()
