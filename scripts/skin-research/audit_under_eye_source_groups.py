#!/usr/bin/env python3
"""Audit a frozen under-eye COCO ZIP for cross-split source leakage.

The audit is deliberately fail-closed. Exact and perceptual image similarity
only produce review candidates; they never establish that two images show the
same person, nor that a zero-candidate result is person-independent. Persisted
output contains salted opaque identifiers, not archive member names.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PIL import Image, ImageOps
import io


SPLITS = ("train", "valid", "test")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PAIR_RE = re.compile(
    r"(?:^[0-9a-f]{8}-)?(?P<source_id>[0-9]{5,})_(?P<side>left|right)_jpg$",
    re.IGNORECASE,
)
RF_SUFFIX = re.compile(r"\.rf\.[0-9a-f]{16,64}(?=\.[^.]+$)", re.IGNORECASE)


class AuditError(ValueError):
    """Raised when the archive cannot be audited without weakening evidence."""


@dataclass(frozen=True)
class Record:
    split: str
    member: str
    record_id: str
    explicit_pair_id: str | None
    byte_sha256: str
    normalized_pixel_sha256: str
    dhash: int
    phash: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_id(salt: str, kind: str, value: str) -> str:
    return hashlib.sha256(f"{salt}:{kind}:{value}".encode("utf-8")).hexdigest()[:24]


def _validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    mode = info.external_attr >> 16
    if path.is_absolute() or ".." in path.parts or "\\" in info.filename or ":" in info.filename:
        raise AuditError("unsafe ZIP member")
    if stat.S_ISLNK(mode):
        raise AuditError("symbolic links are not allowed")


def _explicit_pair(file_name: str) -> str | None:
    stem = RF_SUFFIX.sub("", Path(file_name).name)
    stem = Path(stem).stem
    match = PAIR_RE.fullmatch(stem)
    return match.group("source_id") if match else None


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


def _features(payload: bytes) -> tuple[str, str, int, int]:
    try:
        with Image.open(io.BytesIO(payload)) as opened:
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
            normalized = rgb.resize((256, 256), Image.Resampling.LANCZOS)
            gray = ImageOps.grayscale(rgb)
            return (
                hashlib.sha256(payload).hexdigest(),
                hashlib.sha256(normalized.tobytes()).hexdigest(),
                _dhash(gray),
                _phash(gray),
            )
    except (OSError, ValueError) as exc:
        raise AuditError("image could not be decoded") from exc


def _load_records(archive: zipfile.ZipFile, salt: str) -> list[Record]:
    infos = archive.infolist()
    if len({info.filename for info in infos}) != len(infos):
        raise AuditError("duplicate ZIP member")
    for info in infos:
        _validate_member(info)

    records: list[Record] = []
    for split in SPLITS:
        annotation_name = f"{split}/_annotations.coco.json"
        try:
            payload = json.loads(archive.read(annotation_name))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AuditError(f"invalid COCO annotations for {split}") from exc
        images = payload.get("images")
        if not isinstance(images, list):
            raise AuditError(f"missing COCO images for {split}")
        for row in images:
            file_name = row.get("file_name")
            if not isinstance(file_name, str) or Path(file_name).name != file_name:
                raise AuditError(f"invalid image record in {split}")
            member = f"{split}/{file_name}"
            try:
                image_bytes = archive.read(member)
            except KeyError as exc:
                raise AuditError(f"missing image bytes in {split}") from exc
            byte_sha, pixel_sha, dhash, phash = _features(image_bytes)
            explicit_pair = _explicit_pair(file_name)
            records.append(
                Record(
                    split=split,
                    member=member,
                    record_id=_private_id(salt, "record", member),
                    explicit_pair_id=(
                        _private_id(salt, "explicit-source-photo", explicit_pair)
                        if explicit_pair else None
                    ),
                    byte_sha256=byte_sha,
                    normalized_pixel_sha256=pixel_sha,
                    dhash=dhash,
                    phash=phash,
                )
            )
    return records


def _distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def audit_under_eye_archive(
    source_zip: str | Path,
    expected_sha256: str,
    salt: str,
    *,
    dhash_max_distance: int = 8,
    phash_max_distance: int = 12,
    review_queue_size: int = 20,
) -> tuple[dict[str, Any], dict[str, str]]:
    source_path = Path(source_zip)
    if not SHA256.fullmatch(expected_sha256):
        raise AuditError("expected SHA256 must be a lowercase 64-character digest")
    if _sha256_file(source_path) != expected_sha256:
        raise AuditError("source archive SHA256 does not match the pinned export")
    if len(salt) < 16:
        raise AuditError("privacy salt must contain at least 16 characters")
    if dhash_max_distance < 0 or phash_max_distance < 0 or review_queue_size < 1:
        raise AuditError("audit thresholds and queue size must be positive")

    with zipfile.ZipFile(source_path) as archive:
        records = _load_records(archive, salt)

    explicit_groups: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        if record.explicit_pair_id:
            explicit_groups[record.explicit_pair_id].append(record)
    explicit_complete = {
        group_id: members for group_id, members in explicit_groups.items() if len(members) == 2
    }
    explicit_cross = {
        group_id: members for group_id, members in explicit_complete.items()
        if len({member.split for member in members}) > 1
    }

    ranked: list[dict[str, Any]] = []
    exact_bytes = 0
    exact_pixels = 0
    tight = 0
    comparisons = 0
    for left, right in combinations(records, 2):
        if left.split == right.split:
            continue
        comparisons += 1
        byte_exact = left.byte_sha256 == right.byte_sha256
        pixel_exact = left.normalized_pixel_sha256 == right.normalized_pixel_sha256
        dhash_distance = _distance(left.dhash, right.dhash)
        phash_distance = _distance(left.phash, right.phash)
        threshold_match = pixel_exact or (
            dhash_distance <= dhash_max_distance and phash_distance <= phash_max_distance
        )
        exact_bytes += int(byte_exact)
        exact_pixels += int(pixel_exact)
        tight += int(threshold_match)
        explicit_same = bool(
            left.explicit_pair_id and left.explicit_pair_id == right.explicit_pair_id
        )
        ranked.append({
            "candidateId": _private_id(salt, "candidate", ":".join(sorted((left.member, right.member)))),
            "recordIds": sorted((left.record_id, right.record_id)),
            "splitPair": "-".join(sorted((left.split, right.split))),
            "exactByteMatch": byte_exact,
            "exactNormalizedPixelMatch": pixel_exact,
            "dHashDistance": dhash_distance,
            "pHashDistance": phash_distance,
            "tightPerceptualThresholdMatch": threshold_match,
            "explicitSameSourcePhotoPair": explicit_same,
            "reviewStatus": (
                "reviewed_explicit_source_photo_pair" if explicit_same else "unreviewed_candidate"
            ),
        })
    ranked.sort(key=lambda row: (
        not row["exactNormalizedPixelMatch"],
        row["dHashDistance"] + row["pHashDistance"],
        row["pHashDistance"],
        row["candidateId"],
    ))

    split_counts = Counter(record.split for record in records)
    resolver = {record.record_id: record.member for record in records}
    audit = {
        "schemaVersion": "under-eye-source-group-audit-v1",
        "source": {"archiveSHA256": expected_sha256, "exportFormat": "coco"},
        "privacy": {
            "rawFileNamesPersisted": False,
            "rawSourceNamesPersisted": False,
            "resolverCommitted": False,
            "identifierMethod": "salted-sha256-prefix-24",
            "saltSHA256": hashlib.sha256(salt.encode("utf-8")).hexdigest(),
        },
        "inventory": {
            "images": len(records),
            "splits": dict(split_counts),
            "crossSplitRecordComparisons": comparisons,
            "explicitCompleteSourcePhotoPairs": len(explicit_complete),
            "explicitCrossSplitSourcePhotoPairs": len(explicit_cross),
            "exactByteMatches": exact_bytes,
            "exactNormalizedPixelMatches": exact_pixels,
            "tightPerceptualThresholdMatches": tight,
        },
        "method": {
            "comparisonScope": "all cross-split image pairs",
            "dHashBits": 64,
            "dHashMaximumDistance": dhash_max_distance,
            "pHashBits": 63,
            "pHashMaximumDistance": phash_max_distance,
            "perceptualRule": "dHash and pHash thresholds must both pass",
            "rankedReviewQueueSize": min(review_queue_size, len(ranked)),
            "candidateOnly": True,
        },
        "rankedReviewCandidates": ranked[:review_queue_size],
        "decision": {
            "explicitSourcePhotoLeakageKnown": bool(explicit_cross),
            "explicitKnownLeakageCanBeRegrouped": True,
            "personIndependenceEstablished": False,
            "trainingAuthorized": False,
            "testEligibleForFinalAcceptance": False,
            "reason": (
                "Explicit source-photo pairs cover only filename-supported crops; image similarity "
                "cannot establish complete person identity coverage."
            ),
        },
        "limitations": [
            "A zero exact/tight perceptual match count does not prove person independence.",
            "Unrelated photos of the same person can remain across splits.",
            "Ranked similarity candidates require private human review and are not identity truth.",
            "This audit does not authorize upload, training, activation or roadmap acceptance.",
        ],
    }
    return audit, resolver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--private-resolver", type=Path)
    parser.add_argument("--dhash-max-distance", type=int, default=8)
    parser.add_argument("--phash-max-distance", type=int, default=12)
    parser.add_argument("--review-queue-size", type=int, default=20)
    args = parser.parse_args()
    audit, resolver = audit_under_eye_archive(
        args.source_zip,
        args.source_sha256,
        args.salt,
        dhash_max_distance=args.dhash_max_distance,
        phash_max_distance=args.phash_max_distance,
        review_queue_size=args.review_queue_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.private_resolver:
        args.private_resolver.parent.mkdir(parents=True, exist_ok=True)
        args.private_resolver.write_text(
            json.dumps(resolver, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
