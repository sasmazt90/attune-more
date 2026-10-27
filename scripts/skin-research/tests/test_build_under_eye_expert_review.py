import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_under_eye_expert_review.py"
SPEC = importlib.util.spec_from_file_location("under_eye_expert_review", SCRIPT)
review = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(review)


class UnderEyeExpertReviewTests(unittest.TestCase):
    def _archive(self, path: Path):
        split_sizes = {"train": 80, "valid": 40, "test": 5}
        class_counts = {}
        with zipfile.ZipFile(path, "w") as archive:
            for split, count in split_sizes.items():
                if split == "test":
                    archive.writestr("test/_annotations.coco.json", b"not-json-and-must-not-be-read")
                    for index in range(count):
                        archive.writestr(f"test/private-test-{index}.jpg", b"locked-test-bytes")
                    continue
                images = []
                annotations = []
                counts = Counter()
                for index in range(count):
                    image_id = index + (0 if split == "train" else 1000)
                    filename = f"private-{split}-{index}.jpg"
                    images.append({"id": image_id, "file_name": filename, "width": 100, "height": 100})
                    archive.writestr(f"{split}/{filename}", ("synthetic-image-" + filename).encode())
                    mode = index % 4
                    category_ids = (1,) if mode == 0 else (2,) if mode == 1 else (1, 2)
                    for category_id in category_ids:
                        repeats = 2 if index % 7 == 0 else 1
                        for repeat in range(repeats):
                            offset = 2 + repeat + index % 10
                            polygon = [offset, 2, offset + 10, 2, offset + 10, 12, offset, 12]
                            annotations.append({
                                "id": len(annotations) + 1,
                                "image_id": image_id,
                                "category_id": category_id,
                                "segmentation": [polygon],
                                "area": 100,
                                "bbox": [offset, 2, 10, 10],
                            })
                            counts["darkcircle" if category_id == 1 else "eyebag"] += 1
                payload = {
                    "images": images,
                    "annotations": annotations,
                    "categories": [{"id": 1, "name": "darkcircle"}, {"id": 2, "name": "eyebag"}],
                }
                archive.writestr(
                    f"{split}/_annotations.coco.json",
                    json.dumps(payload, separators=(",", ":")),
                )
                class_counts[split] = dict(counts)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = {"splits": split_sizes, "reviewClassCounts": class_counts}
        return digest, expected

    def _completed(self, template):
        value = copy.deepcopy(template)
        value["reviewerRole"] = "expert_review"
        for policy in value["classPolicies"]:
            for key in (
                "positiveDefinitionLocked", "maskExtentPolicyLocked",
                "hardNegativePolicyLocked", "ambiguousCasePolicyLocked",
            ):
                policy[key] = True
        for row in value["items"]:
            row["expertReviewed"] = True
            row["assessability"] = "assessable"
            if row["selectionKind"] == "source_positive":
                row["targetPresence"] = "present"
                row["maskExtentDecision"] = "correct"
            else:
                row["targetPresence"] = "absent"
                row["maskExtentDecision"] = "not_applicable"
            row["semanticDecision"] = "keep"
        return value

    def test_queue_is_deterministic_private_and_test_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "source.zip"
            digest, expected = self._archive(archive)
            first, resolver = review.build_queue(
                archive, "under-eye-review-test-salt-v1",
                expected=expected, expected_archive_sha256=digest,
            )
            second, _ = review.build_queue(
                archive, "under-eye-review-test-salt-v1",
                expected=expected, expected_archive_sha256=digest,
            )
            self.assertEqual(first, second)
            self.assertEqual(first["selection"]["items"], 88)
            self.assertFalse(first["dataset"]["testAnnotationPayloadRead"])
            self.assertFalse(first["dataset"]["testImageBytesRead"])
            self.assertEqual(first["dataset"]["testSelectedForReview"], 0)
            self.assertTrue(all(not row["missingTargetAnnotationIsNegative"] for row in first["items"]))
            self.assertTrue(resolver)
            rendered = json.dumps(first)
            self.assertNotIn("private-train", rendered)
            self.assertNotIn("private-valid", rendered)
            self.assertNotIn("private-test", rendered)
            self.assertFalse(first["decision"]["trainingAuthorized"])

    def test_complete_review_builds_protocol_but_does_not_authorize_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "source.zip"
            digest, expected = self._archive(archive)
            queue, _ = review.build_queue(
                archive, "under-eye-review-test-salt-v1",
                expected=expected, expected_archive_sha256=digest,
            )
            template = review.build_template(queue)
            protocol = review.build_protocol(queue, self._completed(template))
            self.assertTrue(protocol["decision"]["semanticProtocolReady"])
            self.assertFalse(protocol["decision"]["personIndependentSplitReady"])
            self.assertFalse(protocol["decision"]["trainingAuthorized"])
            self.assertEqual({row["name"] for row in protocol["classes"]}, set(review.CLASSES))

    def test_pending_false_negative_and_wrong_binding_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "source.zip"
            digest, expected = self._archive(archive)
            queue, _ = review.build_queue(
                archive, "under-eye-review-test-salt-v1",
                expected=expected, expected_archive_sha256=digest,
            )
            template = review.build_template(queue)
            with self.assertRaisesRegex(review.ReviewError, "reviewer"):
                review.build_protocol(queue, template)
            value = self._completed(template)
            hard_negative = next(row for row in value["items"] if row["selectionKind"] == "candidate_hard_negative")
            hard_negative.update({
                "targetPresence": "present",
                "maskExtentDecision": "correct",
                "semanticDecision": "keep",
            })
            with self.assertRaisesRegex(review.ReviewError, "false-negative"):
                review.build_protocol(queue, value)
            value = self._completed(template)
            value["reviewQueueCanonicalSHA256"] = "0" * 64
            with self.assertRaisesRegex(review.ReviewError, "bound"):
                review.build_protocol(queue, value)

    def test_bad_geometry_and_archive_digest_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "source.zip"
            digest, expected = self._archive(archive)
            with self.assertRaisesRegex(review.ReviewError, "SHA256"):
                review.build_queue(
                    archive, "under-eye-review-test-salt-v1",
                    expected=expected, expected_archive_sha256="0" * 64,
                )
            bad = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(bad, "w") as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "valid/_annotations.coco.json":
                        value = json.loads(payload)
                        value["annotations"][0]["segmentation"] = [[1, 2, 3]]
                        payload = json.dumps(value).encode()
                    target.writestr(info.filename, payload)
            bad_digest = hashlib.sha256(bad.read_bytes()).hexdigest()
            with self.assertRaisesRegex(review.ReviewError, "polygon"):
                review.build_queue(
                    bad, "under-eye-review-test-salt-v1",
                    expected=expected, expected_archive_sha256=bad_digest,
                )


if __name__ == "__main__":
    unittest.main()
