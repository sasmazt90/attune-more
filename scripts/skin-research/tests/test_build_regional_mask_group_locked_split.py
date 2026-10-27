import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_regional_mask_group_locked_split.py"
SPEC = importlib.util.spec_from_file_location("regional_group_split", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fixture():
    items = []
    decisions = []
    for index in range(337):
        review_id = f"ri-{index:024x}"
        items.append({
            "reviewItemId": review_id,
            "currentSplit": "train",
            "sourceAnnotationCounts": {
                "Oily": 1 + (index % 3),
                "Redness": 1 if index % 2 else 2,
            },
        })
        decisions.append({
            "reviewItemId": review_id,
            "sourcePersonGroupId": f"sg-{index:024x}",
            "reviewMethod": "visual_same_person_review",
            "decision": "reviewed_group",
        })
    binding = MODULE._digest(items)
    queue = {
        "schemaVersion": "regional-mask-source-person-review-queue-v1",
        "source": {
            "project": "tolgar-sasmaz/attune-skin-regional-skin-map",
            "versionNumber": 1,
            "providerExportSHA256": "a" * 64,
        },
        "coverage": {"queueItemsSHA256": binding},
        "items": items,
    }
    decision_doc = {
        "schemaVersion": "regional-mask-source-person-review-decisions-v1",
        "queueItemsSHA256": binding,
        "items": decisions,
        "attestations": {"allRecordsVisuallyOrProvenanceReviewed": True},
    }
    return queue, decision_doc


class RegionalGroupLockedSplitTests(unittest.TestCase):
    def test_manifest_is_complete_group_locked_and_deterministic(self):
        queue, decisions = fixture()
        first = MODULE.build_manifest(queue, decisions)
        second = MODULE.build_manifest(queue, decisions)
        self.assertEqual(first, second)
        self.assertEqual(first["result"]["records"], {
            "train": 236, "valid": 50, "final_test": 51,
        })
        self.assertEqual(first["result"]["crossSplitGroupCount"], 0)
        self.assertEqual(len(first["assignments"]), 337)
        split_for_group = {}
        for row in first["assignments"]:
            split_for_group.setdefault(row["sourcePersonGroupId"], row["targetSplit"])
            self.assertEqual(split_for_group[row["sourcePersonGroupId"]], row["targetSplit"])

    def test_unreviewed_record_fails_closed(self):
        queue, decisions = fixture()
        broken = copy.deepcopy(decisions)
        broken["items"][0]["decision"] = "unreviewed"
        with self.assertRaisesRegex(MODULE.SplitError, "all records require"):
            MODULE.build_manifest(queue, broken)

    def test_queue_binding_mismatch_fails_closed(self):
        queue, decisions = fixture()
        broken = copy.deepcopy(decisions)
        broken["queueItemsSHA256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.SplitError, "not bound"):
            MODULE.build_manifest(queue, broken)


if __name__ == "__main__":
    unittest.main()
