"""Regression checks for the positive-only crows-feet review package."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import zipfile
import sys

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/skin-research/prepare_crows_feet_review_set.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("crows_review", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def picture(color):
    image = Image.new("RGB", (24, 24), color)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def make_archive(path):
    category = [{"id": 5, "name": "crows_feet"}, {"id": 9, "name": "wrinkle"}]
    valid = {"id": 1, "image_id": 1, "category_id": 5, "bbox": [2, 2, 8, 8],
             "segmentation": [[2, 2, 10, 3, 9, 10, 3, 9]], "area": 50, "iscrowd": 0}
    with zipfile.ZipFile(path, "w") as archive:
        for number, split in enumerate(module.SPLITS):
            images = [
                {"id": 1, "file_name": "same_jpg.rf.%s.png" % ("a" * 12 if split != "test" else "b" * 12),
                 "width": 24, "height": 24},
                {"id": 2, "file_name": f"negative-{split}.png", "width": 24, "height": 24},
            ]
            annotations = [{**valid}]
            if split == "train":
                annotations.append({"id": 2, "image_id": 1, "category_id": 5,
                                    "bbox": [0, 0, 20, 20],
                                    "segmentation": [[0, 0, 20, 20, 0, 20, 15, 0]],
                                    "area": 200, "iscrowd": 0})
            data = {"images": images, "annotations": annotations, "categories": category}
            archive.writestr(f"{split}/{images[0]['file_name']}", picture((20 + number, 40, 60)))
            archive.writestr(f"{split}/{images[1]['file_name']}", picture((200, 200, 200)))
            archive.writestr(f"{split}/_annotations.coco.json", json.dumps(data))


def test_positive_only_package_quarantines_and_keeps_groups_together():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.zip"
        target = Path(directory) / "review.zip"
        make_archive(source)
        before = source.read_bytes()
        receipt = module.prepare(source, target)
        assert source.read_bytes() == before
        assert receipt["validImages"] == 3
        assert receipt["validAnnotations"] == 3
        assert receipt["quarantinedAnnotations"] == 1
        assert receipt["quarantineReasons"] == {"SELF_INTERSECTION": 1}
        assert receipt["sourceGroups"] == 1
        assert receipt["crossSplitGroupsAfter"] == 0
        assert receipt["trainingAuthorized"] is False
        assert receipt["negativeCompletenessVerified"] is False
        populated = [name for name, value in receipt["splits"].items() if value["images"]]
        assert len(populated) == 1
        with zipfile.ZipFile(target) as archive:
            assert "REVIEW_MANIFEST.json" in archive.namelist()
            assert not any("negative-" in name for name in archive.namelist())
            data = json.loads(archive.read(f"{populated[0]}/_annotations.coco.json"))
            assert {item["name"] for item in data["categories"]} == {"crows_feet"}
            assert len(data["images"]) == len(data["annotations"]) == 3


def test_existing_output_is_never_overwritten():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.zip"
        target = Path(directory) / "review.zip"
        make_archive(source)
        target.write_bytes(b"preserve")
        try:
            module.prepare(source, target)
        except FileExistsError as error:
            assert str(error) == "OUTPUT_EXISTS"
        else:
            raise AssertionError("existing review package must not be overwritten")


def test_source_stem_removes_only_roboflow_fingerprint():
    assert module.source_stem("23725_png_jpg.rf.0123456789ab.jpg") == "23725_png_jpg"
    assert module.source_stem("plain-name.jpg") == "plain-name"
