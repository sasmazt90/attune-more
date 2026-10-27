import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_physical_camera_benchmark_release.py"
SPEC = importlib.util.spec_from_file_location("check_physical_camera_benchmark_release", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/physical-camera-benchmark-release-receipt-20261027-v2.json"


def receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def _write(root, name, payload):
    path = root / "docs" / "skin" / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {
        "path": f"docs/skin/evidence/{name}",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _install_complete_artifacts(candidate, root):
    classes = ["pimple"]
    method_ref = "method_1111111111111111"
    threshold_ref = "thresholds_2222222222222222"
    geometry_ref = "geometry_3333333333333333"
    policy_ref = "policy_4444444444444444"
    replay_ref = "replay_5555555555555555"
    captures = [
        {"captureRef": f"capture_{index:016x}"}
        for index in range(1, 4)
    ]
    artifacts = {
        "cameraManifest": {
            "methodVersion": "physical-camera-benchmark-manifest-v1",
            "sourceType": "physical-camera", "generated": False, "split": "camera_final",
            "subjectCount": 1, "captureCount": 3, "completeThreePoseTriplets": True,
            "subjectIndependentFromTrainingValidationThresholdSelection": True,
            "containsImageBytesOrPaths": False, "containsModelPredictions": False,
            "containsExpertTruth": False, "captures": captures,
        },
        "expertTruth": {
            "methodVersion": "physical-camera-expert-truth-v1",
            "cameraManifestMethodVersion": "physical-camera-benchmark-manifest-v1",
            "captureCount": 3, "activatedClasses": classes, "truthCellCount": 3,
            "twoIndependentHumanReviewsPerCell": True, "modelProposalUsedAsTruth": False,
            "missingTruthInterpretedAsNegative": False, "unknownInterpretedAsNormal": False,
            "rednessIndependentFromSensitivity": True, "rednessOverlapAllowed": True,
            "normalRequiresExplicitEvaluatedTruth": True,
        },
        "captureEvaluation": {
            "methodVersion": "physical-camera-capture-level-evaluation-v1",
            "evaluatedMethodRef": method_ref, "evaluatedMethodVersion": "skin-method-v1",
            "thresholdLockRef": threshold_ref, "cameraFinalUsedForThresholdSelection": False,
            "classMetrics": {"pimple": {}}, "captureLevelMetricsComputed": True,
            "activationAllowed": False,
        },
        "localizationEvaluation": {
            "methodVersion": "physical-camera-localization-evaluation-v1",
            "evaluatedMethodRef": method_ref, "evaluatedMethodVersion": "skin-method-v1",
            "thresholdLockRef": threshold_ref, "geometryLockRef": geometry_ref,
            "cameraFinalUsedForThresholdSelection": False,
            "cameraFinalUsedForGeometrySelection": False, "classMetrics": {"pimple": {}},
            "localizationMetricsComputed": True, "activationAllowed": False,
            "boxesAcceptedAsPolygons": False, "modelGeometryUsedAsExpertTruth": False,
        },
        "acceptancePolicy": {
            "methodVersion": "physical-camera-acceptance-policy-v1",
            "policyRef": policy_ref, "lockedBeforeCameraFinal": True,
            "cameraFinalUsedForPolicySelection": False, "policyMutatedAfterLock": False,
            "appliesToMethodRef": method_ref, "appliesToMethodVersion": "skin-method-v1",
            "thresholdLockRef": threshold_ref, "geometryLockRef": geometry_ref,
            "applyPerClassWithoutMacroAveraging": True,
            "applySameMinimumsToEveryObservedSlice": True,
            "classes": [{"classId": "pimple"}],
        },
        "productReplay": {
            "methodVersion": "physical-camera-product-replay-v1", "replayRef": replay_ref,
            "sourceType": "physical-camera", "generated": False, "split": "camera_final",
            "endpoint": "/api/local-health/skin", "evaluatedMethodRef": method_ref,
            "evaluatedMethodVersion": "skin-method-v1", "thresholdLockRef": threshold_ref,
            "geometryLockRef": geometry_ref, "realBrowser": True, "apiPassed": True,
            "overviewPassed": True, "everyRegionPassed": True, "mapPassed": True,
            "historyWriteReadPassed": True, "methodIncompatibleHistoryExcluded": True,
            "unavailableStatePassed": True, "retainedPhotoReplayPassed": True,
            "privacyRetentionDeletionPassed": True, "normalRequiresExplicitEvaluatedTruth": True,
            "unknownNeverRenderedAsNormal": True, "rednessIndependentFromSensitivity": True,
            "rednessOverlapAllowed": True, "physicalCaptureCount": 3,
            "classes": [{"classId": "pimple"}],
        },
        "acceptanceGate": {
            "methodVersion": "physical-camera-acceptance-gate-v1",
            "policyRef": policy_ref, "evaluatedMethodRef": method_ref,
            "evaluatedMethodVersion": "skin-method-v1", "thresholdLockRef": threshold_ref,
            "geometryLockRef": geometry_ref, "everyClassPassedIndependently": True,
            "everyObservedSlicePassedIndependently": True, "macroAveragingUsed": False,
            "trainingFinishedOrRecommendedUsedAsAcceptance": False,
            "realProductReplayPassed": True, "mapContractPassed": True,
            "cameraAccepted": True, "activationAllowed": True,
            "classVerdicts": {"pimple": {"passed": True}},
        },
    }
    candidate["artifacts"] = {
        name: _write(root, f"physical-camera-{name}.json", payload)
        for name, payload in artifacts.items()
    }
    for field in (
        "consentedPhysicalCaptures", "immutableCaptureHashes", "subjectIdentityIndependent",
        "notUsedForTrainingValidationOrThresholdSelection", "expertTruthPerActivatedClass",
        "evaluatedNegativeAndUnknownPolicy", "deviceLightingSkinTonePoseSlices",
        "captureQualityGateRecorded", "lockedThresholdsAndMethodIdentity",
        "perClassMetricsAndFailuresRecorded", "apiBrowserMapHistoryReplayPassed",
        "privacyRetentionDeletionPassed",
    ):
        candidate[field] = True
    candidate.update({
        "benchmarkId": "camera_benchmark_" + candidate["artifacts"]["cameraManifest"]["sha256"][:16],
        "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": "skin-method-v1",
        "thresholdLockRef": threshold_ref,
        "geometryLockRef": geometry_ref,
        "policyRef": policy_ref,
        "replayRef": replay_ref,
    })


class PhysicalCameraBenchmarkGateTest(unittest.TestCase):
    def test_current_generated_package_is_smoke_only(self):
        result = MODULE.evaluate_release(receipt())
        self.assertTrue(result["workingBaselinePreserved"])
        self.assertTrue(result["generatedIntegrationSmokeAllowed"])
        self.assertFalse(result["generatedAccuracyEvidenceAllowed"])
        self.assertFalse(result["physicalCameraBenchmarkAccepted"])
        self.assertFalse(result["evidenceRegistryComplete"])
        self.assertIn("cameraManifest_evidence_missing", result["blockers"])

    def test_generated_source_cannot_be_relabelled_as_camera_or_expert_truth(self):
        bad = receipt()
        bad["generatedEvidence"]["realCameraCapture"] = True
        with self.assertRaisesRegex(MODULE.CameraGateError, "cannot become physical camera"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["generatedEvidence"]["expertGroundTruth"] = True
        with self.assertRaisesRegex(MODULE.CameraGateError, "cannot become expert truth"):
            MODULE.evaluate_release(bad)

    def test_working_product_output_cannot_be_marked_missing(self):
        bad = receipt()
        bad["workingBaseline"]["productAlreadyProducesConcreteResults"] = False
        with self.assertRaisesRegex(MODULE.CameraGateError, "cannot become missing"):
            MODULE.evaluate_release(bad)

    def test_threshold_leakage_missing_labels_and_redness_alias_fail_hard(self):
        bad = receipt()
        bad["acceptanceContract"]["thresholdsMayBeFitOnCameraFinal"] = True
        with self.assertRaisesRegex(MODULE.CameraGateError, "cannot fit thresholds"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["acceptanceContract"]["missingClassTruthMeansNegative"] = True
        with self.assertRaisesRegex(MODULE.CameraGateError, "cannot become negative"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["acceptanceContract"]["rednessIsIndependentLayer"] = False
        with self.assertRaisesRegex(MODULE.CameraGateError, "redness must remain independent"):
            MODULE.evaluate_release(bad)

    def test_receipt_booleans_alone_cannot_pass(self):
        future = copy.deepcopy(receipt())
        for key, value in list(future["physicalCameraCandidate"].items()):
            if isinstance(value, bool):
                future["physicalCameraCandidate"][key] = True
        result = MODULE.evaluate_release(future)
        self.assertFalse(result["physicalCameraBenchmarkAccepted"])
        self.assertIn("cameraManifest_evidence_missing", result["blockers"])

    def test_complete_sha_bound_pipeline_can_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            _install_complete_artifacts(future["physicalCameraCandidate"], Path(directory))
            result = MODULE.evaluate_release(future, Path(directory))
        self.assertTrue(result["physicalCameraBenchmarkAccepted"])
        self.assertTrue(result["evidenceRegistryComplete"])
        self.assertEqual(result["physicalCameraBenchmarkIdentity"]["activatedClasses"], ["pimple"])
        self.assertFalse(result["generatedPhysicalCameraAcceptanceAllowed"])

    def test_artifact_digest_and_cross_identity_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            root = Path(directory)
            _install_complete_artifacts(future["physicalCameraCandidate"], root)
            future["physicalCameraCandidate"]["artifacts"]["expertTruth"]["sha256"] = "a" * 64
            with self.assertRaisesRegex(MODULE.CameraGateError, "digest mismatch"):
                MODULE.evaluate_release(future, root)

        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            root = Path(directory)
            _install_complete_artifacts(future["physicalCameraCandidate"], root)
            future["physicalCameraCandidate"]["thresholdLockRef"] = "thresholds_aaaaaaaaaaaaaaaa"
            with self.assertRaisesRegex(MODULE.CameraGateError, "thresholdLockRef changed"):
                MODULE.evaluate_release(future, root)

    def test_stale_receipt_schema_is_rejected(self):
        bad = receipt()
        bad["schemaVersion"] = 1
        with self.assertRaisesRegex(MODULE.CameraGateError, "receipt schema"):
            MODULE.evaluate_release(bad)


if __name__ == "__main__":
    unittest.main()
