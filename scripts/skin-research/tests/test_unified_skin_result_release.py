import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_unified_skin_result_release.py"
spec = importlib.util.spec_from_file_location("check_unified_skin_result_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "unified-skin-result-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class UnifiedSkinResultReleaseTests(unittest.TestCase):
    def test_working_baseline_is_preserved_while_final_acceptance_is_blocked(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["workingBaselinePreserved"])
        self.assertTrue(result["currentIntegratedPresentationAllowed"])
        self.assertFalse(result["roadmapAccepted"])
        self.assertIn("real_browser_api_e2e_missing", result["blockers"])

    def test_generated_smoke_cannot_be_promoted_to_real_camera(self):
        receipt = _receipt()
        receipt["generatedSmoke"]["realCameraCapture"] = True
        with self.assertRaisesRegex(module.GateInputError, "real camera"):
            module.evaluate_release(receipt)

    def test_unknown_cannot_become_normal(self):
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["unknownCountsAsNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "count as normal"):
            module.evaluate_release(receipt)

    def test_redness_cannot_be_renamed_sensitivity(self):
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["rednessSensitivityAliasAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "sensitivity"):
            module.evaluate_release(receipt)

    def test_code_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["apps/vehicle-app/src/utils/regionalSkinMap.ts"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "implementation blobs"):
            module.evaluate_release(receipt)

    def test_complete_future_end_to_end_evidence_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        for field in receipt["acceptanceCandidate"]:
            receipt["acceptanceCandidate"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["finalRoadmapAcceptanceAllowed"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["blockers"], [])


if __name__ == "__main__":
    unittest.main()
