import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_independent_camera_reservation.py"
SPEC = importlib.util.spec_from_file_location("build_source_independent_camera_reservation", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def complete_manifest():
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "cameraReservationRef": "camera_3333333333333333",
        "reservedSubjectCount": 12,
        "reservedSessionCount": 12,
        "expectedCaptureCount": 36,
        "requiredViews": list(MODULE.REQUIRED_VIEWS),
        "reservationEvidenceSHA256": "a" * 64,
        "captureProtocolSHA256": "b" * 64,
        "consentProtocolSHA256": "c" * 64,
        "privacyRetentionPolicySHA256": "d" * 64,
        "cameraPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
        "independenceVerification": {
            "sourceRegistryCompared": True,
            "noSubjectOverlapFound": True,
            "comparisonEvidenceSHA256": "e" * 64,
            "humanConfirmationRequired": True,
            "similarityAloneAcceptedAsIdentity": False,
        },
    }


class SourceIndependentCameraReservationTest(unittest.TestCase):
    def test_committed_facts_stay_blocked(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        result = MODULE.summarize_committed_facts(receipt)
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["reserved"])
        self.assertEqual(result["requiredViews"], ["front", "left", "right"])
        self.assertFalse(result["generated"])
        self.assertTrue(result["reservationIsNotAcceptanceEvidence"])

    def test_complete_manifest_emits_gate_compatible_artifact(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertTrue(artifact["reserved"])
        self.assertEqual(artifact["sourceType"], "physical-camera")
        self.assertFalse(artifact["generated"])
        self.assertTrue(artifact["consentRequired"])
        self.assertTrue(artifact["subjectIndependentFromSourceRegistry"])
        self.assertFalse(artifact["usedForTrainingValidationOrThresholdSelection"])

    def test_incomplete_template_is_blocked(self):
        template = complete_manifest()
        template.update({
            "releaseRef": None, "sourceRegistryRef": None,
            "cameraReservationRef": None, "reservedSubjectCount": 0,
            "reservedSessionCount": 0, "expectedCaptureCount": 0,
            "reservationEvidenceSHA256": None, "captureProtocolSHA256": None,
            "consentProtocolSHA256": None, "privacyRetentionPolicySHA256": None,
            "independenceVerification": None,
        })
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("reserved_subject_count_empty", result["blockers"])
        self.assertIn("independence_verification_missing", result["blockers"])
        with self.assertRaisesRegex(MODULE.CameraReservationInputError, "reservation is incomplete"):
            MODULE.build_release_artifact(template)

    def test_generated_fixture_or_source_overlap_fails_hard_or_blocks(self):
        for field in ("generated", "controlledFixture", "syntheticOrRenderedMediaAllowed"):
            bad = complete_manifest()
            bad["cameraPolicy"][field] = True
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.CameraReservationInputError, "unsafe camera reservation policy"):
                    MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["independenceVerification"]["noSubjectOverlapFound"] = False
        self.assertIn("independence_noSubjectOverlapFound_incomplete", MODULE.evaluate_private_manifest(bad)["blockers"])

    def test_training_selection_or_threshold_reuse_fails_hard(self):
        for field in (
            "usedForTrainingValidationOrThresholdSelection",
            "usedForModelSelection",
            "usedForTestThresholdRetuning",
        ):
            bad = complete_manifest()
            bad["cameraPolicy"][field] = True
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.CameraReservationInputError, "unsafe camera reservation policy"):
                    MODULE.evaluate_private_manifest(bad)

    def test_session_and_triplet_counts_must_match(self):
        bad = complete_manifest()
        bad["reservedSessionCount"] = 11
        self.assertIn("one_session_per_subject_contract_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["expectedCaptureCount"] = 35
        self.assertIn("front_left_right_capture_count_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])

    def test_required_views_and_similarity_identity_are_locked(self):
        bad = complete_manifest()
        bad["requiredViews"] = ["front"]
        with self.assertRaisesRegex(MODULE.CameraReservationInputError, "view contract changed"):
            MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["independenceVerification"]["similarityAloneAcceptedAsIdentity"] = True
        with self.assertRaisesRegex(MODULE.CameraReservationInputError, "similarity alone cannot establish"):
            MODULE.evaluate_private_manifest(bad)

    def test_private_identity_media_and_model_payloads_fail_hard(self):
        for forbidden in ("subjectIds", "personId", "path", "email", "demographics", "captures", "predictions", "annotations"):
            bad = complete_manifest()
            bad[forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.CameraReservationInputError, "private identity, media or model payload"):
                    MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
