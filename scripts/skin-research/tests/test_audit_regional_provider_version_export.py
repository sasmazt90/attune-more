import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "audit_regional_provider_version_export.py"
SPEC = importlib.util.spec_from_file_location("regional_provider_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
MANIFEST = Path(__file__).parents[3] / "docs/skin/evidence/regional-mask-group-locked-split-20261027-v1.json"


def write_archive(root: Path, changed_split=None):
    for index, split in enumerate(MODULE.SPLITS, start=1):
        split_root = root / split
        split_root.mkdir(parents=True)
        file_name = f"private-provider-{split}.jpg"
        (split_root / file_name).write_bytes(f"image-{split}".encode())
        category = 2 if split == changed_split else 1
        coco = {
            "images": [{"id": 100 + index, "file_name": file_name, "width": 10, "height": 12}],
            "categories": [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}],
            "annotations": [{
                "id": 200 + index,
                "image_id": 100 + index,
                "category_id": category,
                "bbox": [1, 2, 3, 4],
                "segmentation": [[1, 2, 3, 4, 5, 6]],
                "area": 12,
                "iscrowd": 0,
            }],
        }
        (split_root / "_annotations.coco.json").write_text(json.dumps(coco), encoding="utf-8")


class RegionalProviderVersionExportAuditTests(unittest.TestCase):
    def test_exact_archives_emit_only_privacy_safe_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider)
            result = MODULE.build_audit(expected, provider, MANIFEST, 2)
            self.assertTrue(result["allProviderRecordsMatchedManifestOnce"])
            self.assertEqual(result["images"], 3)
            serialized = json.dumps(result)
            self.assertNotIn("private-provider", serialized)
            self.assertNotIn("image_id", serialized)

    def test_annotation_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, changed_split="valid")
            with self.assertRaisesRegex(MODULE.AuditError, "valid archive"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)


if __name__ == "__main__":
    unittest.main()
