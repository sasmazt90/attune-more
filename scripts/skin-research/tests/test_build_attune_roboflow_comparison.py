import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_attune_roboflow_comparison.py"
SPEC = importlib.util.spec_from_file_location("comparison", SCRIPT)
comparison = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(comparison)


def sha(char):
    return char * 64


def fixtures():
    subjects = []
    calls = []
    captures = []
    aggregate = {str(value): {"total": 0, "byClass": {}} for value in comparison.THRESHOLDS}
    for index in range(6):
        key = f"{index + 1}.Subject"
        filename = f"{key}_front.jpg"
        jpeg_hash = f"{index + 1:x}" * 64
        subjects.append(
            {
                "subjectKey": key,
                "poses": {
                    "front": {"filename": filename, "sha256": jpeg_hash, "width": 2048, "height": 1529},
                    "side_1": {"filename": f"{key}_side_1.jpg", "sha256": sha("a"), "width": 2048, "height": 1529},
                    "side_2": {"filename": f"{key}_side_2.jpg", "sha256": sha("b"), "width": 2048, "height": 1529},
                },
            }
        )
        predictions = [
            {"confidence": 0.55, "class": "akne"},
            {"confidence": 0.10, "class": "kizariklik"},
        ]
        counts = {}
        for threshold in comparison.THRESHOLDS:
            label = str(threshold)
            counts[label] = comparison._threshold_counts(predictions, threshold)
            aggregate[label]["total"] += counts[label]["total"]
            for name, count in counts[label]["byClass"].items():
                aggregate[label]["byClass"][name] = aggregate[label]["byClass"].get(name, 0) + count
        calls.append(
            {
                "input": {"filename": filename, "sha256": jpeg_hash, "width": 2048, "height": 1529},
                "thresholdCounts": counts,
                "predictions": predictions,
            }
        )
        rows = [
            {
                "id": criterion,
                "quality": "valid",
                "value": float(index),
                "limitationCode": None,
                "methodVersion": "fixture-v1",
            }
            for criterion in comparison.CURRENT_CRITERIA
        ]
        rgba_hash = f"{index + 7:x}" * 64
        captures.append(
            {
                "subjectKey": key,
                "pose": "FRONT",
                "input": {"filename": filename, "jpegSha256": jpeg_hash, "decodedRgbaSha256": rgba_hash},
                "response": {
                    "methodVersion": "fixture-v1",
                    "photoId": rgba_hash,
                    "storage": "volatile-memory-only",
                    "sourceWidth": 2048,
                    "sourceHeight": 1529,
                    "measurements": {name: [] for name in comparison.REGIONS},
                    "maps": {},
                    "contours": {},
                    "general": {
                        "measurements": rows,
                        "skinType": {
                            "quality": "valid",
                            "value": "normal",
                            "confidence": 0.9,
                            "limitationCode": None,
                            "methodVersion": "fixture-v1",
                        },
                    },
                },
            }
        )
    manifest = {
        "source": {"declaredGenerated": True, "expertGroundTruth": False, "realCameraCapture": False},
        "capturePackage": {"subjects": 6, "images": 18, "completeTriplets": True},
        "subjects": subjects,
    }
    roboflow = {
        "source": {"expertGroundTruth": False},
        "model": {
            "requestedModelId": "ciltanalizi-rfa8m/12",
            "requestedConfidence": 0.08,
            "resolvedModel": {"model_package_id": comparison.ROBOFLOW_PACKAGE},
        },
        "aggregateThresholdCounts": aggregate,
        "calls": calls,
    }
    attune = {
        "sourceCommit": comparison.CURRENT_PRODUCT_COMMIT,
        "endpoint": comparison.CURRENT_ENDPOINT,
        "captures": captures,
    }
    return manifest, roboflow, attune


class ComparisonContractTest(unittest.TestCase):
    def test_complete_source_bound_bundle_builds(self):
        manifest, roboflow, attune = fixtures()
        receipt = comparison.build(manifest, roboflow, attune)
        self.assertTrue(receipt["comparisonReady"])
        self.assertEqual(len(receipt["subjects"]), 6)
        self.assertFalse(receipt["claims"]["accuracyMeasured"])

    def test_missing_attune_subject_is_blocked(self):
        manifest, roboflow, attune = fixtures()
        attune["captures"].pop()
        with self.assertRaisesRegex(comparison.ContractError, "all six FRONT"):
            comparison.build(manifest, roboflow, attune)

    def test_decoded_photo_identity_mismatch_is_blocked(self):
        manifest, roboflow, attune = fixtures()
        attune["captures"][0]["response"]["photoId"] = sha("f")
        with self.assertRaisesRegex(comparison.ContractError, "photoId mismatch"):
            comparison.build(manifest, roboflow, attune)

    def test_roboflow_counts_are_recomputed(self):
        manifest, roboflow, attune = fixtures()
        roboflow["calls"][0]["thresholdCounts"]["0.5"]["total"] = 99
        with self.assertRaisesRegex(comparison.ContractError, "do not recompute"):
            comparison.build(manifest, roboflow, attune)

    def test_wrong_product_commit_is_blocked(self):
        manifest, roboflow, attune = fixtures()
        attune["sourceCommit"] = sha("0")
        with self.assertRaisesRegex(comparison.ContractError, "current merged product commit"):
            comparison.build(manifest, roboflow, attune)

    def test_cli_failure_writes_no_comparison(self):
        manifest, roboflow, attune = fixtures()
        attune["captures"].pop()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = {}
            for name, value in (("manifest", manifest), ("roboflow", roboflow), ("attune", attune)):
                paths[name] = root / f"{name}.json"
                paths[name].write_text(json.dumps(value), encoding="utf-8")
            output_json = root / "comparison.json"
            output_md = root / "comparison.md"
            status = comparison.main(
                [
                    "--manifest", str(paths["manifest"]),
                    "--roboflow", str(paths["roboflow"]),
                    "--attune", str(paths["attune"]),
                    "--output-json", str(output_json),
                    "--output-md", str(output_md),
                ]
            )
            self.assertEqual(status, 2)
            self.assertFalse(output_json.exists())
            self.assertFalse(output_md.exists())


if __name__ == "__main__":
    unittest.main()
