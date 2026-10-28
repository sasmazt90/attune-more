import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "check_regional_provider_dataset_release.py"
SPEC = importlib.util.spec_from_file_location("regional_provider_gate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def receipt():
    return {
        "schemaVersion": MODULE.SCHEMA,
        "providerProject": {
            "id": MODULE.PROJECT_ID,
            "type": MODULE.PROJECT_TYPE,
            "public": False,
            "images": 476,
            "splits": {"train": 334, "valid": 85, "test": 57},
            "classes": {"Oily": 1373, "Redness": 898},
        },
        "upload": {
            "taskId": "RzTdxfpBr9REzkke1mPp",
            "status": "completed",
            "uploaded": 139,
            "duplicates": 198,
            "annotated": 337,
            "errors": 0,
            "warnings": 0,
            "failedChunks": 0,
        },
        "postUploadRecords": {
            "records": 139,
            "splits": {"train": 90, "valid": 22, "test": 27},
            "annotations": {"Oily": 308, "Redness": 327},
        },
        "groupLockedManifest": {
            "path": MODULE.MANIFEST_PATH,
            "blobSHA": MODULE.MANIFEST_BLOB_SHA,
            "sha256": MODULE.MANIFEST_FILE_SHA256,
            "assignmentsSHA256": MODULE.ASSIGNMENTS_SHA256,
            "queueItemsSHA256": MODULE.QUEUE_SHA256,
            "reviewDecisionsSHA256": MODULE.DECISIONS_SHA256,
            "records": MODULE.TARGET_SPLITS,
            "annotations": MODULE.TARGET_ANNOTATIONS,
            "crossSplitGroupCount": 0,
            "allRecordsAssignedExactlyOnce": True,
        },
        "candidateVersion": None,
        "releasePrerequisites": {
            "rightsReviewed": False,
            "expertSemanticMaskProtocolAccepted": False,
            "independentPhysicalCameraHoldoutReserved": False,
        },
    }


def exact_audit():
    return {
        "schemaVersion": MODULE.AUDIT_SCHEMA,
        "project": MODULE.PROJECT_ID,
        "projectType": MODULE.PROJECT_TYPE,
        "public": False,
        "versionNumber": 2,
        "images": MODULE.TARGET_IMAGES,
        "splits": MODULE.TARGET_SPLITS,
        "annotations": MODULE.TARGET_ANNOTATIONS,
        "classTotals": MODULE.TARGET_CLASS_TOTALS,
        "manifestFileSHA256": MODULE.MANIFEST_FILE_SHA256,
        "assignmentsSHA256": MODULE.ASSIGNMENTS_SHA256,
        "recordIdentityBasis": "image-content-sha256",
        "geometryIdentityBasis": "canonical-simple-polygon-ring-v2",
        "exportArchiveSHA256": "1" * 64,
        "splitImageContentSetSHA256": {
            "train": "2" * 64,
            "valid": "3" * 64,
            "test": "4" * 64,
        },
        "splitRecordAnnotationSetSHA256": {
            "train": "5" * 64,
            "valid": "6" * 64,
            "test": "7" * 64,
        },
        "allProviderRecordsMatchedManifestOnce": True,
        "unexpectedProviderRecords": 0,
        "missingManifestRecords": 0,
        "crossSplitContentHashCount": 0,
        "duplicateImageContentCount": 0,
        "polygonGeometryVerified": True,
        "simplePolygonGeometryVerified": True,
        "selfIntersectionCount": 0,
        "pathSafetyVerified": True,
        "categoryIdentityVerified": True,
        "bboxWithinImageVerified": True,
        "positiveAreaVerified": True,
        "boxGeometryAcceptedAsPolygonTruth": False,
        "crowdOrRLEGeometryAcceptedAsPolygonTruth": False,
        "invalidPolygonCount": 0,
        "outsidePointCount": 0,
        "degeneratePolygonCount": 0,
        "polygonAnnotations": {
            split: sum(MODULE.TARGET_ANNOTATIONS[split].values())
            for split in MODULE.TARGET_SPLITS
        },
        "polygons": {
            split: sum(MODULE.TARGET_ANNOTATIONS[split].values())
            for split in MODULE.TARGET_SPLITS
        },
        "vertices": {
            split: sum(MODULE.TARGET_ANNOTATIONS[split].values()) * 4
            for split in MODULE.TARGET_SPLITS
        },
        "sourcePersonCoverageComplete": True,
        "crossSplitGroupCount": 0,
        "finalTestUsedForSelectionOrThresholds": False,
        "containsFilenamesOrProviderImageIds": False,
    }


def exact_candidate(identity):
    return {
        "versionNumber": 2,
        "images": MODULE.TARGET_IMAGES,
        "splits": MODULE.TARGET_SPLITS,
        "annotations": MODULE.TARGET_ANNOTATIONS,
        "classTotals": MODULE.TARGET_CLASS_TOTALS,
        "exportAudit": identity,
    }


class RegionalProviderDatasetReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        audit_path = self.root / "docs/skin/evidence/provider-v2-audit.json"
        audit_path.parent.mkdir(parents=True)
        audit_path.write_text(json.dumps(exact_audit(), sort_keys=True) + "\n", encoding="utf-8")
        self.audit_path = audit_path
        self.audit_identity = {
            "path": "docs/skin/evidence/provider-v2-audit.json",
            "sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        }
        post_audit = {
            "schemaVersion": MODULE.POST_UPLOAD_AUDIT_SCHEMA,
            "project": MODULE.PROJECT_ID,
            "uploadTaskId": "RzTdxfpBr9REzkke1mPp",
            "selectedRecords": 139,
            "membershipClassification": "unverified_until_exact_provider_export",
            "contentIdentityEstablished": False,
            "annotationIdentityEstablished": False,
            "tagEstablishesUnwantedMembership": False,
            "tagBasedDeletionOrVersionExclusionAllowed": False,
            "exactProviderExportAuditRequired": True,
            "containsFilenamesOrProviderImageIds": False,
        }
        post_path = self.root / "docs/skin/evidence/post-upload-audit.json"
        post_path.write_text(json.dumps(post_audit, sort_keys=True) + "\n", encoding="utf-8")
        self.post_audit_identity = {
            "path": "docs/skin/evidence/post-upload-audit.json",
            "sha256": hashlib.sha256(post_path.read_bytes()).hexdigest(),
        }

    def make_receipt(self):
        value = receipt()
        value["postUploadProvenanceAudit"] = self.post_audit_identity
        return value

    def tearDown(self):
        self.temporary.cleanup()

    def test_observed_provider_drift_blocks_training(self):
        result = MODULE.evaluate_release(self.make_receipt(), self.root)
        self.assertTrue(result["mutableProjectDriftDetected"])
        self.assertFalse(result["providerVersionReady"])
        self.assertFalse(result["trainingAuthorized"])
        self.assertTrue(result["providerPolygonGeometryAuditRequired"])
        self.assertFalse(result["boxGeometryAcceptedAsPolygonTruth"])
        self.assertIn("provider_version_2_missing", result["blockers"])
        self.assertIn("mutable_provider_project_drifted_from_group_locked_candidate", result["blockers"])

    def test_exact_immutable_v2_and_prerequisites_allow_one_training(self):
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(self.audit_identity)
        value["releasePrerequisites"] = {
            "rightsReviewed": True,
            "expertSemanticMaskProtocolAccepted": True,
            "independentPhysicalCameraHoldoutReserved": True,
        }
        result = MODULE.evaluate_release(value, self.root)
        self.assertTrue(result["providerVersionReady"])
        self.assertTrue(result["trainingAuthorized"])
        self.assertFalse(result["finalTestAuthorized"])
        self.assertFalse(result["activationAllowed"])

    def test_version_one_cannot_be_relabelled_as_replacement(self):
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(self.audit_identity)
        value["candidateVersion"]["versionNumber"] = 1
        result = MODULE.evaluate_release(value, self.root)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("provider_version_2_missing", result["blockers"])

    def test_wrong_candidate_split_fails_closed(self):
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(self.audit_identity)
        value["candidateVersion"]["splits"] = {"train": 237, "valid": 50, "test": 50}
        result = MODULE.evaluate_release(value, self.root)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("exact_group_locked_provider_version_unconfirmed", result["blockers"])

    def test_declarative_candidate_without_export_audit_fails_closed(self):
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(None)
        with self.assertRaisesRegex(MODULE.GateInputError, "evidence identity missing"):
            MODULE.evaluate_release(value, self.root)

    def test_export_audit_digest_mismatch_fails_closed(self):
        value = self.make_receipt()
        identity = dict(self.audit_identity)
        identity["sha256"] = "f" * 64
        value["candidateVersion"] = exact_candidate(identity)
        with self.assertRaisesRegex(MODULE.GateInputError, "digest mismatch"):
            MODULE.evaluate_release(value, self.root)

    def test_export_audit_record_identity_mismatch_blocks(self):
        audit = exact_audit()
        audit["missingManifestRecords"] = 1
        self.audit_path.write_text(json.dumps(audit, sort_keys=True) + "\n", encoding="utf-8")
        identity = dict(self.audit_identity)
        identity["sha256"] = hashlib.sha256(self.audit_path.read_bytes()).hexdigest()
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(identity)
        result = MODULE.evaluate_release(value, self.root)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("provider_export_audit_mismatch", result["blockers"])

    def test_box_only_or_declarative_polygon_geometry_cannot_authorize_training(self):
        audit = exact_audit()
        audit["polygonGeometryVerified"] = False
        audit["boxGeometryAcceptedAsPolygonTruth"] = True
        self.audit_path.write_text(json.dumps(audit, sort_keys=True) + "\n", encoding="utf-8")
        identity = dict(self.audit_identity)
        identity["sha256"] = hashlib.sha256(self.audit_path.read_bytes()).hexdigest()
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(identity)
        result = MODULE.evaluate_release(value, self.root)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("provider_export_audit_mismatch", result["blockers"])

    def test_polygon_cardinality_mismatch_blocks(self):
        audit = exact_audit()
        audit["polygons"]["test"] -= 1
        self.audit_path.write_text(json.dumps(audit, sort_keys=True) + "\n", encoding="utf-8")
        identity = dict(self.audit_identity)
        identity["sha256"] = hashlib.sha256(self.audit_path.read_bytes()).hexdigest()
        value = self.make_receipt()
        value["candidateVersion"] = exact_candidate(identity)
        result = MODULE.evaluate_release(value, self.root)
        self.assertFalse(result["providerVersionReady"])
        self.assertIn("provider_polygon_geometry_audit_mismatch", result["blockers"])

    def test_unsafe_path_or_non_simple_geometry_cannot_authorize_training(self):
        for field in ("pathSafetyVerified", "simplePolygonGeometryVerified"):
            audit = exact_audit()
            audit[field] = False
            self.audit_path.write_text(json.dumps(audit, sort_keys=True) + "\n", encoding="utf-8")
            identity = dict(self.audit_identity)
            identity["sha256"] = hashlib.sha256(self.audit_path.read_bytes()).hexdigest()
            value = self.make_receipt()
            value["candidateVersion"] = exact_candidate(identity)
            result = MODULE.evaluate_release(value, self.root)
            self.assertFalse(result["providerVersionReady"])
            self.assertIn("provider_export_audit_mismatch", result["blockers"])

    def test_out_of_image_bbox_or_nonpositive_area_cannot_authorize_training(self):
        for field in ("bboxWithinImageVerified", "positiveAreaVerified"):
            audit = exact_audit()
            audit[field] = False
            self.audit_path.write_text(json.dumps(audit, sort_keys=True) + "\n", encoding="utf-8")
            identity = dict(self.audit_identity)
            identity["sha256"] = hashlib.sha256(self.audit_path.read_bytes()).hexdigest()
            value = self.make_receipt()
            value["candidateVersion"] = exact_candidate(identity)
            result = MODULE.evaluate_release(value, self.root)
            self.assertFalse(result["providerVersionReady"])
            self.assertIn("provider_export_audit_mismatch", result["blockers"])

    def test_project_growth_must_match_uploaded_records(self):
        value = self.make_receipt()
        value["providerProject"]["images"] = 475
        value["providerProject"]["splits"]["train"] = 333
        with self.assertRaisesRegex(MODULE.GateInputError, "project growth"):
            MODULE.evaluate_release(value, self.root)

    def test_upload_errors_fail_input_validation(self):
        value = self.make_receipt()
        value["upload"]["errors"] = 1
        with self.assertRaisesRegex(MODULE.GateInputError, "upload has errors"):
            MODULE.evaluate_release(value, self.root)

    def test_post_upload_tag_cannot_authorize_exclusion(self):
        result = MODULE.evaluate_release(self.make_receipt(), self.root)
        self.assertTrue(result["postUploadProvenanceVerified"])
        self.assertFalse(result["tagBasedExclusionAuthorized"])
        self.assertIn("mutable_provider_membership_requires_exact_export_audit", result["blockers"])


if __name__ == "__main__":
    unittest.main()

