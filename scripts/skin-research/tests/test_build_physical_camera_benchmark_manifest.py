import copy
import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_physical_camera_benchmark_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_physical_camera_benchmark_manifest", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_index(subjects=2):
    captures = []
    sequence = 1
    for subject in range(subjects):
        for pose in ("front", "left", "right"):
            captures.append({
                "subjectRef": f"subject_{subject + 1:016x}",
                "captureRef": f"capture_{sequence:016x}",
                "consentRef": f"consent_{subject + 1:016x}",
                "imageSha256": f"{sequence:064x}",
                "pose": pose,
                "deviceClass": "mobile-rear" if subject == 0 else "mobile-front",
                "lightingBin": "indoor-diffuse" if subject == 0 else "daylight-shade",
                "skinToneBin": "fitzpatrick-ii" if subject == 0 else "fitzpatrick-v",
                "captureQualityGateRef": f"quality_{sequence:016x}",
                "captureQuality": "pass",
                "sourceType": "physical-camera",
                "generated": False,
                "split": "camera_final",
                "usedForTraining": False,
                "usedForValidation": False,
                "usedForThresholdSelection": False,
            })
            sequence += 1
    return {"captures": captures}


class PhysicalCameraManifestTest(unittest.TestCase):
    def test_builds_privacy_safe_triplet_manifest(self):
        result = MODULE.build_manifest(valid_index())
        self.assertEqual(result["subjectCount"], 2)
        self.assertEqual(result["captureCount"], 6)
        self.assertTrue(result["completeThreePoseTriplets"])
        self.assertFalse(result["containsImageBytesOrPaths"])
        self.assertFalse(result["containsModelPredictions"])
        self.assertFalse(result["containsExpertTruth"])
        self.assertEqual(result["sliceCounts"]["pose"], {"front": 2, "left": 2, "right": 2})

    def test_generated_capture_is_rejected(self):
        bad = valid_index(1)
        bad["captures"][0]["generated"] = True
        with self.assertRaisesRegex(MODULE.CameraManifestError, "cannot enter camera_final"):
            MODULE.build_manifest(bad)

    def test_training_validation_or_threshold_leakage_is_rejected(self):
        for field in ("usedForTraining", "usedForValidation", "usedForThresholdSelection"):
            bad = valid_index(1)
            bad["captures"][0][field] = True
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraManifestError, "leaks"):
                MODULE.build_manifest(bad)

    def test_private_identity_or_path_fields_are_rejected(self):
        for field in ("name", "email", "path", "filename", "imageBytes", "predictions", "expertLabel"):
            bad = valid_index(1)
            bad["captures"][0][field] = "secret"
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.CameraManifestError, "forbidden private field"):
                MODULE.build_manifest(bad)

    def test_duplicate_hash_and_incomplete_triplet_are_rejected(self):
        bad = valid_index(1)
        bad["captures"][1]["imageSha256"] = bad["captures"][0]["imageSha256"]
        with self.assertRaisesRegex(MODULE.CameraManifestError, "duplicate imageSha256"):
            MODULE.build_manifest(bad)
        incomplete = valid_index(1)
        incomplete["captures"].pop()
        with self.assertRaisesRegex(MODULE.CameraManifestError, "exact front/left/right"):
            MODULE.build_manifest(incomplete)

    def test_failed_capture_quality_and_nonopaque_references_are_rejected(self):
        bad = valid_index(1)
        bad["captures"][0]["captureQuality"] = "fail"
        with self.assertRaisesRegex(MODULE.CameraManifestError, "capture-quality"):
            MODULE.build_manifest(bad)
        bad = valid_index(1)
        bad["captures"][0]["subjectRef"] = "Alice Smith"
        with self.assertRaisesRegex(MODULE.CameraManifestError, "opaque reference"):
            MODULE.build_manifest(bad)


if __name__ == "__main__":
    unittest.main()
