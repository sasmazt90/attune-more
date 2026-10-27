import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "build_under_eye_grouped_archive.py"
SPEC = importlib.util.spec_from_file_location("build_under_eye_grouped_archive", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


EXPECTED = {
    "images": 3,
    "annotations": 3,
    "splits": {"train": 1, "valid": 1, "test": 1},
    "classes": {"darkcircle": 2, "eyebag": 1},
    "reviewed_cross_split_pairs": 1,
    "moved_images": 1,
    "output_splits": {"train": 2, "valid": 0, "test": 1},
}


def _dataset(split, filename, category_id):
    return {
        "images": [{"id": 7, "file_name": filename, "width": 10, "height": 10}],
        "annotations": [{
            "id": 9,
            "image_id": 7,
            "category_id": category_id,
            "segmentation": [[1, 1, 5, 1, 5, 5, 1, 5]],
            "bbox": [1, 1, 4, 4],
            "area": 16,
            "iscrowd": 0,
        }],
        "categories": [
            {"id": 1, "name": "darkcircle"},
            {"id": 2, "name": "eyebag"},
        ],
        "info": {"split": split},
    }


def _fixture(tmp_path):
    source = tmp_path / "source.zip"
    names = {
        "train": "abc-pair_left.jpg.rf.aaaaaaaaaaaaaaaa.jpg",
        "valid": "abc-pair_right.jpg.rf.bbbbbbbbbbbbbbbb.jpg",
        "test": "independent.jpg.rf.cccccccccccccccc.jpg",
    }
    with zipfile.ZipFile(source, "w") as archive:
        for split, filename in names.items():
            category = 2 if split == "train" else 1
            archive.writestr(f"{split}/_annotations.coco.json", json.dumps(_dataset(split, filename, category)))
            archive.writestr(f"{split}/{filename}", f"pixels-{split}".encode())
        archive.writestr("README.txt", "fixture")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "reviewedSourcePhotoPairs": [{
            "crossSplit": True,
            "members": [names["train"], names["valid"]],
        }]
    }))
    return source, review


class BuildUnderEyeGroupedArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_build_is_deterministic_and_preserves_payloads(self):
        source, review = _fixture(self.tmp_path)
        one = self.tmp_path / "one.zip"
        two = self.tmp_path / "two.zip"
        receipt = MODULE.build_grouped_archive(source, review, one, expected=EXPECTED)
        MODULE.build_grouped_archive(source, review, two, expected=EXPECTED)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        self.assertEqual(receipt["output"]["splits"], {"train": 2, "valid": 0, "test": 1})
        self.assertEqual(receipt["imageBytesChanged"], 0)
        self.assertEqual(receipt["annotationPayloadsChanged"], 0)
        self.assertFalse(receipt["trainingAuthorized"])
        with zipfile.ZipFile(one) as archive:
            valid = json.loads(archive.read("valid/_annotations.coco.json"))
            self.assertEqual(valid["images"], [])
            self.assertEqual(valid["annotations"], [])

    def test_rejects_unreviewed_member(self):
        source, review = _fixture(self.tmp_path)
        review.write_text(json.dumps({
            "reviewedSourcePhotoPairs": [{
                "crossSplit": True,
                "members": ["missing_left.jpg", "missing_right.jpg"],
            }]
        }))
        with self.assertRaisesRegex(MODULE.ArchiveValidationError, "not present"):
            MODULE.build_grouped_archive(source, review, self.tmp_path / "out.zip", expected=EXPECTED)

    def test_rejects_unsafe_archive_member(self):
        source, review = _fixture(self.tmp_path)
        unsafe = self.tmp_path / "unsafe.zip"
        with zipfile.ZipFile(source) as src, zipfile.ZipFile(unsafe, "w") as dst:
            for info in src.infolist():
                dst.writestr(info.filename, src.read(info))
            dst.writestr("../escape", "bad")
        with self.assertRaisesRegex(MODULE.ArchiveValidationError, "unsafe ZIP member"):
            MODULE.build_grouped_archive(unsafe, review, self.tmp_path / "out.zip", expected=EXPECTED)

    def test_rejects_invalid_polygon(self):
        source, review = _fixture(self.tmp_path)
        invalid = self.tmp_path / "invalid.zip"
        with zipfile.ZipFile(source) as src, zipfile.ZipFile(invalid, "w") as dst:
            for info in src.infolist():
                payload = src.read(info)
                if info.filename == "test/_annotations.coco.json":
                    data = json.loads(payload)
                    data["annotations"][0]["segmentation"] = [[1, 2, 3]]
                    payload = json.dumps(data).encode()
                dst.writestr(info.filename, payload)
        with self.assertRaisesRegex(MODULE.ArchiveValidationError, "invalid polygon"):
            MODULE.build_grouped_archive(invalid, review, self.tmp_path / "out.zip", expected=EXPECTED)


if __name__ == "__main__":
    unittest.main()
