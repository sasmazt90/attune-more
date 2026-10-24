import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "summarize_current_merged_skin_output.py"
REPOSITORY = SCRIPT.parents[2]
COMMITTED_SOURCE = (
    REPOSITORY / "docs/skin/evidence/"
    "attune-roboflow-source-bound-comparison-20261024-v1.json"
)
COMMITTED_SUMMARY = (
    REPOSITORY / "docs/skin/evidence/"
    "current-merged-skin-capability-20261024-v1.json"
)
SPEC = importlib.util.spec_from_file_location("merged_skin", SCRIPT)
merged_skin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(merged_skin)


def fixture():
    subjects = []
    for index in range(6):
        criteria = {criterion: {"quality": "valid", "value": float(index), "limitationCode": None}
                    for criterion in merged_skin.CURRENT_CRITERIA}
        subjects.append({"subjectKey": f"subject-{index}", "attune": {
            "photoId": f"{index + 1:x}" * 64,
            "criteria": criteria,
            "skinType": {"quality": "valid", "value": "normal"},
            "regionalInventory": list(merged_skin.REGIONS),
            "mapCount": 12,
            "contourCount": 1,
        }})
    return {
        "comparisonReady": True,
        "sourceCommit": merged_skin.CURRENT_PRODUCT_COMMIT,
        "endpoint": merged_skin.CURRENT_ENDPOINT,
        "attuneExecutionProvenance": {
            "baseCommit": merged_skin.CURRENT_PRODUCT_COMMIT,
            "localRevisionSHA256": "a" * 64,
            "productOrModelOrThresholdChanges": False,
        },
        "subjects": subjects,
        "claims": {
            "accuracyMeasured": False,
            "expertGroundTruth": False,
            "realCameraAcceptance": False,
            "thresholdCalibrationAuthorized": False,
            "productionActivationAuthorized": False,
        },
    }


class CurrentMergedSkinOutputTest(unittest.TestCase):
    def test_committed_source_replays_to_exact_capability_receipt(self):
        source = json.loads(COMMITTED_SOURCE.read_text(encoding="utf-8"))
        expected = json.loads(COMMITTED_SUMMARY.read_text(encoding="utf-8"))
        result = merged_skin.summarize(source)
        self.assertEqual(result, expected)
        self.assertTrue(result["productAlreadyProducesConcreteResults"])
        self.assertEqual(result["currentMergedBaseline"]["commit"],
                         merged_skin.CURRENT_PRODUCT_COMMIT)
        self.assertEqual(result["subjectsWithMaps"], 6)

    def test_complete_receipt_proves_existing_concrete_output(self):
        result = merged_skin.summarize(fixture())
        self.assertTrue(result["productAlreadyProducesConcreteResults"])
        self.assertEqual(result["validCriterionValues"], 54)
        self.assertEqual(result["separateSkinTypeResults"], 6)
        self.assertEqual(result["regionalInventoriesComplete"], 6)
        self.assertFalse(result["claims"]["accuracyMeasured"])

    def test_missing_existing_criterion_is_blocked(self):
        value = fixture()
        del value["subjects"][0]["attune"]["criteria"]["bags"]
        with self.assertRaisesRegex(merged_skin.ContractError, "criterion inventory"):
            merged_skin.summarize(value)

    def test_missing_map_is_blocked(self):
        value = fixture()
        value["subjects"][0]["attune"]["mapCount"] = 0
        with self.assertRaisesRegex(merged_skin.ContractError, "no concrete maps"):
            merged_skin.summarize(value)

    def test_accuracy_overclaim_is_blocked(self):
        value = fixture()
        value["claims"]["accuracyMeasured"] = True
        with self.assertRaisesRegex(merged_skin.ContractError, "overclaims"):
            merged_skin.summarize(value)

    def test_cli_failure_writes_nothing(self):
        value = fixture()
        value["sourceCommit"] = "0" * 40
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "source.json", root / "output.json"
            source.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(merged_skin.main(["--comparison", str(source), "--output", str(output)]), 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
