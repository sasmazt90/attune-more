#!/usr/bin/env python3
"""Build the expert-semantics artifact for selected skin sources.

Mapping tables route research review; they do not define expert truth.  The
committed current-facts receipt therefore only produces a blocked preflight.
The exact ``skin-source-expert-semantics-v1`` artifact can be emitted only
from an opaque private manifest that binds a qualified-human protocol for
every target and preserves the accepted map, unknown and overlap contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "skin-source-expert-semantics-input-v1"
CURRENT_FACTS_METHOD = "skin-source-expert-semantics-current-facts-v1"
PREFLIGHT_METHOD = "skin-source-expert-semantics-preflight-v1"
ARTIFACT_METHOD = "skin-source-expert-semantics-v1"
TARGETS = ("acne", "oil", "dry", "redness", "tone", "lines", "dark", "bags", "type", "sag")
SELECTED_SOURCES_BLOB = "cfd24d16f86f3437dd3b1d925053cc7ebe543399"
EXPANDED_SOURCES_BLOB = "8771f1aed674f1c7f554dcb6fa539b20c7696f38"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "image", "images",
    "annotation", "annotations", "polygon", "polygons", "bbox", "mask",
    "reviewer", "reviewerId", "reviewerName", "definition", "instructions",
    "prediction", "predictions", "modelProposal", "modelProposals",
}
SAFE_POLICY = {
    "mappingUsedAsExpertTruth": False,
    "boxesUsedAsPixelTruth": False,
    "rectanglePolygonsUsedAsPixelTruth": False,
    "missingLabelMeansNegativeOrNormal": False,
    "toneUsedAsLocalizedPigmentation": False,
    "pulUsedAsBroadRegionalDryness": False,
    "wholeFaceClassReplicatedIntoRegions": False,
    "modelPredictionUsedAsExpertTruth": False,
    "normalRequiresEvaluatedNormal": True,
    "rednessIndependentFromSensitivity": True,
}
MAP_CONTRACT = {
    "dry": "blue",
    "oily": "green",
    "redness": "red-contour-or-hatching-independent",
    "normal": "uncoloured-only-if-evaluated-normal",
    "unknown": "light-grey-never-normal",
    "mixedLayersAllowed": True,
    "combinationRule": "oily-t-zone-plus-supported-normal-or-dry-outside-t-zone",
    "combinationRequiresCoverageAndRuleValidation": True,
}


class SemanticsInputError(ValueError):
    """Raised when expert semantics or map safety changes."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise SemanticsInputError(f"{location} contains raw/private semantics or model payload")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def _validate_map_contract(value: Any) -> None:
    if value != MAP_CONTRACT:
        raise SemanticsInputError("accepted map contract changed")


def summarize_current_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Replay committed routing facts while keeping expert release blocked."""
    if not isinstance(facts, dict):
        raise SemanticsInputError("current facts must be a JSON object")
    if facts.get("schemaVersion") != 1 or facts.get("methodVersion") != CURRENT_FACTS_METHOD:
        raise SemanticsInputError("current facts identity changed")
    if facts.get("mappingGitBlobs") != {
        "selectedSources": SELECTED_SOURCES_BLOB,
        "expandedSources": EXPANDED_SOURCES_BLOB,
    }:
        raise SemanticsInputError("mapping source blob identity changed")
    if facts.get("targets") != list(TARGETS):
        raise SemanticsInputError("mapping target inventory changed")
    required = {
        "mappingLabelsAreResearchRoutingHints": True,
        "sourceReviewExpertReviewed": False,
        "modelPredictionsUsedForSelection": False,
        "unknownAreasMasked": True,
        "boxIsNotMask": True,
        "perClassExpertSemanticsLocked": False,
    }
    for field, expected in required.items():
        if facts.get(field) != expected:
            raise SemanticsInputError(f"current semantic fact changed: {field}")
    _validate_map_contract(facts.get("mapContract"))
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": None,
        "sourceRegistryRef": None,
        "targets": list(TARGETS),
        "reviewedTargetCount": 0,
        "perClassExpertSemanticsLocked": False,
        **SAFE_POLICY,
        "mapContract": MAP_CONTRACT,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": [
            "expert_semantic_protocols_missing",
            "per_class_expert_semantics_not_locked",
            "source_label_mappings_are_routing_hints_only",
        ],
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque private expert protocol registry."""
    if not isinstance(manifest, dict):
        raise SemanticsInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise SemanticsInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise SemanticsInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    if not _is_opaque(registry_ref):
        blockers.append("source_registry_ref_missing_or_invalid")
    if manifest.get("targetsExpected") != list(TARGETS):
        raise SemanticsInputError("expected expert target inventory changed")
    policy = manifest.get("truthPolicy")
    if not isinstance(policy, dict):
        blockers.append("truth_policy_missing")
    elif set(policy) != set(SAFE_POLICY):
        raise SemanticsInputError("truth policy fields changed")
    else:
        for field, expected in SAFE_POLICY.items():
            if policy.get(field) != expected:
                raise SemanticsInputError(f"unsafe expert truth policy: {field}")
    _validate_map_contract(manifest.get("mapContract"))

    review = manifest.get("review")
    if not isinstance(review, dict):
        blockers.append("expert_review_summary_missing")
    else:
        allowed_review = {
            "allTargetsReviewed", "expertAuthorizationConfirmed",
            "semanticDisagreementsResolved", "protocolsLockedBeforeDatasetRelease",
        }
        if set(review) - allowed_review:
            raise SemanticsInputError("expert review summary contains unsupported fields")
        for field in sorted(allowed_review):
            if review.get(field) is not True:
                blockers.append(f"review_{field}_incomplete")

    entries = manifest.get("targetSemantics", [])
    if not isinstance(entries, list):
        raise SemanticsInputError("targetSemantics must be a list")
    if not entries:
        blockers.append("target_semantics_registry_empty")
    allowed_entry = {
        "target", "expertProtocolSHA256", "expertDefinitionLocked",
        "positiveExtentDefined", "evaluatedNegativeDefined",
        "unknownUnassessableDefined", "overlapPolicyDefined",
        "qualifiedHumanReviewRequired", "modelProposalsHiddenDuringReview",
        "sourceLabelsAcceptedAsExpertTruth",
    }
    true_fields = (
        "expertDefinitionLocked", "positiveExtentDefined", "evaluatedNegativeDefined",
        "unknownUnassessableDefined", "overlapPolicyDefined",
        "qualifiedHumanReviewRequired", "modelProposalsHiddenDuringReview",
    )
    targets: list[str] = []
    hashes: list[str] = []
    canonical: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SemanticsInputError(f"target semantic {index} must be an object")
        if set(entry) - allowed_entry:
            raise SemanticsInputError(f"target semantic {index} contains unsupported fields")
        target = entry.get("target")
        digest = entry.get("expertProtocolSHA256")
        if target not in TARGETS:
            blockers.append(f"target_semantic_{index}_target_invalid")
        else:
            targets.append(target)
        if not _is_sha256(digest):
            blockers.append(f"target_semantic_{index}_protocol_sha256_invalid")
        else:
            hashes.append(digest)
        for field in true_fields:
            if entry.get(field) is not True:
                blockers.append(f"target_semantic_{index}_{field}_incomplete")
        if entry.get("sourceLabelsAcceptedAsExpertTruth") is not False:
            raise SemanticsInputError("source labels cannot substitute for expert truth")
        if target in TARGETS and _is_sha256(digest):
            canonical.append({"target": target, "expertProtocolSHA256": digest})
    if len(targets) != len(set(targets)):
        raise SemanticsInputError("expert semantic targets must be unique")
    if len(hashes) != len(set(hashes)):
        raise SemanticsInputError("expert protocol hashes must be unique")
    if set(targets) != set(TARGETS) or len(entries) != len(TARGETS):
        blockers.append("expert_target_inventory_incomplete")
    blockers = sorted(set(blockers))
    digest = hashlib.sha256(_canonical_bytes(sorted(canonical, key=lambda item: item["target"]))).hexdigest() if canonical else None
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "targets": list(TARGETS),
        "reviewedTargetCount": len(set(targets)),
        "semanticsRegistryDigest": digest,
        "perClassExpertSemanticsLocked": not blockers,
        **SAFE_POLICY,
        "mapContract": MAP_CONTRACT,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise SemanticsInputError("expert semantics are incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "targets": list(TARGETS),
        "semanticsRegistryDigest": preflight["semanticsRegistryDigest"],
        "perClassExpertSemanticsLocked": True,
        **SAFE_POLICY,
        "mapContract": MAP_CONTRACT,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--current-facts", type=Path)
    source.add_argument("--private-manifest", type=Path)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if args.current_facts is not None:
        facts = json.loads(args.current_facts.read_text(encoding="utf-8"))
        preflight = summarize_current_facts(facts)
        if args.artifact_output is not None:
            raise SemanticsInputError("committed routing facts cannot emit an expert release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
