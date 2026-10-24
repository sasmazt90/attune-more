import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_acne_semantic_review_queue.py"
SPEC = importlib.util.spec_from_file_location("acne_semantic_queue", SCRIPT)
queue_module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(queue_module)


def write_split(root: Path, split: str, rows):
    folder = root / split
    folder.mkdir()
    images, annotations = [], []
    categories = [
        {"id": index + 1, "name": name}
        for index, name in enumerate(queue_module.CLASSES)
    ]
    class_ids = {row["name"]: row["id"] for row in categories}
    annotation_id = 1
    for image_id, (name, classes) in enumerate(rows, 1):
        (folder / name).write_bytes((name + split).encode())
        images.append({"id": image_id, "file_name": name, "width": 100, "height": 100})
        for index, class_name in enumerate(classes):
            annotations.append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": class_ids[class_name],
                "bbox": [index, index, index + 1, index + 1],
            })
            annotation_id += 1
    (folder / "_annotations.coco.json").write_text(json.dumps({
        "images": images, "annotations": annotations, "categories": categories,
    }), encoding="utf-8")


class AcneSemanticReviewQueueTest(unittest.TestCase):
    def dataset(self, root: Path):
        rows = [
            ("pimple.jpg", ["Pimple"]),
            ("marks.jpg", ["Post acne"]),
            ("pigment.jpg", ["Pigmentation"]),
            ("mixed.jpg", list(queue_module.CLASSES)),
            ("negative.jpg", []),
        ]
        write_split(root, "train", rows)
        write_split(root, "valid", rows)
        write_split(root, "test", rows)

    def test_builds_privacy_safe_queue_without_test_items(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            queue, resolver = queue_module.build_queue(root, "a" * 64)
        self.assertEqual(queue["dataset"]["images"], 15)
        self.assertEqual(queue["dataset"]["reviewPoolImages"], 10)
        self.assertEqual(queue["dataset"]["lockedTestImages"], 5)
        self.assertTrue(queue["reviewItems"])
        self.assertTrue(all(row["split"] != "test" for row in queue["reviewItems"]))
        self.assertTrue(any(row["purpose"] == "hard_negative_other_target" for row in queue["reviewItems"]))
        self.assertTrue(any(row["purpose"] == "unlabelled_negative" for row in queue["reviewItems"]))
        self.assertNotIn("pimple.jpg", json.dumps(queue))
        self.assertIn("pimple.jpg", resolver.values())
        self.assertFalse(queue["decision"]["trainingAuthorized"])

    def test_receipt_template_is_bound_and_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            queue, _ = queue_module.build_queue(root, "b" * 64)
        receipt = queue_module.build_receipt_template(queue)
        self.assertEqual(receipt["datasetArchiveSHA256"], "b" * 64)
        self.assertEqual(len(receipt["reviewPackageCanonicalSHA256"]), 64)
        self.assertEqual([row["name"] for row in receipt["classes"]], list(queue_module.CLASSES))
        self.assertTrue(all(row["expertReviewed"] is False for row in receipt["classes"]))

    def test_rejects_path_traversal_and_bad_archive_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            with self.assertRaisesRegex(queue_module.QueueError, "archive sha256"):
                queue_module.build_queue(root, "bad")
            path = root / "valid" / "_annotations.coco.json"
            value = json.loads(path.read_text())
            value["images"][0]["file_name"] = "../escape.jpg"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(queue_module.QueueError, "image fields"):
                queue_module.build_queue(root, "c" * 64)


if __name__ == "__main__":
    unittest.main()
