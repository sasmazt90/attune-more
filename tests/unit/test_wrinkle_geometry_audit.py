"""Wrinkle-source geometry audit regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/skin-research/audit_wrinkle_geometry.py"
spec = importlib.util.spec_from_file_location("wrinkle_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_archive(path):
    categories = [{"id": 1, "name": "wrinkles"}, {"id": 2, "name": "other"}]
    with zipfile.ZipFile(path, "w") as archive:
        for split in module.SPLITS:
            images = [{"id": 1, "file_name": f"{split}.jpg", "width": 100, "height": 100}]
            annotations = [{
                "id": 1, "image_id": 1, "category_id": 1,
                "bbox": [10, 20, 40, 30], "segmentation": [[10, 20, 50, 20, 45, 50, 12, 48]],
            }]
            if split == "train":
                annotations.append({
                    "id": 2, "image_id": 1, "category_id": 1,
                    "bbox": [0, 0, 100, 100], "segmentation": [[0, 0, 100, 0, 100, 100, 0, 100]],
                })
            archive.writestr(f"{split}/x.jpg", b"not-decoded-by-this-audit")
            archive.writestr(f"{split}/_annotations.coco.json", json.dumps({
                "images": images, "annotations": annotations, "categories": categories,
            }))


def test_polygon_and_rectangle_are_separate_and_not_accepted():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "fixture.zip"
        make_archive(source)
        result = module.audit(source, "wrinkles")
        assert result["annotations"] == 4
        assert result["imagesWithClass"] == 3
        assert result["geometry"] == {"polygon": 3, "rectangle-polygon": 1}
        assert result["descriptiveBuckets"]["maskAreaAtLeast40Percent"] == 0
        assert result["acceptance"]["crowsFeetDefinitionSupported"] is False
        assert result["acceptance"]["genericWrinkleTrainingAuthorized"] is False


def test_area_and_quantile_math():
    area, points = module.polygon_area([0, 0, 4, 0, 4, 3, 0, 3])
    assert area == 12
    assert module.is_axis_rectangle(points)
    assert module.quantiles([1, 2, 3, 4, 5])["median"] == 3


def test_unsafe_archive_member_rejected():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "unsafe.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("../bad", b"x")
        try:
            module.audit(source, "wrinkles")
        except ValueError as error:
            assert str(error) == "UNSAFE_ARCHIVE_MEMBER"
        else:
            raise AssertionError("unsafe member must be rejected")
