import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_acne_validation_failure_queue.py"
SPEC = importlib.util.spec_from_file_location("acne_failure_queue", SCRIPT)
queue = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(queue)


def image(index: int):
    return {
        "imageId": f"private-{index}",
        "imageName": f"private-{index}.jpg",
        "split": "valid",
        "augmentations": 0,
        "cluster": {"id": index % 3},
        "stats": {"truePositives": 1, "falsePositives": 1, "falseNegatives": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5},
        "confusion": [[0, 3, 1 + index % 2], [3, 1, 1], [2, 1, 1]],
    }


def payload():
    return {
        "evalId": queue.EVAL_ID,
        "modelId": queue.MODEL_ID,
        "project": queue.PROJECT,
        "versionId": "1",
        "split": "valid",
        "confidenceThreshold": 0.3,
        "totalImages": queue.EXPECTED_IMAGES,
        "images": [image(index) for index in range(queue.EXPECTED_IMAGES)],
    }


class AcneValidationFailureQueueTest(unittest.TestCase):
    def test_complete_validation_payload_builds_privacy_safe_queue(self):
        result = queue.build_queue(payload(), observed_at="2026-10-28T19:40:00Z", per_class_limit=5)
        self.assertEqual(result["source"]["split"], "valid")
        self.assertFalse(result["source"]["testSplitRead"])
        self.assertTrue(result["decision"]["privateResolverRequired"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(len(result["classes"]["Pigmentation"]["reviewItems"]), 5)

    def test_private_identifiers_never_appear_in_output(self):
        result = queue.build_queue(payload(), observed_at="now", per_class_limit=2)
        serialized = str(result)
        self.assertNotIn("private-0", serialized)
        self.assertNotIn(".jpg", serialized)
        self.assertTrue(result["privacy"]["recordRefsAreSHA256Pseudonyms"])

    def test_test_split_rejects(self):
        value = payload(); value["split"] = "test"
        with self.assertRaisesRegex(queue.QueueError, "validation@0.30"):
            queue.build_queue(value, observed_at="now")

    def test_nonstored_threshold_rejects(self):
        value = payload(); value["confidenceThreshold"] = 0.35
        with self.assertRaisesRegex(queue.QueueError, "validation@0.30"):
            queue.build_queue(value, observed_at="now")

    def test_incomplete_inventory_rejects(self):
        value = payload(); value["images"].pop()
        with self.assertRaisesRegex(queue.QueueError, "all validation"):
            queue.build_queue(value, observed_at="now")

    def test_duplicate_private_row_rejects(self):
        value = payload(); value["images"][1] = copy.deepcopy(value["images"][0])
        with self.assertRaisesRegex(queue.QueueError, "duplicate validation"):
            queue.build_queue(value, observed_at="now")

    def test_augmented_row_rejects(self):
        value = payload(); value["images"][0]["augmentations"] = 1
        with self.assertRaisesRegex(queue.QueueError, "unaugmented"):
            queue.build_queue(value, observed_at="now")

    def test_invalid_confusion_index_rejects(self):
        value = payload(); value["images"][0]["confusion"][0][0] = 4
        with self.assertRaisesRegex(queue.QueueError, "out of range"):
            queue.build_queue(value, observed_at="now")


if __name__ == "__main__":
    unittest.main()
