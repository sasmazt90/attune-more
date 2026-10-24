import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_regional_skin_type_boxes.py"
SPEC = importlib.util.spec_from_file_location("regional_skin_type_box_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit)


def write_split(root: Path, split: str, images, annotations):
    folder = root / split
    folder.mkdir()
    (folder / "_annotations.coco.json").write_text(json.dumps({
        "images": [
            {"id": image_id, "file_name": name, "width": 100, "height": 80}
            for image_id, name in images
        ],
        "annotations": annotations,
        "categories": [
            {"id": 1, "name": "dry"},
            {"id": 2, "name": "oily"},
        ],
    }), encoding="utf-8")


def annotation(annotation_id, image_id, category_id, bbox=None, segmentation=None):
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": bbox or [10, 10, 20, 20],
        "segmentation": [] if segmentation is None else segmentation,
    }


class RegionalSkinTypeBoxAuditTest(unittest.TestCase):
    def fixture(self, root: Path, cross_split=False):
        write_split(root, "train", [
            (1, "p00001_jpg.rf.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"),
            (2, "p00001_jpg.rf.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg"),
        ], [annotation(1, 1, 1), annotation(2, 2, 1)])
        valid_source = "p00001" if cross_split else "p00002"
        write_split(root, "valid", [
            (3, f"{valid_source}_jpg.rf.cccccccccccccccccccccccccccccccc.jpg"),
        ], [annotation(3, 3, 2)])
        write_split(root, "test", [
            (4, "p00003_jpg.rf.dddddddddddddddddddddddddddddddd.jpg"),
        ], [annotation(4, 4, 1)])

    def test_boxes_are_never_promoted_to_regional_truth(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            result = audit.audit_export(root, "a" * 64, "workspace/project", 2)
        inventory = result["inventory"]
        self.assertEqual(inventory["images"], 4)
        self.assertEqual(inventory["uniqueSourceIds"], 3)
        self.assertEqual(inventory["augmentationCopiesBeyondUniqueSources"], 1)
        self.assertEqual(inventory["nonEmptySegmentations"], 0)
        self.assertEqual(inventory["crossSplitSourceIds"], {
            "train-valid": 0, "train-test": 0, "valid-test": 0,
        })
        self.assertFalse(result["taskSemantics"]["boxToMaskConversionAllowed"])
        self.assertFalse(result["taskSemantics"]["missingAnnotationMeansNormal"])
        self.assertFalse(result["decision"]["regionalTruthEligible"])
        self.assertIn(
            "EVALUATED_NORMAL_CLASS_MISSING", result["decision"]["reasons"]
        )

    def test_same_source_across_splits_blocks_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root, cross_split=True)
            result = audit.audit_export(root, "b" * 64, "workspace/project", 2)
        self.assertEqual(result["inventory"]["crossSplitSourceIds"]["train-valid"], 1)
        self.assertIn("SOURCE_ID_CROSSES_SPLITS", result["decision"]["reasons"])

    def test_nonempty_segmentation_is_counted_but_does_not_override_task_type(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            path = root / "test" / "_annotations.coco.json"
            payload = json.loads(path.read_text())
            payload["annotations"][0]["segmentation"] = [[10, 10, 30, 10, 30, 30]]
            path.write_text(json.dumps(payload))
            result = audit.audit_export(root, "c" * 64, "workspace/project", 2)
        self.assertEqual(result["inventory"]["nonEmptySegmentations"], 1)
        self.assertEqual(result["taskSemantics"]["providerTaskType"], "object-detection")
        self.assertFalse(result["decision"]["regionalTruthEligible"])

    def test_invalid_bbox_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            path = root / "valid" / "_annotations.coco.json"
            payload = json.loads(path.read_text())
            payload["annotations"][0]["bbox"] = [95, 10, 20, 20]
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(audit.AuditError, "out-of-bounds bbox"):
                audit.audit_export(root, "d" * 64, "workspace/project", 2)

    def test_unexpected_class_set_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            path = root / "train" / "_annotations.coco.json"
            payload = json.loads(path.read_text())
            payload["categories"] = [{"id": 1, "name": "dry"}]
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(audit.AuditError, "exactly the dry and oily"):
                audit.audit_export(root, "e" * 64, "workspace/project", 2)


if __name__ == "__main__":
    unittest.main()
