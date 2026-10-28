import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "audit_under_eye_grouped_provider_export.py"
SPEC = importlib.util.spec_from_file_location("under_eye_grouped_provider_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_archive(path: Path, *, changed_split=None, unsafe=False, box_only=False, rotate=False):
    entries = {}
    image_index = 1
    annotation_index = 1
    extra_annotations = 71
    class_remaining = {"darkcircle": 382, "eyebag": 487}
    for split, count in MODULE.EXPECTED["splits"].items():
        images = []
        annotations = []
        for local in range(count):
            file_name = f"private-{split}-{local}.jpg"
            image_bytes = f"private-image-{split}-{local}".encode()
            entries[f"{split}/{file_name}"] = image_bytes
            images.append({"id": image_index, "file_name": file_name, "width": 40, "height": 30})
            annotation_count = 3 if extra_annotations else 2
            if extra_annotations:
                extra_annotations -= 1
            for _ in range(annotation_count):
                class_name = "darkcircle" if class_remaining["darkcircle"] else "eyebag"
                class_remaining[class_name] -= 1
                polygon = [1, 2, 8, 2, 8, 9, 1, 9]
                if rotate:
                    polygon = [8.0, 2.0, 8.0, 9.0, 1.0, 9.0, 1.0, 2.0]
                if split == changed_split and local == 0:
                    polygon[-1] = 3
                annotations.append({
                    "id": annotation_index,
                    "image_id": image_index,
                    "category_id": 1 if class_name == "darkcircle" else 2,
                    "bbox": [1, 2, 7, 7],
                    "segmentation": [] if box_only else [polygon],
                    "area": 49,
                    "iscrowd": 0,
                })
                annotation_index += 1
            image_index += 1
        coco = {
            "images": images,
            "categories": [{"id": 1, "name": "darkcircle"}, {"id": 2, "name": "eyebag"}],
            "annotations": annotations,
        }
        entries[f"{split}/_annotations.coco.json"] = json.dumps(coco).encode()
    assert class_remaining == {"darkcircle": 0, "eyebag": 0}
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
        if unsafe:
            archive.writestr("../escape.txt", b"not allowed")


class UnderEyeGroupedProviderExportAuditTests(unittest.TestCase):
    def test_exact_archive_emits_privacy_safe_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.zip"
            provider = root / "provider.zip"
            write_archive(expected)
            write_archive(provider, rotate=True)
            expected_sha = hashlib.sha256(expected.read_bytes()).hexdigest()
            result = MODULE.build_audit(expected, provider, 1, expected_archive_sha256=expected_sha)
            self.assertTrue(result["allProviderRecordsMatchedAuthorizedArchiveOnce"])
            self.assertEqual(result["images"], 399)
            self.assertEqual(result["annotations"], 869)
            serialized = json.dumps(result)
            self.assertNotIn("private-", serialized)
            self.assertNotIn("image_id", serialized)
            self.assertFalse(result["researchTrainingAuthorized"])

    def test_polygon_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.zip"
            provider = root / "provider.zip"
            write_archive(expected)
            write_archive(provider, changed_split="valid")
            expected_sha = hashlib.sha256(expected.read_bytes()).hexdigest()
            with self.assertRaisesRegex(MODULE.AuditError, "valid archive"):
                MODULE.build_audit(expected, provider, 1, expected_archive_sha256=expected_sha)

    def test_boxes_cannot_substitute_for_polygons(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.zip"
            provider = root / "provider.zip"
            write_archive(expected)
            write_archive(provider, box_only=True)
            expected_sha = hashlib.sha256(expected.read_bytes()).hexdigest()
            with self.assertRaisesRegex(MODULE.AuditError, "boxes cannot substitute"):
                MODULE.build_audit(expected, provider, 1, expected_archive_sha256=expected_sha)

    def test_unsafe_zip_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.zip"
            provider = root / "provider.zip"
            write_archive(expected)
            write_archive(provider, unsafe=True)
            expected_sha = hashlib.sha256(expected.read_bytes()).hexdigest()
            with self.assertRaisesRegex(MODULE.AuditError, "unsafe ZIP"):
                MODULE.build_audit(expected, provider, 1, expected_archive_sha256=expected_sha)

    def test_authorized_archive_digest_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.zip"
            provider = root / "provider.zip"
            write_archive(expected)
            write_archive(provider)
            with self.assertRaisesRegex(MODULE.AuditError, "not the authorized"):
                MODULE.build_audit(expected, provider, 1, expected_archive_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
