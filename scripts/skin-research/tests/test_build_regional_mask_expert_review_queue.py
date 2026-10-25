import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_regional_mask_expert_review_queue import AuditError, build_queue


SOURCE_SHA = "a" * 64
EXPORT_SHA = "b" * 64
SALT = "regional-mask-expert-review-test-v1"


class RegionalMaskExpertReviewQueueTests(unittest.TestCase):
    def _export(self, root: Path) -> None:
        for split, count in (("train", 244), ("valid", 63), ("test", 30)):
            folder = root / split
            folder.mkdir()
            images = []
            annotations = []
            for index in range(count):
                image_id = index + {"train": 0, "valid": 1000, "test": 2000}[split]
                name = f"synthetic-{split}-{index}.jpg"
                images.append({"id": image_id, "file_name": name, "width": 100, "height": 100})
                if split == "valid" and index == 0:
                    class_ids = (1, 2)
                else:
                    class_ids = (1,) if index % 2 == 0 else (2,)
                for class_id in class_ids:
                    annotations.append({
                        "id": len(annotations),
                        "image_id": image_id,
                        "category_id": class_id,
                        "area": 100 + index,
                        "segmentation": [[1, 1, 11, 1, 11, 11, 1, 11]],
                    })
            payload = {
                "images": images,
                "annotations": annotations,
                "categories": [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))

    def test_queue_is_private_deterministic_and_test_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            first, resolver = build_queue(root, SOURCE_SHA, EXPORT_SHA, SALT)
            second, _ = build_queue(root, SOURCE_SHA, EXPORT_SHA, SALT)
            self.assertEqual(first, second)
            self.assertEqual(first["selection"]["testImagesRead"], 0)
            self.assertEqual(first["selection"]["testImagesSelected"], 0)
            self.assertGreaterEqual(first["selection"]["selectedUniqueImages"], 80)
            self.assertTrue(all(row["split"] in {"train", "valid"} for row in first["items"]))
            self.assertEqual(len(resolver), 307)
            rendered = json.dumps(first)
            self.assertNotIn("synthetic-train", rendered)
            self.assertNotIn(str(root), rendered)
            self.assertFalse(first["decision"]["trainingAuthorized"])

    def test_wrong_split_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            path = root / "valid" / "_annotations.coco.json"
            payload = json.loads(path.read_text())
            payload["images"].pop()
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AuditError, "image counts"):
                build_queue(root, SOURCE_SHA, EXPORT_SHA, SALT)

    def test_invalid_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            with self.assertRaisesRegex(AuditError, "digests"):
                build_queue(root, "bad", EXPORT_SHA, SALT)


if __name__ == "__main__":
    unittest.main()
