#!/usr/bin/env python3
"""Fail-closed release gate for broad tone unevenness.

The current product already exposes a regional CIELAB chromatic-variation
appearance proxy.  It may remain visible under that narrow contract, but it
is not clinical severity and must never populate the localized Post acne or
Pigmentation headings.  This gate separates continued proxy presentation
from roadmap acceptance and from future localized co-reporting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SEPARATION_VERSION = "tone-localized-pigmentation-separation-v1"
TONE_MEANING = "broad-regional-chromatic-variation"
EXPECTED_CODE_BLOBS = {
    "services/core-api/skin_product_contract.py": "f152726978bee2eea36b0563d9ac36cbcf330c7b",
    "services/core-api/skin_general.py": "ef5869c6801d3845ec8424e17474b3a3e0fd665a",
    "services/core-api/appearance_analysis.py": "1ebb762a76865f4a33f7f0d5aadab36a5115d46e",
    "apps/vehicle-app/src/utils/skinIndicators.ts": "eeb3599bec0361bcca7298fc277fa53a32fc06d5",
    "apps/vehicle-app/src/utils/skinOverview.ts": "4d31010f82bfd5c42a49b46c20880630d57079dd",
}
EXPECTED_EVIDENCE_BLOB = "2415926f1706a8a8991a5180fe338a01bd1391d8"


class GateInputError(ValueError):
    """Raised when a frozen product or semantic boundary is contradicted."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    _require(receipt.get("contractEvidenceBlob"), EXPECTED_EVIDENCE_BLOB, "contract evidence identity changed")
    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "semantic implementation blobs changed")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("separationVersion"), SEPARATION_VERSION, "separation version changed")
    _require(contract.get("toneMeaning"), TONE_MEANING, "tone meaning changed")
    _require(contract.get("clinicalSeverity"), False, "tone cannot claim clinical severity")
    _require(contract.get("localizedPigmentationDetector"), False, "tone cannot become a localized pigmentation detector")
    _require(contract.get("toneCanSupplyPostAcne"), False, "tone cannot populate Post acne")
    _require(contract.get("toneCanSupplyPigmentation"), False, "tone cannot populate Pigmentation")
    _require(contract.get("missingLocalizedResultMeansZero"), False, "an unavailable localized result cannot become zero")
    _require(contract.get("localizedHeadingsSeparate"), True, "localized headings must remain separate")
    _require(contract.get("currentProductIntegrated"), True, "working product integration evidence changed")

    candidate = receipt.get("candidate", {})
    _require(candidate.get("mode"), "regional-cielab-appearance-proxy", "unknown tone candidate mode")
    if candidate.get("clinicalClaimsDisabled") is not True:
        raise GateInputError("clinical tone claims must remain disabled")
    if candidate.get("localizedHeadingsDerivedFromTone") is not False:
        raise GateInputError("localized headings cannot be derived from tone")

    requirements = {
        "cameraCalibrationProtocolComplete": "camera_calibration_protocol_missing",
        "illuminationShadowHairRobustnessPassed": "illumination_shadow_hair_robustness_missing",
        "skinToneSubgroupCalibrationPassed": "skin_tone_subgroup_calibration_missing",
        "samePersonRepeatabilityPassed": "same_person_repeatability_missing",
        "untouchedCameraHoldoutPassed": "untouched_camera_holdout_missing",
        "workingProductIntegrationPassed": "working_product_integration_replay_missing",
    }
    blockers = [reason for field, reason in requirements.items() if candidate.get(field) is not True]

    local_support = candidate.get("acceptedLocalizedPigmentationSupportAvailable") is True
    local_excluded = candidate.get("localizedSupportExcludedFromToneSampling") is True
    co_reporting_passed = candidate.get("coReportingIndependentCameraPassed") is True
    if local_support and not local_excluded:
        blockers.append("accepted_localized_support_not_excluded_from_tone")
    if local_support and not co_reporting_passed:
        blockers.append("localized_tone_coreporting_camera_acceptance_missing")

    roadmap_accepted = not blockers
    localized_co_reporting_allowed = local_support and local_excluded and co_reporting_passed
    return {
        "schemaVersion": 1,
        "methodVersion": "tone-unevenness-release-gate-v1",
        "currentProxyPresentationAllowed": True,
        "currentProxyClaim": "broad regional chromatic-variation appearance only",
        "clinicalSeverityClaimAllowed": False,
        "toneCanSupplyPostAcne": False,
        "toneCanSupplyPigmentation": False,
        "localizedCoReportingAllowed": localized_co_reporting_allowed,
        "localizedSupportExcluded": local_excluded if local_support else False,
        "productActivationAllowed": roadmap_accepted,
        "roadmapAccepted": roadmap_accepted,
        "blockers": blockers,
        "decision": "ready" if roadmap_accepted else "blocked",
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
