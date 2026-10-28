import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "audit_regional_post_upload_provenance.py"
SPEC = importlib.util.spec_from_file_location("regional_post_upload_provenance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def observation():
    return {
        "schemaVersion": MODULE.SCHEMA,
        "project": MODULE.PROJECT_ID,
        "upload": {
            "taskId": MODULE.UPLOAD_TASK_ID,
            "status": "completed",
            "total": 337,
            "uploaded": 139,
            "duplicates": 198,
            "annotated": 337,
            "errors": 0,
            "warnings": 0,
            "failedChunks": 0,
        },
        "selectedRecords": {
            "tag": MODULE.SELECTION_TAG,
            "records": 139,
            "allSelectedRecordsCarryTag": True,
            "selectionWasCreatedAfterUpload": True,
            "contentOrAnnotationIdentityCompared": False,
        },
        "privacy": {
            "containsFilenames": False,
            "containsProviderImageIds": False,
            "containsImageBytes": False,
        },
    }


class RegionalPostUploadProvenanceTests(unittest.TestCase):
    def test_tag_is_provenance_only_and_cannot_authorize_exclusion(self):
        result = MODULE.build_audit(observation())
        self.assertFalse(result["tagEstablishesUnwantedMembership"])
        self.assertFalse(result["tagBasedDeletionOrVersionExclusionAllowed"])
        self.assertTrue(result["exactProviderExportAuditRequired"])

    def test_count_mismatch_fails_closed(self):
        value = copy.deepcopy(observation())
        value["selectedRecords"]["records"] = 138
        with self.assertRaisesRegex(MODULE.AuditError, "selected record count changed"):
            MODULE.build_audit(value)

    def test_content_identity_claim_is_rejected(self):
        value = copy.deepcopy(observation())
        value["selectedRecords"]["contentOrAnnotationIdentityCompared"] = True
        with self.assertRaisesRegex(MODULE.AuditError, "must not claim content identity"):
            MODULE.build_audit(value)


if __name__ == "__main__":
    unittest.main()
