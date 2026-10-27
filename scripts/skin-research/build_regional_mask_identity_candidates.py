#!/usr/bin/env python3
"""Rank cross-split regional source/person candidates without deciding identity.

The strict full-image audit is intentionally high precision and found no
candidate at its locked threshold.  This tool adds a bounded review layer: it
ranks pairs using full and central grayscale crops, binds every record to the
complete 337-item coverage queue, and emits only pseudonymous identifiers.
Distances are review prioritisation signals, never identity or split truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from audit_regional_skin_type_source_groups import AuditError, SHA256, SPLITS
from build_regional_mask_group_coverage_review import _digest, _review_id


CROP_SCALES = (1.0, 0.8, 0.6)
PAIR_QUOTAS = {"train-valid": 24, "train-test": 16, "valid-test": 8}
DECISIONS = {"same_person_or_source", "different_person_or_source", "uncertain"}


@dataclass(frozen=True)
class Record:
    split: str
    review_item_id: str
    path: Path
    features: dict[str, tuple[int, int]]


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("invalid JSON input") from exc
    if not isinstance(value, dict):
        raise AuditError("JSON root must be an object")
    return value


def _dhash(gray: Image.Image) -> int:
    pixels = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return value


def _phash(gray: Image.Image) -> int:
    pixels = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    positions = np.arange(32, dtype=np.float64)
    frequencies = np.arange(8, dtype=np.float64)[:, None]
    cosine = np.cos((math.pi / 32.0) * (positions + 0.5) * frequencies)
    values = (cosine @ pixels @ cosine.T).flatten()[1:]
    median = float(np.median(values))
    result = 0
    for bit in values >= median:
        result = (result << 1) | int(bit)
    return result


def _crop(gray: Image.Image, scale: float) -> Image.Image:
    width, height = gray.size
    crop_width = max(1, int(width * scale))
    crop_height = max(1, int(height * scale))
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return gray.crop((left, top, left + crop_width, top + crop_height))


def _features(path: Path) -> dict[str, tuple[int, int]]:
    try:
        with Image.open(path) as opened:
            gray = ImageOps.grayscale(ImageOps.exif_transpose(opened).convert("RGB"))
            return {
                f"center-{scale:.1f}": (_dhash(_crop(gray, scale)), _phash(_crop(gray, scale)))
                for scale in CROP_SCALES
            }
    except (OSError, ValueError) as exc:
        raise AuditError("image could not be decoded") from exc


def _distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _pair_name(left: str, right: str) -> str:
    return "-".join(sorted((left, right), key=SPLITS.index))


def _load_records(root: Path, export_sha256: str) -> list[Record]:
    records: list[Record] = []
    for split in SPLITS:
        payload = _load(root / split / "_annotations.coco.json")
        images = payload.get("images")
        if not isinstance(images, list):
            raise AuditError("COCO images array is missing")
        for row in images:
            if not isinstance(row, dict) or not isinstance(row.get("file_name"), str):
                raise AuditError("COCO image record is invalid")
            name = row["file_name"]
            path = root / split / Path(name).name
            if not path.is_file():
                raise AuditError("image file is missing")
            records.append(Record(
                split=split,
                review_item_id=_review_id(export_sha256, split, name),
                path=path,
                features=_features(path),
            ))
    return records


def _rank_pair(left: Record, right: Record) -> dict[str, Any]:
    distances = {}
    for key in sorted(left.features):
        left_dhash, left_phash = left.features[key]
        right_dhash, right_phash = right.features[key]
        distances[key] = {
            "dHashDistance": _distance(left_dhash, right_dhash),
            "pHashDistance": _distance(left_phash, right_phash),
        }
    best_scale, best = min(
        distances.items(),
        key=lambda item: (
            item[1]["dHashDistance"] + item[1]["pHashDistance"],
            item[1]["pHashDistance"],
            item[0],
        ),
    )
    ids = sorted((left.review_item_id, right.review_item_id))
    return {
        "candidateId": "ic-" + hashlib.sha256((ids[0] + "\0" + ids[1]).encode()).hexdigest()[:24],
        "leftReviewItemId": ids[0],
        "rightReviewItemId": ids[1],
        "splitPair": _pair_name(left.split, right.split),
        "bestCropScale": best_scale,
        "bestCombinedDistance": best["dHashDistance"] + best["pHashDistance"],
        "distances": distances,
        "reviewStatus": "unreviewed_candidate",
        "automaticIdentityDecision": False,
    }


def build_candidates(
    root: Path,
    coverage_queue_path: Path,
    source_archive_sha256: str,
    provider_export_sha256: str,
    *,
    max_record_appearances: int = 3,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    for digest in (source_archive_sha256, provider_export_sha256):
        if not SHA256.fullmatch(digest):
            raise AuditError("archive digests must be lowercase sha256 values")
    if max_record_appearances < 1:
        raise AuditError("record appearance limit must be positive")

    coverage = _load(coverage_queue_path)
    if coverage.get("schemaVersion") != "regional-mask-source-person-review-queue-v1":
        raise AuditError("coverage queue schema is invalid")
    source = coverage.get("source", {})
    if source.get("sourceArchiveSHA256") != source_archive_sha256:
        raise AuditError("source archive is not bound to the coverage queue")
    if source.get("providerExportSHA256") != provider_export_sha256:
        raise AuditError("provider export is not bound to the coverage queue")
    coverage_items = coverage.get("items")
    if not isinstance(coverage_items, list):
        raise AuditError("coverage queue items are missing")
    if coverage.get("coverage", {}).get("queueItemsSHA256") != _digest(coverage_items):
        raise AuditError("coverage queue item binding is invalid")
    expected_ids = {row.get("reviewItemId") for row in coverage_items if isinstance(row, dict)}
    if len(expected_ids) != 337:
        raise AuditError("coverage queue must contain 337 unique records")

    records = _load_records(root, provider_export_sha256)
    record_ids = {record.review_item_id for record in records}
    if len(records) != 337 or record_ids != expected_ids:
        raise AuditError("private export does not match every exact coverage item")

    ranked: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left.split == right.split:
                continue
            row = _rank_pair(left, right)
            ranked[row["splitPair"]].append(row)
    for rows in ranked.values():
        rows.sort(key=lambda row: (
            row["bestCombinedDistance"],
            min(value["pHashDistance"] for value in row["distances"].values()),
            row["candidateId"],
        ))

    appearances: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for split_pair, quota in PAIR_QUOTAS.items():
        chosen = []
        for row in ranked[split_pair]:
            ids = (row["leftReviewItemId"], row["rightReviewItemId"])
            if any(appearances[item_id] >= max_record_appearances for item_id in ids):
                continue
            chosen.append(row)
            appearances.update(ids)
            if len(chosen) == quota:
                break
        if len(chosen) != quota:
            raise AuditError("candidate diversity constraints cannot satisfy split-pair quota")
        selected.extend(chosen)
    selected.sort(key=lambda row: (row["splitPair"], row["bestCombinedDistance"], row["candidateId"]))
    candidates_sha = _digest(selected)

    resolver = {record.review_item_id: str(record.path) for record in records}
    queue = {
        "schemaVersion": "regional-mask-identity-candidate-queue-v1",
        "source": {
            "sourceArchiveSHA256": source_archive_sha256,
            "providerExportSHA256": provider_export_sha256,
            "coverageQueueItemsSHA256": coverage["coverage"]["queueItemsSHA256"],
            "project": "tolgar-sasmaz/attune-skin-regional-skin-map",
            "versionNumber": 1,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "privateResolverCommitted": False,
        },
        "method": {
            "comparisonScope": "all cross-split image pairs",
            "cropScales": list(CROP_SCALES),
            "featureSignals": ["grayscale-dhash-64", "grayscale-phash-63"],
            "splitPairQuotas": PAIR_QUOTAS,
            "maximumCandidateAppearancesPerRecord": max_record_appearances,
            "rankingOnly": True,
            "distanceThresholdEstablishesIdentity": False,
            "candidateReviewMayEstablishFullCoverage": False,
        },
        "coverage": {
            "privateExportRecords": len(records),
            "crossSplitPairsCompared": sum(len(rows) for rows in ranked.values()),
            "selectedCandidates": len(selected),
            "uniqueCandidateRecords": len(appearances),
            "candidatesSHA256": candidates_sha,
        },
        "candidates": selected,
        "decision": {
            "candidateReviewComplete": False,
            "personOrSourceCoverageComplete": False,
            "currentSplitIndependent": False,
            "trainingAuthorized": False,
            "finalTestAuthorized": False,
            "activationAllowed": False,
        },
    }
    template = {
        "schemaVersion": "regional-mask-identity-candidate-decisions-v1",
        "candidatesSHA256": candidates_sha,
        "reviewerRole": None,
        "items": [
            {
                "candidateId": row["candidateId"],
                "decision": "unreviewed",
                "reviewMethod": None,
                "notesContainIdentityOrPrivateData": False,
            }
            for row in selected
        ],
        "attestations": {
            "bothPrivateImagesReviewedForEveryCandidate": False,
            "distanceNotUsedAsAutomaticIdentityTruth": False,
            "uncertainPairsRemainUnmerged": False,
            "noRawIdentityOrPrivateNotesCommitted": False,
        },
    }
    return queue, template, resolver


def evaluate_candidates(queue: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    if queue.get("schemaVersion") != "regional-mask-identity-candidate-queue-v1":
        raise AuditError("candidate queue schema is invalid")
    if decisions.get("schemaVersion") != "regional-mask-identity-candidate-decisions-v1":
        raise AuditError("candidate decisions schema is invalid")
    candidates = queue.get("candidates")
    rows = decisions.get("items")
    if not isinstance(candidates, list) or not isinstance(rows, list):
        raise AuditError("candidate decision items are invalid")
    binding = queue.get("coverage", {}).get("candidatesSHA256")
    if binding != _digest(candidates) or decisions.get("candidatesSHA256") != binding:
        raise AuditError("decisions are not bound to the exact candidate queue")
    expected = {row.get("candidateId") for row in candidates if isinstance(row, dict)}
    received = [row.get("candidateId") for row in rows if isinstance(row, dict)]
    if len(expected) != 48 or set(received) != expected or len(received) != len(set(received)):
        raise AuditError("decisions must cover every exact candidate once")
    reviewed = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("decision") in DECISIONS
        and row.get("reviewMethod") == "private_visual_pair_review"
        and row.get("notesContainIdentityOrPrivateData") is False
    ]
    attestations = decisions.get("attestations", {})
    attested = all(attestations.get(key) is True for key in (
        "bothPrivateImagesReviewedForEveryCandidate",
        "distanceNotUsedAsAutomaticIdentityTruth",
        "uncertainPairsRemainUnmerged",
        "noRawIdentityOrPrivateNotesCommitted",
    ))
    complete = (
        len(reviewed) == 48
        and attested
        and decisions.get("reviewerRole") == "authorized_source_identity_reviewer"
    )
    counts = Counter(row.get("decision") for row in reviewed)
    return {
        "schemaVersion": "regional-mask-identity-candidate-result-v1",
        "candidatesSHA256": binding,
        "reviewedCandidates": len(reviewed),
        "unreviewedCandidates": 48 - len(reviewed),
        "decisions": {name: counts[name] for name in sorted(DECISIONS)},
        "candidateReviewComplete": complete,
        "confirmedSamePersonOrSourcePairs": counts["same_person_or_source"],
        "personOrSourceCoverageComplete": False,
        "currentSplitIndependent": False,
        "trainingAuthorized": False,
        "finalTestAuthorized": False,
        "activationAllowed": False,
        "blockers": [
            reason for condition, reason in (
                (complete, "candidate_review_incomplete"),
                (False, "full_337_record_source_person_review_incomplete"),
                (False, "group_locked_replacement_version_missing"),
                (False, "expert_semantic_mask_protocol_not_accepted"),
            ) if not condition
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--coverage-queue", type=Path, required=True)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--provider-export-sha256", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    queue, template, resolver = build_candidates(
        args.root,
        args.coverage_queue,
        args.source_archive_sha256,
        args.provider_export_sha256,
    )
    args.queue.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    if not args.decisions.exists():
        args.decisions.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    if args.evaluate:
        if args.result is None:
            raise AuditError("--result is required with --evaluate")
        result = evaluate_candidates(queue, _load(args.decisions))
        args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
