import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resolve_regional_skin_type_source_groups import ResolutionError, resolve_candidates


def audit():
    return {
        "schemaVersion": "regional-skin-type-source-group-audit-v1",
        "source": {"archiveSHA256": "a" * 64},
        "inventory": {"uniqueSourceIds": 5},
        "candidates": [
            {"candidateId": "one", "leftSourceId": "a", "rightSourceId": "b", "splitPairs": ["train-test"]},
            {"candidateId": "two", "leftSourceId": "b", "rightSourceId": "c", "splitPairs": ["test-train"]},
            {"candidateId": "three", "leftSourceId": "d", "rightSourceId": "e", "splitPairs": ["train-valid"]},
        ],
    }


def decisions():
    return {
        "schemaVersion": "regional-skin-type-source-group-decisions-v1",
        "source": {"archiveSHA256": "a" * 64},
        "reviewerRole": "engineering_visual_review_not_expert_annotation",
        "decisions": [
            {"candidateId": "one", "result": "same_source_or_person"},
            {"candidateId": "two", "result": "same_source_or_person"},
            {"candidateId": "three", "result": "different_source_or_person"},
        ],
    }


class ResolutionTests(unittest.TestCase):
    def test_connected_same_person_candidates_form_one_group(self):
        result = resolve_candidates(audit(), decisions())
        self.assertEqual(result["coverage"]["confirmedGroups"], 1)
        self.assertEqual(result["coverage"]["confirmedGroupMembers"], 3)
        self.assertEqual(result["coverage"]["confirmedCrossSplitGroups"], 1)
        self.assertTrue(result["decision"]["splitIndependenceViolated"])
        self.assertFalse(result["decision"]["trainingAuthorized"])

    def test_missing_decision_rejected(self):
        receipt = decisions()
        receipt["decisions"].pop()
        with self.assertRaises(ResolutionError):
            resolve_candidates(audit(), receipt)

    def test_archive_mismatch_rejected(self):
        receipt = decisions()
        receipt["source"]["archiveSHA256"] = "b" * 64
        with self.assertRaises(ResolutionError):
            resolve_candidates(audit(), receipt)


if __name__ == "__main__":
    unittest.main()
