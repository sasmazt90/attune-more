import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).parents[1] / "build_acne_group_coverage_proposal.py"
SPEC = importlib.util.spec_from_file_location("acne_group_proposal", SCRIPT)
proposal = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(proposal)


def write_split(root: Path, split: str, names_and_shades):
    folder = root / split
    folder.mkdir()
    images = []
    for image_id, (name, shade) in enumerate(names_and_shades, 1):
        Image.new("RGB", (16, 16), (shade, shade, shade)).save(folder / name, "JPEG")
        images.append({"id": image_id, "file_name": name, "width": 16, "height": 16})
    (folder / "_annotations.coco.json").write_text(json.dumps({
        "images": images,
        "annotations": [],
        "categories": [{"id": index + 1, "name": name} for index, name in enumerate(proposal.CLASSES)],
    }), encoding="utf-8")


class AcneGroupCoverageProposalTest(unittest.TestCase):
    def dataset(self, root: Path):
        write_split(root, "train", [
            ("shared-photo_jpg.rf.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg", 20),
            ("independent-train_jpg.rf.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg", 100),
        ])
        write_split(root, "valid", [
            ("shared-photo_jpg.rf.cccccccccccccccccccccccccccccccc.jpg", 21),
            ("independent-valid_jpg.rf.dddddddddddddddddddddddddddddddd.jpg", 160),
        ])
        write_split(root, "test", [
            ("locked-test_jpg.rf.eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.jpg", 220),
        ])

    def test_represents_every_record_without_claiming_singletons_reviewed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            initial_decisions = root / "decisions.json"
            initial_decisions.write_text(json.dumps({
                "schemaVersion": "source-group-review-decisions-v1",
                "decisions": [],
            }))
            result = proposal.build_proposal(root, "a" * 64, initial_decisions)
        coverage = result["coverageProposal"]
        self.assertEqual(result["dataset"]["images"], 5)
        self.assertTrue(coverage["allRecordsRepresentedExactlyOnce"])
        self.assertEqual(coverage["reviewedRecords"], 0)
        self.assertEqual(coverage["unreviewedRecords"], 5)
        self.assertFalse(coverage["readyForGroupLockedSplit"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertNotIn("shared-photo", json.dumps(result))

    def test_known_same_source_decision_forms_confirmed_group(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.dataset(root)
            empty = root / "empty.json"
            empty.write_text(json.dumps({"schemaVersion": "source-group-review-decisions-v1", "decisions": []}))
            first = proposal.build_proposal(root, "b" * 64, empty)
            candidate = next(
                row for row in first["reviewQueue"]["pairs"]
                if row["crossSplit"] and "normalized_source_name" in row["methods"]
            )
            method_candidate = next(
                row for row in proposal.build_proposal(root, "b" * 64, empty)["reviewQueue"]["pairs"]
                if row["pairId"] == candidate["pairId"]
            )
            # Reconstruct the method-specific candidate id used by the source-review decisions.
            member_ids = [row["recordId"] for row in method_candidate["members"]]
            identifier = proposal.candidate_id("perceptual_dhash", member_ids)
            decisions = root / "decisions.json"
            decisions.write_text(json.dumps({
                "schemaVersion": "source-group-review-decisions-v1",
                "decisions": [{
                    "candidateId": identifier,
                    "decision": "same_source_or_person",
                    "reviewer": "engineering_visual_review",
                    "rationale": "synthetic same image",
                }],
            }))
            result = proposal.build_proposal(root, "b" * 64, decisions)
        self.assertEqual(result["coverageProposal"]["confirmedGroups"], 1)
        self.assertEqual(result["coverageProposal"]["reviewedRecords"], 2)
        self.assertEqual(result["coverageProposal"]["unreviewedRecords"], 3)

    def test_unknown_decision_and_path_escape_fail_closed(self):
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
                    "rationale": "invalid",
                }],
            }))
            with self.assertRaisesRegex(proposal.ProposalError, "unknown candidate"):
                proposal.build_proposal(root, "c" * 64, decisions)
            decisions.write_text(json.dumps({"schemaVersion": "source-group-review-decisions-v1", "decisions": []}))
            path = root / "test" / "_annotations.coco.json"
            value = json.loads(path.read_text())
            value["images"][0]["file_name"] = "../escape.jpg"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(proposal.ProposalError, "filename"):
                proposal.build_proposal(root, "c" * 64, decisions)


if __name__ == "__main__":
    unittest.main()
