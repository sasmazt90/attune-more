"""Find privacy-safe cross-split source/person candidates in a COCO export.

This is a candidate generator, not an identity classifier. It emits only
salted record identifiers and image-distance evidence. A zero-candidate result
does not establish person independence, and no candidate is auto-merged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


SPLITS = ("train", "valid", "test")
SOURCE_NAME = re.compile(
    r"^(?P<source>.+?)_jpg\.rf\.[0-9a-f]{32}\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AuditError(ValueError):
    """Raised when a privacy-safe audit cannot be completed exactly."""


@dataclass(frozen=True)
class ImageRecord:
    split: str
    source_id: str
    record_id: str
    path: Path
    pixel_sha256: str
    dhash: int
    phash: int


def _private_id(salt: str, kind: str, value: str) -> str:
    return hashlib.sha256(f"{salt}:{kind}:{value}".encode("utf-8")).hexdigest()[:24]


def _source_name(file_name: str) -> str:
    match = SOURCE_NAME.fullmatch(Path(file_name).name)
    if not match:
        raise AuditError("image filename does not expose a stable Roboflow source id")
    return match.group("source")


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
    low = cosine @ pixels @ cosine.T
    values = low.flatten()[1:]
    median = float(np.median(values))
    value = 0
    for bit in values >= median:
        value = (value << 1) | int(bit)
    return value


def _image_features(path: Path) -> tuple[str, int, int]:
    try:
        with Image.open(path) as opened:
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
            normalized = rgb.resize((256, 256), Image.Resampling.LANCZOS)
            pixel_sha = hashlib.sha256(normalized.tobytes()).hexdigest()
            gray = ImageOps.grayscale(rgb)
            return pixel_sha, _dhash(gray), _phash(gray)
    except (OSError, ValueError) as exc:
        raise AuditError("image could not be decoded") from exc


def _load_records(root: Path, salt: str) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    for split in SPLITS:
        annotation_path = root / split / "_annotations.coco.json"
        try:
            payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditError(f"invalid COCO annotations for {split}") from exc
        images = payload.get("images")
        if not isinstance(images, list):
            raise AuditError(f"missing COCO images for {split}")
        for row in images:
            file_name = row.get("file_name")
            if not isinstance(file_name, str):
                raise AuditError(f"invalid image record in {split}")
            path = root / split / Path(file_name).name
            if not path.is_file():
                raise AuditError(f"missing image file in {split}")
            source_name = _source_name(file_name)
            source_id = _private_id(salt, "source", source_name)
            record_id = _private_id(salt, "record", f"{split}:{file_name}")
            pixel_sha, dhash, phash = _image_features(path)
            records.append(
                ImageRecord(split, source_id, record_id, path, pixel_sha, dhash, phash)
            )
    return records


def _distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def audit_source_groups(
    root: Path,
    archive_sha256: str,
    salt: str,
    *,
    dhash_max_distance: int = 8,
    phash_max_distance: int = 12,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not SHA256.fullmatch(archive_sha256):
        raise AuditError("archive sha256 must be a lowercase 64-character digest")
    if len(salt) < 16:
        raise AuditError("privacy salt must contain at least 16 characters")
    if dhash_max_distance < 0 or phash_max_distance < 0:
        raise AuditError("hash thresholds must be non-negative")

    records = _load_records(root, salt)
    by_source: dict[str, list[ImageRecord]] = {}
    for record in records:
        by_source.setdefault(record.source_id, []).append(record)

    source_splits = {
        source_id: sorted({record.split for record in members})
        for source_id, members in by_source.items()
    }
    source_id_cross_split = [
        source_id for source_id, splits in source_splits.items() if len(splits) > 1
    ]

    candidates: list[dict[str, Any]] = []
    for left_source, right_source in combinations(sorted(by_source), 2):
        left_members = by_source[left_source]
        right_members = by_source[right_source]
        split_pairs = sorted(
            {f"{left.split}-{right.split}" for left in left_members for right in right_members
             if left.split != right.split}
        )
        if not split_pairs:
            continue
        exact = False
        min_dhash = 64
        min_phash = 63
        best_records: tuple[str, str] | None = None
        for left in left_members:
            for right in right_members:
                if left.split == right.split:
                    continue
                current_exact = left.pixel_sha256 == right.pixel_sha256
                current_dhash = _distance(left.dhash, right.dhash)
                current_phash = _distance(left.phash, right.phash)
                score = (not current_exact, current_dhash + current_phash, current_phash)
                current_best = (not exact, min_dhash + min_phash, min_phash)
                if best_records is None or score < current_best:
                    exact = current_exact
                    min_dhash = current_dhash
                    min_phash = current_phash
                    best_records = (left.record_id, right.record_id)
        qualifies = exact or (
            min_dhash <= dhash_max_distance and min_phash <= phash_max_distance
        )
        if qualifies and best_records is not None:
            candidates.append({
                "candidateId": _private_id(salt, "pair", f"{left_source}:{right_source}"),
                "leftSourceId": left_source,
                "rightSourceId": right_source,
                "splitPairs": split_pairs,
                "representativeRecordIds": list(best_records),
                "exactNormalizedPixelMatch": exact,
                "minimumDHashDistance": min_dhash,
                "minimumPHashDistance": min_phash,
                "reviewStatus": "unreviewed_candidate",
            })

    candidates.sort(key=lambda row: (
        not row["exactNormalizedPixelMatch"],
        row["minimumDHashDistance"] + row["minimumPHashDistance"],
        row["candidateId"],
    ))
    resolver = {record.record_id: str(record.path) for record in records}
    audit = {
        "schemaVersion": "regional-skin-type-source-group-audit-v1",
        "source": {
            "archiveSHA256": archive_sha256,
            "exportFormat": "coco",
        },
        "privacy": {
            "rawFileNamesPersisted": False,
            "rawSourceNamesPersisted": False,
            "resolverCommitted": False,
            "identifierMethod": "salted-sha256-prefix-24",
        },
        "inventory": {
            "images": len(records),
            "uniqueSourceIds": len(by_source),
            "sourceIdsCrossingSplits": len(source_id_cross_split),
            "crossSplitPerceptualCandidates": len(candidates),
            "exactNormalizedPixelCandidates": sum(
                1 for row in candidates if row["exactNormalizedPixelMatch"]
            ),
        },
        "method": {
            "comparisonScope": "cross-split source pairs only",
            "dHashBits": 64,
            "dHashMaximumDistance": dhash_max_distance,
            "pHashBits": 63,
            "pHashMaximumDistance": phash_max_distance,
            "perceptualRule": "dHash and pHash thresholds must both pass",
            "candidateOnly": True,
        },
        "candidates": candidates,
        "decision": {
            "personIndependenceEstablished": False,
            "trainingAuthorized": False,
            "testEligibleForFinalAcceptance": False,
            "reason": "Perceptual similarity is candidate-only and cannot establish complete person identity coverage.",
        },
    }
    return audit, resolver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--dhash-max-distance", type=int, default=8)
    parser.add_argument("--phash-max-distance", type=int, default=12)
    args = parser.parse_args()
    audit, resolver = audit_source_groups(
        args.root,
        args.archive_sha256,
        args.salt,
        dhash_max_distance=args.dhash_max_distance,
        phash_max_distance=args.phash_max_distance,
    )
    args.output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
