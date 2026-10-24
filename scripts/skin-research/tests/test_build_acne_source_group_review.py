import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).parents[1] / "build_acne_source_group_review.py"
SPEC = importlib.util.spec_from_file_location("acne_source_groups", SCRIPT)
acne_source_groups = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(acne_source_groups)


def jpeg(path: Path, shade: int):
    Image.new("RGB", (16, 16), (shade, shade, shade)).save(path, format="JPEG")


def write_split(root: Path, split: str, names_and_shades: list[tuple[str, int]]):
    folder = root / split
    folder.mkdir()
    images = []
    for image_id, (name, shade) in enumerate(names_and_shades, 1):
        jpeg(folder / name, shade)
        images.append({"id": image_id, "file_name": name, "width": 16, "height": 16})
    (folder / "_annotations.coco.json").write_text(json.dumps({
        "categories": [
            {"id": index + 1, "name": name}
            for index, name in enumerate(acne_source_groups.CLASSES)
        ],
        "images": images,
        "annotations": [],
    }), encoding="utf-8")


class AcneSourceGroupReviewTest(unittest.TestCase):
    def dataset(self, root: Path):
        shared = "same-photo_jpg.rf.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"
        write_split(root, "train", [
            (shared, 20),
            ("portrait-alpha_jpg.rf.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg", 80),
        ])
        write_split(root, "valid", [
            ("same-photo_jpg.rf.cccccccccccccccccccccccccccccccc.jpg", 20),
            ("portrait-alpha_jpg.rf.dddddddddddddddddddddddddddddddd.jpg", 81),
        ])
        write_split(root, "test", [
            ("different_jpg.rf.eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.jpg", 180),
        ])

    def test_builds_hashed_review_queue_and_never_claims_independence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            result = acne_source_groups.build_review(root, "a" * 64)
        self.assertEqual(result["dataset"]["images"], 5)
        self.assertEqual(len(result["recordIndex"]), 5)
        self.assertEqual(
            {row["split"] for row in result["recordIndex"]},
            {"train", "valid", "test"},
        )
        self.assertEqual(result["candidateCounts"]["exact_content"], 1)
        self.assertGreaterEqual(result["candidateCounts"]["normalized_source_name"], 2)
        self.assertGreaterEqual(result["candidateCounts"]["perceptual_phash"], 1)
        self.assertNotIn("same-photo", json.dumps(result))
        self.assertFalse(result["privacy"]["containsFilenames"])
        self.assertFalse(result["decision"]["splitIndependenceEstablished"])
        self.assertTrue(result["decision"]["splitIndependenceViolated"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(
            result["regroupingPlan"]["confirmedGroups"][0]["requiredAction"],
            "assign_all_members_to_one_split",
        )
        self.assertFalse(result["regroupingPlan"]["targetSplitsAssigned"])

    def test_applies_review_decision_only_to_a_known_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            initial = acne_source_groups.build_review(root, "b" * 64)
            candidate = next(
                row for row in initial["reviewCandidates"]
                if row["method"] == "perceptual_dhash"
            )
            decisions = root / "decisions.json"
            decisions.write_text(json.dumps({
                "schemaVersion": "source-group-review-decisions-v1",
                "decisions": [{
                    "candidateId": candidate["candidateId"],
                    "decision": "same_source_or_person",
                    "reviewer": "engineering_visual_review",
                    "rationale": "different synthetic source images",
                }],
            }), encoding="utf-8")
            result = acne_source_groups.build_review(root, "b" * 64, decisions)
        reviewed = next(
            row for row in result["reviewCandidates"]
            if row["candidateId"] == candidate["candidateId"]
        )
        self.assertEqual(reviewed["review"]["decision"], "same_source_or_person")
        self.assertFalse(result["decision"]["personOrSourceGroupCoverageEstablished"])

    def test_unknown_decision_and_path_filename_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            decisions = root / "decisions.json"
            decisions.write_text(json.dumps({
                "schemaVersion": "source-group-review-decisions-v1",
                "decisions": [{
                    "candidateId": "unknown",
                    "decision": "same_source",
                    "reviewer": "expert_review",
                    "rationale": "not a real candidate",
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(acne_source_groups.ReviewError, "unknown candidate"):
                acne_source_groups.build_review(root, "c" * 64, decisions)
            coco_path = root / "test" / "_annotations.coco.json"
            value = json.loads(coco_path.read_text(encoding="utf-8"))
            value["images"][0]["file_name"] = "../escape.jpg"
            coco_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(acne_source_groups.ReviewError, "filename"):
                acne_source_groups.build_review(root, "c" * 64)

    def test_central_hash_is_deterministic_and_validates_fraction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "portrait.jpg"
            image = Image.new("RGB", (40, 60), "white")
            for x in range(12, 28):
                for y in range(10, 50):
                    image.putpixel((x, y), (x * 5, y * 3, 20))
            image.save(path, format="JPEG")
            first = acne_source_groups.central_perceptual_hash(path)
            second = acne_source_groups.central_perceptual_hash(path)
            self.assertEqual(first, second)
            with self.assertRaisesRegex(acne_source_groups.ReviewError, "crop fraction"):
                acne_source_groups.perceptual_hash(path, crop_fraction=0.4)

    def test_directional_hash_is_deterministic_and_validates_crop_name(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "portrait.png"
            image = Image.new("RGB", (24, 20), "white")
            for x in range(12):
                for y in range(20):
                    image.putpixel((x, y), (x * 8, y * 6, 40))
            image.save(path)
            first = acne_source_groups.directional_perceptual_hash(path, "left_80")
            second = acne_source_groups.directional_perceptual_hash(path, "left_80")
            self.assertEqual(first, second)
            self.assertNotEqual(
                first,
                acne_source_groups.directional_perceptual_hash(path, "right_80"),
            )
            variants = acne_source_groups.perceptual_hash_variants(path)
            self.assertEqual(variants["full"], acne_source_groups.perceptual_hash(path))
            self.assertEqual(
                variants["central"],
                acne_source_groups.central_perceptual_hash(path),
            )
            self.assertEqual(variants["directional"]["left_80"], first)
            with self.assertRaisesRegex(acne_source_groups.ReviewError, "unknown directional"):
                acne_source_groups.directional_perceptual_hash(path, "diagonal")


if __name__ == "__main__":
    unittest.main()
