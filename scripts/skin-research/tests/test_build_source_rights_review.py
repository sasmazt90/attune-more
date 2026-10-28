import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_rights_review.py"
SPEC = importlib.util.spec_from_file_location("build_source_rights_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
CURRENT_FACTS = REPO_ROOT / "docs/skin/evidence/source-rights-review-current-facts-20261028-v1.json"


def complete_manifest():
    manifest = {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "selectedArchiveCountExpected": 2,
        "policy": {
            "privateManifestOutsideGit": True,
            "publicNamesOrPathsAllowed": False,
            "rawRightsDocumentsCommitted": False,
            "reviewerIdentityAllowed": False,
            "excludedArchiveAccessAllowed": False,
            "publisherDeclarationAcceptedAsIndividualImageProof": False,
        },
        "selectedArchives": [],
    }
    for opaque, evidence in (("a", "1"), ("b", "2")):
        manifest["selectedArchives"].append({
            "opaqueId": f"selected_{opaque * 16}",
            "rightsEvidenceSHA256": evidence * 64,
            "unresolvedRightsCount": 0,
            "archiveRightsReviewed": True,
            "allIndividualImageRightsReviewed": True,
            "researchTrainingUseAllowed": True,
            "modelEvaluationUseAllowed": True,
            "productInferenceUseAllowed": True,
            "derivativeArtifactsAllowed": True,
            "reviewerAuthorizationConfirmed": True,
            "excludedArchive": False,
            "excludedArchiveAccessed": False,
            "containsUnverifiedStockSource": False,
            "publisherDeclarationUsedAsIndividualImageRightsProof": False,
        })
    return manifest


class SourceRightsReviewTest(unittest.TestCase):
    def test_committed_mapping_facts_stay_blocked(self):
        facts = json.loads(CURRENT_FACTS.read_text(encoding="utf-8"))
        result = MODULE.summarize_current_facts(facts)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["selectedArchiveCountExpected"], 11)
        self.assertFalse(result["allIndividualImageRightsReviewed"])
        self.assertIn("publisher_declaration_is_not_individual_image_rights_proof", result["blockers"])

    def test_complete_private_manifest_emits_exact_release_shape(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertTrue(artifact["allSelectedArchivesReviewed"])
        self.assertTrue(artifact["allIndividualImageRightsReviewed"])
        self.assertEqual(artifact["unresolvedRightsCount"], 0)
        self.assertFalse(artifact["excludedArchivesAccessed"])
        self.assertNotIn("selected_aaaaaaaaaaaaaaaa", str(artifact))
        self.assertNotIn("1" * 64, str(artifact))

    def test_digest_is_deterministic_across_entry_order(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["selectedArchives"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["rightsRegistryDigest"],
            MODULE.build_release_artifact(reversed_manifest)["rightsRegistryDigest"],
        )

    def test_incomplete_template_is_blocked(self):
        template = {
            "schemaVersion": 1,
            "methodVersion": MODULE.INPUT_METHOD,
            "releaseRef": None,
            "sourceRegistryRef": None,
            "selectedArchiveCountExpected": None,
            "policy": {
                "privateManifestOutsideGit": True,
                "publicNamesOrPathsAllowed": False,
                "rawRightsDocumentsCommitted": False,
                "reviewerIdentityAllowed": False,
                "excludedArchiveAccessAllowed": False,
                "publisherDeclarationAcceptedAsIndividualImageProof": False,
            },
            "selectedArchives": [],
        }
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("selected_archive_rights_registry_empty", result["blockers"])
        with self.assertRaisesRegex(MODULE.RightsInputError, "rights review is incomplete"):
            MODULE.build_release_artifact(template)

    def test_private_names_paths_documents_and_reviewer_identity_fail_hard(self):
        for forbidden in ("archiveName", "path", "url", "rightsDocument", "reviewerId", "email"):
            bad = complete_manifest()
            bad["selectedArchives"][0][forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.RightsInputError, "private name/path/document field"):
                    MODULE.evaluate_private_manifest(bad)

    def test_excluded_archive_access_and_publisher_substitution_fail_hard(self):
        for field in ("excludedArchive", "excludedArchiveAccessed"):
            bad = complete_manifest()
            bad["selectedArchives"][0][field] = True
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.RightsInputError, "excluded archives cannot enter or be accessed"):
                    MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["selectedArchives"][0]["publisherDeclarationUsedAsIndividualImageRightsProof"] = True
        with self.assertRaisesRegex(MODULE.RightsInputError, "cannot substitute"):
            MODULE.evaluate_private_manifest(bad)

    def test_unresolved_scope_gap_duplicate_and_count_mismatch_are_blocked_or_rejected(self):
        bad = complete_manifest()
        bad["selectedArchives"][0]["unresolvedRightsCount"] = 3
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_unresolved_rights_present", result["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][0]["productInferenceUseAllowed"] = False
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_productInferenceUseAllowed_incomplete", result["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][1]["rightsEvidenceSHA256"] = "1" * 64
        with self.assertRaisesRegex(MODULE.RightsInputError, "evidence hashes must be unique"):
            MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["selectedArchiveCountExpected"] = 3
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_count_mismatch", result["blockers"])


if __name__ == "__main__":
    unittest.main()
