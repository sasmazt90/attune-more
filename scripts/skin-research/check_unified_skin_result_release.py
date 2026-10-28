#!/usr/bin/env python3
"""Identity-bound task-13 gate for unified results, maps and history.

The merged product already returns concrete skin results. That working flow
remains available. Final roadmap acceptance is a separate release: it must
bind every concern gate, physical-camera benchmark, browser/API/IndexedDB
replay, independent final-test evidence and privacy controls to immutable
files. Mutable receipt booleans cannot promote generated smoke or rejected
class models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BRANCH = "work/skin-roadmap-20261023"
EXPECTED_RECEIPT_SCHEMA = 16
EXPECTED_REPOSITORY_CI_SCHEMA = 3
EXPECTED_REPOSITORY_CI_WORKFLOW_ID = 362950948
EXPECTED_REPOSITORY_CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
EXPECTED_BROWSER_WORKFLOW_ID = 370615037
EXPECTED_BROWSER_WORKFLOW_PATH = ".github/workflows/e2e-audit.yml"
EXPECTED_CODE_BLOBS = {
    "apps/vehicle-app/src/utils/regionalSkinMap.ts": "258ab2d845b3743ede309938cd14da8831a01046",
    "apps/vehicle-app/src/utils/skinOverview.ts": "4d31010f82bfd5c42a49b46c20880630d57079dd",
    "apps/vehicle-app/src/utils/skinPhotoHistory.ts": "d143cb121cc39149b1ee4d26d4e4bacd9ba0f288",
    "apps/vehicle-app/src/components/skin/SkinFacePanel.tsx": "c86d90f41ad1b9c54025e111cd636271c533618a",
    "apps/vehicle-app/src/components/skin/SkinTrendModal.tsx": "4709e9214cee28bbd2de5bfa9d20261b63f489c3",
    "shared/localization/messages.json": "71c0f5dc25ac984331559b43a48d9b9da1e1492e",
    "services/core-api/skin_product_contract.py": "f152726978bee2eea36b0563d9ac36cbcf330c7b",
}
EXPECTED_INPUT_EVIDENCE = {
    "currentProductRecheck": {
        "path": "docs/skin/evidence/current-product-skin-contract-recheck-20261025-v1.json",
        "sha256": "42b85a7c24591456934823eb443e93e79bce874b2b5a39ef1262f06a9150f850",
    },
    "unifiedMapCorrection": {
        "path": "docs/skin/evidence/unified-map-contract-correction-20261025-v1.json",
        "sha256": "e2eeb9e5244c5a7bf593072736d0dc345f673bff4e4ddc78ef678ffae91d0de3",
    },
    "generatedSmoke": {
        "path": "docs/skin/evidence/camera-triplet-generated-smoke-20261024-v1.json",
        "sha256": "104308686d284695f43336bcaf3c04414f68f24bdde8eb9a9eab19ba1f68f46d",
    },
}
EXPECTED_GATE_TASKS = {
    "acneConcerns": ["01", "02", "03"],
    "oily": ["04"],
    "dryness": ["05"],
    "skinTypeCombination": ["06"],
    "redness": ["07"],
    "toneUnevenness": ["08"],
    "underEye": ["09", "10"],
    "wrinkles": ["11"],
    "sag": ["12"],
}
EXPECTED_GATE_METHODS = {
    "acneConcerns": "acne-concerns-per-class-release-gate-v2",
    "oily": "regional-oily-appearance-release-gate-v2",
    "dryness": "regional-dryness-release-gate-v2",
    "skinTypeCombination": "skin-type-combination-release-gate-v2",
    "redness": "regional-redness-release-gate-v2",
    "toneUnevenness": "tone-unevenness-release-gate-v2",
    "underEye": "under-eye-per-class-release-gate-v5",
    "wrinkles": "wrinkle-per-class-release-gate-v2",
    "sag": "sag-appearance-release-gate-v2",
}
EXPECTED_PHYSICAL_CAMERA_GATE_METHOD = "physical-camera-benchmark-release-gate-v2"
EXPECTED_REGIONAL_PROVIDER_DATASET_GATE_METHOD = "regional-provider-dataset-release-gate-v3"
EXPECTED_HEADINGS = [
    "tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags",
    "Post acne", "Pigmentation", "skinType",
]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class GateInputError(ValueError):
    """Raised when evidence identity or product semantics are contradicted."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def _require_positive_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GateInputError(message)
    return value


def _load_evidence(identity: Any, label: str, evidence_root: Path) -> dict[str, Any]:
    if not isinstance(identity, dict):
        raise GateInputError(f"{label} evidence identity missing")
    path = identity.get("path")
    digest = identity.get("sha256")
    if not isinstance(path, str) or not path.startswith("docs/skin/evidence/"):
        raise GateInputError(f"{label} evidence path missing")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None or digest == "0" * 64:
        raise GateInputError(f"{label} evidence sha256 missing")
    file_path = evidence_root / path
    if not file_path.is_file():
        raise GateInputError(f"{label} evidence file missing")
    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if actual != digest:
        raise GateInputError(f"{label} evidence digest mismatch")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateInputError(f"{label} evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GateInputError(f"{label} evidence must be a JSON object")
    return payload


def _validate_gate_registry(receipt: dict[str, Any], evidence_root: Path) -> tuple[bool, list[str], dict[str, Any]]:
    registry = receipt.get("classReleaseGates")
    if not isinstance(registry, dict) or set(registry) != set(EXPECTED_GATE_TASKS):
        raise GateInputError("class release gate registry is incomplete")
    blockers: list[str] = []
    summary: dict[str, Any] = {}
    for name, expected_tasks in EXPECTED_GATE_TASKS.items():
        entry = registry[name]
        if not isinstance(entry, dict):
            raise GateInputError(f"{name} release gate entry missing")
        _require(entry.get("tasks"), expected_tasks, f"{name} task coverage changed")
        _require(
            entry.get("methodVersion"), EXPECTED_GATE_METHODS[name],
            f"{name} release gate is not the current expected method",
        )
        payload = _load_evidence(entry.get("evidence"), f"{name} release gate", evidence_root)
        _require(payload.get("methodVersion"), entry.get("methodVersion"), f"{name} gate method identity changed")
        accepted = payload.get("roadmapAccepted") is True
        _require(entry.get("roadmapAccepted"), accepted, f"{name} gate acceptance does not match evidence")
        summary[name] = {
            "tasks": expected_tasks,
            "methodVersion": payload.get("methodVersion"),
            "roadmapAccepted": accepted,
        }
        if not accepted:
            blockers.extend(f"task_{task}_release_gate_not_accepted" for task in expected_tasks)
    return not blockers, blockers, summary


def _validate_regional_provider_dataset_gate(
    receipt: dict[str, Any], evidence_root: Path,
) -> tuple[bool, list[str], dict[str, Any]]:
    entry = receipt.get("regionalProviderDatasetGate")
    if not isinstance(entry, dict):
        raise GateInputError("regional provider dataset gate entry missing")
    _require(
        entry.get("methodVersion"), EXPECTED_REGIONAL_PROVIDER_DATASET_GATE_METHOD,
        "regional provider dataset gate is not the current expected method",
    )
    payload = _load_evidence(
        entry.get("evidence"), "regional provider dataset gate", evidence_root,
    )
    _require(
        payload.get("methodVersion"), entry.get("methodVersion"),
        "regional provider dataset gate method identity changed",
    )
    _require(
        payload.get("project"), "tolgar-sasmaz/attune-skin-regional-skin-map",
        "regional provider project identity changed",
    )
    provider_version_ready = payload.get("providerVersionReady") is True
    training_authorized = payload.get("trainingAuthorized") is True
    manifest_verified = payload.get("groupLockedManifestVerified") is True
    _require(
        entry.get("providerVersionReady"), provider_version_ready,
        "regional provider version readiness does not match evidence",
    )
    _require(
        entry.get("trainingAuthorized"), training_authorized,
        "regional provider training authorization does not match evidence",
    )
    ready = provider_version_ready and training_authorized and manifest_verified
    blockers: list[str] = []
    if not provider_version_ready:
        blockers.append("regional_provider_version_not_ready")
    if not training_authorized:
        blockers.append("regional_provider_training_not_authorized")
    if not manifest_verified:
        blockers.append("regional_group_locked_manifest_not_verified")
    return ready, blockers, {
        "methodVersion": payload.get("methodVersion"),
        "project": payload.get("project"),
        "groupLockedManifestVerified": manifest_verified,
        "providerVersionReady": provider_version_ready,
        "trainingAuthorized": training_authorized,
    }


def _validate_repository_ci(identity: Any, evidence_root: Path) -> dict[str, Any]:
    payload = _load_evidence(identity, "repository CI", evidence_root)
    _require(payload.get("schemaVersion"), EXPECTED_REPOSITORY_CI_SCHEMA, "repository CI schema changed")
    _require(payload.get("branch"), EXPECTED_BRANCH, "repository CI branch identity changed")
    actions = payload.get("githubActions", {})
    repository_run_id = _require_positive_int(
        actions.get("runId"), "repository CI run identity missing",
    )
    _require(
        actions.get("url"),
        f"https://github.com/sasmazt90/attune-more/actions/runs/{repository_run_id}",
        "repository CI run URL identity changed",
    )
    _require(
        actions.get("workflowId"), EXPECTED_REPOSITORY_CI_WORKFLOW_ID,
        "repository CI workflow identity changed",
    )
    _require(
        actions.get("workflowPath"), EXPECTED_REPOSITORY_CI_WORKFLOW_PATH,
        "repository CI workflow path changed",
    )
    _require(actions.get("branch"), EXPECTED_BRANCH, "repository CI workflow branch identity changed")
    frontend_job_id = _require_positive_int(
        actions.get("frontendJobId"), "repository CI frontend job identity missing",
    )
    backend_job_id = _require_positive_int(
        actions.get("backendJobId"), "repository CI backend job identity missing",
    )
    if frontend_job_id == backend_job_id:
        raise GateInputError("repository CI job identities must be distinct")
    _require(
        payload.get("implementationCommit"), actions.get("headSha"),
        "repository CI implementation commit does not match workflow head",
    )
    _require(actions.get("conclusion"), "success", "repository CI is not green")
    _require(actions.get("frontendProductionBuild"), "success", "frontend production build is not green")
    _require(actions.get("localizationContract"), "success", "localization contract is not green")
    _require(actions.get("completeSkinResearchEvidenceSuite", {}).get("result"), "OK", "skin evidence suite is not green")
    browser = payload.get("browserAcceptance", {})
    _require(browser.get("conclusion"), "success", "browser acceptance CI is not green")
    _require(browser.get("branch"), EXPECTED_BRANCH, "browser acceptance branch identity changed")
    _require(
        browser.get("headSha"), payload.get("implementationCommit"),
        "browser acceptance commit does not match repository CI implementation commit",
    )
    _require(
        browser.get("workflowId"), EXPECTED_BROWSER_WORKFLOW_ID,
        "browser acceptance workflow identity changed",
    )
    _require(
        browser.get("workflowPath"), EXPECTED_BROWSER_WORKFLOW_PATH,
        "browser acceptance workflow path changed",
    )
    browser_job_id = _require_positive_int(
        browser.get("jobId"), "browser acceptance job identity missing",
    )
    artifact_id = _require_positive_int(
        browser.get("artifactId"), "browser acceptance artifact identity missing",
    )
    artifact_digest = browser.get("artifactDigest")
    if not isinstance(artifact_digest, str) or ARTIFACT_SHA256.fullmatch(artifact_digest) is None:
        raise GateInputError("browser acceptance artifact digest invalid")
    artifact_run = browser.get("artifactWorkflowRun", {})
    if not isinstance(artifact_run, dict) or set(artifact_run) != {"runId", "branch", "headSha"}:
        raise GateInputError("browser artifact workflow identity is incomplete")
    _require(artifact_run.get("runId"), browser.get("runId"), "browser artifact workflow run identity changed")
    _require(artifact_run.get("branch"), EXPECTED_BRANCH, "browser artifact branch identity changed")
    _require(
        artifact_run.get("headSha"), payload.get("implementationCommit"),
        "browser artifact commit does not match repository CI implementation commit",
    )
    _require(browser.get("sanitizedEvidenceOnly"), True, "browser acceptance artifact is not sanitized evidence")
    _require(browser.get("realBrowser"), True, "browser acceptance did not use a real browser")
    _require(browser.get("apiHistoryPrivacyPassed"), True, "browser API/history/privacy acceptance is not green")
    _require(browser.get("controlledFixture"), True, "browser acceptance must remain a controlled fixture")
    _require(browser.get("physicalCameraCapture"), False, "browser fixture cannot become physical-camera evidence")
    _require(browser.get("expertGroundTruth"), False, "browser fixture cannot become expert ground truth")
    _require(browser.get("accuracyEvidence"), False, "browser fixture cannot become accuracy evidence")
    return {
        "runId": repository_run_id,
        "workflowId": actions.get("workflowId"),
        "workflowPath": actions.get("workflowPath"),
        "frontendJobId": frontend_job_id,
        "backendJobId": backend_job_id,
        "headSha": actions.get("headSha"),
        "conclusion": "success",
        "browserAcceptanceRunId": browser.get("runId"),
        "browserAcceptanceJobId": browser_job_id,
        "browserAcceptanceHeadSha": browser.get("headSha"),
        "browserAcceptanceWorkflowId": browser.get("workflowId"),
        "browserAcceptanceWorkflowPath": browser.get("workflowPath"),
        "browserAcceptanceArtifactId": artifact_id,
        "browserAcceptanceArtifactDigest": artifact_digest,
        "browserControlledFixture": True,
    }


def _validate_candidate(
    candidate: dict[str, Any], evidence_root: Path,
    all_class_gates_accepted: bool, physical_camera_accepted: bool,
    repository_ci: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any] | None]:
    identity_fields = (
        "releaseId", "repositoryCommit", "productBuildId", "browserRunId",
        "cameraBenchmarkId", "historyPolicyId",
    )
    evidence_fields = (
        "browserApiReplay", "indexedDbHistoryReplay", "physicalCameraAcceptance",
        "independentFinalTests", "unavailableOverlapControls", "privacyLifecycle",
        "workingProductReplay",
    )
    mode = candidate.get("mode")
    if mode == "no-final-acceptance-candidate":
        if any(candidate.get(field) is not None for field in identity_fields):
            raise GateInputError("missing final candidate cannot claim release identities")
        if candidate.get("evidence") not in (None, {}):
            raise GateInputError("missing final candidate cannot claim acceptance evidence")
        blockers = ["identity_bound_end_to_end_candidate_missing"]
        if not all_class_gates_accepted:
            blockers.append("all_class_release_gates_not_accepted")
        if not physical_camera_accepted:
            blockers.append("physical_camera_benchmark_not_accepted")
        return False, blockers, None
    if mode != "accepted-end-to-end-release":
        raise GateInputError("unknown unified release candidate mode")
    for field in identity_fields:
        if not isinstance(candidate.get(field), str) or not candidate[field]:
            raise GateInputError(f"unified candidate {field} missing")
    evidence = candidate.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(evidence_fields):
        raise GateInputError("unified candidate evidence registry is incomplete")

    browser = _load_evidence(evidence["browserApiReplay"], "browser/API replay", evidence_root)
    _require(browser.get("realBrowser"), True, "browser replay must use a real browser")
    _require(browser.get("apiE2EPassed"), True, "browser/API E2E did not pass")
    _require(browser.get("sixRegionalViewsPassed"), True, "six regional views were not replayed")
    history = _load_evidence(evidence["indexedDbHistoryReplay"], "IndexedDB history replay", evidence_root)
    _require(history.get("indexedDbWriteReadPassed"), True, "IndexedDB write/read replay did not pass")
    _require(history.get("methodCompatibleHistoryPassed"), True, "method-compatible history did not pass")
    _require(history.get("crossMethodBridgeAllowed"), False, "history cannot bridge incompatible methods")
    _require(history.get("malformedRecordFallbackAllowed"), False, "malformed history cannot fall back")
    camera = _load_evidence(evidence["physicalCameraAcceptance"], "physical-camera acceptance", evidence_root)
    _require(camera.get("physicalCameraBenchmarkAccepted"), True, "physical-camera benchmark evidence is not accepted")
    _require(camera.get("consentedPhysicalCaptures"), True, "physical-camera captures are not consented")
    _require(camera.get("expertTruthPerActivatedClass"), True, "physical-camera expert truth is incomplete")
    final_tests = _load_evidence(evidence["independentFinalTests"], "independent final tests", evidence_root)
    _require(final_tests.get("perActivatedClassPassed"), True, "independent final tests did not pass per class")
    _require(final_tests.get("thresholdSelectionSplit"), "validation", "thresholds must be selected on validation")
    _require(final_tests.get("finalTestUsedForSelection"), False, "final test cannot select methods or thresholds")
    controls = _load_evidence(evidence["unavailableOverlapControls"], "unavailable/overlap controls", evidence_root)
    _require(controls.get("unknownCountsAsNormal"), False, "unknown cannot count as Normal")
    _require(controls.get("rednessIndependentLayer"), True, "Redness must remain independent")
    _require(controls.get("rednessSensitivityAliasAllowed"), False, "Redness cannot become sensitivity")
    _require(controls.get("dryOilyRednessOverlapPassed"), True, "map overlap controls did not pass")
    _require(controls.get("unsupportedHeadingsUnavailable"), True, "unsupported headings must remain unavailable")
    privacy = _load_evidence(evidence["privacyLifecycle"], "privacy lifecycle", evidence_root)
    _require(privacy.get("consentPassed"), True, "camera consent control did not pass")
    _require(privacy.get("retentionPassed"), True, "camera retention control did not pass")
    _require(privacy.get("deletionPassed"), True, "camera deletion control did not pass")
    replay = _load_evidence(evidence["workingProductReplay"], "working product replay", evidence_root)
    _require(replay.get("endpoint"), "/api/local-health/skin", "working product endpoint changed")
    _require(replay.get("concreteResultsPassed"), True, "working concrete result replay did not pass")
    _require(replay.get("mapCardsHistoryPassed"), True, "map/cards/history replay did not pass")
    _require(replay.get("twelveProductHeadingsPassed"), True, "twelve product headings did not pass")

    browser_bound = {
        "browser/API replay": browser,
        "IndexedDB history replay": history,
        "unavailable/overlap controls": controls,
        "privacy lifecycle": privacy,
        "working product replay": replay,
    }
    for label, payload in browser_bound.items():
        for field in ("repositoryCommit", "productBuildId", "browserRunId", "historyPolicyId"):
            _require(payload.get(field), candidate[field], f"{label} {field} identity mismatch")
    _require(repository_ci.get("headSha"), candidate["repositoryCommit"], "repository CI commit identity mismatch")
    _require(camera.get("cameraBenchmarkId"), candidate["cameraBenchmarkId"], "physical-camera benchmark identity mismatch")
    _require(final_tests.get("releaseId"), candidate["releaseId"], "independent final-test release identity mismatch")
    _require(final_tests.get("repositoryCommit"), candidate["repositoryCommit"], "independent final-test commit identity mismatch")

    blockers = []
    if not all_class_gates_accepted:
        blockers.append("all_class_release_gates_not_accepted")
    if not physical_camera_accepted:
        blockers.append("physical_camera_benchmark_not_accepted")
    identity = {field: candidate[field] for field in identity_fields}
    return not blockers, blockers, identity


def evaluate_release(receipt: dict[str, Any], evidence_root: Path = ROOT) -> dict[str, Any]:
    _require(receipt.get("schemaVersion"), EXPECTED_RECEIPT_SCHEMA, "unified release receipt schema changed")
    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "unified implementation blobs changed")
    _require(receipt.get("inputEvidence"), EXPECTED_INPUT_EVIDENCE, "unified input evidence identities changed")
    for name, identity in EXPECTED_INPUT_EVIDENCE.items():
        _load_evidence(identity, name, evidence_root)
    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("commit"), "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285", "merged baseline changed")
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product output cannot become missing")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint identity changed")
    _require(baseline.get("headings"), EXPECTED_HEADINGS, "product heading inventory changed")
    _require(baseline.get("appearanceHeadings"), 11, "appearance heading count changed")
    _require(baseline.get("separateSkinType"), True, "skin type must remain separate")
    _require(baseline.get("regionalResults"), True, "regional result flow changed")
    _require(baseline.get("overviewMapAndHistory"), True, "overview/map/history flow changed")
    contract = receipt.get("mapAndHistoryContract", {})
    _require(contract.get("dryColour"), "#2563EB", "dry must remain blue")
    _require(contract.get("oilyColour"), "#16A34A", "oily must remain green")
    _require(contract.get("rednessColour"), "#DC2626", "Redness must remain red")
    _require(contract.get("rednessIndependentLayer"), True, "Redness must remain independent")
    _require(contract.get("rednessSensitivityAliasAllowed"), False, "Redness cannot become sensitivity")
    _require(contract.get("normalColour"), None, "evaluated Normal must remain uncoloured")
    _require(contract.get("unknownColour"), "#D1D5DB", "unknown must remain light gray")
    _require(contract.get("unknownCountsAsNormal"), False, "unknown cannot count as Normal")
    _require(contract.get("mixedColoursAllowed"), True, "overlapping layers must remain allowed")
    _require(contract.get("wholeFaceClassReplicationAllowed"), False, "whole-face classes cannot become regional truth")
    _require(contract.get("boxAsPolygonAllowed"), False, "Boxes cannot become polygons")
    _require(contract.get("modelPredictionAsExpertTruthAllowed"), False, "model output cannot become expert truth")
    _require(contract.get("methodIdentityRequiredForHistory"), True, "history cannot bridge incompatible methods")
    smoke = receipt.get("generatedSmoke", {})
    _require(smoke.get("declaredGenerated"), True, "generated smoke identity changed")
    _require(smoke.get("physicalCameraCapture"), False, "generated smoke cannot become physical camera")
    _require(smoke.get("expertGroundTruth"), False, "generated smoke cannot become expert truth")
    _require(smoke.get("accuracyEvidence"), False, "generated smoke cannot become accuracy evidence")
    _require(smoke.get("integrationSmokeAllowed"), True, "generated integration smoke changed")

    repository_ci = _validate_repository_ci(receipt.get("repositoryCI"), evidence_root)
    regional_provider_ready, regional_provider_blockers, regional_provider_summary = (
        _validate_regional_provider_dataset_gate(receipt, evidence_root)
    )
    all_class_gates, class_blockers, gate_summary = _validate_gate_registry(receipt, evidence_root)
    camera_entry = receipt.get("physicalCameraGate", {})
    _require(
        camera_entry.get("methodVersion"), EXPECTED_PHYSICAL_CAMERA_GATE_METHOD,
        "physical-camera release gate is not the current expected method",
    )
    camera_payload = _load_evidence(camera_entry.get("evidence"), "physical-camera release gate", evidence_root)
    _require(camera_payload.get("methodVersion"), camera_entry.get("methodVersion"), "physical-camera gate method identity changed")
    camera_accepted = camera_payload.get("roadmapCameraAcceptanceAllowed") is True
    _require(camera_entry.get("accepted"), camera_accepted, "physical-camera gate acceptance does not match evidence")
    candidate_accepted, candidate_blockers, identity = _validate_candidate(
        receipt.get("acceptanceCandidate", {}), evidence_root, all_class_gates, camera_accepted, repository_ci
    )
    blockers = (
        regional_provider_blockers
        + class_blockers
        + ([] if camera_accepted else ["physical_camera_benchmark_not_accepted"])
        + candidate_blockers
    )
    blockers = list(dict.fromkeys(blockers))
    accepted = regional_provider_ready and candidate_accepted and not blockers
    return {
        "schemaVersion": 16,
        "methodVersion": "unified-skin-result-release-gate-v16",
        "workingBaselinePreserved": True,
        "currentIntegratedPresentationAllowed": True,
        "generatedReplayIntegrationSmokeAllowed": True,
        "generatedReplayAccuracyEvidenceAllowed": False,
        "repositoryCI": repository_ci,
        "regionalProviderDatasetGate": regional_provider_summary,
        "regionalProviderDatasetReady": regional_provider_ready,
        "classReleaseGates": gate_summary,
        "allClassReleaseGatesAccepted": all_class_gates,
        "physicalCameraBenchmarkAccepted": camera_accepted,
        "acceptedEndToEndCandidatePresent": identity is not None,
        "acceptedEndToEndCandidateIdentity": identity,
        "finalRoadmapAcceptanceAllowed": accepted,
        "roadmapAccepted": accepted,
        "blockers": blockers,
        "decision": "ready" if accepted else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(json.loads(args.receipt.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


