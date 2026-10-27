import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name):
    path = ROOT / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CAMERA = load("build_physical_camera_benchmark_manifest.py")
MODULE = load("build_physical_camera_expert_truth.py")


def camera_manifest():
    captures = []
    for number, pose in enumerate(("front", "left", "right"), 1):
        captures.append({
            "subjectRef": "subject_0000000000000001",
            "captureRef": f"capture_{number:016x}",
            "consentRef": "consent_0000000000000001",
            "imageSha256": f"{number:064x}",
            "pose": pose,
            "deviceClass": "mobile-front",
            "lightingBin": "indoor-diffuse",
            "skinToneBin": "fitzpatrick-iii",
            "captureQualityGateRef": f"quality_{number:016x}",
            "captureQuality": "pass",
            "sourceType": "physical-camera",
            "generated": False,
            "split": "camera_final",
            "usedForTraining": False,
            "usedForValidation": False,
            "usedForThresholdSelection": False,
        })
    return CAMERA.build_manifest({"captures": captures})


POLYGON = [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]]


def reviews(classes=("pimple", "redness")):
    data = {
        "protocolRef": "protocol_0000000000000001",
        "activatedClasses": list(classes),
        "reviews": [],
        "adjudications": [],
    }
    for capture in camera_manifest()["captures"]:
        for class_id in classes:
            decision = "positive" if class_id == "redness" else "evaluated_negative"
            polygons = copy.deepcopy(POLYGON) if decision == "positive" else []
            for reviewer in (1, 2):
                data["reviews"].append({
                    "captureRef": capture["captureRef"],
                    "classId": class_id,
                    "reviewerRef": f"reviewer_{reviewer:016x}",
                    "qualificationRef": f"qualification_{reviewer:016x}",
                    "decision": decision,
                    "polygons": copy.deepcopy(polygons),
                    "humanAuthored": True,
                    "modelProposalViewed": False,
                })
    return data


class PhysicalCameraExpertTruthTest(unittest.TestCase):
    def test_builds_complete_dual_review_truth(self):
        result = MODULE.build_expert_truth(camera_manifest(), reviews())
        self.assertEqual(result["captureCount"], 3)
        self.assertEqual(result["truthCellCount"], 6)
        self.assertEqual(result["decisionCounts"], {"evaluated_negative": 3, "positive": 3})
        self.assertFalse(result["missingTruthInterpretedAsNegative"])
        self.assertTrue(result["rednessOverlapAllowed"])

    def test_missing_cell_is_not_silently_negative(self):
        bad = reviews()
        capture = bad["reviews"][0]["captureRef"]
        class_id = bad["reviews"][0]["classId"]
        bad["reviews"] = [r for r in bad["reviews"] if not (r["captureRef"] == capture and r["classId"] == class_id)]
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "missing is not negative"):
            MODULE.build_expert_truth(camera_manifest(), bad)

    def test_exactly_two_independent_reviewers_are_required(self):
        bad = reviews()
        bad["reviews"][1]["reviewerRef"] = bad["reviews"][0]["reviewerRef"]
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "independent experts"):
            MODULE.build_expert_truth(camera_manifest(), bad)

    def test_model_visible_or_nonhuman_review_is_rejected(self):
        bad = reviews()
        bad["reviews"][0]["modelProposalViewed"] = True
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "blinded"):
            MODULE.build_expert_truth(camera_manifest(), bad)
        bad = reviews()
        bad["reviews"][0]["humanAuthored"] = False
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "human-authored"):
            MODULE.build_expert_truth(camera_manifest(), bad)

    def test_positive_localized_truth_requires_valid_polygon(self):
        bad = reviews()
        positive = next(item for item in bad["reviews"] if item["decision"] == "positive")
        positive["polygons"] = []
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "requires polygon"):
            MODULE.build_expert_truth(camera_manifest(), bad)
        bad = reviews()
        positive = next(item for item in bad["reviews"] if item["decision"] == "positive")
        positive["polygons"] = [[[1.2, 0.1], [0.2, 0.1], [0.2, 0.2]]]
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "normalized"):
            MODULE.build_expert_truth(camera_manifest(), bad)

    def test_disagreement_requires_independent_third_expert(self):
        bad = reviews()
        bad["reviews"][1]["decision"] = "unknown"
        bad["reviews"][1]["polygons"] = []
        with self.assertRaisesRegex(MODULE.ExpertTruthError, "third-expert"):
            MODULE.build_expert_truth(camera_manifest(), bad)
        bad["adjudications"].append({
            "captureRef": bad["reviews"][0]["captureRef"],
            "classId": bad["reviews"][0]["classId"],
            "adjudicatorRef": "reviewer_0000000000000003",
            "qualificationRef": "qualification_0000000000000003",
            "decision": "evaluated_negative",
            "polygons": [],
            "humanAuthored": True,
            "modelProposalViewed": False,
        })
        result = MODULE.build_expert_truth(camera_manifest(), bad)
        self.assertEqual(result["disagreementCount"], 1)

    def test_private_identity_and_model_output_fields_are_rejected(self):
        for field in ("name", "email", "path", "filename", "predictions", "confidence"):
            bad = reviews()
            bad["reviews"][0][field] = "private"
            with self.subTest(field=field), self.assertRaisesRegex(MODULE.ExpertTruthError, "forbidden"):
                MODULE.build_expert_truth(camera_manifest(), bad)

    def test_unknown_and_unassessable_remain_distinct_from_negative_and_normal(self):
        data = reviews(("normal",))
        data["reviews"][0]["decision"] = "unknown"
        data["reviews"][0]["polygons"] = []
        data["reviews"][1]["decision"] = "unknown"
        data["reviews"][1]["polygons"] = []
        data["reviews"][2]["decision"] = "unassessable"
        data["reviews"][3]["decision"] = "unassessable"
        data["reviews"][4]["decision"] = "evaluated_negative"
        data["reviews"][5]["decision"] = "evaluated_negative"
        result = MODULE.build_expert_truth(camera_manifest(), data)
        self.assertEqual(result["decisionCounts"], {"evaluated_negative": 1, "unassessable": 1, "unknown": 1})
        self.assertTrue(result["normalRequiresExplicitEvaluatedTruth"])


if __name__ == "__main__":
    unittest.main()
