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


def write_archive(
    root: Path,
    changed_split=None,
    rotate_split=None,
    box_only_split=None,
    outside_split=None,
    self_intersect_split=None,
    unsafe_path_split=None,
    invalid_bbox_split=None,
    invalid_area_split=None,
    duplicate_categories_split=None,
    duplicate_content=False,
):
    for index, split in enumerate(MODULE.SPLITS, start=1):
        split_root = root / split
        split_root.mkdir(parents=True)
        file_name = "../outside.jpg" if split == unsafe_path_split else f"private-provider-{split}.jpg"
        (split_root / file_name).write_bytes(
            b"same-image" if duplicate_content else f"image-{split}".encode()
        )
        category = 2 if split == changed_split else 1
        polygon = [1, 2, 4, 2, 4, 6, 1, 6]
        if split == rotate_split:
            polygon = [4, 2, 4, 6, 1, 6, 1, 2]
        if split == outside_split:
            polygon = [1, 2, 14, 2, 4, 6, 1, 6]
        if split == self_intersect_split:
            polygon = [1, 2, 4, 6, 1, 6, 4, 2]
        categories = [{"id": 1, "name": "Oily"}, {"id": 2, "name": "Redness"}]
        if split == duplicate_categories_split:
            categories[1]["id"] = 1
        coco = {
            "images": [{"id": 100 + index, "file_name": file_name, "width": 10, "height": 12}],
            "categories": categories,
            "annotations": [{
                "id": 200 + index,
                "image_id": 100 + index,
                "category_id": category,
                "bbox": [9, 10, 3, 4] if split == invalid_bbox_split else [1, 2, 3, 4],
                "segmentation": [] if split == box_only_split else [polygon],
                "area": 0 if split == invalid_area_split else 12,
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
            self.assertTrue(result["polygonGeometryVerified"])
            self.assertFalse(result["boxGeometryAcceptedAsPolygonTruth"])
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

    def test_polygon_ring_rotation_is_equivalent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, rotate_split="valid")
            result = MODULE.build_audit(expected, provider, MANIFEST, 2)
            self.assertTrue(result["polygonGeometryVerified"])

    def test_box_only_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, box_only_split="test")
            with self.assertRaisesRegex(MODULE.AuditError, "boxes are not polygon truth"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_outside_polygon_point_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, outside_split="train")
            with self.assertRaisesRegex(MODULE.AuditError, "outside points"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_duplicate_or_cross_split_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected, duplicate_content=True)
            write_archive(provider, duplicate_content=True)
            with self.assertRaisesRegex(MODULE.AuditError, "cross-split image content"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_path_traversal_is_rejected_before_private_bytes_are_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, unsafe_path_split="valid")
            with self.assertRaisesRegex(MODULE.AuditError, "path is unsafe"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_self_intersecting_polygon_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, self_intersect_split="train")
            with self.assertRaisesRegex(MODULE.AuditError, "self-intersects"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_bbox_and_area_must_be_valid_inside_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, invalid_bbox_split="test")
            with self.assertRaisesRegex(MODULE.AuditError, "bbox is invalid"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)
            provider = root / "provider-area"
            write_archive(provider, invalid_area_split="test")
            with self.assertRaisesRegex(MODULE.AuditError, "area is invalid"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)

    def test_duplicate_category_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            provider = root / "provider"
            write_archive(expected)
            write_archive(provider, duplicate_categories_split="valid")
            with self.assertRaisesRegex(MODULE.AuditError, "class inventory changed"):
                MODULE.build_audit(expected, provider, MANIFEST, 2)


if __name__ == "__main__":
    unittest.main()

