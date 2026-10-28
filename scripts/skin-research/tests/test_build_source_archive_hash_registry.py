import copy
import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_archive_hash_registry.py"
SPEC = importlib.util.spec_from_file_location("build_source_archive_hash_registry", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def complete_manifest():
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "policy": {
            "privateManifestOutsideGit": True,
            "publicNamesOrPathsAllowed": False,
            "excludedArchiveAccessAllowed": False,
            "excludedArchiveHashRecomputationAllowed": False,
        },
        "review": {
            "selectedArchiveCountExpected": 2,
            "allSelectedArchivesEnumerated": True,
            "reviewerAuthorizationConfirmed": True,
        },
        "selectedArchives": [
            {
                "opaqueId": "selected_aaaaaaaaaaaaaaaa",
                "archiveSHA256": "1" * 64,
                "authorizedPriorHashEvidenceSHA256": "2" * 64,
                "hashVerifiedAgainstAuthorizedPriorEvidence": True,
                "selectedForResearch": True,
                "excludedArchive": False,
            },
            {
                "opaqueId": "selected_bbbbbbbbbbbbbbbb",
                "archiveSHA256": "3" * 64,
                "authorizedPriorHashEvidenceSHA256": "4" * 64,
                "hashVerifiedAgainstAuthorizedPriorEvidence": True,
                "selectedForResearch": True,
                "excludedArchive": False,
            },
        ],
        "excludedArchiveHashOverlap": [],
    }


class SourceArchiveHashRegistryTest(unittest.TestCase):
    def test_complete_manifest_emits_release_artifact_without_private_hashes(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertTrue(artifact["allArchiveHashesVerified"])
        self.assertEqual(artifact["selectedArchiveCount"], 2)
        serialized = str(artifact)
        self.assertNotIn("1" * 64, serialized)
        self.assertNotIn("selected_aaaaaaaaaaaaaaaa", serialized)

    def test_registry_digest_is_deterministic_across_entry_order(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["selectedArchives"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["registryDigest"],
            MODULE.build_release_artifact(reversed_manifest)["registryDigest"],
        )

    def test_incomplete_template_is_blocked_and_cannot_emit_artifact(self):
        template = {
            "schemaVersion": 1,
            "methodVersion": MODULE.INPUT_METHOD,
            "releaseRef": None,
            "sourceRegistryRef": None,
            "policy": {
                "privateManifestOutsideGit": True,
                "publicNamesOrPathsAllowed": False,
                "excludedArchiveAccessAllowed": False,
                "excludedArchiveHashRecomputationAllowed": False,
            },
            "review": {
                "selectedArchiveCountExpected": None,
                "allSelectedArchivesEnumerated": False,
                "reviewerAuthorizationConfirmed": False,
            },
            "selectedArchives": [],
            "excludedArchiveHashOverlap": None,
        }
        preflight = MODULE.evaluate_manifest(template)
        self.assertEqual(preflight["decision"], "blocked")
        self.assertFalse(preflight["readyForReleaseArtifact"])
        self.assertIn("selected_archive_registry_empty", preflight["blockers"])
        with self.assertRaisesRegex(MODULE.RegistryInputError, "hash registry is incomplete"):
            MODULE.build_release_artifact(template)

    def test_names_paths_urls_and_extra_fields_fail_hard(self):
        for forbidden in ("filename", "archivePath", "sourceURL", "bucket"):
            bad = complete_manifest()
            bad["selectedArchives"][0][forbidden] = "private-value"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.RegistryInputError, "forbidden name/path/URL field"):
                    MODULE.evaluate_manifest(bad)
        bad = complete_manifest()
        bad["selectedArchives"][0]["comment"] = "unexpected"
        with self.assertRaisesRegex(MODULE.RegistryInputError, "unsupported fields"):
            MODULE.evaluate_manifest(bad)

    def test_excluded_archive_access_overlap_and_recomputation_fail_hard(self):
        bad = complete_manifest()
        bad["selectedArchives"][0]["excludedArchive"] = True
        with self.assertRaisesRegex(MODULE.RegistryInputError, "excluded archive cannot enter"):
            MODULE.evaluate_manifest(bad)
        bad = complete_manifest()
        bad["excludedArchiveHashOverlap"] = ["f" * 64]
        with self.assertRaisesRegex(MODULE.RegistryInputError, "overlap"):
            MODULE.evaluate_manifest(bad)
        for field in ("excludedArchiveAccessAllowed", "excludedArchiveHashRecomputationAllowed"):
            bad = complete_manifest()
            bad["policy"][field] = True
            with self.assertRaisesRegex(MODULE.RegistryInputError, "unsafe policy"):
                MODULE.evaluate_manifest(bad)

    def test_unverified_duplicate_and_count_mismatch_are_blocked_or_rejected(self):
        bad = complete_manifest()
        bad["selectedArchives"][0]["hashVerifiedAgainstAuthorizedPriorEvidence"] = False
        preflight = MODULE.evaluate_manifest(bad)
        self.assertIn("selected_archive_0_hash_unverified", preflight["blockers"])
        bad = complete_manifest()
        bad["review"]["selectedArchiveCountExpected"] = 3
        preflight = MODULE.evaluate_manifest(bad)
        self.assertIn("selected_archive_count_mismatch", preflight["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][1]["archiveSHA256"] = "1" * 64
        with self.assertRaisesRegex(MODULE.RegistryInputError, "hashes must be unique"):
            MODULE.evaluate_manifest(bad)


if __name__ == "__main__":
    unittest.main()
