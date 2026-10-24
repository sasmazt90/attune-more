#!/usr/bin/env python3
"""Build a privacy-safe source-group review queue from a COCO export.

This tool does not alter labels or splits. It deliberately treats filename and
perceptual matches as review candidates rather than ground truth. The committed
output contains hashes and aggregate counts, never filenames or image bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


SPLITS = ("train", "valid", "test")
CLASSES = ("Pimple", "Post acne", "Pigmentation")
ARCHIVE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RF_SUFFIX = re.compile(r"\.rf\.[0-9a-f]{32}\.[^.]+$", re.IGNORECASE)
SOURCE_FORMAT_SUFFIX = re.compile(r"_(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
VALID_DECISIONS = {"same_source", "different_source", "unresolved"}


class ReviewError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"cannot read {path}: {exc}") from exc


def normalized_source_name(file_name: str) -> str:
    source = RF_SUFFIX.sub("", Path(file_name).name)
    source = SOURCE_FORMAT_SUFFIX.sub("", source)
    return re.sub(r"[^a-z0-9]+", "", source.lower())


def digest_token(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def difference_hash(path: Path) -> int:
    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("L").resize(
                (9, 8), Image.Resampling.LANCZOS
            )
            pixels = list(image.get_flattened_data())
    except (OSError, UnidentifiedImageError) as exc:
        raise ReviewError(f"cannot decode an image in {path.parent.name}") from exc
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | int(
                pixels[row * 9 + column] > pixels[row * 9 + column + 1]
            )
    return value


def candidate_id(method: str, member_ids: list[str]) -> str:
    return digest_token(method + "\0" + "\0".join(sorted(member_ids)))


def cross_split(members: list[dict[str, Any]]) -> bool:
    return len({member["split"] for member in members}) > 1


def load_decisions(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schemaVersion") != "source-group-review-decisions-v1":
        raise ReviewError("review decisions have an invalid schema")
    decisions: dict[str, dict[str, str]] = {}
    for row in value.get("decisions", []):
        if not isinstance(row, dict):
            raise ReviewError("review decision rows must be objects")
        identifier = row.get("candidateId")
        decision = row.get("decision")
        rationale = row.get("rationale")
        reviewer = row.get("reviewer")
        if (not isinstance(identifier, str) or not identifier
                or decision not in VALID_DECISIONS
                or not isinstance(rationale, str) or not rationale.strip()
                or reviewer not in {"engineering_visual_review", "expert_review"}):
            raise ReviewError("review decision row is incomplete")
        if identifier in decisions:
            raise ReviewError("review decision candidate ids must be unique")
        decisions[identifier] = {
            "decision": decision,
            "rationale": rationale.strip(),
            "reviewer": reviewer,
        }
    return decisions


def build_review(
    root: Path,
    archive_sha256: str,
    decisions_path: Path | None = None,
    dhash_distance: int = 8,
) -> dict[str, Any]:
    if not ARCHIVE_SHA256.fullmatch(archive_sha256):
        raise ReviewError("archive sha256 must be a lowercase 64-character digest")
    if not 0 <= dhash_distance <= 8:
        raise ReviewError("dHash distance must be between zero and eight")
    decisions = load_decisions(decisions_path)
    records: list[dict[str, Any]] = []

    for split in SPLITS:
        folder = root / split
        coco = load_json(folder / "_annotations.coco.json")
        images = coco.get("images")
        categories = coco.get("categories")
        if not isinstance(images, list) or not isinstance(categories, list):
            raise ReviewError(f"{split} COCO arrays are missing")
        class_names = {row.get("name") for row in categories if isinstance(row, dict)}
        if not set(CLASSES).issubset(class_names):
            raise ReviewError(f"{split} class inventory mismatch")
        ids: set[int] = set()
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("id"), int):
                raise ReviewError(f"{split} image record is invalid")
            if image["id"] in ids:
                raise ReviewError(f"{split} image ids are duplicated")
            ids.add(image["id"])
            file_name = image.get("file_name")
            if not isinstance(file_name, str) or not file_name or Path(file_name).name != file_name:
                raise ReviewError(f"{split} image filename is invalid")
            image_path = folder / file_name
            try:
                content_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ReviewError(f"{split} image file is missing") from exc
            source_name = normalized_source_name(file_name)
            record_id = digest_token(split + "\0" + file_name + "\0" + content_sha)
            records.append({
                "recordId": record_id,
                "split": split,
                "contentSHA256": content_sha,
                "sourceNameToken": digest_token(source_name) if source_name else None,
                "sourceNameQuality": (
                    "usable" if len(source_name) >= 8 and not source_name.isdigit()
                    else "weak_or_degenerate"
                ),
                "dHash": difference_hash(image_path),
            })

    def public_member(record: dict[str, Any]) -> dict[str, str]:
        return {"recordId": record["recordId"], "split": record["split"]}

    candidates: list[dict[str, Any]] = []

    content_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_groups: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        content_groups[record["contentSHA256"]].append(record)
        source_groups[record["sourceNameToken"]].append(record)

    for members in content_groups.values():
        if len(members) > 1 and cross_split(members):
            member_ids = [member["recordId"] for member in members]
            candidates.append({
                "candidateId": candidate_id("exact_content", member_ids),
                "method": "exact_content",
                "members": [public_member(member) for member in sorted(members, key=lambda row: row["recordId"])],
                "automaticEvidence": "same_bytes",
            })

    for token, members in source_groups.items():
        if token is None or len(members) < 2 or not cross_split(members):
            continue
        member_ids = [member["recordId"] for member in members]
        candidates.append({
            "candidateId": candidate_id("normalized_source_name", member_ids),
            "method": "normalized_source_name",
            "members": [public_member(member) for member in sorted(members, key=lambda row: row["recordId"])],
            "sourceNameQuality": (
                "usable" if all(member["sourceNameQuality"] == "usable" for member in members)
                else "weak_or_degenerate"
            ),
            "automaticEvidence": "review_only",
        })

    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left["split"] == right["split"]:
                continue
            distance = (left["dHash"] ^ right["dHash"]).bit_count()
            if distance <= dhash_distance and left["contentSHA256"] != right["contentSHA256"]:
                member_ids = [left["recordId"], right["recordId"]]
                candidates.append({
                    "candidateId": candidate_id("perceptual_dhash", member_ids),
                    "method": "perceptual_dhash",
                    "members": [public_member(member) for member in sorted((left, right), key=lambda row: row["recordId"])],
                    "hammingDistance": distance,
                    "automaticEvidence": "review_only",
                })

    candidates.sort(key=lambda row: (row["method"], row["candidateId"]))
    known_ids = {row["candidateId"] for row in candidates}
    unknown_decisions = sorted(set(decisions) - known_ids)
    if unknown_decisions:
        raise ReviewError("review decisions refer to unknown candidate ids")
    for row in candidates:
        review = decisions.get(row["candidateId"])
        row["review"] = review or {
            "decision": "unresolved",
            "rationale": "candidate has not been reviewed",
            "reviewer": "none",
        }

    counts = {
        method: sum(row["method"] == method for row in candidates)
        for method in ("exact_content", "normalized_source_name", "perceptual_dhash")
    }
    unresolved_usable = sum(
        row["review"]["decision"] == "unresolved"
        and row.get("sourceNameQuality") != "weak_or_degenerate"
        for row in candidates
    )
    confirmed_leakage = sum(
        row["method"] == "exact_content"
        or row["review"]["decision"] == "same_source"
        for row in candidates
    )
    return {
        "schemaVersion": "acne-source-group-review-v1",
        "dataset": {
            "archiveSHA256": archive_sha256,
            "images": len(records),
            "splits": {split: sum(row["split"] == split for row in records) for split in SPLITS},
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "candidateMembersAreHashed": True,
        },
        "methods": {
            "exactContentSHA256": True,
            "normalizedSourceName": "candidate-only; short or numeric keys are weak",
            "perceptualDHash": {
                "size": "9x8 grayscale",
                "maxHammingDistance": dhash_distance,
                "candidateOnly": True,
            },
        },
        "candidateCounts": counts,
        "reviewCandidates": candidates,
        "reviewSummary": {
            "sameSource": sum(row["review"]["decision"] == "same_source" for row in candidates),
            "differentSource": sum(row["review"]["decision"] == "different_source" for row in candidates),
            "unresolved": sum(row["review"]["decision"] == "unresolved" for row in candidates),
            "unresolvedUsableCandidates": unresolved_usable,
            "confirmedCrossSplitSourceLeakageGroups": confirmed_leakage,
        },
        "decision": {
            "personOrSourceGroupCoverageEstablished": False,
            "splitIndependenceEstablished": False,
            "splitIndependenceViolated": confirmed_leakage > 0,
            "trainingAuthorized": False,
            "modelAccepted": False,
            "reason": (
                "CROSS_SPLIT_SOURCE_LEAKAGE_CONFIRMED; REGROUP_BEFORE_RETRAINING"
                if confirmed_leakage
                else "SOURCE_PERSON_GROUP_COVERAGE_REMAINS_UNAVAILABLE; DO_NOT_RETRAIN"
            ),
            "next": [
                "resolve usable candidates against the private images",
                "obtain source/person identifiers or create reviewed source groups",
                "build a new group-locked split only after semantic and negative review",
                "keep the existing test split untouched during validation-only resolution experiments",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dhash-distance", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        result = build_review(
            args.dataset,
            args.archive_sha256,
            decisions_path=args.decisions,
            dhash_distance=args.dhash_distance,
        )
    except ReviewError as exc:
        print(f"source-group review blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
