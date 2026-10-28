import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_geometry_audit.py"
SPEC = importlib.util.spec_from_file_location("build_source_geometry_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
SOURCE_RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def complete_manifest():
    base = {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "selectedArchiveCountExpected": 2,
        "selectedArchives": [],
    }
    for index, (opaque, evidence) in enumerate((("a", "1"), ("b", "2"))):
        base["selectedArchives"].append({
            "opaqueId": f"selected_{opaque * 16}",
            "geometryEvidenceSHA256": evidence * 64,
            "imageCount": 100 + index,
            "annotationCount": 200 + index,
            "releaseEligiblePolygonCount": 180 + index,
            "releaseEligibleInvalidGeometryIssueCount": 0,
            "allImagesAndAnnotationsEnumerated": True,
            "actualGeometryAudited": True,
            "expertSemanticsBound": True,
            "rightsApprovedForGeometryReview": True,
            "boxesAcceptedAsPixelTruth": False,
            "rectanglePolygonsAcceptedAsPixelTruth": False,
            "modelGeometryAcceptedAsExpertTruth": False,
            "missingLabelsAcceptedAsNegativeOrNormal": False,
        })
    return base


class SourceGeometryAuditTest(unittest.TestCase):
    def test_committed_facts_stay_blocked_and_preserve_known_geometry(self):
        receipt = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
        result = MODULE.summarize_committed_facts(receipt)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["knownInvalidGeometryIssueCount"], 57)
        self.assertEqual(result["knownBoxOnlyAnnotationCount"], 3129)
        self.assertEqual(result["knownRectanglePolygonCount"], 1067)
        self.assertFalse(result["allGeometryAudited"])

    def test_complete_private_manifest_emits_exact_release_shape(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertTrue(artifact["allGeometryAudited"])
        self.assertEqual(artifact["invalidGeometryIssueCount"], 0)
        self.assertEqual(artifact["selectedArchiveCount"], 2)
        self.assertFalse(artifact["boxesAcceptedAsPixelTruth"])

    def test_release_digest_is_deterministic_across_entry_order(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["selectedArchives"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["geometryRegistryDigest"],
            MODULE.build_release_artifact(reversed_manifest)["geometryRegistryDigest"],
        )

    def test_incomplete_template_is_blocked(self):
        template = {
            "schemaVersion": 1,
            "methodVersion": MODULE.INPUT_METHOD,
            "releaseRef": None,
            "sourceRegistryRef": None,
            "selectedArchiveCountExpected": None,
            "selectedArchives": [],
        }
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("selected_archive_geometry_registry_empty", result["blockers"])
        with self.assertRaisesRegex(MODULE.GeometryInputError, "geometry audit is incomplete"):
            MODULE.build_release_artifact(template)

    def test_private_payload_and_model_proposals_fail_hard(self):
        for forbidden in ("archiveName", "path", "annotations", "reviewerId", "modelProposals"):
            bad = complete_manifest()
            bad["selectedArchives"][0][forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.GeometryInputError, "private or proposal payload"):
                    MODULE.evaluate_private_manifest(bad)

    def test_unsafe_truth_promotion_fails_hard(self):
        for field in MODULE.ALLOWED_SAFETY_KEYS:
            bad = complete_manifest()
            bad["selectedArchives"][0][field] = True
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.GeometryInputError, "unsafe geometry truth policy"):
                    MODULE.evaluate_private_manifest(bad)

    def test_invalid_geometry_empty_inventory_and_duplicate_evidence_are_rejected(self):
        bad = complete_manifest()
        bad["selectedArchives"][0]["releaseEligibleInvalidGeometryIssueCount"] = 3
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_invalid_geometry_present", result["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][0]["annotationCount"] = 0
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("selected_archive_0_geometry_inventory_empty", result["blockers"])
        bad = complete_manifest()
        bad["selectedArchives"][1]["geometryEvidenceSHA256"] = "1" * 64
        with self.assertRaisesRegex(MODULE.GeometryInputError, "evidence hashes must be unique"):
            MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
