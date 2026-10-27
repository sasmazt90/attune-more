import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_regional_mask_group_coverage_review import (
    AuditError,
    build_review,
    evaluate_decisions,
)


SOURCE_SHA = "a" * 64
EXPORT_SHA = "b" * 64


class RegionalMaskGroupCoverageReviewTests(unittest.TestCase):
    def _export(self, root: Path) -> None:
        for split, count in (("train", 244), ("valid", 63), ("test", 30)):
            folder = root / split
            folder.mkdir()
            images = []
            annotations = []
            for index in range(count):
                image_id = index + {"train": 0, "valid": 1000, "test": 2000}[split]
                name = f"private-{split}-{index}.jpg"
                images.append({"id": image_id, "file_name": name, "width": 100, "height": 100})
                for class_id in ((1, 2) if index % 7 == 0 else (1 if index % 2 == 0 else 2,)):
                    annotations.append({
                        "id": len(annotations),
                        "image_id": image_id,
                        "category_id": class_id,
                        "segmentation": [[1, 1, 10, 1, 10, 10]],
                    })
            # Fill to the exact frozen class totals without changing the image inventory.
            target = {"train": (780, 429), "valid": (195, 105), "test": (90, 37)}[split]
            counts = [sum(row["category_id"] == class_id for row in annotations) for class_id in (1, 2)]
            for class_id, needed in ((1, target[0] - counts[0]), (2, target[1] - counts[1])):
                for offset in range(needed):
                    annotations.append({
                        "id": len(annotations),
                        "image_id": images[offset % len(images)]["id"],
                        "category_id": class_id,
                        "segmentation": [[1, 1, 10, 1, 10, 10]],
                    })
            payload = {
                "images": images,
                "annotations": annotations,
                "categories": [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))

    def test_queue_covers_every_record_without_private_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            queue, template, resolver = build_review(root, SOURCE_SHA, EXPORT_SHA)
            self.assertEqual(queue["coverage"]["records"], 337)
            self.assertEqual(len(queue["items"]), 337)
            self.assertEqual(len(template["items"]), 337)
            self.assertEqual(len(resolver), 337)
            rendered = json.dumps(queue)
            self.assertNotIn("private-train", rendered)
            self.assertNotIn(str(root), rendered)
            self.assertFalse(queue["decision"]["currentSplitIndependent"])

    def test_blank_template_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            queue, template, _ = build_review(root, SOURCE_SHA, EXPORT_SHA)
            result = evaluate_decisions(queue, template)
            self.assertEqual(result["reviewedRecords"], 0)
            self.assertIn("source_person_review_incomplete", result["blockers"])
            self.assertFalse(result["trainingAuthorized"])

    def test_complete_review_detects_cross_split_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            queue, decisions, _ = build_review(root, SOURCE_SHA, EXPORT_SHA)
            decisions["reviewerRole"] = "authorized_source_identity_reviewer"
            decisions["attestations"] = {key: True for key in decisions["attestations"]}
            for index, row in enumerate(decisions["items"]):
                row.update({
                    "sourcePersonGroupId": f"sg-{index:024x}",
                    "reviewMethod": "visual_same_person_review",
                    "decision": "reviewed_group",
                })
            # Deliberately bind one train and one test item to the same reviewed group.
            by_split = {}
            for row in queue["items"]:
                by_split.setdefault(row["currentSplit"], row["reviewItemId"])
            indexed = {row["reviewItemId"]: row for row in decisions["items"]}
            indexed[by_split["test"]]["sourcePersonGroupId"] = indexed[by_split["train"]]["sourcePersonGroupId"]
            result = evaluate_decisions(queue, decisions)
            self.assertTrue(result["personOrSourceCoverageComplete"])
            self.assertEqual(result["crossSplitGroupCount"], 1)
            self.assertTrue(result["replacementSplitRequired"])
            self.assertFalse(result["currentSplitIndependent"])

    def test_queue_binding_and_exact_coverage_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            queue, decisions, _ = build_review(root, SOURCE_SHA, EXPORT_SHA)
            decisions["queueItemsSHA256"] = "0" * 64
            with self.assertRaisesRegex(AuditError, "exact queue"):
                evaluate_decisions(queue, decisions)


if __name__ == "__main__":
    unittest.main()
