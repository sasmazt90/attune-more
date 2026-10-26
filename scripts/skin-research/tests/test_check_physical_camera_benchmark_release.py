import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_physical_camera_benchmark_release.py"
SPEC = importlib.util.spec_from_file_location("check_physical_camera_benchmark_release", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/physical-camera-benchmark-release-receipt-20261026-v1.json"


def receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


class PhysicalCameraBenchmarkGateTest(unittest.TestCase):
    def test_current_generated_package_is_smoke_only(self):
        result = MODULE.evaluate_release(receipt())
        self.assertTrue(result["workingBaselinePreserved"])
        self.assertTrue(result["generatedIntegrationSmokeAllowed"])
        self.assertFalse(result["generatedAccuracyEvidenceAllowed"])
        self.assertFalse(result["physicalCameraBenchmarkAccepted"])

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

    def test_complete_future_physical_candidate_can_pass_without_promoting_generated_data(self):
        future = copy.deepcopy(receipt())
        future["physicalCameraCandidate"] = {key: True for key in future["physicalCameraCandidate"]}
        result = MODULE.evaluate_release(future)
        self.assertTrue(result["physicalCameraBenchmarkAccepted"])
        self.assertFalse(result["generatedAccuracyEvidenceAllowed"])
        self.assertFalse(result["generatedPhysicalCameraAcceptanceAllowed"])


if __name__ == "__main__":
    unittest.main()
