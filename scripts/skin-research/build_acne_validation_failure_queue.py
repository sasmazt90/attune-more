#!/usr/bin/env python3
"""Create a privacy-safe expert-review queue from validation-only model failures.

Roboflow image identifiers and filenames are consumed only as private resolver
inputs.  The committed output contains deterministic opaque references and
counts.  Model errors remain proposals for human review, never expert truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, TextIO


EVAL_ID = "7s06OfIzx78XzATqr5oA"
MODEL_ID = "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-1-rfdetr-small-t2"
PROJECT = "attune-skin-acne-marks-pigmentation"
CLASSES = ("Pigmentation", "Pimple", "Post acne")
BACKGROUND = 3
EXPECTED_IMAGES = 165
CONFIDENCE = 0.3


class QueueError(ValueError):
    """Raised when the private provider payload is unsafe or incomplete."""


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QueueError(f"{label} must be a non-negative integer")
    return value


def _unit_metric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QueueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise QueueError(f"{label} must be finite and between zero and one")
    return result


def _record_ref(image_id: str, image_name: str) -> str:
    material = f"acne-validation-failure-v1\0{EVAL_ID}\0{image_id}\0{image_name}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _queue_digest(classes: dict[str, Any]) -> str:
    payload = json.dumps(classes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_queue(payload: dict[str, Any], *, observed_at: str, per_class_limit: int = 15) -> dict[str, Any]:
    if payload.get("evalId") != EVAL_ID or payload.get("modelId") != MODEL_ID:
        raise QueueError("evaluation/model identity changed")
    if payload.get("project") != PROJECT or payload.get("versionId") != "1":
        raise QueueError("project/version binding changed")
    if payload.get("split") != "valid" or payload.get("confidenceThreshold") != CONFIDENCE:
        raise QueueError("only the fixed validation@0.30 slice is allowed")
    if payload.get("totalImages") != EXPECTED_IMAGES:
        raise QueueError("validation inventory changed")
    images = payload.get("images")
    if not isinstance(images, list) or len(images) != EXPECTED_IMAGES:
        raise QueueError("all validation image results are required")
    if isinstance(per_class_limit, bool) or not isinstance(per_class_limit, int) or per_class_limit <= 0:
        raise QueueError("per-class limit must be a positive integer")

    seen: set[tuple[str, str]] = set()
    candidates: dict[str, list[dict[str, Any]]] = {name: [] for name in CLASSES}
    aggregates = {name: {"missedToBackground": 0, "falsePositiveFromBackground": 0, "crossClassOutbound": 0, "crossClassInbound": 0} for name in CLASSES}
    for image in images:
        if not isinstance(image, dict):
            raise QueueError("image rows must be objects")
        image_id, image_name = image.get("imageId"), image.get("imageName")
        if not isinstance(image_id, str) or not image_id or not isinstance(image_name, str) or not image_name:
            raise QueueError("private resolver identifiers are required")
        identity = (image_id, image_name)
        if identity in seen:
            raise QueueError("duplicate validation image row")
        seen.add(identity)
        if image.get("split") != "valid" or image.get("augmentations") != 0:
            raise QueueError("queue rows must be unaugmented validation images")
        stats = image.get("stats", {})
        for field in ("truePositives", "falsePositives", "falseNegatives"):
            _nonnegative_int(stats.get(field), f"stats.{field}")
        for field in ("precision", "recall", "f1"):
            _unit_metric(stats.get(field), f"stats.{field}")
        counts: dict[tuple[int, int], int] = {}
        for triple in image.get("confusion", []):
            if not isinstance(triple, list) or len(triple) != 3:
                raise QueueError("confusion rows must be [actual,predicted,count]")
            actual, predicted, count = triple
            if actual not in range(4) or predicted not in range(4):
                raise QueueError("confusion class index is out of range")
            count = _nonnegative_int(count, "confusion count")
            if (actual, predicted) in counts:
                raise QueueError("duplicate confusion cell")
            counts[(actual, predicted)] = count
        ref = _record_ref(image_id, image_name)
        cluster = image.get("cluster", {}).get("id")
        if isinstance(cluster, bool) or not isinstance(cluster, int) or cluster < -1:
            raise QueueError("cluster id must be an integer")
        for index, class_name in enumerate(CLASSES):
            missed = counts.get((index, BACKGROUND), 0)
            fp = counts.get((BACKGROUND, index), 0)
            outbound = sum(counts.get((index, other), 0) for other in range(3) if other != index)
            inbound = sum(counts.get((other, index), 0) for other in range(3) if other != index)
            aggregates[class_name]["missedToBackground"] += missed
            aggregates[class_name]["falsePositiveFromBackground"] += fp
            aggregates[class_name]["crossClassOutbound"] += outbound
            aggregates[class_name]["crossClassInbound"] += inbound
            score = 5 * missed + 4 * outbound + 3 * inbound + 2 * fp
            if score:
                candidates[class_name].append({
                    "recordRef": ref,
                    "clusterId": cluster,
                    "priorityScore": score,
                    "failureCounts": {
                        "missedToBackground": missed,
                        "falsePositiveFromBackground": fp,
                        "crossClassOutbound": outbound,
                        "crossClassInbound": inbound,
                    },
                    "modelProposalOnly": True,
                })

    class_queues: dict[str, Any] = {}
    for class_name in CLASSES:
        ranked = sorted(candidates[class_name], key=lambda row: (-row["priorityScore"], row["recordRef"]))
        class_queues[class_name] = {
            "aggregateFailures": aggregates[class_name],
            "candidateImagesWithFailure": len(ranked),
            "reviewItems": ranked[:per_class_limit],
            "reviewItemsSelected": min(len(ranked), per_class_limit),
            "expertDecisionsComplete": False,
        }

    return {
        "schemaVersion": "acne-validation-failure-review-queue-v1",
        "observedAt": observed_at,
        "source": {
            "project": PROJECT,
            "version": 1,
            "evalId": EVAL_ID,
            "modelId": MODEL_ID,
            "split": "valid",
            "images": EXPECTED_IMAGES,
            "confidenceThreshold": CONFIDENCE,
            "thresholdSelectedHere": False,
            "testSplitRead": False,
        },
        "rankingPolicy": {
            "method": "5*missed + 4*cross_outbound + 3*cross_inbound + 2*background_fp",
            "perClassLimit": per_class_limit,
            "rankingIsExpertTruth": False,
            "rankingAuthorizesRelabel": False,
        },
        "classes": class_queues,
        "queueDigest": _queue_digest(class_queues),
        "decision": {
            "privateResolverRequired": True,
            "expertReviewComplete": False,
            "trainingAuthorized": False,
            "finalTestEvaluationAuthorized": False,
            "productActivationAllowed": False,
            "reason": "EXPERT_REVIEW_REQUIRED_BEFORE_TARGETED_REMEDIATION",
        },
        "privacy": {
            "containsImageIds": False,
            "containsFilenames": False,
            "containsPaths": False,
            "containsImageBytes": False,
            "recordRefsAreSHA256Pseudonyms": True,
        },
    }


def _read_json(path: str, stdin: TextIO) -> dict[str, Any]:
    if path == "-":
        return json.load(stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Private provider JSON path, or - for stdin")
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--per-class-limit", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_queue(_read_json(args.input, sys.stdin), observed_at=args.observed_at, per_class_limit=args.per_class_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
