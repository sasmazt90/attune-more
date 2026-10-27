import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_under_eye_source_groups import AuditError, _sha256_file, audit_under_eye_archive


SALT = "under-eye-source-audit-test-salt"


def _jpeg(color):
    output = io.BytesIO()
    Image.new("RGB", (48, 32), color).save(output, format="JPEG")
    return output.getvalue()


def _fixture(path: Path, duplicate: bool = False) -> None:
    names = {
        "train": "aaaaaaaa-123456_left_jpg.rf." + "1" * 32 + ".jpg",
        "valid": "bbbbbbbb-123456_right_jpg.rf." + "2" * 32 + ".jpg",
        "test": "cccccccc-999999_left_jpg.rf." + "3" * 32 + ".jpg",
    }
    colors = {"train": (120, 80, 40), "valid": (20, 160, 210), "test": (210, 30, 90)}
    if duplicate:
        colors["valid"] = colors["train"]
    with zipfile.ZipFile(path, "w") as archive:
        for index, split in enumerate(("train", "valid", "test"), start=1):
            name = names[split]
            archive.writestr(f"{split}/{name}", _jpeg(colors[split]))
            archive.writestr(
                f"{split}/_annotations.coco.json",
                json.dumps({"images": [{"id": index, "file_name": name}], "annotations": []}),
            )


class UnderEyeSourceAuditTests(unittest.TestCase):
    def test_finds_explicit_cross_split_pair_without_persisting_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.zip"
            _fixture(source)
            audit, resolver = audit_under_eye_archive(source, _sha256_file(source), SALT)
            self.assertEqual(audit["inventory"]["images"], 3)
            self.assertEqual(audit["inventory"]["explicitCompleteSourcePhotoPairs"], 1)
            self.assertEqual(audit["inventory"]["explicitCrossSplitSourcePhotoPairs"], 1)
            self.assertFalse(audit["decision"]["personIndependenceEstablished"])
            rendered = json.dumps(audit)
            self.assertNotIn("123456", rendered)
            self.assertNotIn("left_jpg", rendered)
            self.assertEqual(len(resolver), 3)

    def test_exact_image_is_candidate_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.zip"
            _fixture(source, duplicate=True)
            audit, _ = audit_under_eye_archive(source, _sha256_file(source), SALT)
            self.assertGreaterEqual(audit["inventory"]["exactByteMatches"], 1)
            self.assertGreaterEqual(audit["inventory"]["tightPerceptualThresholdMatches"], 1)
            self.assertFalse(audit["decision"]["trainingAuthorized"])

    def test_rejects_wrong_source_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.zip"
            _fixture(source)
            with self.assertRaisesRegex(AuditError, "does not match"):
                audit_under_eye_archive(source, "0" * 64, SALT)

    def test_rejects_unsafe_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.zip"
            _fixture(source)
            with zipfile.ZipFile(source, "a") as archive:
                archive.writestr("../escape", b"bad")
            with self.assertRaisesRegex(AuditError, "unsafe"):
                audit_under_eye_archive(source, _sha256_file(source), SALT)


if __name__ == "__main__":
    unittest.main()
