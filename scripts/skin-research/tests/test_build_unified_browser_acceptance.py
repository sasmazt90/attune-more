import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "scripts/skin-research/build_unified_browser_acceptance.py"
SPEC = importlib.util.spec_from_file_location("build_unified_browser_acceptance", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def row(identifier, unavailable=False):
    reason = MODULE.UNAVAILABLE.get(identifier)
    return {
        "id": identifier,
        "score": None if unavailable else 10,
        "appearance": {
            "value": None if unavailable else 10,
            "limitationCode": reason,
            "components": {"localizedInstancesAvailable": False} if unavailable else {},
        },
    }


class UnifiedBrowserAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        indicators = [row(identifier, identifier in MODULE.UNAVAILABLE) for identifier in MODULE.HEADINGS]
        run = {
            "graphs": MODULE.REGIONS,
            "api": {"endpoint": "/api/local-health/skin", "requestCount": 3, "successfulResponseCount": 3, "uniqueRequestPhotoIds": 3, "allRequestsHaveSuccessfulResponse": True},
            "result": {"general": {"indicators": indicators}},
        }
        self.browser = {
            "status": "PASS", "methodVersion": "skin-browser-api-replay-v1", "buildId": "build-a",
            "realBrowser": True, "browserEngine": "chromium", "controlledFixture": True,
            "physicalCamera": False, "expertGroundTruth": False, "accuracyEvidence": False,
            "endpoint": "/api/local-health/skin", "apiE2EPassed": True, "sixRegionalViewsPassed": True,
            "mapCardsHistoryPassed": True, "twelveProductHeadingsPassed": True,
            "unsupportedHeadingsUnavailable": True, "poseMock": False, "qualityOverride": False,
            "pageErrors": [], "runs": [run, run],
        }
        scans = []
        for index in range(3):
            scan = {key: {region: f"opaque-{index}-{region}" for region in MODULE.REGIONS} for key in ("sourceByRegion", "shaByRegion", "poseByRegion")}
            scan["id"] = f"scan-{index}"
            scans.append(scan)
        self.history = {
            "status": "PASS", "methodVersion": "skin-indexeddb-history-replay-v1", "buildId": "build-a",
            "realBrowser": True, "browserEngine": "chromium", "controlledFixture": True,
            "physicalUserAcceptance": False, "expertGroundTruth": False, "accuracyEvidence": False,
            "indexedDbWriteReadPassed": True, "relaunchThreeRecords": True,
            "allSixRegionsAndSelectedMaps": True, "twelveProductHeadingsPassed": True,
            "unsupportedHeadingsUnavailable": True, "deleteOne": True, "revokePhotosKeepsNumeric": True,
            "retentionPassed": True, "deletionPassed": True, "pageErrors": [], "scans": scans,
        }
        self.privacy = {
            "status": "PASS", "methodVersion": "skin-privacy-lifecycle-browser-v1", "buildId": "build-a",
            "realBrowser": True, "browserEngine": "chromium", "controlledFixture": True,
            "physicalUserAcceptance": False, "expertGroundTruth": False, "accuracyEvidence": False,
            "explicitPhotoConsent": True, "consentPassed": True, "retentionPassed": True,
            "localWipeVerified": True, "deletionPassed": True, "backendForwardedToRealIsolatedService": True,
            "backendWipeAcceptance": True, "sharedBackendUnchanged": True, "relaunchStillEmpty": True,
            "isolatedBackendRecordsBefore": 2, "isolatedBackendRecordsAfter": 0,
        }
        self.ci = {"githubActions": {"conclusion": "success", "frontendProductionBuild": "success", "completeSkinResearchEvidenceSuite": {"result": "OK"}}}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def args(self):
        return argparse.Namespace(
            browser_proof=self.write("browser.json", self.browser),
            history_proof=self.write("history.json", self.history),
            privacy_proof=self.write("privacy.json", self.privacy),
            ci_evidence=self.write("ci.json", self.ci),
            repository_commit="a" * 40, browser_run_id="browser-run-1",
            history_policy_id="method-compatible-history-v2", output_dir=self.root / "out",
        )

    def test_builds_five_privacy_safe_evidence_files(self):
        result = MODULE.build(self.args())
        self.assertEqual(set(result), {"browser-api-replay.json", "indexeddb-history-replay.json", "privacy-lifecycle.json", "unavailable-overlap-controls.json", "working-product-replay.json"})
        self.assertTrue(result["browser-api-replay.json"]["apiE2EPassed"])
        self.assertTrue(result["indexeddb-history-replay.json"]["indexedDbWriteReadPassed"])
        self.assertFalse(result["indexeddb-history-replay.json"]["crossMethodBridgeAllowed"])
        self.assertTrue(result["working-product-replay.json"]["twelveProductHeadingsPassed"])
        self.assertFalse(result["browser-api-replay.json"]["physicalCameraCapture"])

    def test_rejects_missing_unavailable_localized_heading(self):
        self.browser["runs"][0]["result"]["general"]["indicators"][-1]["score"] = 1
        with self.assertRaisesRegex(MODULE.EvidenceError, "pigmentation must remain unavailable"):
            MODULE.build(self.args())

    def test_rejects_build_identity_mismatch(self):
        self.history["buildId"] = "other-build"
        with self.assertRaisesRegex(MODULE.EvidenceError, "build identities disagree"):
            MODULE.build(self.args())

    def test_rejects_physical_camera_promotion(self):
        self.browser["physicalCamera"] = True
        with self.assertRaisesRegex(MODULE.EvidenceError, "cannot claim physical-camera"):
            MODULE.build(self.args())

    def test_rejects_incomplete_region_coverage(self):
        self.history["scans"][0]["sourceByRegion"].pop("chin")
        with self.assertRaisesRegex(MODULE.EvidenceError, "coverage changed"):
            MODULE.build(self.args())

    def test_rejects_duplicate_retained_scan_identity(self):
        self.history["scans"][1]["id"] = self.history["scans"][0]["id"]
        with self.assertRaisesRegex(MODULE.EvidenceError, "three distinct"):
            MODULE.build(self.args())

    def test_rejects_missing_history_policy_identity(self):
        args = self.args()
        args.history_policy_id = ""
        with self.assertRaisesRegex(MODULE.EvidenceError, "history policy"):
            MODULE.build(args)

    def test_failed_browser_run_artifact_is_sanitized_and_stage_bound(self):
        workflow = (ROOT / ".github/workflows/e2e-audit.yml").read_text(encoding="utf-8")
        privacy = (ROOT / "tests/e2e/current_skin_photo_wipe_success.py").read_text(encoding="utf-8")
        self.assertIn("ATTUNE_SAFE_STAGE_FILE=audit-results/unified-skin-result-browser-acceptance/sanitized/privacy-runtime-status.json", workflow)
        self.assertIn("path: audit-results/unified-skin-result-browser-acceptance/sanitized/", workflow)
        self.assertNotIn("path: audit-results/unified-skin-result-browser-acceptance/\n", workflow)
        self.assertIn("'physicalCameraCapture':False", privacy)
        self.assertIn("stage('completed','pass')", privacy)
        self.assertIn("if os.name=='nt':return capture_owned_window(page,profile,path)", privacy)
        self.assertNotIn(";capture_owned_window(p,profile,OUT/'wipe-local-and-backend-success.png')", privacy)


if __name__ == "__main__":
    unittest.main()
