import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_regional_provider_dataset_release.py"
SPEC = importlib.util.spec_from_file_location("regional_provider_gate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def receipt():
    return {
        "schemaVersion": MODULE.SCHEMA,
        "providerProject": {
            "id": MODULE.PROJECT_ID,
            "type": MODULE.PROJECT_TYPE,
            "public": False,
            "images": 476,
            "splits": {"train": 334, "valid": 85, "test": 57},
            "classes": {"Oily": 1373, "Redness": 898},
        },
        "upload": {
            "status": "completed",
            "uploaded": 139,
            "duplicates": 198,
            "annotated": 337,
            "errors": 0,
            "warnings": 0,
            "failedChunks": 0,
        },
        "postUploadRecords": {
            "records": 139,
            "splits": {"train": 90, "valid": 22, "test": 27},
            "annotations": {"Oily": 308, "Redness": 327},
        },
        "groupLockedManifest": {
            "blobSHA": MODULE.MANIFEST_BLOB_SHA,
            "queueItemsSHA256": MODULE.QUEUE_SHA256,
            "reviewDecisionsSHA256": MODULE.DECISIONS_SHA256,
            "records": MODULE.TARGET_SPLITS,
            "annotations": MODULE.TARGET_ANNOTATIONS,
            "crossSplitGroupCount": 0,
            "allRecordsAssignedExactlyOnce": True,
        },
        "candidateVersion": None,
        "releasePrerequisites": {
            "rightsReviewed": False,
            "expertSemanticMaskProtocolAccepted": False,
            "independentPhysicalCameraHoldoutReserved": False,
        },
    }


def exact_candidate():
    return {
        "versionNumber": 2,
        "images": MODULE.TARGET_IMAGES,
        "splits": MODULE.TARGET_SPLITS,
        "annotations": MODULE.TARGET_ANNOTATIONS,
        "classTotals": MODULE.TARGET_CLASS_TOTALS,
        "manifestBlobSHA": MODULE.MANIFEST_BLOB_SHA,
        "queueItemsSHA256": MODULE.QUEUE_SHA256,
        "reviewDecisionsSHA256": MODULE.DECISIONS_SHA256,
        "sourcePersonCoverageComplete": True,
        "crossSplitGroupCount": 0,
        "allRecordsAssignedExactlyOnce": True,
        "finalTestUsedForSelectionOrThresholds": False,
    }


class RegionalProviderDatasetReleaseTests(unittest.TestCase):
    def test_observed_provider_drift_blocks_training(self):
        result = MODULE.evaluate_release(receipt())
        self.assertTrue(result["mutableProjectDriftDetected"])
        self.assertFalse(result["providerVersionReady"])
        self.assertFalse(result["trainingAuthorized"])
        self.assertIn("provider_version_2_missing", result["blockers"])
        self.assertIn("mutable_provider_project_drifted_from_group_locked_candidate", result["blockers"])

    def test_exact_immutable_v2_and_prerequisites_allow_one_training(self):
        value = receipt()
        value["candidateVersion"] = exact_candidate()
        value["releasePrerequisites"] = {
            "rightsReviewed": True,
            "expertSemanticMaskProtocolAccepted": True,
            "independentPhysicalCameraHoldoutReserved": True,
        }
        result = MODULE.evaluate_release(value)
        self.assertTrue(result["providerVersionReady"])
        self.assertTrue(result["trainingAuthorized"])
        self.assertFalse(result["finalTestAuthorized"])
        self.assertFalse(result["activationAllowed"])

    def test_version_one_cannot_be_relabelled_as_replacement(self):
        value = receipt()
        value["candidateVersion"] = exact_candidate()
        value["candidateVersion"]["versionNumber"] = 1
        result = MODULE.evaluate_release(value)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("provider_version_2_missing", result["blockers"])

    def test_wrong_candidate_split_fails_closed(self):
        value = receipt()
        value["candidateVersion"] = exact_candidate()
        value["candidateVersion"]["splits"] = {"train": 237, "valid": 50, "test": 50}
        result = MODULE.evaluate_release(value)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("exact_group_locked_provider_version_unconfirmed", result["blockers"])

    def test_project_growth_must_match_uploaded_records(self):
        value = receipt()
        value["providerProject"]["images"] = 475
        value["providerProject"]["splits"]["train"] = 333
        with self.assertRaisesRegex(MODULE.GateInputError, "project growth"):
            MODULE.evaluate_release(value)

    def test_upload_errors_fail_input_validation(self):
        value = receipt()
        value["upload"]["errors"] = 1
        with self.assertRaisesRegex(MODULE.GateInputError, "upload has errors"):
            MODULE.evaluate_release(value)


if __name__ == "__main__":
    unittest.main()
