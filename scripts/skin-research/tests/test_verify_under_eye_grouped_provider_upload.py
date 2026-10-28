import copy
import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "verify_under_eye_grouped_provider_upload.py"
SPEC = importlib.util.spec_from_file_location("verify_under_eye_grouped_provider_upload", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


TASK_ID = "jwquQEBFgx3HWd9ziIMn"
REPO_ROOT = Path(__file__).parents[3]
FACTS_PATH = REPO_ROOT / "docs/skin/evidence/under-eye-grouped-provider-upload-facts-20261028-v1.json"
EVIDENCE_PATH = REPO_ROOT / "docs/skin/evidence/under-eye-grouped-provider-upload-verification-20261028-v1.json"


def valid_facts():
    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-grouped-provider-upload-facts-v1",
        "observedAt": "2026-10-28T23:40:18Z",
        "project": MODULE.EXPECTED_PROJECT,
        "private": True,
        "archiveSHA256": MODULE.EXPECTED_ARCHIVE_SHA256,
        "archiveBytes": MODULE.EXPECTED_ARCHIVE_BYTES,
        "upload": {
            "taskId": TASK_ID,
            "status": "completed",
            "progress": {"current": 399, "total": 399},
            "result": {
                "uploaded": 399,
                "duplicates": 0,
                "annotated": 399,
                "videosStaged": 0,
                "videoIds": [],
                "uploadErrors": [],
                "annotationErrors": [],
                "warnings": [{"type": "ignored", "path": "README.roboflow.txt", "reason": "readme"}],
                "chunkCount": 4,
                "failedChunks": 0,
            },
        },
        "annotationBoard": {
            "datasetImages": 399,
            "datasetAnnotated": 399,
            "datasetUnannotated": 0,
            "percentLabeled": 100,
            "uploadJobStatus": "complete",
        },
        "paginatedDatasetSearch": {
            "complete": True,
            "pages": 5,
            "images": 399,
            "splits": {"train": 284, "valid": 77, "test": 38},
            "classAnnotationCounts": {"darkcircle": 382, "eyebag": 487},
        },
        "providerProjectSummaryImages": 0,
        "versions": [],
        "trainings": [],
    }


class ProviderUploadVerificationTests(unittest.TestCase):
    def test_committed_evidence_replays_exactly(self):
        facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID),
            evidence,
        )

    def test_accepts_exact_upload_and_records_provider_summary_lag(self):
        receipt = MODULE.verify_provider_upload(valid_facts(), expected_task_id=TASK_ID)
        self.assertTrue(receipt["uploadCompleted"])
        self.assertTrue(receipt["providerProjectSummaryLagObserved"])
        self.assertFalse(receipt["versionGenerationAuthorized"])
        self.assertFalse(receipt["productActivationAllowed"])
        self.assertNotIn("imageId", json.dumps(receipt))

    def test_accepts_eventually_consistent_project_summary(self):
        facts = valid_facts()
        facts["providerProjectSummaryImages"] = 399
        receipt = MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)
        self.assertTrue(receipt["providerProjectSummaryConsistent"])
        self.assertFalse(receipt["providerProjectSummaryLagObserved"])

    def test_rejects_task_identity_drift(self):
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "task identity"):
            MODULE.verify_provider_upload(valid_facts(), expected_task_id="other")

    def test_rejects_partial_upload(self):
        facts = valid_facts()
        facts["upload"]["result"]["uploaded"] = 398
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "uploaded image"):
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)

    def test_rejects_annotation_errors(self):
        facts = valid_facts()
        facts["upload"]["result"]["annotationErrors"] = [{"reason": "bad"}]
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "annotation errors"):
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)

    def test_rejects_split_drift(self):
        facts = valid_facts()
        facts["paginatedDatasetSearch"]["splits"]["test"] = 39
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "split counts"):
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)

    def test_rejects_class_count_drift(self):
        facts = valid_facts()
        facts["paginatedDatasetSearch"]["classAnnotationCounts"]["darkcircle"] = 381
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "class counts"):
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)

    def test_rejects_version_or_training_promotion(self):
        for field in ("versions", "trainings"):
            facts = valid_facts()
            facts[field] = [1]
            with self.subTest(field=field), self.assertRaises(MODULE.ProviderUploadVerificationError):
                MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)

    def test_rejects_non_private_destination(self):
        facts = valid_facts()
        facts["private"] = False
        with self.assertRaisesRegex(MODULE.ProviderUploadVerificationError, "not private"):
            MODULE.verify_provider_upload(facts, expected_task_id=TASK_ID)


if __name__ == "__main__":
    unittest.main()
