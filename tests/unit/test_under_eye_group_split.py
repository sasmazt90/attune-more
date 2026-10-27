"""Tests for conservative under-eye source-photo grouping."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import zipfile

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/skin-research/prepare_under_eye_group_split.py"
spec = importlib.util.spec_from_file_location("under_eye_split", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def picture(colour):
    image = Image.new("RGB", (12, 12), colour)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def fixture(path):
    categories = [
        {"id": 1, "name": "darkcircle", "supercategory": "under-eye"},
        {"id": 2, "name": "eyebag", "supercategory": "under-eye"},
    ]
    records = {
        "train": [("aaaaaaaa-123456_left_jpg.rf.a.jpg", 1), ("cccccccc-44_1_jpg.rf.c.jpg", 2)],
        "valid": [("bbbbbbbb-123456_right_jpg.rf.b.jpg", 1), ("dddddddd-44_2_jpg.rf.d.jpg", 2)],
        "test": [("eeeeeeee-img_44_jpg.rf.e.jpg", 1)],
    }
    with zipfile.ZipFile(path, "w") as archive:
        for split, rows in records.items():
            images, annotations = [], []
            for index, (name, category) in enumerate(rows):
                images.append({"id": index, "file_name": name, "width": 12, "height": 12})
                annotations.append({
                    "id": index,
                    "image_id": index,
                    "category_id": category,
                    "bbox": [1, 1, 8, 8],
                    "area": 40,
                    "iscrowd": 0,
                    "segmentation": [[1, 1, 9, 1, 8, 8, 2, 9]],
                })
                archive.writestr(f"{split}/{name}", picture((index * 40, category * 50, 80)))
            archive.writestr(
                f"{split}/_annotations.coco.json",
                json.dumps({"images": images, "annotations": annotations, "categories": categories}),
            )


def test_only_explicit_left_right_pairs_group():
    assert module.source_photo_pair("aaaaaaaa-123456_left_jpg.rf.a.jpg") == "123456"
    assert module.source_photo_pair("bbbbbbbb-123456_right_jpg.rf.b.jpg") == "123456"
    assert module.source_photo_pair("cccccccc-44_1_jpg.rf.c.jpg") is None
    assert module.source_photo_pair("eeeeeeee-img_44_jpg.rf.e.jpg") is None


def test_unpaired_explicit_crop_is_recorded_but_not_moved():
    rows = [{"sourcePhotoPair": "99999", "fileName": "99999_left_jpg.rf.x.jpg",
             "sourceSplit": "test"}]
    reviewed, unpaired, moved = module.assign_splits(rows)
    assert reviewed == []
    assert unpaired == [{"sourcePhotoPair": "99999", "member": "99999_left_jpg.rf.x.jpg",
                         "sourceSplit": "test"}]
    assert moved == []
    assert rows[0]["assignedSplit"] == "test"


def test_cross_split_pair_moves_wholly_to_train_without_numeric_collision():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.zip"
        output = Path(directory) / "output.zip"
        fixture(source)
        receipt = module.prepare(source, output)
        assert receipt["images"] == 5
        assert receipt["annotations"] == 5
        assert receipt["crossSplitSourcePhotoPairs"] == 1
        assert receipt["splits"] == {"train": 3, "valid": 1, "test": 1}
        assert len(receipt["movedToTrain"]) == 1
        assert receipt["movedToTrain"][0]["fileName"].endswith("right_jpg.rf.b.jpg")
        assert receipt["acceptance"]["imageBytesPreserved"] is True
        assert receipt["acceptance"]["annotationGeometryPreserved"] is True
        assert receipt["acceptance"]["personIndependent"] is False


def test_export_refuses_overwrite():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.zip"
        output = Path(directory) / "output.zip"
        fixture(source)
        module.prepare(source, output)
        try:
            module.write_export(source, output, [], [], {})
        except FileExistsError:
            pass
        else:
            raise AssertionError("existing output must not be overwritten")
