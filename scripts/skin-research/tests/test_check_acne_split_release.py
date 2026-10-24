import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "check_acne_split_release.py"
SPEC = importlib.util.spec_from_file_location("acne_split_release", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)


def source_review():
    return {
        "schemaVersion": "acne-source-group-review-v1",
        "dataset": {
            "archiveSHA256": "a" * 64,
            "images": 3,
            "splits": {"train": 1, "valid": 1, "test": 1},
        },
        "recordIndex": [
            {"recordId": "r1", "split": "train"},
            {"recordId": "r2", "split": "valid"},
            {"recordId": "r3", "split": "test"},
        ],
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
        },
        "reviewSummary": {"confirmedCrossSplitSourceLeakageGroups": 1},
        "regroupingPlan": {"confirmedGroups": [{
            "members": [
                {"recordId": "r1", "split": "train"},
                {"recordId": "r2", "split": "valid"},
            ]
        }]},
    }


def complete_semantics():
    return {
        "schemaVersion": "acne-semantic-negative-review-v1",
        "classes": [{
            "name": name,
            "expertReviewed": True,
            "positiveDefinitionLocked": True,
            "hardNegativePolicyLocked": True,
            "ambiguousCasePolicyLocked": True,
        } for name in gate.CLASSES],
    }


class AcneSplitReleaseGateTest(unittest.TestCase):
    def test_current_dataset_fails_closed_without_review_receipts(self):
        result = gate.build_gate(source_review())
        self.assertFalse(result["decision"]["readyToGenerateReplacementSplit"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(result["replacementSplit"]["missingRecords"], 3)
        self.assertEqual(result["semanticNegativeReview"]["missingClasses"], list(gate.CLASSES))
        self.assertEqual(result["currentSplit"]["confirmedLeakageMembers"], 2)

    def test_complete_receipts_only_authorize_split_generation(self):
        groups = {
            "schemaVersion": "acne-source-person-group-coverage-v1",
            "reviewer": "engineering_visual_review",
            "allRecordsReviewed": True,
            "testSplitPolicy": "locked_existing_test_records",
            "groups": [
                {"groupId": "g12", "targetSplit": "train", "members": ["r1", "r2"]},
                {"groupId": "g3", "targetSplit": "test", "members": ["r3"]},
            ],
        }
        result = gate.build_gate(source_review(), groups, complete_semantics())
        self.assertTrue(result["decision"]["readyToGenerateReplacementSplit"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertFalse(result["decision"]["testEvaluationAuthorized"])

    def test_duplicate_or_moved_test_record_blocks_release(self):
        groups = {
            "schemaVersion": "acne-source-person-group-coverage-v1",
            "reviewer": "expert_review",
            "allRecordsReviewed": True,
            "testSplitPolicy": "locked_existing_test_records",
            "groups": [
                {"groupId": "g1", "targetSplit": "train", "members": ["r1", "r3"]},
                {"groupId": "g2", "targetSplit": "valid", "members": ["r2", "r2"]},
            ],
        }
        result = gate.build_gate(source_review(), groups, complete_semantics())
        self.assertFalse(result["decision"]["readyToGenerateReplacementSplit"])
        self.assertEqual(result["replacementSplit"]["duplicateAssignments"], 1)
        self.assertEqual(result["replacementSplit"]["testRecordsMoved"], 1)

    def test_privacy_or_index_mismatch_is_rejected(self):
        value = source_review()
        value["privacy"]["containsFilenames"] = True
        with self.assertRaisesRegex(gate.GateError, "privacy safe"):
            gate.build_gate(value)
        value = source_review()
        value["dataset"]["images"] = 4
        with self.assertRaisesRegex(gate.GateError, "does not cover"):
            gate.build_gate(value)


if __name__ == "__main__":
    unittest.main()
