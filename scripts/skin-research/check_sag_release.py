#!/usr/bin/env python3
"""Fail-closed release gate for the sag appearance roadmap target.

The current implementation is a visible contour/fold appearance proxy.  It
may remain available under that narrow semantic contract, but it is not a
localized learned sag model, elasticity measurement, clinical severity, or a
cross-person change measure.  This gate prevents those identities from being
silently exchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOURCE_ARCHIVE_SHA256 = "8f2bebd6b97bdd3acd06a42798babbd377b7937db362a734586ff5fb3d0ea4a1"
SEMANTICS = "visible-lower-face-contour-fold-appearance-v1"
COMPARISON_MODE = "same-person-compatible-capture-only"
WHOLE_FACE_BLOCK = "WHOLE_FACE_ORDINAL_CANNOT_REPLACE_LOCAL_SAG"
EXPECTED_CODE_BLOBS = {
    "services/core-api/skin_product_contract.py": "f152726978bee2eea36b0563d9ac36cbcf330c7b",
    "services/core-api/instant_appearance.py": "01526d099dc0614938fc8f7d5d68507c4c7e06ef",
    "services/core-api/skin_general.py": "ef5869c6801d3845ec8424e17474b3a3e0fd665a",
    "services/core-api/contour_appearance.py": "748bef67cc59857b2e12e5c48211db973bf29d22",
    "apps/vehicle-app/src/utils/appearanceMeasurements.ts": "45b056e1aff9ce2fb7791995134ad7b5f4a9a57e",
}


class GateInputError(ValueError):
    """Raised when immutable source or semantic evidence is contradicted."""


def _require(value: Any, expected: Any, message: str) -> None:
    if value != expected:
        raise GateInputError(message)


def evaluate_release(receipt: dict[str, Any]) -> dict[str, Any]:
    source = receipt.get("sourceAudit", {})
    _require(source.get("archiveSHA256"), SOURCE_ARCHIVE_SHA256, "source archive identity changed")
    _require(source.get("containsSagTarget"), False, "18-criterion source must not be relabelled as sag")
    _require(source.get("nearestButNonEquivalentTarget"), "elasticity", "elasticity boundary changed")
    _require(source.get("personIndependent"), False, "unreviewed source cannot become person-independent")
    _require(source.get("expertProtocolVerified"), False, "unreviewed source cannot gain expert status")

    contract = receipt.get("semanticContract", {})
    _require(contract.get("appearanceSemantics"), SEMANTICS, "appearance semantics changed")
    _require(contract.get("comparisonMode"), COMPARISON_MODE, "comparison mode changed")
    _require(contract.get("clinicalSeverity"), False, "clinical severity claim is forbidden")
    _require(contract.get("elasticity"), False, "elasticity claim is forbidden")
    _require(contract.get("wholeFaceOrdinalReplacementAllowed"), False, "whole-face ordinal replacement is forbidden")
    _require(contract.get("wholeFaceBlockReason"), WHOLE_FACE_BLOCK, "whole-face block reason changed")

    _require(receipt.get("codeBlobs"), EXPECTED_CODE_BLOBS, "semantic implementation blobs changed")

    candidate = receipt.get("candidate", {})
    mode = candidate.get("mode")
    if mode == "whole-face-ordinal":
        raise GateInputError("whole-face ordinal sag is not a localized appearance target")
    if mode not in {"visible-contour-fold-proxy", "localized-sag-appearance-model"}:
        raise GateInputError("unknown sag candidate mode")
    if candidate.get("clinicalClaimsDisabled") is not True or candidate.get("elasticityClaimsDisabled") is not True:
        raise GateInputError("forbidden clinical or elasticity claim enabled")

    requirements = {
        "localizedExpertTruthComplete": "localized_expert_truth_missing",
        "sourceGroupSplitIndependent": "source_group_split_independence_missing",
        "poseExpressionProtocolComplete": "pose_expression_protocol_missing",
        "samePersonCaptureProtocolComplete": "same_person_capture_protocol_missing",
        "validationPassed": "validation_acceptance_missing",
        "untouchedTestPassed": "untouched_test_acceptance_missing",
        "cameraHoldoutPassed": "independent_camera_acceptance_missing",
        "productIntegrationPassed": "working_product_integration_acceptance_missing",
    }
    blockers = [message for field, message in requirements.items() if candidate.get(field) is not True]
    if mode != "localized-sag-appearance-model":
        blockers.insert(0, "localized_learned_model_missing")

    activation = not blockers
    proxy_allowed = mode == "visible-contour-fold-proxy" and contract.get("productSemanticsIntegrated") is True
    return {
        "schemaVersion": 1,
        "methodVersion": "sag-appearance-release-gate-v1",
        "currentProxyPresentationAllowed": proxy_allowed,
        "currentProxyClaim": "visible lower-face contour/fold appearance only" if proxy_allowed else None,
        "crossPersonComparisonAllowed": False,
        "clinicalSeverityClaimAllowed": False,
        "elasticityClaimAllowed": False,
        "researchTrainingAuthorized": bool(candidate.get("localizedExpertTruthComplete") and candidate.get("sourceGroupSplitIndependent")),
        "testEvaluationAuthorized": bool(candidate.get("validationPassed") and candidate.get("untouchedTestReserved")),
        "productActivationAllowed": activation,
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
