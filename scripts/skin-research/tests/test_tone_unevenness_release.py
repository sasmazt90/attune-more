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
    path = ROOT / "docs" / "skin" / "evidence" / "tone-unevenness-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_preparation(receipt):
    for field in (
        "cameraCalibrationProtocolComplete",
        "sourcePersonIndependentCalibrationSplit",
        "adjudicatedExpertToneTruthComplete",
        "qualityPolicyLockedBeforeValidation",
        "untouchedPhysicalCameraFinalReserved",
    ):
        receipt["preparation"][field] = True


def _install_calibrated_candidate(receipt):
    candidate = receipt["candidate"]
    candidate.update({
        "mode": "accepted-calibrated-proxy",
        "methodId": "regional-cielab-chromatic-variation-calibrated-v2",
        "calibrationReleaseId": "tone-calibration-release-v2",
        "cameraBenchmarkId": "physical-camera-tone-final-v1",
        "captureProtocolId": "attune-camera-capture-protocol-v1",
        "lockedPolicyId": "tone-policy-v2",
        "acceptanceEvidence": {"path": "docs/skin/evidence/future-tone-acceptance.json", "sha256": "a" * 64},
        "accepted": True,
        "truthSource": "adjudicated-physical-camera",
        "thresholdSelectionSplit": "validation",
        "cameraFinalUsedForSelection": False,
    })
    receipt["calibrationValidation"]["methodId"] = candidate["methodId"]
    receipt["calibrationValidation"]["acceptanceEvidence"] = {
        "path": "docs/skin/evidence/future-tone-validation.json",
        "sha256": "b" * 64,
    }


class ToneUnevennessReleaseTests(unittest.TestCase):
    def test_current_proxy_remains_visible_without_claiming_roadmap_acceptance(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertTrue(result["currentProxyPresentationAllowed"])
        self.assertEqual(result["currentProxyClaim"], "broad regional chromatic-variation appearance only")
        self.assertFalse(result["clinicalSeverityClaimAllowed"])
        self.assertFalse(result["acceptedCalibratedMethodPresent"])
        self.assertFalse(result["calibratedToneActivationAllowed"])
        self.assertFalse(result["roadmapAccepted"])

    def test_tone_cannot_supply_localized_pigmentation_or_post_acne(self):
        receipt = _receipt()
        receipt["semanticContract"]["toneCanSupplyPigmentation"] = True
        with self.assertRaisesRegex(module.GateInputError, "populate Pigmentation"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["semanticContract"]["toneCanSupplyPostAcne"] = True
        with self.assertRaisesRegex(module.GateInputError, "populate Post acne"):
            module.evaluate_release(receipt)

    def test_unknown_or_unassessable_cannot_become_normal(self):
        receipt = _receipt()
        receipt["semanticContract"]["unknownOrUnassessableMeansNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become normal"):
            module.evaluate_release(receipt)

    def test_code_and_camera_gate_blob_drift_are_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["services/core-api/skin_general.py"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "blobs"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["inputBlobs"]["cameraBenchmarkReleaseGate"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "input blobs"):
            module.evaluate_release(receipt)

    def test_uncalibrated_proxy_cannot_claim_method_identity(self):
        receipt = _receipt()
        receipt["candidate"]["methodId"] = "fake-ready-method"
        with self.assertRaisesRegex(module.GateInputError, "cannot claim"):
            module.evaluate_release(receipt)

    def test_base_proxy_identity_is_not_a_distinct_calibrated_method(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_calibrated_candidate(receipt)
        receipt["candidate"]["methodId"] = module.BASE_METHOD_ID
        with self.assertRaisesRegex(module.GateInputError, "distinct calibrated"):
            module.evaluate_release(receipt)

    def test_zero_digest_cannot_bind_calibration_acceptance(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_calibrated_candidate(receipt)
        receipt["candidate"]["acceptanceEvidence"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(module.GateInputError, "sha256"):
            module.evaluate_release(receipt)

    def test_camera_final_cannot_select_policy(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_calibrated_candidate(receipt)
        receipt["candidate"]["cameraFinalUsedForSelection"] = True
        with self.assertRaisesRegex(module.GateInputError, "camera final"):
            module.evaluate_release(receipt)

    def test_complete_preparation_authorizes_evaluation_but_not_activation(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        result = module.evaluate_release(receipt)
        self.assertTrue(result["calibrationEvaluationAuthorized"])
        self.assertFalse(result["acceptedCalibratedMethodPresent"])
        self.assertFalse(result["calibratedToneActivationAllowed"])

    def test_accepted_local_support_must_be_excluded_before_coreporting(self):
        receipt = _receipt()
        localized = receipt["localizedSupport"]
        localized.update({
            "mode": "accepted-localized-methods",
            "methodIds": ["accepted-pigmentation-detector-v2"],
            "acceptanceEvidence": {"path": "docs/skin/evidence/future-localized.json", "sha256": "c" * 64},
            "accepted": True,
        })
        result = module.evaluate_release(receipt)
        self.assertFalse(result["localizedCoReportingAllowed"])
        self.assertIn("accepted_localized_support_not_excluded_from_tone", result["activationBlockers"])

    def test_validation_must_bind_exact_calibrated_method(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_calibrated_candidate(receipt)
        receipt["calibrationValidation"]["methodId"] = "different-method"
        with self.assertRaisesRegex(module.GateInputError, "not bound"):
            module.evaluate_release(receipt)

    def test_complete_identity_bound_future_calibration_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        _complete_preparation(receipt)
        _install_calibrated_candidate(receipt)
        for field in (
            "illuminationShadowHairWhiteBalanceRobustnessPassed",
            "skinToneSubgroupCalibrationPassed",
            "samePersonRepeatabilityPassed",
            "policyLockedBeforeCameraFinal",
            "untouchedPhysicalCameraFinalPassed",
            "deviceLightingSkinTonePoseSlicesPassed",
            "workingProductIntegrationPassed",
            "unknownUnavailableAndHistoryControlsPassed",
        ):
            receipt["calibrationValidation"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["acceptedCalibratedMethodPresent"])
        self.assertTrue(result["calibratedToneActivationAllowed"])
        self.assertTrue(result["roadmapAccepted"])


if __name__ == "__main__":
    unittest.main()
