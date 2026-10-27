import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_regional_mask_group_coverage_review import build_review
from build_regional_mask_identity_candidates import (
    AuditError,
    build_candidates,
    evaluate_candidates,
)


SOURCE_SHA = "a" * 64
EXPORT_SHA = "b" * 64


class RegionalMaskIdentityCandidateTests(unittest.TestCase):
    def _export(self, root: Path) -> Path:
        for split, count in (("train", 244), ("valid", 63), ("test", 30)):
            folder = root / split
            folder.mkdir()
            images = []
            for index in range(count):
                image_id = index + {"train": 0, "valid": 1000, "test": 2000}[split]
                name = f"private-{split}-{index}.jpg"
                images.append({"id": image_id, "file_name": name, "width": 40, "height": 40})
                color = (
                    (index * 37 + image_id) % 255,
                    (index * 71 + image_id // 2) % 255,
                    (index * 19 + image_id // 3) % 255,
                )
                pixels = Image.new("RGB", (40, 40), color)
                # Add deterministic structure so hash rankings are not all tied.
                for x in range(index % 17):
                    pixels.putpixel((x, (index * 3 + x) % 40), (255, 255, 255))
                pixels.save(folder / name)
            payload = {
                "images": images,
                "annotations": "not-read-by-identity-candidate-builder",
                "categories": [],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))

        # Build the exact coverage queue from a separate valid metadata fixture.
        coverage_root = root.parent / "coverage"
        coverage_root.mkdir()
        for split, count in (("train", 244), ("valid", 63), ("test", 30)):
            folder = coverage_root / split
            folder.mkdir()
            source = json.loads((root / split / "_annotations.coco.json").read_text())
            annotations = []
            for index, image in enumerate(source["images"]):
                annotations.append({"image_id": image["id"], "category_id": 1})
            targets = {"train": (780, 429), "valid": (195, 105), "test": (90, 37)}[split]
            for class_id, total in ((1, targets[0]), (2, targets[1])):
                existing = sum(row["category_id"] == class_id for row in annotations)
                for index in range(total - existing):
                    annotations.append({"image_id": source["images"][index % count]["id"], "category_id": class_id})
            payload = {
                "images": source["images"],
                "annotations": annotations,
                "categories": [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))
        queue, _, _ = build_review(coverage_root, SOURCE_SHA, EXPORT_SHA)
        queue_path = root.parent / "coverage-queue.json"
        queue_path.write_text(json.dumps(queue))
        return queue_path

    def test_candidate_queue_is_private_bounded_and_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            root.mkdir()
            coverage = self._export(root)
            queue, template, resolver = build_candidates(root, coverage, SOURCE_SHA, EXPORT_SHA)
            self.assertEqual(queue["coverage"]["selectedCandidates"], 48)
            self.assertEqual(sum(queue["method"]["splitPairQuotas"].values()), 48)
            self.assertEqual(len(resolver), 337)
            self.assertEqual(len(template["items"]), 48)
            rendered = json.dumps(queue)
            self.assertNotIn("private-train", rendered)
            self.assertNotIn(str(root), rendered)
            self.assertFalse(queue["decision"]["currentSplitIndependent"])

    def test_blank_decisions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            root.mkdir()
            coverage = self._export(root)
            queue, template, _ = build_candidates(root, coverage, SOURCE_SHA, EXPORT_SHA)
            result = evaluate_candidates(queue, template)
            self.assertEqual(result["reviewedCandidates"], 0)
            self.assertIn("candidate_review_incomplete", result["blockers"])
            self.assertFalse(result["trainingAuthorized"])

    def test_complete_candidate_review_still_cannot_claim_full_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            root.mkdir()
            coverage = self._export(root)
            queue, decisions, _ = build_candidates(root, coverage, SOURCE_SHA, EXPORT_SHA)
            decisions["reviewerRole"] = "authorized_source_identity_reviewer"
            decisions["attestations"] = {key: True for key in decisions["attestations"]}
            for row in decisions["items"]:
                row.update({"decision": "different_person_or_source", "reviewMethod": "private_visual_pair_review"})
            result = evaluate_candidates(queue, decisions)
            self.assertTrue(result["candidateReviewComplete"])
            self.assertFalse(result["personOrSourceCoverageComplete"])
            self.assertFalse(result["currentSplitIndependent"])

    def test_export_must_match_every_coverage_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            root.mkdir()
            coverage = self._export(root)
            payload_path = root / "test" / "_annotations.coco.json"
            payload = json.loads(payload_path.read_text())
            payload["images"].pop()
            payload_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AuditError, "exact coverage item"):
                build_candidates(root, coverage, SOURCE_SHA, EXPORT_SHA)


if __name__ == "__main__":
    unittest.main()
