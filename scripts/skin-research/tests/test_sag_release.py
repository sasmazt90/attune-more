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
    path = ROOT / "docs" / "skin" / "evidence" / "sag-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_preparation(receipt):
    for field in (
        "sourceRightsAndScopeReviewed",
        "localizedExpertPolygonProtocolComplete",
        "sourcePersonGroupSplitIndependent",
        "poseExpressionProtocolComplete",
        "samePersonCaptureProtocolComplete",
        "qualityPolicyLockedBeforeValidation",
        "untouchedFinalTestReserved",
        "physicalCameraHoldoutReserved",
    ):
        receipt["preparation"][field] = True


def _install_candidate(receipt):
    candidate = receipt["candidate"]
    candidate.update({
        "mode": "accepted-localized-sag-method",
        "methodId": "localized-lower-face-sag-polygons-v2",
        "datasetReleaseId": "sag-expert-polygons-grouped-r2",
        "projectId": "tolgar-sasmaz/attune-skin-sag-localized",
        "datasetVersion": 2,
        "trainingId": "sag-training-v2",
        "modelId": "tolgar-sasmaz/attune-skin-sag-localized-2-model-v1",
        "captureProtocolId": "attune-camera-capture-protocol-v1",
        "lockedPolicyId": "sag-policy-v2",
        "acceptanceEvidence": {"path": "docs/skin/evidence/future-sag-candidate.json", "sha256": "a" * 64},
        "accepted": True,
        "truthSource": "adjudicated-localized-expert-polygons",
        "outputGeometry": "polygon",
        "thresholdSelectionSplit": "validation",
        "finalTestUsedForSelection": False,
        "clinicalClaimsDisabled": True,
        "elasticityClaimsDisabled": True,
    })
    validation = receipt["validation"]
    for field in ("methodId", "projectId", "datasetVersion", "trainingId", "modelId"):
        validation[field] = candidate[field]
    validation["acceptanceEvidence"] = {
        "path": "docs/skin/evidence/future-sag-validation.json",
        "sha256": "b" * 64,
    }


class SagReleaseTests(unittest.TestCase):
    def test_current_proxy_remains_visible_but_is_not_roadmap_acceptance(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertTrue(result["currentProxyPresentationAllowed"])
        self.assertEqual(result["currentProxyClaim"], "visible lower-face contour/fold appearance only")
        self.assertFalse(result["acceptedLocalizedMethodPresent"])
        self.assertFalse(result["localizedSagActivationAllowed"])
        self.assertFalse(result["roadmapAccepted"])

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

    def test_unknown_or_unassessable_cannot_become_normal(self):
        receipt = _receipt()
        receipt["semanticContract"]["unknownOrUnassessableMeansNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become normal"):
            module.evaluate_release(receipt)

    def test_code_and_camera_input_blob_drift_are_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["services/core-api/instant_appearance.py"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "blobs"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["inputBlobs"]["cameraLocalizationEvaluator"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "input blobs"):
            module.evaluate_release(receipt)

    def test_missing_candidate_cannot_claim_model_identity(self):
        receipt = _receipt()
        receipt["candidate"]["modelId"] = "fake-model"
        with self.assertRaisesRegex(module.GateInputError, "cannot claim"):
            module.evaluate_release(receipt)

    def test_base_proxy_is_not_a_distinct_localized_method(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["candidate"]["methodId"] = module.BASE_METHOD_ID
        with self.assertRaisesRegex(module.GateInputError, "distinct localized"):
            module.evaluate_release(receipt)

    def test_candidate_requires_group_locked_version_two_or_later(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["candidate"]["datasetVersion"] = 1
        with self.assertRaisesRegex(module.GateInputError, "version 2"):
            module.evaluate_release(receipt)

    def test_box_geometry_cannot_be_claimed_as_localized_sag_polygon(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["candidate"]["outputGeometry"] = "box"
        with self.assertRaisesRegex(module.GateInputError, "polygon geometry"):
            module.evaluate_release(receipt)

    def test_zero_digest_cannot_bind_candidate_acceptance(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["candidate"]["acceptanceEvidence"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(module.GateInputError, "sha256"):
            module.evaluate_release(receipt)

    def test_final_test_cannot_select_policy(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["candidate"]["finalTestUsedForSelection"] = True
        with self.assertRaisesRegex(module.GateInputError, "final test"):
            module.evaluate_release(receipt)

    def test_complete_preparation_authorizes_training_but_not_activation(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["acceptedLocalizedMethodPresent"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["localizedSagActivationAllowed"])

    def test_validation_must_bind_exact_training_and_model(self):
        receipt = _receipt()
        _complete_preparation(receipt)
        _install_candidate(receipt)
        receipt["validation"]["modelId"] = "different-model"
        with self.assertRaisesRegex(module.GateInputError, "candidate modelId"):
            module.evaluate_release(receipt)

    def test_complete_identity_bound_future_candidate_can_pass(self):
        receipt = copy.deepcopy(_receipt())
        _complete_preparation(receipt)
        _install_candidate(receipt)
        for field in (
            "validationPerClassPassed",
            "policyLockedBeforeFinalTest",
            "untouchedFinalTestPassed",
            "independentPhysicalCameraPassed",
            "poseExpressionRobustnessPassed",
            "samePersonRepeatabilityPassed",
            "deviceLightingSkinTonePoseSlicesPassed",
            "localizedPolygonGeometryPassed",
            "workingProductIntegrationPassed",
            "unknownUnavailableAndHistoryControlsPassed",
        ):
            receipt["validation"][field] = True
        result = module.evaluate_release(receipt)
        self.assertEqual(result["decision"], "ready")
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["localizedSagActivationAllowed"])
        self.assertTrue(result["roadmapAccepted"])


if __name__ == "__main__":
    unittest.main()
