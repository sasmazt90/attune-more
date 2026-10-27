import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_regional_mask_source_groups import AuditError, build_audit


SOURCE_SHA = "a" * 64
EXPORT_SHA = "b" * 64
SALT = "regional-mask-source-test-v1"


class RegionalMaskSourceAuditTests(unittest.TestCase):
    def _export(self, root: Path, duplicate: bool = False, invalid: bool = False) -> None:
        colors = {"train": (120, 90, 70), "valid": (25, 180, 210), "test": (210, 40, 130)}
        counts = {"train": 244, "valid": 63, "test": 30}
        for split in ("train", "valid", "test"):
            folder = root / split
            folder.mkdir()
            images = []
            annotations = []
            for index in range(counts[split]):
                image_id = {"train": 0, "valid": 1000, "test": 2000}[split] + index
                name = f"{split}-{index}_jpg.rf.{image_id:032x}.jpg"
                color = colors[split]
                if duplicate and split == "valid" and index == 0:
                    color = colors["train"]
                Image.new("RGB", (40, 40), color).save(folder / name)
                images.append({"id": image_id, "file_name": name, "width": 40, "height": 40})
                category_id = 1 if index % 2 == 0 else 2
                polygon = [1, 1, 20, 1, 20, 20, 1, 20]
                if invalid and split == "test" and index == 0:
                    polygon = [1, 1, 50, 1, 20, 20]
                annotations.append({
                    "id": image_id,
                    "image_id": image_id,
                    "category_id": category_id,
                    "segmentation": [polygon],
                    "bbox": [1, 1, 19, 19],
                    "area": 361,
                })
            payload = {
                "images": images,
                "annotations": annotations,
                "categories": [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))

    def test_geometry_and_privacy_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            audit, resolver = build_audit(root, SOURCE_SHA, EXPORT_SHA, SALT)
            self.assertEqual(audit["inventory"]["images"], 337)
            self.assertEqual(audit["inventory"]["polygonAnnotations"], 337)
            self.assertEqual(audit["inventory"]["invalidPolygonAnnotations"], 0)
            self.assertEqual(len(resolver), 337)
            self.assertFalse(audit["decision"]["personIndependenceEstablished"])
            rendered = json.dumps(audit)
            self.assertNotIn("train-0", rendered)
            self.assertNotIn(str(root), rendered)

    def test_exact_candidate_remains_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root, duplicate=True)
            audit, _ = build_audit(root, SOURCE_SHA, EXPORT_SHA, SALT)
            self.assertGreater(audit["inventory"]["crossSplitPerceptualCandidates"], 0)
            self.assertFalse(audit["decision"]["replacementSplitReady"])

    def test_invalid_polygon_is_counted_not_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root, invalid=True)
            audit, _ = build_audit(root, SOURCE_SHA, EXPORT_SHA, SALT)
            self.assertEqual(audit["inventory"]["invalidPolygonAnnotations"], 1)
            self.assertFalse(audit["decision"]["trainingAuthorized"])

    def test_wrong_split_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            payload_path = root / "test" / "_annotations.coco.json"
            payload = json.loads(payload_path.read_text())
            payload["images"].pop()
            payload["annotations"].pop()
            payload_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AuditError, "split counts"):
                build_audit(root, SOURCE_SHA, EXPORT_SHA, SALT)


if __name__ == "__main__":
    unittest.main()
