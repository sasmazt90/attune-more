import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_source_mapping_release.py"
SPEC = importlib.util.spec_from_file_location("check_source_mapping_release", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261025-v1.json"


def receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


class SourceMappingReleaseGateTest(unittest.TestCase):
    def test_current_audits_are_research_only_and_fail_closed(self):
        result = MODULE.evaluate_release(receipt())
        self.assertTrue(result["researchRoutingAllowed"])
        self.assertFalse(result["trainingDataReleaseAuthorized"])
        self.assertFalse(result["productTruthAuthorized"])
        self.assertIn("source_person_grouping_incomplete", result["blockers"])

    def test_box_or_missing_label_promotion_fails_hard(self):
        bad = receipt()
        bad["mappingContract"]["boxesArePixelTruth"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "boxes cannot become pixel truth"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["mappingContract"]["missingLabelMeansNegativeOrNormal"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "missing labels"):
            MODULE.evaluate_release(bad)

    def test_tone_pul_or_assistant_review_semantic_promotion_fails_hard(self):
        bad = receipt()
        bad["mappingContract"]["toneMayBecomeProductPigmentation"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "tone cannot become"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["mappingContract"]["pulMayBecomeBroadRegionalDryness"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "pul cannot become"):
            MODULE.evaluate_release(bad)
        bad = receipt()
        bad["auditFacts"]["sourceReview"]["expertReviewed"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "assistant review"):
            MODULE.evaluate_release(bad)

    def test_reconciled_future_candidate_can_release_without_rewriting_source_facts(self):
        future = copy.deepcopy(receipt())
        future["acceptanceCandidate"] = {key: True for key in future["acceptanceCandidate"]}
        result = MODULE.evaluate_release(future)
        self.assertTrue(result["trainingDataReleaseAuthorized"])
        self.assertTrue(result["productTruthAuthorized"])

    def test_git_blob_identity_matches_git_hash_object_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"source mapping\n")
            self.assertEqual(MODULE.git_blob_sha1(path), "52e4e6f600fd596776b7ba191764109eece3c76b")


if __name__ == "__main__":
    unittest.main()
