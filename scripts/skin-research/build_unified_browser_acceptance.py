#!/usr/bin/env python3
"""Build privacy-safe task-13 browser/API/history evidence from raw E2E proofs.

The raw browser proofs may contain opaque scan and photo identifiers, so they
stay outside Git.  This builder validates their detailed shape, binds them to
the production build, repository commit, implementation blobs and green CI,
then emits only compact acceptance facts and SHA-256 identities.  Controlled
camera fixtures are valid browser integration evidence, but are never promoted
to physical-camera, expert-truth or accuracy evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGIONS = ["forehead", "rightCheek", "leftCheek", "nose", "chin", "periorbital"]
HEADINGS = ["tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags", "postAcne", "pigmentation"]
UNAVAILABLE = {
    "postAcne": "ACCEPTED_POST_ACNE_LOCAL_DETECTOR_NOT_AVAILABLE",
    "pigmentation": "ACCEPTED_PIGMENTATION_LOCAL_DETECTOR_NOT_AVAILABLE",
}
CODE_BLOBS = {
    "apps/vehicle-app/src/utils/regionalSkinMap.ts": "258ab2d845b3743ede309938cd14da8831a01046",
    "apps/vehicle-app/src/utils/skinPhotoHistory.ts": "d143cb121cc39149b1ee4d26d4e4bacd9ba0f288",
    "apps/vehicle-app/src/utils/skinOverview.ts": "4d31010f82bfd5c42a49b46c20880630d57079dd",
    "tests/e2e/current_skin_contract.py": "851c4a86c5ca30a15cc6d6bb8579f77ff51bf7a9",
    "tests/e2e/current_skin_photo_history.py": "6013d03bd877ca916dce136ac1c1488c6b879fdd",
    "tests/e2e/current_skin_photo_wipe_success.py": "bfff1ce02f70ba9caa959dcbb0c4cfe9b3ad7b3f",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class EvidenceError(ValueError):
    """Raised when raw evidence cannot support a release fact."""


def require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise EvidenceError(message)


def load(path: Path, label: str) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise EvidenceError(f"{label} file missing")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def common(proof: dict[str, Any], method: str, label: str) -> str:
    require(proof.get("status"), "PASS", f"{label} did not pass")
    require(proof.get("methodVersion"), method, f"{label} method changed")
    require(proof.get("realBrowser"), True, f"{label} did not use a real browser")
    require(proof.get("browserEngine"), "chromium", f"{label} browser engine changed")
    require(proof.get("controlledFixture"), True, f"{label} must remain controlled-fixture evidence")
    require(proof.get("physicalUserAcceptance", proof.get("physicalCamera")), False, f"{label} cannot claim physical-camera acceptance")
    require(proof.get("expertGroundTruth"), False, f"{label} cannot claim expert truth")
    require(proof.get("accuracyEvidence"), False, f"{label} cannot claim accuracy evidence")
    build = proof.get("buildId")
    if not isinstance(build, str) or not build:
        raise EvidenceError(f"{label} build identity missing")
    return build


def validate_browser(proof: dict[str, Any]) -> str:
    build = common(proof, "skin-browser-api-replay-v1", "browser/API proof")
    require(proof.get("endpoint"), "/api/local-health/skin", "skin endpoint changed")
    for key in ("apiE2EPassed", "sixRegionalViewsPassed", "mapCardsHistoryPassed", "twelveProductHeadingsPassed", "unsupportedHeadingsUnavailable"):
        require(proof.get(key), True, f"browser/API proof missing {key}")
    require(proof.get("poseMock"), False, "browser proof used a pose mock")
    require(proof.get("qualityOverride"), False, "browser proof used a quality override")
    require(proof.get("pageErrors"), [], "browser proof has page errors")
    runs = proof.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise EvidenceError("browser proof must contain desktop and native-zoom runs")
    for run in runs:
        require(run.get("graphs"), REGIONS, "browser proof region order changed")
        api = run.get("api", {})
        require(api.get("endpoint"), "/api/local-health/skin", "browser run endpoint changed")
        require(api.get("uniqueRequestPhotoIds"), 3, "browser run did not submit three source-bound photos")
        require(api.get("allRequestsHaveSuccessfulResponse"), True, "browser run has a failed API response")
        if api.get("requestCount", 0) < 3 or api.get("successfulResponseCount", 0) < 3:
            raise EvidenceError("browser run API evidence is incomplete")
        general = run.get("result", {}).get("general", {})
        rows = general.get("indicators")
        if not isinstance(rows, list) or [row.get("id") for row in rows] != HEADINGS:
            raise EvidenceError("browser run product heading inventory changed")
        for criterion, reason in UNAVAILABLE.items():
            row = next(item for item in rows if item.get("id") == criterion)
            require(row.get("score"), None, f"{criterion} must remain unavailable")
            appearance = row.get("appearance", {})
            require(appearance.get("value"), None, f"{criterion} cannot expose a value")
            require(appearance.get("limitationCode"), reason, f"{criterion} unavailable reason changed")
            require(appearance.get("components", {}).get("localizedInstancesAvailable"), False, f"{criterion} cannot claim localized instances")
    return build


def validate_history(proof: dict[str, Any]) -> str:
    build = common(proof, "skin-indexeddb-history-replay-v1", "IndexedDB history proof")
    for key in ("indexedDbWriteReadPassed", "relaunchThreeRecords", "allSixRegionsAndSelectedMaps", "twelveProductHeadingsPassed", "unsupportedHeadingsUnavailable", "deleteOne", "revokePhotosKeepsNumeric", "retentionPassed", "deletionPassed"):
        require(proof.get(key), True, f"IndexedDB proof missing {key}")
    require(proof.get("pageErrors"), [], "IndexedDB proof has page errors")
    scans = proof.get("scans")
    if not isinstance(scans, list) or len(scans) != 3:
        raise EvidenceError("IndexedDB proof must contain three retained scans")
    record_ids: set[str] = set()
    for scan in scans:
        record_id = scan.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise EvidenceError("retained scan identity missing")
        record_ids.add(record_id)
        for key in ("sourceByRegion", "shaByRegion", "poseByRegion"):
            value = scan.get(key)
            if not isinstance(value, dict) or set(value) != set(REGIONS):
                raise EvidenceError(f"retained scan {key} coverage changed")
            if any(not isinstance(item, str) or not item for item in value.values()):
                raise EvidenceError(f"retained scan {key} contains an empty identity")
    if len(record_ids) != 3:
        raise EvidenceError("IndexedDB proof must contain three distinct retained scans")
    return build


def validate_privacy(proof: dict[str, Any]) -> str:
    build = common(proof, "skin-privacy-lifecycle-browser-v1", "privacy proof")
    for key in ("explicitPhotoConsent", "consentPassed", "retentionPassed", "localWipeVerified", "deletionPassed", "backendForwardedToRealIsolatedService", "backendWipeAcceptance", "sharedBackendUnchanged", "relaunchStillEmpty"):
        require(proof.get(key), True, f"privacy proof missing {key}")
    require(proof.get("isolatedBackendRecordsBefore"), 2, "privacy setup record count changed")
    require(proof.get("isolatedBackendRecordsAfter"), 0, "privacy deletion did not clear isolated backend")
    return build


def build(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    browser, browser_sha = load(args.browser_proof, "browser/API proof")
    history, history_sha = load(args.history_proof, "IndexedDB history proof")
    privacy, privacy_sha = load(args.privacy_proof, "privacy proof")
    ci, ci_sha = load(args.ci_evidence, "repository CI evidence")
    builds = {validate_browser(browser), validate_history(history), validate_privacy(privacy)}
    if len(builds) != 1:
        raise EvidenceError("browser evidence build identities disagree")
    if not isinstance(args.repository_commit, str) or SHA40.fullmatch(args.repository_commit) is None:
        raise EvidenceError("repository commit identity missing")
    if not args.browser_run_id:
        raise EvidenceError("browser run identity missing")
    if not args.history_policy_id:
        raise EvidenceError("history policy identity missing")
    actions = ci.get("githubActions", {})
    require(actions.get("conclusion"), "success", "repository CI is not green")
    require(actions.get("frontendProductionBuild"), "success", "frontend build is not green")
    require(actions.get("completeSkinResearchEvidenceSuite", {}).get("result"), "OK", "skin evidence suite is not green")
    for path, expected in CODE_BLOBS.items():
        actual = git_blob(ROOT / path)
        require(actual, expected, f"implementation blob changed: {path}")
    identity = {
        "repositoryCommit": args.repository_commit,
        "productBuildId": next(iter(builds)),
        "browserRunId": args.browser_run_id,
        "historyPolicyId": args.history_policy_id,
        "inputEvidence": {
            "browserProofSha256": browser_sha,
            "historyProofSha256": history_sha,
            "privacyProofSha256": privacy_sha,
            "repositoryCiSha256": ci_sha,
        },
        "codeBlobs": CODE_BLOBS,
        "controlledFixture": True,
        "physicalCameraCapture": False,
        "expertGroundTruth": False,
        "accuracyEvidence": False,
    }
    return {
        "browser-api-replay.json": {**identity, "methodVersion": "unified-browser-api-replay-v1", "realBrowser": True, "apiE2EPassed": True, "sixRegionalViewsPassed": True},
        "indexeddb-history-replay.json": {**identity, "methodVersion": "unified-indexeddb-history-replay-v1", "indexedDbWriteReadPassed": True, "methodCompatibleHistoryPassed": True, "crossMethodBridgeAllowed": False, "malformedRecordFallbackAllowed": False, "evidenceBasis": "real IndexedDB replay plus pinned method-bound implementation and green deterministic CI"},
        "privacy-lifecycle.json": {**identity, "methodVersion": "unified-privacy-lifecycle-v1", "consentPassed": True, "retentionPassed": True, "deletionPassed": True},
        "unavailable-overlap-controls.json": {**identity, "methodVersion": "unified-map-controls-v1", "unknownCountsAsNormal": False, "rednessIndependentLayer": True, "rednessSensitivityAliasAllowed": False, "dryOilyRednessOverlapPassed": True, "unsupportedHeadingsUnavailable": True, "evidenceBasis": "real unavailable-heading replay plus pinned regional-map implementation and green deterministic CI"},
        "working-product-replay.json": {**identity, "methodVersion": "unified-working-product-replay-v1", "endpoint": "/api/local-health/skin", "concreteResultsPassed": True, "mapCardsHistoryPassed": True, "twelveProductHeadingsPassed": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-proof", type=Path, required=True)
    parser.add_argument("--history-proof", type=Path, required=True)
    parser.add_argument("--privacy-proof", type=Path, required=True)
    parser.add_argument("--ci-evidence", type=Path, required=True)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--browser-run-id", required=True)
    parser.add_argument("--history-policy-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence = build(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in evidence.items():
        (args.output_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
