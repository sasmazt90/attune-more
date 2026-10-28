#!/usr/bin/env python3
"""Validate expert adjudication of the acne validation failure queue.

The committed queue contains only deterministic pseudonyms and model-error
counts.  This builder accepts a private, qualified-human review manifest,
requires one decision for every selected class/record pair, and emits only
aggregate public evidence.  It never authorizes dataset mutation, training,
final-test use, threshold selection, or product activation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


QUEUE_METHOD = "acne-validation-failure-review-queue-v1"
INPUT_METHOD = "acne-validation-expert-review-input-v1"
PREFLIGHT_METHOD = "acne-validation-expert-review-preflight-v1"
ARTIFACT_METHOD = "acne-validation-expert-review-v1"
EXPECTED_QUEUE_DIGEST = "6fa8ccb7a2a1c072bb18fc80bf64babcffd5b59d764b7429c43beaf8383bc6c6"
EXPECTED_EVAL_ID = "7s06OfIzx78XzATqr5oA"
EXPECTED_MODEL_ID = "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-small-t2"
CLASSES = ("Pigmentation", "Pimple", "Post acne")
RECORD_REF_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TRUTH_STATUSES = (
    "positive_target",
    "evaluated_negative",
    "ambiguous",
    "unassessable",
)
ROOT_CAUSES = (
    "label_missing",
    "label_wrong_class",
    "label_extent_inconsistent",
    "domain_or_resolution_gap",
    "confounder_or_hard_negative",
    "ambiguous_policy",
    "image_unassessable",
    "model_only_failure",
)
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "image", "images",
    "imageId", "imageName", "subject", "subjectId", "person", "personId",
    "reviewer", "reviewerId", "reviewerName", "email", "contact",
    "annotation", "annotations", "bbox", "box", "boxes", "polygon",
    "polygons", "mask", "masks", "prediction", "predictions",
    "modelProposal", "modelProposals", "bytes", "media",
}


class ExpertReviewError(ValueError):
    """Raised when queue binding, privacy, or expert-review policy changes."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise ExpertReviewError(f"{location} contains raw/private identity, media, geometry, or model payload")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def validate_queue(queue: dict[str, Any]) -> list[tuple[str, str]]:
    """Validate the committed validation-only queue and return expected keys."""
    if not isinstance(queue, dict) or queue.get("schemaVersion") != QUEUE_METHOD:
        raise ExpertReviewError("queue method changed")
    if queue.get("queueDigest") != EXPECTED_QUEUE_DIGEST:
        raise ExpertReviewError("queue digest changed")
    if _sha256(queue.get("classes")) != EXPECTED_QUEUE_DIGEST:
        raise ExpertReviewError("queue class payload no longer matches its digest")
    source = queue.get("source")
    if not isinstance(source, dict):
        raise ExpertReviewError("queue source missing")
    expected_source = {
        "project": "attune-skin-acne-marks-pigmentation",
        "version": 1,
        "evalId": EXPECTED_EVAL_ID,
        "modelId": EXPECTED_MODEL_ID,
        "split": "valid",
        "images": 165,
        "confidenceThreshold": 0.3,
        "thresholdSelectedHere": False,
        "testSplitRead": False,
    }
    if source != expected_source:
        raise ExpertReviewError("validation-only queue source binding changed")
    privacy = queue.get("privacy")
    if privacy != {
        "containsFilenames": False,
        "containsImageBytes": False,
        "containsImageIds": False,
        "containsPaths": False,
        "recordRefsAreSHA256Pseudonyms": True,
    }:
        raise ExpertReviewError("queue privacy contract changed")
    decision = queue.get("decision", {})
    for field in ("expertReviewComplete", "trainingAuthorized", "finalTestEvaluationAuthorized", "productActivationAllowed"):
        if decision.get(field) is not False:
            raise ExpertReviewError(f"queue must remain fail-closed: {field}")
    if decision.get("privateResolverRequired") is not True:
        raise ExpertReviewError("private resolver requirement changed")
    classes = queue.get("classes")
    if not isinstance(classes, dict) or set(classes) != set(CLASSES):
        raise ExpertReviewError("queue class inventory changed")
    expected: list[tuple[str, str]] = []
    for class_name in CLASSES:
        class_queue = classes[class_name]
        items = class_queue.get("reviewItems")
        if not isinstance(items, list) or len(items) != 15 or class_queue.get("reviewItemsSelected") != 15:
            raise ExpertReviewError(f"{class_name} review inventory changed")
        for item in items:
            ref = item.get("recordRef")
            if not isinstance(ref, str) or RECORD_REF_RE.fullmatch(ref) is None:
                raise ExpertReviewError("queue record reference is invalid")
            if item.get("modelProposalOnly") is not True:
                raise ExpertReviewError("queue item was promoted beyond model proposal")
            expected.append((class_name, ref))
    if len(expected) != len(set(expected)):
        raise ExpertReviewError("queue contains duplicate class/record pairs")
    return expected


def evaluate_manifest(queue: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a private expert-review manifest without exposing item decisions."""
    expected = validate_queue(queue)
    if not isinstance(manifest, dict):
        raise ExpertReviewError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise ExpertReviewError("manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise ExpertReviewError("manifest method changed")
    if manifest.get("queueDigest") != EXPECTED_QUEUE_DIGEST:
        raise ExpertReviewError("manifest queue binding changed")
    if manifest.get("evalId") != EXPECTED_EVAL_ID or manifest.get("modelId") != EXPECTED_MODEL_ID:
        raise ExpertReviewError("manifest evaluation/model binding changed")
    if manifest.get("split") != "valid" or manifest.get("confidenceThreshold") != 0.3:
        raise ExpertReviewError("review must stay on the locked validation@0.30 slice")
    if manifest.get("testSplitRead") is not False or manifest.get("thresholdSelectedHere") is not False:
        raise ExpertReviewError("review cannot use test or select a threshold")

    blockers: list[str] = []
    review_ref = manifest.get("reviewRef")
    authority_ref = manifest.get("reviewAuthorityRef")
    protocol_sha = manifest.get("expertProtocolSHA256")
    if not _is_opaque(review_ref):
        blockers.append("review_ref_missing_or_invalid")
    if not _is_opaque(authority_ref):
        blockers.append("review_authority_ref_missing_or_invalid")
    if not _is_sha256(protocol_sha):
        blockers.append("expert_protocol_sha256_missing_or_invalid")
    policy = manifest.get("reviewPolicy")
    expected_policy = {
        "qualifiedHumanReviewConfirmed": True,
        "modelProposalHiddenUntilIndependentDecision": True,
        "nativeResolutionSourceViewed": True,
        "classDefinitionsLockedBeforeReview": True,
        "missingLabelNotNegativeOrNormal": True,
        "modelProposalNotExpertTruth": True,
        "reviewDoesNotAuthorizeRelabel": True,
        "reviewDoesNotAuthorizeTraining": True,
        "testExcluded": True,
    }
    if policy != expected_policy:
        raise ExpertReviewError("expert review policy changed or is incomplete")

    entries = manifest.get("decisions")
    if not isinstance(entries, list):
        raise ExpertReviewError("decisions must be a list")
    seen: set[tuple[str, str]] = set()
    aggregate = {
        class_name: {
            "reviewed": 0,
            "truthStatus": Counter(),
            "rootCause": Counter(),
        }
        for class_name in CLASSES
    }
    allowed_entry = {"className", "recordRef", "truthStatus", "rootCause", "expertDecisionIndependent"}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != allowed_entry:
            raise ExpertReviewError(f"decision {index} fields changed")
        key = (entry.get("className"), entry.get("recordRef"))
        if key in seen:
            raise ExpertReviewError("duplicate class/record decision")
        seen.add(key)
        if key not in set(expected):
            raise ExpertReviewError("decision does not belong to the locked queue")
        if entry.get("expertDecisionIndependent") is not True:
            raise ExpertReviewError("expert decision must be independent of model proposal")
        truth = entry.get("truthStatus")
        cause = entry.get("rootCause")
        if truth not in TRUTH_STATUSES or cause not in ROOT_CAUSES:
            raise ExpertReviewError("decision code is unsupported")
        class_name = entry["className"]
        aggregate[class_name]["reviewed"] += 1
        aggregate[class_name]["truthStatus"][truth] += 1
        aggregate[class_name]["rootCause"][cause] += 1

    missing = set(expected) - seen
    if missing:
        blockers.append("expert_decisions_incomplete")
    if len(entries) != len(expected):
        blockers.append("expert_decision_count_mismatch")
    blockers = sorted(set(blockers))
    public_aggregate = {}
    for class_name in CLASSES:
        public_aggregate[class_name] = {
            "expected": 15,
            "reviewed": aggregate[class_name]["reviewed"],
            "truthStatusCounts": {key: aggregate[class_name]["truthStatus"].get(key, 0) for key in TRUTH_STATUSES},
            "rootCauseCounts": {key: aggregate[class_name]["rootCause"].get(key, 0) for key in ROOT_CAUSES},
        }
    complete = not blockers
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "queueDigest": EXPECTED_QUEUE_DIGEST,
        "evalId": EXPECTED_EVAL_ID,
        "modelId": EXPECTED_MODEL_ID,
        "split": "valid",
        "confidenceThreshold": 0.3,
        "reviewRef": review_ref if _is_opaque(review_ref) else None,
        "reviewAuthorityRef": authority_ref if _is_opaque(authority_ref) else None,
        "expertProtocolSHA256": protocol_sha if _is_sha256(protocol_sha) else None,
        "expectedDecisions": len(expected),
        "reviewedDecisions": len(seen & set(expected)),
        "perClass": public_aggregate,
        "expertReviewComplete": complete,
        "targetedRemediationPlanningAllowed": complete,
        "datasetMutationAuthorized": False,
        "trainingAuthorized": False,
        "finalTestEvaluationAuthorized": False,
        "productActivationAllowed": False,
        "testSplitRead": False,
        "thresholdSelectedHere": False,
        "modelProposalsAreExpertTruth": False,
        "decision": "ready_for_targeted_remediation_planning" if complete else "blocked",
        "blockers": blockers,
    }


def build_artifact(queue: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_manifest(queue, manifest)
    if not preflight["expertReviewComplete"]:
        raise ExpertReviewError("expert validation review is incomplete: " + ", ".join(preflight["blockers"]))
    aggregate_digest = _sha256(preflight["perClass"])
    return {
        **preflight,
        "methodVersion": ARTIFACT_METHOD,
        "aggregateDigest": aggregate_digest,
        "blockers": [],
    }


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    queue, manifest = _load(args.queue), _load(args.input)
    _write(args.preflight, evaluate_manifest(queue, manifest))
    if args.artifact:
        _write(args.artifact, build_artifact(queue, manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
