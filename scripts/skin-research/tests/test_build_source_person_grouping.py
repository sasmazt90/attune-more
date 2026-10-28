import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_person_grouping.py"
SPEC = importlib.util.spec_from_file_location("build_source_person_grouping", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def complete_manifest():
    manifest = {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "selectedArchiveCountExpected": MODULE.SELECTED_ARCHIVE_COUNT,
        "identityPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
        "selectedArchives": [],
    }
    for index in range(1, MODULE.SELECTED_ARCHIVE_COUNT + 1):
        entry = {
            "opaqueId": f"source_{index:016x}",
            "groupingEvidenceSHA256": f"{index:x}" * 64,
            "recordCount": 100 + index,
            "groupCount": 90 + index,
            "exactDuplicateGroupCount": 5,
            "ambiguousCandidateGroupCount": 4,
            "unresolvedAmbiguousCandidateGroupCount": 0,
            "allRecordsAssignedExactlyOnce": True,
            "exactDuplicatesCoGrouped": True,
            "ambiguousCandidatesHumanReviewed": True,
            "sourcePersonCoverageComplete": True,
            "crossSplitGroupCount": 0,
            **MODULE.SAFE_POLICY,
        }
        manifest["selectedArchives"].append(entry)
    return manifest


class SourcePersonGroupingTest(unittest.TestCase):
    def test_committed_facts_stay_blocked_without_inventing_identity(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        result = MODULE.summarize_committed_facts(receipt)
        self.assertEqual(result["knownRecordCount"], 7865)
        self.assertEqual(result["knownExactCrossSplitGroupCount"], 66)
        self.assertEqual(result["knownFilenameCandidateGroupCount"], 286)
        self.assertEqual(result["knownPerceptualCandidatePairCount"], 1301)
        self.assertFalse(result["sourcePersonGroupingComplete"])
        self.assertFalse(result["similarityCandidateAcceptedAsIdentity"])
        self.assertEqual(result["decision"], "blocked")

    def test_complete_manifest_emits_gate_compatible_artifact(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertEqual(artifact["selectedArchiveCount"], MODULE.SELECTED_ARCHIVE_COUNT)
        self.assertGreater(artifact["recordCount"], 0)
        self.assertTrue(artifact["sourcePersonGroupingComplete"])
        self.assertEqual(artifact["crossSplitGroupCount"], 0)
        for field, expected in MODULE.SAFE_POLICY.items():
            self.assertEqual(artifact[field], expected)

    def test_digest_is_deterministic_across_archive_order(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["selectedArchives"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["groupingRegistryDigest"],
            MODULE.build_release_artifact(reversed_manifest)["groupingRegistryDigest"],
        )

    def test_incomplete_template_is_blocked(self):
        template = {
            "schemaVersion": 1,
            "methodVersion": MODULE.INPUT_METHOD,
            "releaseRef": None,
            "sourceRegistryRef": None,
            "selectedArchiveCountExpected": MODULE.SELECTED_ARCHIVE_COUNT,
            "identityPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
            "selectedArchives": [],
        }
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("selected_archive_grouping_registry_empty", result["blockers"])
        with self.assertRaisesRegex(MODULE.GroupingInputError, "source/person grouping is incomplete"):
            MODULE.build_release_artifact(template)

    def test_unsafe_identity_promotions_fail_hard(self):
        for field, safe in MODULE.SAFE_POLICY.items():
            bad = complete_manifest()
            bad["identityPolicy"][field] = not safe
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.GroupingInputError, "unsafe grouping identity policy"):
                    MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["selectedArchives"][0]["similarityCandidateAcceptedAsIdentity"] = True
        with self.assertRaisesRegex(MODULE.GroupingInputError, "unsafe archive grouping identity policy"):
            MODULE.evaluate_private_manifest(bad)

    def test_unresolved_or_cross_split_groups_block_release(self):
        bad = complete_manifest()
        bad["selectedArchives"][0]["unresolvedAmbiguousCandidateGroupCount"] = 1
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_ambiguous_candidates_unresolved", result["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][0]["crossSplitGroupCount"] = 1
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_cross_split_groups_present", result["blockers"])

    def test_incomplete_coverage_and_duplicate_evidence_are_rejected_or_blocked(self):
        bad = complete_manifest()
        bad["selectedArchives"].pop()
        self.assertIn("selected_archive_count_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][1]["opaqueId"] = bad["selectedArchives"][0]["opaqueId"]
        with self.assertRaisesRegex(MODULE.GroupingInputError, "opaque IDs must be unique"):
            MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["selectedArchives"][0]["allRecordsAssignedExactlyOnce"] = False
        self.assertIn("selected_archive_0_allRecordsAssignedExactlyOnce_incomplete", MODULE.evaluate_private_manifest(bad)["blockers"])

    def test_private_identity_and_raw_grouping_payloads_fail_hard(self):
        for forbidden in ("archiveName", "path", "recordIds", "groupId", "subjectId", "reviewerId", "embeddings", "predictions"):
            bad = complete_manifest()
            bad["selectedArchives"][0][forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.GroupingInputError, "private identity or raw grouping payload"):
                    MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
