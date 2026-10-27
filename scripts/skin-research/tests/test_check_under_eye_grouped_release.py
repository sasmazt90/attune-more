import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_under_eye_grouped_release.py"
SPEC = importlib.util.spec_from_file_location("check_under_eye_grouped_release", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def reproduction(sha="a" * 64):
    return {
        "methodVersion": "under-eye-grouped-archive-v2",
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
        },
        "groupedProject": {
            "images": 0,
            "versions": [],
            "upload": {"taskId": "existing-task", "status": "created", "progress": None},
        },
    }


class UnderEyeGroupedReleaseGateTest(unittest.TestCase):
    def test_current_sha_mismatch_blocks_every_downstream_operation(self):
        result = MODULE.evaluate_release(
            reproduction("b" * 64), remote(), authorized_archive_sha256="a" * 64
        )
        self.assertFalse(result["archiveUploadAuthorized"])
        self.assertFalse(result["versionGenerationAuthorized"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["productActivationAllowed"])
        self.assertIn("candidate_archive_sha256_does_not_match_authorized_archive", result["blockers"])

    def test_exact_archive_only_authorizes_reuse_of_existing_upload_task(self):
        result = MODULE.evaluate_release(
            reproduction("a" * 64), remote(), authorized_archive_sha256="a" * 64
        )
        self.assertTrue(result["archiveUploadAuthorized"])
        self.assertTrue(result["existingUploadTaskReusable"])
        self.assertFalse(result["versionGenerationAuthorized"])
        self.assertFalse(result["researchTrainingAuthorized"])

    def test_verified_import_and_version_can_authorize_research_training_only(self):
        state = remote()
        state["groupedProject"] = {
            "images": 399,
            "versions": [1],
            "upload": {"taskId": "existing-task", "status": "completed", "progress": 1},
            "importedDataset": dict(MODULE.EXPECTED_GROUPED),
            "generatedVersion": {
                "ready": True,
                "splits": {"train": 284, "valid": 77, "test": 38},
                "augmentation": {},
            },
        }
        result = MODULE.evaluate_release(
            reproduction("a" * 64), state, authorized_archive_sha256="a" * 64
        )
        self.assertTrue(result["versionGenerationAuthorized"])
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["testEvaluationAuthorized"])
        self.assertFalse(result["productActivationAllowed"])

    def test_changed_pixels_geometry_or_provider_augmentation_fail_hard(self):
        bad = reproduction()
        bad["imageBytesChanged"] = 1
        with self.assertRaisesRegex(MODULE.GateInputError, "image bytes changed"):
            MODULE.evaluate_release(bad, remote(), authorized_archive_sha256="a" * 64)
        bad = reproduction()
        state = remote()
        state["pilotVersion"]["augmentation"] = {"flip": True}
        with self.assertRaisesRegex(MODULE.GateInputError, "augmentation-free"):
            MODULE.evaluate_release(bad, state, authorized_archive_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
