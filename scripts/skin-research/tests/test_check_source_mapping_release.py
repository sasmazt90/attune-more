import copy
import hashlib
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
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"


def receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def _write(root, name, payload):
    path = root / "docs" / "skin" / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {"path": f"docs/skin/evidence/{name}", "sha256": hashlib.sha256(raw).hexdigest()}


def _install_complete_artifacts(candidate, root):
    release_ref = "release_1111111111111111"
    registry_ref = "source_registry_2222222222222222"
    split_ref = "split_3333333333333333"
    camera_ref = "camera_4444444444444444"
    common = {"releaseRef": release_ref}
    artifacts = {
        "excludedArchiveInventory": {
            **common, "methodVersion": "excluded-archive-inventory-reconciliation-v1",
            "requiredArchiveCount": 4, "inventoryReconciled": True,
            "preservationPolicyEnforced": True, "containsPublicNamesOrPaths": False,
            "excludedArchivesAccessed": False, "mutationPerformed": False,
            "uploadPerformed": False, "trainingUsePerformed": False,
            "productUsePerformed": False, "sourceReleaseContributionAllowed": False,
        },
        "archiveHashRegistry": {
            **common, "methodVersion": "source-archive-hash-registry-v1",
            "sourceRegistryRef": registry_ref, "selectedArchiveCount": 11,
            "allArchiveHashesVerified": True, "containsArchiveNamesOrPaths": False,
            "excludedArchivesPresent": False, "excludedArchiveHashesRecomputed": False,
        },
        "rightsReview": {
            **common, "methodVersion": "source-rights-review-v1",
            "sourceRegistryRef": registry_ref, "selectedArchiveCount": 11,
            "allSelectedArchivesReviewed": True, "allIndividualImageRightsReviewed": True,
            "unresolvedRightsCount": 0, "excludedArchivesAccessed": False,
        },
        "expertSemantics": {
            **common, "methodVersion": "skin-source-expert-semantics-v1",
            "sourceRegistryRef": registry_ref, "targets": list(MODULE.TARGETS),
            "perClassExpertSemanticsLocked": True, "mappingUsedAsExpertTruth": False,
            "boxesUsedAsPixelTruth": False, "rectanglePolygonsUsedAsPixelTruth": False,
            "missingLabelMeansNegativeOrNormal": False, "toneUsedAsLocalizedPigmentation": False,
            "pulUsedAsBroadRegionalDryness": False, "wholeFaceClassReplicatedIntoRegions": False,
            "modelPredictionUsedAsExpertTruth": False,
        },
        "geometryAudit": {
            **common, "methodVersion": "skin-source-geometry-audit-v1",
            "sourceRegistryRef": registry_ref, "selectedArchiveCount": 11,
            "allGeometryAudited": True, "invalidGeometryIssueCount": 0,
            "boxesAcceptedAsPixelTruth": False, "rectanglePolygonsAcceptedAsPixelTruth": False,
            "modelGeometryAcceptedAsExpertTruth": False,
        },
        "sourcePersonGrouping": {
            **common, "methodVersion": "skin-source-person-grouping-v1",
            "sourceRegistryRef": registry_ref, "recordCount": 5000,
            "sourcePersonGroupingComplete": True, "crossSplitGroupCount": 0,
            "singletonAssignmentAcceptedAsIdentity": False,
            "similarityCandidateAcceptedAsIdentity": False,
        },
        "lockedSplit": {
            **common, "methodVersion": "skin-source-group-locked-split-v1",
            "sourceRegistryRef": registry_ref, "splitRef": split_ref,
            "counts": {"train": 3500, "validation": 750, "final_test": 750},
            "groupLocked": True, "allRecordsAssignedExactlyOnce": True,
            "crossSplitGroupCount": 0, "finalTestUsedForSelection": False,
            "finalTestUsedForThresholds": False, "cameraSubjectsIncluded": False,
        },
        "cameraReservation": {
            **common, "methodVersion": "skin-source-independent-camera-reservation-v1",
            "sourceRegistryRef": registry_ref, "cameraReservationRef": camera_ref,
            "reserved": True, "sourceType": "physical-camera", "generated": False,
            "consentRequired": True, "subjectIndependentFromSourceRegistry": True,
            "usedForTrainingValidationOrThresholdSelection": False,
        },
    }
    candidate["artifacts"] = {
        name: _write(root, f"source-{name}.json", payload) for name, payload in artifacts.items()
    }
    for field in (
        "allFourExcludedArchivesReconciled", "allArchiveHashesVerified", "allRightsReviewed",
        "perClassExpertSemanticsLocked", "allGeometryAudited", "sourcePersonGroupingComplete",
        "lockedTrainValidationFinalTestSplit", "independentCameraReserved",
    ):
        candidate[field] = True
    candidate.update({
        "releaseRef": release_ref, "sourceRegistryRef": registry_ref,
        "splitRef": split_ref, "cameraReservationRef": camera_ref,
    })


class SourceMappingReleaseGateTest(unittest.TestCase):
    def test_current_audits_are_research_only_and_fail_closed(self):
        result = MODULE.evaluate_release(receipt())
        self.assertTrue(result["researchRoutingAllowed"])
        self.assertFalse(result["trainingDataReleaseAuthorized"])
        self.assertFalse(result["productTruthAuthorized"])
        self.assertFalse(result["evidenceRegistryComplete"])
        self.assertIn("archiveHashRegistry_evidence_missing", result["blockers"])

    def test_receipt_booleans_alone_cannot_release(self):
        future = copy.deepcopy(receipt())
        for key, value in list(future["acceptanceCandidate"].items()):
            if isinstance(value, bool):
                future["acceptanceCandidate"][key] = True
        result = MODULE.evaluate_release(future)
        self.assertFalse(result["trainingDataReleaseAuthorized"])
        self.assertIn("rightsReview_evidence_missing", result["blockers"])

    def test_complete_sha_bound_release_can_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            _install_complete_artifacts(future["acceptanceCandidate"], Path(directory))
            result = MODULE.evaluate_release(future, Path(directory))
        self.assertTrue(result["trainingDataReleaseAuthorized"])
        self.assertTrue(result["productTruthAuthorized"])
        self.assertTrue(result["evidenceRegistryComplete"])
        self.assertEqual(result["sourceReleaseIdentity"]["selectedArchiveCount"], 11)

    def test_artifact_digest_and_cross_identity_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            root = Path(directory)
            _install_complete_artifacts(future["acceptanceCandidate"], root)
            future["acceptanceCandidate"]["artifacts"]["rightsReview"]["sha256"] = "a" * 64
            with self.assertRaisesRegex(MODULE.GateInputError, "digest mismatch"):
                MODULE.evaluate_release(future, root)
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            root = Path(directory)
            _install_complete_artifacts(future["acceptanceCandidate"], root)
            future["acceptanceCandidate"]["sourceRegistryRef"] = "source_registry_aaaaaaaaaaaaaaaa"
            with self.assertRaisesRegex(MODULE.GateInputError, "sourceRegistryRef changed"):
                MODULE.evaluate_release(future, root)

    def test_semantic_promotion_and_unsafe_path_fail_hard(self):
        bad = receipt()
        bad["mappingContract"]["toneMayBecomeProductPigmentation"] = True
        with self.assertRaisesRegex(MODULE.GateInputError, "tone cannot become"):
            MODULE.evaluate_release(bad)
        with tempfile.TemporaryDirectory() as directory:
            future = receipt()
            root = Path(directory)
            _install_complete_artifacts(future["acceptanceCandidate"], root)
            future["acceptanceCandidate"]["artifacts"]["rightsReview"]["path"] = "docs/skin/evidence/../private.json"
            with self.assertRaisesRegex(MODULE.GateInputError, "outside the source evidence registry"):
                MODULE.evaluate_release(future, root)

    def test_stale_schema_is_rejected(self):
        bad = receipt()
        bad["schemaVersion"] = 1
        with self.assertRaisesRegex(MODULE.GateInputError, "receipt schema"):
            MODULE.evaluate_release(bad)

    def test_git_blob_identity_matches_git_hash_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"source mapping\n")
            self.assertEqual(MODULE.git_blob_sha1(path), "52e4e6f600fd596776b7ba191764109eece3c76b")


if __name__ == "__main__":
    unittest.main()
