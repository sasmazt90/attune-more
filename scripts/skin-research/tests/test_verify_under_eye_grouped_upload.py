import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "verify_under_eye_grouped_upload.py"
SPEC = importlib.util.spec_from_file_location("verify_under_eye_grouped_upload", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UploadPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.archive = root / "grouped.zip"
        self.archive.write_bytes(b"authorized archive bytes")
        archive_sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.reproduction = {
            "methodVersion": "under-eye-grouped-archive-v2",
            "sourceArchiveSHA256": "a" * 64,
            "outputArchiveSHA256": archive_sha,
            "outputArchiveBytes": self.archive.stat().st_size,
            "output": {
                "images": 399,
                "annotations": 869,
                "splits": {"train": 284, "valid": 77, "test": 38},
                "classCounts": {"darkcircle": 382, "eyebag": 487},
            },
            "imageBytesChanged": 0,
            "annotationPayloadsChanged": 0,
            "trainingAuthorized": False,
            "activationAllowed": False,
        }
        self.authorization = {
            "methodVersion": "under-eye-grouped-archive-authorization-v3",
            "sourceArchiveSHA256": "a" * 64,
            "authorizedArchiveSHA256": archive_sha,
            "revokedArchiveSHA256": "b" * 64,
            "authorization": {
                "destinationProject": "tolgar-sasmaz/attune-skin-under-eye-grouped-research",
                "destinationMustRemainPrivate": True,
                "destinationMustBeEmpty": True,
                "freshDirectArchiveUpload": True,
                "reuseExistingCreatedTask": False,
                "versionGeneration": False,
                "researchTraining": False,
                "testEvaluation": False,
                "productActivation": False,
            },
            "requiredPostUploadVerification": copy.deepcopy(self.reproduction["output"]),
        }
        self.gate = {
            "methodVersion": "under-eye-grouped-release-gate-v3",
            "archiveUploadAuthorized": True,
            "exactArchiveAuthorized": True,
            "authorizedArchiveSHA256": archive_sha,
            "candidateArchiveSHA256": archive_sha,
            "sourceArchiveSHA256": "a" * 64,
            "freshDirectUploadRequired": True,
            "existingUploadTaskReusable": False,
            "versionGenerationAuthorized": False,
            "researchTrainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "productActivationAllowed": False,
            "roadmapAccepted": False,
        }
        self.paths = {}
        for name, value in (("reproduction", self.reproduction), ("authorization", self.authorization), ("gate", self.gate)):
            path = root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            self.paths[name] = path

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, value):
        self.paths[name].write_text(json.dumps(value), encoding="utf-8")

    def _verify(self):
        return MODULE.verify_upload_preflight(
            self.archive,
            self.paths["reproduction"],
            self.paths["authorization"],
            self.paths["gate"],
            observed_at="2026-10-28T12:00:00Z",
        )

    def test_accepts_only_exact_authorized_archive(self):
        receipt = self._verify()
        self.assertEqual(receipt["decision"], "ready_for_exact_authorized_upload")
        self.assertFalse(receipt["uploadPerformed"])
        self.assertFalse(receipt["researchTrainingAuthorized"])
        self.assertNotIn(str(self.archive), json.dumps(receipt))

    def test_rejects_wrong_archive_bytes(self):
        self.archive.write_bytes(b"different")
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "authorized SHA256"):
            self._verify()

    def test_rejects_revoked_archive(self):
        self.authorization["revokedArchiveSHA256"] = self.authorization["authorizedArchiveSHA256"]
        self._write("authorization", self.authorization)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "revoked"):
            self._verify()

    def test_rejects_non_private_destination(self):
        self.authorization["authorization"]["destinationMustRemainPrivate"] = False
        self._write("authorization", self.authorization)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "privacy"):
            self._verify()

    def test_rejects_stale_task_reuse(self):
        self.gate["existingUploadTaskReusable"] = True
        self._write("gate", self.gate)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "stale task"):
            self._verify()

    def test_rejects_training_promotion(self):
        self.gate["researchTrainingAuthorized"] = True
        self._write("gate", self.gate)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "researchTrainingAuthorized"):
            self._verify()

    def test_rejects_count_mismatch(self):
        self.authorization["requiredPostUploadVerification"]["images"] = 398
        self._write("authorization", self.authorization)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "counts"):
            self._verify()

    def test_rejects_changed_annotation_payload(self):
        self.reproduction["annotationPayloadsChanged"] = 1
        self._write("reproduction", self.reproduction)
        with self.assertRaisesRegex(MODULE.UploadPreflightError, "annotation payloads"):
            self._verify()


if __name__ == "__main__":
    unittest.main()
