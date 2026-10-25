import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_tone_unevenness_release.py"
spec = importlib.util.spec_from_file_location("check_tone_unevenness_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "tone-unevenness-release-receipt-20261025-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ToneUnevennessReleaseTests(unittest.TestCase):
    def test_current_proxy_remains_narrowly_presented_while_acceptance_is_blocked(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["currentProxyPresentationAllowed"])
        self.assertEqual(result["currentProxyClaim"], "broad regional chromatic-variation appearance only")
        self.assertFalse(result["clinicalSeverityClaimAllowed"])
        self.assertFalse(result["roadmapAccepted"])
        self.assertIn("untouched_camera_holdout_missing", result["blockers"])

    def test_tone_cannot_supply_localized_pigmentation(self):
        receipt = _receipt()
        receipt["semanticContract"]["toneCanSupplyPigmentation"] = True
        with self.assertRaisesRegex(module.GateInputError, "populate Pigmentation"):
            module.evaluate_release(receipt)

    def test_localized_headings_cannot_be_derived_from_tone(self):
        receipt = _receipt()
        receipt["candidate"]["localizedHeadingsDerivedFromTone"] = True
        with self.assertRaisesRegex(module.GateInputError, "derived from tone"):
            module.evaluate_release(receipt)

    def test_code_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["services/core-api/skin_general.py"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "blobs"):
            module.evaluate_release(receipt)

    def test_accepted_local_support_must_be_excluded_before_coreporting(self):
        receipt = _receipt()
        receipt["candidate"]["acceptedLocalizedPigmentationSupportAvailable"] = True
        result = module.evaluate_release(receipt)
        self.assertFalse(result["localizedCoReportingAllowed"])
        self.assertIn("accepted_localized_support_not_excluded_from_tone", result["blockers"])

    def test_complete_future_camera_and_coreporting_evidence_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        candidate = receipt["candidate"]
        for field in (
            "cameraCalibrationProtocolComplete",
            "illuminationShadowHairRobustnessPassed",
            "skinToneSubgroupCalibrationPassed",
            "samePersonRepeatabilityPassed",
            "untouchedCameraHoldoutPassed",
            "workingProductIntegrationPassed",
            "acceptedLocalizedPigmentationSupportAvailable",
            "localizedSupportExcludedFromToneSampling",
            "coReportingIndependentCameraPassed",
        ):
            candidate[field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["localizedCoReportingAllowed"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["blockers"], [])


if __name__ == "__main__":
    unittest.main()
