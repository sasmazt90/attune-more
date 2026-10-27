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
        self.ci = {"githubActions": {"headSha": "a" * 40, "conclusion": "success", "frontendProductionBuild": "success", "completeSkinResearchEvidenceSuite": {"result": "OK"}}}

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

    def use_findings_proofs(self):
        """Synthetic proof-schema fixtures, never browser/model acceptance evidence."""
        self.browser.update(
            methodVersion='skin-findings-browser-api-v2',
            realModelInference=True, approvedFindingsUI=True, findingsMatchServer=True,
            sourceBoundNumericRows=True,
            api=dict(sourcePhotoCount=3, poses=['FRONT', 'LEFT', 'RIGHT'], allRequestsHaveSuccessfulResponse=True),
            nativeZoom=dict(dpr=2, cssZoom='1', innerWidth=800, outerWidth=1600, scroll=800),
            nativeCapture=dict(poses=['FRONT','LEFT','RIGHT'],sourcePhotoCount=3,allRequestsHaveSuccessfulResponse=True,distinctNewRecord=True,findingsMatchServer=True),
        )
        models=json.loads((ROOT/'research/skin-findings/MODEL_MANIFEST.json').read_text())['models']
        expected={m['runtimeName']:m['sha256'] for m in models if m.get('runtimeName') in ('acnes.pt','findings.pt','regional.pt','skinmap.pt','wrinkles.pt')}
        self.browser['runtimeModels']={pose:dict(expected) for pose in ('FRONT','LEFT','RIGHT')}
        self.browser['runtimeModelsAtNativeZoom']={pose:dict(expected) for pose in ('FRONT','LEFT','RIGHT')}
        self.history.update(methodVersion='skin-findings-indexeddb-v2', selectedRecordBinding=True,
                            sourceBoundSixRegions=True, approvedFindingsUI=True, poseMock=False, qualityOverride=False)

    def test_findings_proofs_do_not_promote_historical_layout_assertions(self):
        self.use_findings_proofs()
        output=MODULE.build(self.args())
        self.assertTrue(output['working-product-replay.json']['approvedFindingsUI'])
        self.assertFalse(output['working-product-replay.json']['twelveProductHeadingsPassed'])
        self.assertFalse(output['browser-api-replay.json']['sixRegionalViewsPassed'])

    def test_findings_proof_requires_every_pose_model_identity(self):
        self.use_findings_proofs()
        self.browser['runtimeModels']['LEFT']['findings.pt']='0'*64
        with self.assertRaisesRegex(MODULE.EvidenceError,'LEFT: model identity mismatch'):
            MODULE.build(self.args())

    def test_findings_proof_rejects_missing_inference_or_simulated_zoom(self):
        for change in ({'realModelInference':False}, {'nativeZoom':dict(dpr=1, cssZoom='2', innerWidth=800, outerWidth=1600, scroll=800)}):
            with self.subTest(change=change):
                self.use_findings_proofs(); self.browser.update(change)
                with self.assertRaises(MODULE.EvidenceError):MODULE.build(self.args())

    def test_findings_history_rejects_missing_selected_record_and_source_identity(self):
        self.use_findings_proofs();self.history['selectedRecordBinding']=False
        with self.assertRaisesRegex(MODULE.EvidenceError,'selectedRecordBinding'):MODULE.build(self.args())
        self.history['selectedRecordBinding']=True;self.history['scans'][1]['shaByRegion']['nose']=''
        with self.assertRaisesRegex(MODULE.EvidenceError,'source identities missing'):MODULE.build(self.args())

    def test_ci_must_belong_to_the_tested_immutable_head(self):
        self.ci['githubActions']['headSha']='b'*40
        with self.assertRaisesRegex(MODULE.EvidenceError,'CI head does not match'):MODULE.build(self.args())

    def test_native_zoom_requires_a_new_real_capture_not_only_result_replay(self):
        self.use_findings_proofs();self.browser['nativeCapture']=None
        with self.assertRaisesRegex(MODULE.EvidenceError,'actual browser200 capture missing'):MODULE.build(self.args())

    def test_native_capture_model_identity_cannot_differ_from_verified_bundle(self):
        self.use_findings_proofs();self.browser['runtimeModelsAtNativeZoom']['RIGHT']['acnes.pt']='b'*64
        with self.assertRaisesRegex(MODULE.EvidenceError,'model identity mismatch'):MODULE.build(self.args())


if __name__ == "__main__":
    unittest.main()
