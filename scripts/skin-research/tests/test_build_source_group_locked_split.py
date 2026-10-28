import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_group_locked_split.py"
SPEC = importlib.util.spec_from_file_location("build_source_group_locked_split", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def complete_manifest():
    counts = {"train": 5500, "validation": 1182, "final_test": 1183}
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "splitRef": "split_3333333333333333",
        "selectedArchiveCount": MODULE.SELECTED_ARCHIVE_COUNT,
        "recordCount": sum(counts.values()),
        "counts": counts,
        "sourcePersonGroupingEvidence": {
            "artifactSHA256": "a" * 64,
            "groupingRegistryDigest": "b" * 64,
            "recordCount": sum(counts.values()),
            "sourcePersonGroupingComplete": True,
            "crossSplitGroupCount": 0,
            "singletonAssignmentAcceptedAsIdentity": False,
            "similarityCandidateAcceptedAsIdentity": False,
        },
        "splitPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
        "splitAssignmentSHA256": "c" * 64,
        "targetCoverage": [
            {
                "target": target,
                "counts": {"train": 10 + index, "validation": 2 + index, "final_test": 3 + index},
                "expertLabelsOnly": True,
                "unknownExcludedFromPositiveCoverage": True,
            }
            for index, target in enumerate(MODULE.TARGETS)
        ],
    }


class SourceGroupLockedSplitTest(unittest.TestCase):
    def test_committed_facts_stay_blocked(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        result = MODULE.summarize_committed_facts(receipt)
        self.assertEqual(result["knownRecordCount"], 7865)
        self.assertEqual(result["knownExactCrossSplitGroupCount"], 66)
        self.assertFalse(result["groupLocked"])
        self.assertFalse(result["allRecordsAssignedExactlyOnce"])
        self.assertEqual(result["decision"], "blocked")

    def test_complete_manifest_emits_gate_compatible_artifact(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertEqual(set(artifact["counts"]), {"train", "validation", "final_test"})
        self.assertTrue(artifact["groupLocked"])
        self.assertTrue(artifact["allRecordsAssignedExactlyOnce"])
        self.assertEqual(artifact["crossSplitGroupCount"], 0)
        self.assertFalse(artifact["finalTestUsedForSelection"])
        self.assertFalse(artifact["finalTestUsedForThresholds"])
        self.assertFalse(artifact["cameraSubjectsIncluded"])

    def test_target_coverage_digest_is_order_independent(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["targetCoverage"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["targetCoverageDigest"],
            MODULE.build_release_artifact(reversed_manifest)["targetCoverageDigest"],
        )

    def test_incomplete_template_is_blocked(self):
        template = complete_manifest()
        template["releaseRef"] = None
        template["sourceRegistryRef"] = None
        template["splitRef"] = None
        template["sourcePersonGroupingEvidence"] = None
        template["splitAssignmentSHA256"] = None
        template["targetCoverage"] = []
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("source_person_grouping_evidence_missing", result["blockers"])
        self.assertIn("target_coverage_empty", result["blockers"])
        with self.assertRaisesRegex(MODULE.SplitInputError, "group-locked split is incomplete"):
            MODULE.build_release_artifact(template)

    def test_unsafe_split_policy_fails_hard(self):
        for field, safe in MODULE.SAFE_POLICY.items():
            bad = complete_manifest()
            bad["splitPolicy"][field] = not safe if isinstance(safe, bool) else safe + 1
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.SplitInputError, "unsafe split policy"):
                    MODULE.evaluate_private_manifest(bad)

    def test_counts_and_grouping_identity_must_match(self):
        bad = complete_manifest()
        bad["counts"]["train"] += 1
        self.assertIn("split_record_count_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["sourcePersonGroupingEvidence"]["recordCount"] -= 1
        self.assertIn("grouping_record_count_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["sourcePersonGroupingEvidence"]["crossSplitGroupCount"] = 1
        self.assertIn("source_person_grouping_crossSplitGroupCount_invalid", MODULE.evaluate_private_manifest(bad)["blockers"])

    def test_target_inventory_and_expert_coverage_are_enforced(self):
        bad = complete_manifest()
        bad["targetCoverage"].pop()
        self.assertIn("target_coverage_inventory_incomplete", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["targetCoverage"][1]["target"] = bad["targetCoverage"][0]["target"]
        with self.assertRaisesRegex(MODULE.SplitInputError, "entries must be unique"):
            MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["targetCoverage"][0]["expertLabelsOnly"] = False
        self.assertIn("target_coverage_0_expert_coverage_invalid", MODULE.evaluate_private_manifest(bad)["blockers"])

    def test_private_raw_split_payloads_fail_hard(self):
        for forbidden in ("archiveName", "path", "recordIds", "groupIds", "subjectId", "reviewerId", "annotations", "predictions"):
            bad = complete_manifest()
            bad[forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.SplitInputError, "private identity, label or raw split payload"):
                    MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
