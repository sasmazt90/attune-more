import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_unified_skin_result_release.py"
spec = importlib.util.spec_from_file_location("check_unified_skin_result_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "unified-skin-result-release-receipt-20261028-v16.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write(root, name, payload):
    path = root / "docs" / "skin" / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {"path": f"docs/skin/evidence/{name}", "sha256": hashlib.sha256(raw).hexdigest()}


def _install_complete_evidence(receipt, root):
    receipt["inputEvidence"] = {}
    for name, expected in module.EXPECTED_INPUT_EVIDENCE.items():
        receipt["inputEvidence"][name] = _write(root, Path(expected["path"]).name, {"fixture": name})
    module.EXPECTED_INPUT_EVIDENCE = copy.deepcopy(receipt["inputEvidence"])
    for name, entry in receipt["classReleaseGates"].items():
        payload = {"methodVersion": entry["methodVersion"], "roadmapAccepted": True}
        entry["evidence"] = _write(root, f"{name}-accepted.json", payload)
        entry["roadmapAccepted"] = True
    camera = {
        "methodVersion": receipt["physicalCameraGate"]["methodVersion"],
        "roadmapCameraAcceptanceAllowed": True,
    }
    receipt["physicalCameraGate"]["evidence"] = _write(root, "camera-gate-accepted.json", camera)
    receipt["physicalCameraGate"]["accepted"] = True
    provider = {
        "methodVersion": receipt["regionalProviderDatasetGate"]["methodVersion"],
        "project": "tolgar-sasmaz/attune-skin-regional-skin-map",
        "groupLockedManifestVerified": True,
        "providerVersionReady": True,
        "trainingAuthorized": True,
    }
    receipt["regionalProviderDatasetGate"]["evidence"] = _write(
        root, "regional-provider-dataset-gate-ready.json", provider,
    )
    receipt["regionalProviderDatasetGate"]["providerVersionReady"] = True
    receipt["regionalProviderDatasetGate"]["trainingAuthorized"] = True
    receipt["repositoryCI"] = _write(root, "repository-ci.json", {
        "schemaVersion": module.EXPECTED_REPOSITORY_CI_SCHEMA,
        "branch": module.EXPECTED_BRANCH,
        "implementationCommit": "d" * 40,
        "githubActions": {
            "runId": 99, "url": "https://github.com/sasmazt90/attune-more/actions/runs/99",
            "workflowId": module.EXPECTED_REPOSITORY_CI_WORKFLOW_ID,
            "workflowPath": module.EXPECTED_REPOSITORY_CI_WORKFLOW_PATH,
            "branch": module.EXPECTED_BRANCH,
            "frontendJobId": 101, "backendJobId": 102,
            "headSha": "d" * 40, "conclusion": "success",
            "frontendProductionBuild": "success", "localizationContract": "success",
            "completeSkinResearchEvidenceSuite": {"result": "OK"},
        },
        "browserAcceptance": {
            "runId": 98, "conclusion": "success", "sanitizedEvidenceOnly": True,
            "branch": module.EXPECTED_BRANCH, "headSha": "d" * 40,
            "workflowId": module.EXPECTED_BROWSER_WORKFLOW_ID,
            "workflowPath": module.EXPECTED_BROWSER_WORKFLOW_PATH,
            "jobId": 97, "artifactId": 96,
            "artifactDigest": "sha256:" + "a" * 64,
            "artifactWorkflowRun": {
                "runId": 98, "branch": module.EXPECTED_BRANCH, "headSha": "d" * 40,
            },
            "realBrowser": True, "apiHistoryPrivacyPassed": True,
            "controlledFixture": True, "physicalCameraCapture": False,
            "expertGroundTruth": False, "accuracyEvidence": False,
        },
    })
    candidate = receipt["acceptanceCandidate"]
    candidate.update({
        "mode": "accepted-end-to-end-release", "releaseId": "skin-roadmap-release-v2",
        "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
        "browserRunId": "browser-run-v2", "cameraBenchmarkId": "camera-benchmark-v2",
        "historyPolicyId": "method-compatible-history-v2",
    })
    candidate["evidence"] = {
        "browserApiReplay": _write(root, "browser.json", {
            "realBrowser": True, "apiE2EPassed": True, "sixRegionalViewsPassed": True,
            "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
            "browserRunId": "browser-run-v2", "historyPolicyId": "method-compatible-history-v2",
        }),
        "indexedDbHistoryReplay": _write(root, "history.json", {
            "indexedDbWriteReadPassed": True, "methodCompatibleHistoryPassed": True,
            "crossMethodBridgeAllowed": False, "malformedRecordFallbackAllowed": False,
            "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
            "browserRunId": "browser-run-v2", "historyPolicyId": "method-compatible-history-v2",
        }),
        "physicalCameraAcceptance": _write(root, "camera.json", {
            "physicalCameraBenchmarkAccepted": True, "consentedPhysicalCaptures": True,
            "expertTruthPerActivatedClass": True, "cameraBenchmarkId": "camera-benchmark-v2",
        }),
        "independentFinalTests": _write(root, "final-tests.json", {
            "perActivatedClassPassed": True, "thresholdSelectionSplit": "validation",
            "finalTestUsedForSelection": False, "releaseId": "skin-roadmap-release-v2",
            "repositoryCommit": "d" * 40,
        }),
        "unavailableOverlapControls": _write(root, "controls.json", {
            "unknownCountsAsNormal": False, "rednessIndependentLayer": True,
            "rednessSensitivityAliasAllowed": False, "dryOilyRednessOverlapPassed": True,
            "unsupportedHeadingsUnavailable": True,
            "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
            "browserRunId": "browser-run-v2", "historyPolicyId": "method-compatible-history-v2",
        }),
        "privacyLifecycle": _write(root, "privacy.json", {
            "consentPassed": True, "retentionPassed": True, "deletionPassed": True,
            "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
            "browserRunId": "browser-run-v2", "historyPolicyId": "method-compatible-history-v2",
        }),
        "workingProductReplay": _write(root, "product-replay.json", {
            "endpoint": "/api/local-health/skin", "concreteResultsPassed": True,
            "mapCardsHistoryPassed": True, "twelveProductHeadingsPassed": True,
            "repositoryCommit": "d" * 40, "productBuildId": "vehicle-app-build-v2",
            "browserRunId": "browser-run-v2", "historyPolicyId": "method-compatible-history-v2",
        }),
    }


def _mutate_candidate_evidence(receipt, root, key, field, value):
    identity = receipt["acceptanceCandidate"]["evidence"][key]
    path = root / identity["path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    receipt["acceptanceCandidate"]["evidence"][key] = _write(root, path.name, payload)


def _mutate_repository_ci(receipt, root, field, value, section=None):
    identity = receipt["repositoryCI"]
    path = root / identity["path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    target = payload if section is None else payload[section]
    target[field] = value
    receipt["repositoryCI"] = _write(root, path.name, payload)


class UnifiedSkinResultReleaseTests(unittest.TestCase):
    def test_stale_receipt_schema_cannot_reenter(self):
        receipt = _receipt()
        receipt["schemaVersion"] = 10
        with self.assertRaisesRegex(module.GateInputError, "receipt schema"):
            module.evaluate_release(receipt)

    def test_working_baseline_remains_visible_but_final_acceptance_is_blocked(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["workingBaselinePreserved"])
        self.assertTrue(result["currentIntegratedPresentationAllowed"])
        self.assertFalse(result["allClassReleaseGatesAccepted"])
        self.assertFalse(result["physicalCameraBenchmarkAccepted"])
        self.assertFalse(result["regionalProviderDatasetReady"])
        self.assertIn("regional_provider_version_not_ready", result["blockers"])
        self.assertIn("regional_provider_training_not_authorized", result["blockers"])
        self.assertFalse(result["roadmapAccepted"])

    def test_regional_provider_boolean_cannot_disagree_with_bound_evidence(self):
        receipt = _receipt()
        receipt["regionalProviderDatasetGate"]["providerVersionReady"] = True
        with self.assertRaisesRegex(module.GateInputError, "readiness does not match evidence"):
            module.evaluate_release(receipt)

    def test_stale_regional_provider_gate_cannot_reenter(self):
        receipt = _receipt()
        receipt["regionalProviderDatasetGate"]["methodVersion"] = (
            "regional-provider-dataset-release-gate-v0"
        )
        with self.assertRaisesRegex(module.GateInputError, "current expected method"):
            module.evaluate_release(receipt)

    def test_current_gate_registry_is_bound_to_real_rejected_evidence(self):
        result = module.evaluate_release(_receipt())
        self.assertEqual(set(result["classReleaseGates"]), set(module.EXPECTED_GATE_TASKS))
        self.assertTrue(all(not gate["roadmapAccepted"] for gate in result["classReleaseGates"].values()))
        self.assertIn("task_01_release_gate_not_accepted", result["blockers"])
        self.assertIn("task_12_release_gate_not_accepted", result["blockers"])

    def test_missing_candidate_cannot_claim_release_identity(self):
        receipt = _receipt()
        receipt["acceptanceCandidate"]["repositoryCommit"] = "f" * 40
        with self.assertRaisesRegex(module.GateInputError, "cannot claim"):
            module.evaluate_release(receipt)

    def test_class_gate_boolean_cannot_disagree_with_evidence(self):
        receipt = _receipt()
        receipt["classReleaseGates"]["acneConcerns"]["roadmapAccepted"] = True
        with self.assertRaisesRegex(module.GateInputError, "does not match evidence"):
            module.evaluate_release(receipt)

    def test_stale_under_eye_gate_cannot_reenter_unified_registry(self):
        receipt = _receipt()
        receipt["classReleaseGates"]["underEye"]["methodVersion"] = "under-eye-per-class-release-gate-v2"
        with self.assertRaisesRegex(module.GateInputError, "current expected method"):
            module.evaluate_release(receipt)

    def test_expected_gate_method_registry_covers_every_task_registry_entry(self):
        self.assertEqual(set(module.EXPECTED_GATE_METHODS), set(module.EXPECTED_GATE_TASKS))

    def test_stale_physical_camera_gate_cannot_reenter_unified_registry(self):
        receipt = _receipt()
        receipt["physicalCameraGate"]["methodVersion"] = "physical-camera-benchmark-release-gate-v0"
        with self.assertRaisesRegex(module.GateInputError, "current expected method"):
            module.evaluate_release(receipt)

    def test_evidence_digest_mismatch_is_rejected(self):
        receipt = _receipt()
        receipt["classReleaseGates"]["sag"]["evidence"]["sha256"] = "a" * 64
        with self.assertRaisesRegex(module.GateInputError, "digest mismatch"):
            module.evaluate_release(receipt)

    def test_zero_evidence_digest_is_rejected(self):
        receipt = _receipt()
        receipt["physicalCameraGate"]["evidence"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(module.GateInputError, "sha256"):
            module.evaluate_release(receipt)

    def test_generated_smoke_cannot_become_physical_camera_or_truth(self):
        for field in ("physicalCameraCapture", "expertGroundTruth", "accuracyEvidence"):
            receipt = _receipt()
            receipt["generatedSmoke"][field] = True
            with self.assertRaises(module.GateInputError):
                module.evaluate_release(receipt)

    def test_unknown_cannot_become_normal(self):
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["unknownCountsAsNormal"] = True
        with self.assertRaisesRegex(module.GateInputError, "Normal"):
            module.evaluate_release(receipt)

    def test_redness_cannot_become_sensitivity(self):
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["rednessSensitivityAliasAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "sensitivity"):
            module.evaluate_release(receipt)

    def test_boxes_and_model_predictions_cannot_become_expert_polygons(self):
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["boxAsPolygonAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "Boxes"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["mapAndHistoryContract"]["modelPredictionAsExpertTruthAllowed"] = True
        with self.assertRaisesRegex(module.GateInputError, "expert truth"):
            module.evaluate_release(receipt)

    def test_code_blob_drift_is_rejected(self):
        receipt = _receipt()
        receipt["codeBlobs"]["shared/localization/messages.json"] = "0" * 40
        with self.assertRaisesRegex(module.GateInputError, "implementation blobs"):
            module.evaluate_release(receipt)

    def test_browser_evidence_must_be_real_browser(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                identity = receipt["acceptanceCandidate"]["evidence"]["browserApiReplay"]
                identity["sha256"] = _write(root, "browser.json", {
                    "realBrowser": False, "apiE2EPassed": True, "sixRegionalViewsPassed": True,
                })["sha256"]
                with self.assertRaisesRegex(module.GateInputError, "real browser"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_final_test_cannot_select_thresholds(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                identity = receipt["acceptanceCandidate"]["evidence"]["independentFinalTests"]
                identity["sha256"] = _write(root, "final-tests.json", {
                    "perActivatedClassPassed": True, "thresholdSelectionSplit": "validation",
                    "finalTestUsedForSelection": True,
                })["sha256"]
                with self.assertRaisesRegex(module.GateInputError, "cannot select"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_build_identity_must_match_candidate(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_candidate_evidence(receipt, root, "browserApiReplay", "productBuildId", "other-build")
                with self.assertRaisesRegex(module.GateInputError, "productBuildId identity mismatch"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_history_policy_identity_must_match_across_browser_evidence(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_candidate_evidence(receipt, root, "privacyLifecycle", "historyPolicyId", "other-policy")
                with self.assertRaisesRegex(module.GateInputError, "historyPolicyId identity mismatch"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_commit_must_match_candidate(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                receipt["repositoryCI"] = _write(root, "repository-ci.json", {
                    "schemaVersion": module.EXPECTED_REPOSITORY_CI_SCHEMA,
                    "branch": module.EXPECTED_BRANCH,
                    "implementationCommit": "e" * 40,
                    "githubActions": {
                        "runId": 99, "url": "https://github.com/sasmazt90/attune-more/actions/runs/99",
                        "workflowId": module.EXPECTED_REPOSITORY_CI_WORKFLOW_ID,
                        "workflowPath": module.EXPECTED_REPOSITORY_CI_WORKFLOW_PATH,
                        "branch": module.EXPECTED_BRANCH,
                        "frontendJobId": 101, "backendJobId": 102,
                        "headSha": "e" * 40, "conclusion": "success",
                        "frontendProductionBuild": "success", "localizationContract": "success",
                        "completeSkinResearchEvidenceSuite": {"result": "OK"},
                    },
                    "browserAcceptance": {
                        "runId": 98, "conclusion": "success", "sanitizedEvidenceOnly": True,
                        "branch": module.EXPECTED_BRANCH, "headSha": "e" * 40,
                        "workflowId": module.EXPECTED_BROWSER_WORKFLOW_ID,
                        "workflowPath": module.EXPECTED_BROWSER_WORKFLOW_PATH,
                        "jobId": 97, "artifactId": 96,
                        "artifactDigest": "sha256:" + "a" * 64,
                        "artifactWorkflowRun": {
                            "runId": 98, "branch": module.EXPECTED_BRANCH, "headSha": "e" * 40,
                        },
                        "realBrowser": True, "apiHistoryPrivacyPassed": True,
                        "controlledFixture": True, "physicalCameraCapture": False,
                        "expertGroundTruth": False, "accuracyEvidence": False,
                    },
                })
                with self.assertRaisesRegex(module.GateInputError, "CI commit identity mismatch"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_must_target_working_branch(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "branch", "main")
                with self.assertRaisesRegex(module.GateInputError, "branch identity"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_must_use_pinned_workflow(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            for field, value in (
                ("workflowId", module.EXPECTED_REPOSITORY_CI_WORKFLOW_ID + 1),
                ("workflowPath", ".github/workflows/other.yml"),
                ("branch", "main"),
            ):
                with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, value, "githubActions")
                    with self.assertRaisesRegex(module.GateInputError, "workflow"):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_requires_positive_distinct_job_ids(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            for field, value, message in (
                ("frontendJobId", 0, "frontend job identity missing"),
                ("backendJobId", False, "backend job identity missing"),
                ("backendJobId", 101, "must be distinct"),
            ):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, value, "githubActions")
                    with self.assertRaisesRegex(module.GateInputError, message):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_requires_positive_run_id(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "runId", 0, "githubActions")
                with self.assertRaisesRegex(module.GateInputError, "run identity missing"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_run_url_must_match_run_id(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(
                    receipt, root, "url",
                    "https://github.com/sasmazt90/attune-more/actions/runs/100",
                    "githubActions",
                )
                with self.assertRaisesRegex(module.GateInputError, "run URL identity"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_implementation_commit_must_match_workflow_head(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "implementationCommit", "e" * 40)
                with self.assertRaisesRegex(module.GateInputError, "does not match workflow head"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_ci_stale_schema_is_rejected(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "schemaVersion", 1)
                with self.assertRaisesRegex(module.GateInputError, "schema changed"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_acceptance_commit_must_match_repository_ci(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "headSha", "e" * 40, "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "browser acceptance commit"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_artifact_commit_must_match_repository_ci(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                artifact_run = {
                    "runId": 98, "branch": module.EXPECTED_BRANCH, "headSha": "e" * 40,
                }
                _mutate_repository_ci(receipt, root, "artifactWorkflowRun", artifact_run, "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "browser artifact commit"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_artifact_workflow_run_must_match_browser_run(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                artifact_run = {
                    "runId": 97, "branch": module.EXPECTED_BRANCH, "headSha": "d" * 40,
                }
                _mutate_repository_ci(receipt, root, "artifactWorkflowRun", artifact_run, "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "workflow run identity"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_acceptance_must_use_pinned_workflow(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            for field, value in (
                ("workflowId", module.EXPECTED_BROWSER_WORKFLOW_ID + 1),
                ("workflowPath", ".github/workflows/other.yml"),
            ):
                with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, value, "browserAcceptance")
                    with self.assertRaisesRegex(module.GateInputError, "workflow"):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_acceptance_requires_positive_job_and_artifact_ids(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            for field, value in (("jobId", 0), ("artifactId", False)):
                with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, value, "browserAcceptance")
                    with self.assertRaisesRegex(module.GateInputError, "identity missing"):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_acceptance_requires_sha256_artifact_digest(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "artifactDigest", "sha256:not-a-digest", "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "artifact digest invalid"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_browser_artifact_workflow_identity_rejects_extra_or_missing_fields(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                artifact_run = {
                    "runId": 98, "branch": module.EXPECTED_BRANCH,
                    "headSha": "d" * 40, "mutableNote": "unbound",
                }
                _mutate_repository_ci(receipt, root, "artifactWorkflowRun", artifact_run, "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "identity is incomplete"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_browser_acceptance_must_remain_controlled_fixture(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_repository_ci(receipt, root, "controlledFixture", False, "browserAcceptance")
                with self.assertRaisesRegex(module.GateInputError, "controlled fixture"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_browser_fixture_cannot_be_promoted_to_acceptance_truth(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            for field in ("physicalCameraCapture", "expertGroundTruth", "accuracyEvidence"):
                with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, True, "browserAcceptance")
                    with self.assertRaises(module.GateInputError):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_repository_browser_acceptance_requires_real_sanitized_green_replay(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            cases = (
                ("conclusion", "failure"),
                ("sanitizedEvidenceOnly", False),
                ("realBrowser", False),
                ("apiHistoryPrivacyPassed", False),
            )
            for field, value in cases:
                with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    receipt = _receipt()
                    _install_complete_evidence(receipt, root)
                    _mutate_repository_ci(receipt, root, field, value, "browserAcceptance")
                    with self.assertRaises(module.GateInputError):
                        module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_camera_benchmark_identity_must_match_candidate(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_candidate_evidence(receipt, root, "physicalCameraAcceptance", "cameraBenchmarkId", "other-camera")
                with self.assertRaisesRegex(module.GateInputError, "camera benchmark identity mismatch"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_final_test_release_identity_must_match_candidate(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                _mutate_candidate_evidence(receipt, root, "independentFinalTests", "releaseId", "other-release")
                with self.assertRaisesRegex(module.GateInputError, "final-test release identity mismatch"):
                    module.evaluate_release(receipt, root)
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs

    def test_complete_identity_bound_future_release_can_pass(self):
        original_inputs = copy.deepcopy(module.EXPECTED_INPUT_EVIDENCE)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                receipt = _receipt()
                _install_complete_evidence(receipt, root)
                result = module.evaluate_release(receipt, root)
                self.assertEqual(result["decision"], "ready")
                self.assertTrue(result["allClassReleaseGatesAccepted"])
                self.assertTrue(result["physicalCameraBenchmarkAccepted"])
                self.assertTrue(result["regionalProviderDatasetReady"])
                self.assertTrue(result["acceptedEndToEndCandidatePresent"])
                self.assertTrue(result["finalRoadmapAcceptanceAllowed"])
                self.assertTrue(result["roadmapAccepted"])
                self.assertEqual(result["blockers"], [])
        finally:
            module.EXPECTED_INPUT_EVIDENCE = original_inputs


if __name__ == "__main__":
    unittest.main()


