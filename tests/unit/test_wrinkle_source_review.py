"""Wrinkle source review-board regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/skin-research/render_wrinkle_source_review.py"
spec = importlib.util.spec_from_file_location("wrinkle_review", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_archive(path):
    with zipfile.ZipFile(path, "w") as archive:
        for split in module.SPLITS:
            file_name = f"same_jpg.rf.{split}.jpg"
            archive.writestr(f"{split}/{file_name}", b"not-needed-for-selection")
            archive.writestr(f"{split}/_annotations.coco.json", json.dumps({
                "images": [{"id": 1, "file_name": file_name, "width": 100, "height": 100}],
                "categories": [{"id": 1, "name": "wrinkles"}],
                "annotations": [{"id": 1, "image_id": 1, "category_id": 1,
                                 "bbox": [10, 10, 20, 20],
                                 "segmentation": [[10, 10, 30, 10, 30, 30, 10, 30]]}],
            }))


def test_source_stem_removes_only_roboflow_suffix():
    assert module.source_stem("same_jpg.rf.abc.jpg") == "same_jpg"
    assert module.source_stem("person.v2.jpg") == "person.v2"


def test_cross_split_filename_candidates_are_prioritized():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "fixture.zip"
        make_archive(source)
        rows = module.load_rows(source, "wrinkles")
        selected, reasons = module.choose_rows(rows, 2)
        assert len(selected) == 2
        assert {row["split"] for row in selected} == {"test", "train"}
        assert set(reasons.values()) == {"cross-split-filename-candidate"}


def test_unsafe_archive_member_rejected():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "unsafe.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("../bad", b"x")
        try:
            module.load_rows(source, "wrinkles")
        except ValueError as error:
            assert str(error) == "UNSAFE_ARCHIVE_MEMBER"
        else:
            raise AssertionError("unsafe member must be rejected")
