import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_acne_dataset_geometry.py"
SPEC = importlib.util.spec_from_file_location("acne_geometry", SCRIPT)
acne_geometry = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(acne_geometry)


def write_split(root: Path, split: str, image_bytes: list[bytes], counts: dict[str, int]):
    folder = root / split
    folder.mkdir()
    categories = [
        {"id": index + 1, "name": name}
        for index, name in enumerate(acne_geometry.CLASSES)
    ]
    images, annotations = [], []
    annotation_id = 1
    for image_id, payload in enumerate(image_bytes, 1):
        file_name = f"{split}-{image_id}.jpg"
        (folder / file_name).write_bytes(payload)
        images.append({"id": image_id, "file_name": file_name, "width": 100, "height": 100})
    for category_id, name in enumerate(acne_geometry.CLASSES, 1):
        for index in range(counts[name]):
            image_id = index % len(images) + 1
            annotations.append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "bbox": [1, 1, 1, 1],
            })
            annotation_id += 1
    (folder / "_annotations.coco.json").write_text(json.dumps({
        "categories": categories, "images": images, "annotations": annotations,
    }), encoding="utf-8")


class AcneDatasetGeometryAuditTest(unittest.TestCase):
    def dataset(self, root: Path):
        counts = {"Pimple": 2, "Post acne": 8, "Pigmentation": 1}
        write_split(root, "train", [b"same", b"train"], counts)
        write_split(root, "valid", [b"same", b"valid"], counts)
        write_split(root, "test", [b"test-a", b"test-b"], counts)

    def test_reports_tiny_imbalance_and_exact_split_leakage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            result = acne_geometry.audit(root)
        self.assertEqual(result["dataset"]["images"], 6)
        self.assertEqual(result["dataset"]["annotations"], 33)
        self.assertEqual(result["splitIdentity"]["exactCrossSplitDuplicateGroups"], 1)
        self.assertFalse(result["splitIdentity"]["independenceEstablished"])
        self.assertEqual(result["balance"]["postAcneToPigmentationRatio"], 8)
        self.assertTrue(all(
            row["tinyFraction"] == 1
            for row in result["geometry"]["aggregateByClass"].values()
        ))
        self.assertFalse(result["decision"]["trainingAuthorized"])

    def test_invalid_bbox_fails_and_cli_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            annotation_path = root / "valid" / "_annotations.coco.json"
            value = json.loads(annotation_path.read_text(encoding="utf-8"))
            value["annotations"][0]["bbox"] = [99, 99, 2, 2]
            annotation_path.write_text(json.dumps(value), encoding="utf-8")
            output = root / "result.json"
            self.assertEqual(acne_geometry.main([
                "--dataset", str(root), "--output", str(output)
            ]), 2)
            self.assertFalse(output.exists())

    def test_invalid_class_inventory_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            annotation_path = root / "test" / "_annotations.coco.json"
            value = json.loads(annotation_path.read_text(encoding="utf-8"))
            value["categories"][0]["name"] = "Acne"
            annotation_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(acne_geometry.AuditError, "class inventory"):
                acne_geometry.audit(root)


if __name__ == "__main__":
    unittest.main()
