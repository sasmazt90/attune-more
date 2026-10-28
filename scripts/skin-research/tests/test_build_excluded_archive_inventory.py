import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_excluded_archive_inventory.py"
SPEC = importlib.util.spec_from_file_location("build_excluded_archive_inventory", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def complete_manifest():
    entries = []
    evidence_tokens = (("a", "b"), ("c", "d"), ("e", "f"), ("1", "2"))
    for index, token in enumerate(("1", "2", "3", "4")):
        entries.append({
            "opaqueArchiveRef": f"excluded_{token * 16}",
            "presenceEvidenceSHA256": evidence_tokens[index][0] * 64,
            "preservationEvidenceSHA256": evidence_tokens[index][1] * 64,
            **copy.deepcopy(MODULE.SAFE_ENTRY_POLICY),
        })
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "requiredArchiveCount": 4,
        "inventoryEvidenceSHA256": "9" * 64,
        "preservationPolicySHA256": "0" * 63 + "1",
        "excludedArchives": entries,
    }


class ExcludedArchiveInventoryTest(unittest.TestCase):
    def test_committed_facts_stay_blocked_without_archive_access(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        result = MODULE.summarize_committed_facts(receipt)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["requiredArchiveCount"], 4)
        self.assertEqual(result["reconciledArchiveCount"], 0)
        self.assertFalse(result["excludedArchivesAccessed"])
        self.assertFalse(result["archiveHashesRecomputed"])

    def test_complete_manifest_emits_gate_compatible_artifact(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertEqual(artifact["requiredArchiveCount"], 4)
        self.assertTrue(artifact["inventoryReconciled"])
        self.assertTrue(artifact["preservationPolicyEnforced"])
        self.assertFalse(artifact["containsPublicNamesOrPaths"])
        self.assertFalse(artifact["excludedArchivesAccessed"])
        self.assertFalse(artifact["sourceReleaseContributionAllowed"])

    def test_incomplete_template_is_blocked(self):
        template = complete_manifest()
        template.update({
            "releaseRef": None,
            "inventoryEvidenceSHA256": None,
            "preservationPolicySHA256": None,
            "excludedArchives": [],
        })
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("excluded_archive_count_mismatch", result["blockers"])
        self.assertFalse(result["inventoryReconciled"])
        with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "inventory is incomplete"):
            MODULE.build_release_artifact(template)

    def test_unsafe_archive_action_fails_hard(self):
        for field in (
            "contentsEnumerated", "excludedArchiveAccessed", "mutationPerformed",
            "uploadPerformed", "trainingUsePerformed", "productUsePerformed",
            "sourceReleaseContributionAllowed",
        ):
            bad = complete_manifest()
            bad["excludedArchives"][0][field] = True
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "unsafe excluded archive inventory policy"):
                    MODULE.evaluate_private_manifest(bad)

    def test_metadata_only_presence_policy_is_locked(self):
        for field in ("metadataOnlyVerification", "presenceVerifiedWithoutContentAccess"):
            bad = complete_manifest()
            bad["excludedArchives"][0][field] = False
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "unsafe excluded archive inventory policy"):
                    MODULE.evaluate_private_manifest(bad)

    def test_four_unique_opaque_entries_are_required(self):
        bad = complete_manifest()
        bad["excludedArchives"].pop()
        self.assertIn("excluded_archive_count_mismatch", MODULE.evaluate_private_manifest(bad)["blockers"])
        bad = complete_manifest()
        bad["excludedArchives"][1]["opaqueArchiveRef"] = bad["excludedArchives"][0]["opaqueArchiveRef"]
        with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "opaque references must be unique"):
            MODULE.evaluate_private_manifest(bad)

    def test_evidence_hashes_are_unique_and_digest_is_deterministic(self):
        first = complete_manifest()
        second = complete_manifest()
        second["excludedArchives"].reverse()
        self.assertEqual(
            MODULE.evaluate_private_manifest(first)["excludedArchiveInventoryDigest"],
            MODULE.evaluate_private_manifest(second)["excludedArchiveInventoryDigest"],
        )
        bad = complete_manifest()
        bad["excludedArchives"][1]["presenceEvidenceSHA256"] = bad["excludedArchives"][0]["presenceEvidenceSHA256"]
        with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "evidence hashes must be unique"):
            MODULE.evaluate_private_manifest(bad)

    def test_private_archive_identity_and_contents_fail_hard(self):
        for forbidden in ("name", "path", "url", "filename", "archiveName", "contents", "members", "files", "annotations"):
            bad = complete_manifest()
            bad[forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.ExcludedArchiveInventoryInputError, "identity or content payload"):
                    MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
