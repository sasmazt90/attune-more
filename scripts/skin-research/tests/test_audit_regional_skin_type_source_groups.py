import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_regional_skin_type_source_groups import AuditError, audit_source_groups


ARCHIVE_SHA = "a" * 64
SALT = "regional-source-groups-test-v1"


class SourceGroupAuditTests(unittest.TestCase):
    def _export(self, root: Path, duplicate: bool = False) -> None:
        colors = {"train": (120, 90, 70), "valid": (25, 180, 210), "test": (210, 40, 130)}
        for index, split in enumerate(("train", "valid", "test"), start=1):
            folder = root / split
            folder.mkdir()
            name = f"synthetic{index}_jpg.rf.{str(index) * 32}.jpg"
            color = colors[split]
            if duplicate and split == "valid":
                color = colors["train"]
            Image.new("RGB", (40, 40), color).save(folder / name)
            payload = {
                "images": [{"id": index, "file_name": name, "width": 40, "height": 40}],
                "annotations": [],
                "categories": [],
            }
            (folder / "_annotations.coco.json").write_text(json.dumps(payload))

    def test_exact_cross_split_candidate_is_hashed_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root, duplicate=True)
            audit, resolver = audit_source_groups(root, ARCHIVE_SHA, SALT)
            self.assertEqual(audit["inventory"]["exactNormalizedPixelCandidates"], 1)
            self.assertFalse(audit["decision"]["personIndependenceEstablished"])
            self.assertEqual(len(resolver), 3)
            rendered = json.dumps(audit)
            self.assertNotIn("synthetic1", rendered)
            self.assertNotIn(str(root), rendered)

    def test_distinct_sources_remain_candidate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            audit, _ = audit_source_groups(root, ARCHIVE_SHA, SALT, dhash_max_distance=0, phash_max_distance=0)
            self.assertEqual(audit["inventory"]["sourceIdsCrossingSplits"], 0)
            self.assertFalse(audit["decision"]["testEligibleForFinalAcceptance"])

    def test_short_salt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._export(root)
            with self.assertRaises(AuditError):
                audit_source_groups(root, ARCHIVE_SHA, "short")


if __name__ == "__main__":
    unittest.main()
