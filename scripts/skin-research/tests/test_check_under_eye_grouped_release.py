import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_under_eye_grouped_release.py"
SPEC = importlib.util.spec_from_file_location("check_under_eye_grouped_release", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def reproduction(sha="8bf6b52fcdd8321c0be53301b4c53aa655b01f8268020c2384a3b95193056122"):
    return {
        "methodVersion": "under-eye-grouped-archive-v2",
        "sourceArchiveSHA256": MODULE.EXPECTED_SOURCE_SHA256,
        "source": dict(MODULE.EXPECTED_SOURCE),
        "output": dict(MODULE.EXPECTED_GROUPED),
        "reviewedCrossSplitGroups": 4,
        "movedImages": 5,
        "imageBytesChanged": 0,
        "annotationPayloadsChanged": 0,
        "outputArchiveSHA256": sha,
    }


def remote():
    return {
        "pilotVersion": {
            "version": 2,
            "images": 399,
            "annotations": 869,
            "splits": {"train": 279, "valid": 81, "test": 39},
            "classCounts": {"darkcircle": 382, "eyebag": 487},
            "preprocessing": {},
            "augmentation": {},
            "exportArchiveSHA256": MODULE.EXPECTED_SOURCE_SHA256,
        },
        "groupedProject": {
            "project": MODULE.EXPECTED_GROUPED_PROJECT,
            "private": True,
            "images": 0,
            "versions": [],
            "upload": {
                "taskId": "stale-task",
                "status": "created",
                "progress": None,
                "bytesSent": False,
            },
        },
    }


def provider_audit(sha):
    return {
        "schemaVersion": MODULE.EXPECTED_PROVIDER_AUDIT_SCHEMA,
        "project": MODULE.EXPECTED_GROUPED_PROJECT,
        "public": False,
        "versionNumber": 1,
        "authorizedArchiveSHA256": sha,
        "images": 399,
        "annotations": 869,
        "splits": {"train": 284, "valid": 77, "test": 38},
        "classCounts": {"darkcircle": 382, "eyebag": 487},
        "allProviderRecordsMatchedAuthorizedArchiveOnce": True,
        "unexpectedProviderRecords": 0,
        "missingAuthorizedRecords": 0,
        "crossSplitContentHashCount": 0,
        "polygonGeometryVerified": True,
        "boxGeometryUsedAsPolygonTruth": False,
        "containsFilenamesOrProviderImageIds": False,
        "providerDatasetIdentitySHA256": "1" * 64,
    }


class UnderEyeGroupedReleaseGateTest(unittest.TestCase):
    def test_new_exact_archive_authorizes_only_fresh_direct_upload(self):
        sha = reproduction()["outputArchiveSHA256"]
        result = MODULE.evaluate_release(reproduction(), remote(), authorized_archive_sha256=sha)
        self.assertTrue(result["archiveUploadAuthorized"])
        self.assertFalse(result["existingUploadTaskReusable"])
        self.assertTrue(result["freshDirectUploadRequired"])
        self.assertFalse(result["versionGenerationAuthorized"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertIn("stale_upload_task_must_not_be_reused", result["blockers"])

    def test_revoked_old_archive_fails_hard(self):
        with self.assertRaisesRegex(MODULE.GateInputError, "revoked archive"):
            MODULE.evaluate_release(
                reproduction(MODULE.REVOKED_ARCHIVE_SHA256),
                remote(),
                authorized_archive_sha256=MODULE.REVOKED_ARCHIVE_SHA256,
            )

    def test_source_export_and_private_destination_are_identity_bound(self):
        bad = reproduction()
        bad["sourceArchiveSHA256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.GateInputError, "reviewed export"):
            MODULE.evaluate_release(bad, remote(), authorized_archive_sha256=bad["outputArchiveSHA256"])
        state = remote()
        state["groupedProject"]["private"] = False
        with self.assertRaisesRegex(MODULE.GateInputError, "privacy"):
            MODULE.evaluate_release(
                reproduction(), state, authorized_archive_sha256=reproduction()["outputArchiveSHA256"]
            )

    def test_verified_import_and_version_still_do_not_authorize_training_without_reviews(self):
        state = remote()
        state["groupedProject"].update({
            "images": 399,
            "versions": [1],
            "upload": {"taskId": "fresh-task", "status": "completed", "progress": 1, "bytesSent": True},
            "importedDataset": dict(MODULE.EXPECTED_GROUPED),
            "generatedVersion": {
                "version": 1,
                "ready": True,
                "splits": dict(MODULE.EXPECTED_GROUPED["splits"]),
                "augmentation": {},
            },
        })
        sha = reproduction()["outputArchiveSHA256"]
        result = MODULE.evaluate_release(reproduction(), state, authorized_archive_sha256=sha)
        self.assertTrue(result["versionGenerationAuthorized"])
        self.assertFalse(result["augmentationFreeGroupedVersionVerified"])
        self.assertFalse(result["providerExportIdentityVerified"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertIn("grouped_provider_export_identity_not_verified", result["blockers"])
        self.assertIn("expert_under_eye_semantic_review_missing", result["blockers"])
        self.assertIn("person_independence_not_verified", result["blockers"])

    def test_training_requires_verified_version_expert_semantics_and_identity(self):
        state = remote()
        sha = reproduction()["outputArchiveSHA256"]
        state["groupedProject"].update({
            "images": 399,
            "versions": [1],
            "upload": {"taskId": "fresh-task", "status": "completed", "progress": 1, "bytesSent": True},
            "importedDataset": dict(MODULE.EXPECTED_GROUPED),
            "generatedVersion": {
                "version": 1,
                "ready": True,
                "splits": dict(MODULE.EXPECTED_GROUPED["splits"]),
                "augmentation": {},
            },
            "providerExportAudit": provider_audit(sha),
            "expertReview": {
                "accepted": True,
                "semanticProtocol": "darkcircle-eyebag-v1",
                "reviewedImages": 399,
            },
            "identityReview": {"accepted": True, "personIndependent": True},
        })
        result = MODULE.evaluate_release(reproduction(), state, authorized_archive_sha256=sha)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["augmentationFreeGroupedVersionVerified"])
        self.assertTrue(result["providerExportIdentityVerified"])
        self.assertFalse(result["testEvaluationAuthorized"])
        self.assertFalse(result["productActivationAllowed"])


if __name__ == "__main__":
    unittest.main()

