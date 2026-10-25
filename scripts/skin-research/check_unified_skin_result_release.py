#!/usr/bin/env python3
"""Fail-closed task-13 gate for unified results, maps and history.

The merged product already produces concrete skin results.  This gate keeps
that functioning baseline separate from final roadmap acceptance: generated
replays are integration smoke only, unknown is never normal, Redness remains
an independent layer, history never bridges incompatible methods, and a real
browser plus physical-camera chain is required before completion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_CODE_BLOBS = {
    "apps/vehicle-app/src/utils/regionalSkinMap.ts": "258ab2d845b3743ede309938cd14da8831a01046",
    "apps/vehicle-app/src/utils/skinOverview.ts": "4d31010f82bfd5c42a49b46c20880630d57079dd",
    "apps/vehicle-app/src/utils/skinPhotoHistory.ts": "d143cb121cc39149b1ee4d26d4e4bacd9ba0f288",
    "apps/vehicle-app/src/components/skin/SkinFacePanel.tsx": "c86d90f41ad1b9c54025e111cd636271c533618a",
    "apps/vehicle-app/src/components/skin/SkinTrendModal.tsx": "4709e9214cee28bbd2de5bfa9d20261b63f489c3",
    "shared/localization/messages.json": "d17c71b2895aa771f1efe5e2c80cd7b784cc3ff2",
}
EXPECTED_EVIDENCE_BLOBS = {
    "mergedCapability": "001a343c4ae2537a8b6b9e8ccc2621586ddf014e",
    "mergedRecheck": "bbbe61b13145284d675af7e3e66d25ce439a7ba4",
    "unifiedMapCorrection": "a1f26fa1b754bac84978936ef1a47eba62d5b898",
    "generatedSmoke": "5b44b0b8c03096c8dab3afa01ae2f5235d65193c",
    "presentationLocalization": "adaefa02522398ed32eda6f5021075dfd7251cb0",
    "presentationCi": "3fbf7398944937a361322b51e91062d0a92d7999",
}
EXPECTED_BASELINE_CRITERIA = ["tone", "oil", "redness", "acne", "sag", "dry", "lines", "dark", "bags"]


class GateInputError(ValueError):
    """Raised when immutable implementation or semantic evidence changes."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "unified implementation blobs changed")
    _require(receipt.get("evidenceBlobs"), EXPECTED_EVIDENCE_BLOBS, "unified evidence blobs changed")

    baseline = receipt.get("workingBaseline", {})
    _require(baseline.get("productAlreadyProducesConcreteResults"), True, "working product output cannot become missing")
    _require(baseline.get("endpoint"), "/api/local-health/skin", "skin endpoint identity changed")
    _require(baseline.get("appearanceCriteria"), EXPECTED_BASELINE_CRITERIA, "baseline criterion inventory changed")
    _require(baseline.get("separateSkinType"), True, "skin type must remain separate")
    _require(baseline.get("regionalResults"), True, "regional result flow changed")
    _require(baseline.get("overviewAndHistory"), True, "overview/history flow changed")

    contract = receipt.get("mapAndHistoryContract", {})
    _require(contract.get("dryColour"), "#2563EB", "dry must remain blue")
    _require(contract.get("oilyColour"), "#16A34A", "oily must remain green")
    _require(contract.get("rednessColour"), "#DC2626", "redness must remain red")
    _require(contract.get("rednessIndependentLayer"), True, "redness must remain independent")
    _require(contract.get("rednessSensitivityAliasAllowed"), False, "redness cannot become sensitivity")
    _require(contract.get("normalColour"), None, "evaluated normal must remain uncoloured")
    _require(contract.get("unknownColour"), "#D1D5DB", "unknown must remain light gray")
    _require(contract.get("unknownCountsAsNormal"), False, "unknown cannot count as normal")
    _require(contract.get("methodIdentityRequiredForHistory"), True, "history cannot bridge incompatible methods")
    _require(contract.get("malformedSelectedRecordFallsBack"), False, "malformed selected records cannot fall back")
    _require(contract.get("wholeFaceClassReplicationAllowed"), False, "whole-face classes cannot become regional truth")

    smoke = receipt.get("generatedSmoke", {})
    _require(smoke.get("declaredGenerated"), True, "generated smoke identity changed")
    _require(smoke.get("realCameraCapture"), False, "generated input cannot become a real camera capture")
    _require(smoke.get("expertGroundTruth"), False, "generated input cannot become expert truth")
    _require(smoke.get("accuracyEvidence"), False, "generated smoke cannot become accuracy evidence")

    candidate = receipt.get("acceptanceCandidate", {})
    requirements = {
        "repositoryCiPassed": "repository_ci_missing",
        "realBrowserApiE2EPassed": "real_browser_api_e2e_missing",
        "indexedDbWriteReadReplayPassed": "indexeddb_write_read_replay_missing",
        "physicalCameraTripletPassed": "physical_camera_triplet_missing",
        "expertTruthPerActivatedMethodPassed": "expert_truth_per_activated_method_missing",
        "independentFinalTestPerActivatedClassPassed": "independent_final_test_per_activated_class_missing",
        "classSpecificReleaseGatesPassed": "class_specific_release_gates_missing",
        "unavailableAndOverlapControlsPassed": "unavailable_overlap_controls_missing",
        "methodCompatibleHistoryPassed": "method_compatible_history_acceptance_missing",
    }
    blockers = [reason for field, reason in requirements.items() if candidate.get(field) is not True]
    activation = not blockers
    return {
        "schemaVersion": 1,
        "methodVersion": "unified-skin-result-release-gate-v1",
        "workingBaselinePreserved": True,
        "generatedReplayIntegrationSmokeAllowed": True,
        "generatedReplayAccuracyEvidenceAllowed": False,
        "unknownAsNormalAllowed": False,
        "rednessSensitivityAliasAllowed": False,
        "currentIntegratedPresentationAllowed": True,
        "finalRoadmapAcceptanceAllowed": activation,
        "roadmapAccepted": activation,
        "blockers": blockers,
        "decision": "ready" if activation else "blocked",
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
