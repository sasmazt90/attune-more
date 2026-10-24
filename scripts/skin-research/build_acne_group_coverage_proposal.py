#!/usr/bin/env python3
"""Build a privacy-safe full-record source/person grouping proposal.

Confirmed review decisions are preserved as groups. Every other record remains
an explicitly unreviewed singleton; perceptual/name similarities become review
candidates only. The output cannot be used as a training split receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_acne_source_group_review import (  # noqa: E402
    ARCHIVE_SHA256,
    CLASSES,
    DIRECTIONAL_PHASH_CROPS,
    SPLITS,
    candidate_id,
    central_perceptual_hash,
    difference_hash,
    directional_perceptual_hash,
    digest_token,
    load_decisions,
    load_json,
    normalized_source_name,
    perceptual_hash,
    perceptual_hash_variants,
)


class ProposalError(ValueError):
    pass


class DisjointSet:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            value, self.parent[value] = self.parent[value], root
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def scan_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split in SPLITS:
        folder = root / split
        coco = load_json(folder / "_annotations.coco.json")
        images, categories = coco.get("images"), coco.get("categories")
        if not isinstance(images, list) or not isinstance(categories, list):
            raise ProposalError(f"{split} COCO arrays are missing")
        class_names = {row.get("name") for row in categories if isinstance(row, dict)}
        if not set(CLASSES).issubset(class_names):
            raise ProposalError(f"{split} class inventory mismatch")
        seen: set[int] = set()
        for image in images:
            if not isinstance(image, dict) or not isinstance(image.get("id"), int):
                raise ProposalError(f"{split} image row is invalid")
            if image["id"] in seen:
                raise ProposalError(f"{split} image ids are duplicated")
            seen.add(image["id"])
            file_name = image.get("file_name")
            if not isinstance(file_name, str) or not file_name or Path(file_name).name != file_name:
                raise ProposalError(f"{split} image filename is invalid")
            image_path = folder / file_name
            try:
                content_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ProposalError(f"{split} image file is missing") from exc
            source_name = normalized_source_name(file_name)
            phashes = perceptual_hash_variants(image_path)
            records.append({
                "recordId": digest_token(split + "\0" + file_name + "\0" + content_sha),
                "split": split,
                "contentSHA256": content_sha,
                "sourceNameToken": digest_token(source_name) if source_name else None,
                "sourceNameUsable": len(source_name) >= 8 and not source_name.isdigit(),
                "dHash": difference_hash(image_path),
                "pHash": phashes["full"],
                "centralPHash": phashes["central"],
                "directionalPHashes": phashes["directional"],
            })
    return records


def public_member(record: dict[str, Any]) -> dict[str, str]:
    return {"recordId": record["recordId"], "split": record["split"]}


def private_record_resolver(root: Path) -> dict[str, Any]:
    """Return a local-only record-id resolver; never commit this payload."""
    records = scan_records(root)
    resolver: list[dict[str, str]] = []
    for split in SPLITS:
        folder = root / split
        coco = load_json(folder / "_annotations.coco.json")
        for image in coco["images"]:
            file_name = image["file_name"]
            image_path = folder / file_name
            content_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            record_id = digest_token(split + "\0" + file_name + "\0" + content_sha)
            resolver.append({
                "recordId": record_id,
                "split": split,
                "relativePath": str(Path(split) / file_name),
            })
    if {row["recordId"] for row in resolver} != {row["recordId"] for row in records}:
        raise ProposalError("private resolver does not match scanned records")
    return {
        "schemaVersion": "acne-group-private-resolver-v1",
        "warning": "PRIVATE_LOCAL_ONLY_DO_NOT_COMMIT",
        "records": sorted(resolver, key=lambda row: row["recordId"]),
    }


def build_proposal(
    root: Path,
    archive_sha256: str,
    decisions_path: Path,
    dhash_distance: int = 8,
    phash_distance: int = 10,
    central_phash_distance: int = 10,
    directional_phash_distance: int = 8,
) -> dict[str, Any]:
    if not ARCHIVE_SHA256.fullmatch(archive_sha256):
        raise ProposalError("archive sha256 must be a lowercase 64-character digest")
    if (not 0 <= dhash_distance <= 8 or not 0 <= phash_distance <= 16
            or not 0 <= central_phash_distance <= 16
            or not 0 <= directional_phash_distance <= 16):
        raise ProposalError("perceptual hash distance is outside the safe range")
    decisions = load_decisions(decisions_path)
    records = scan_records(root)
    by_id = {record["recordId"]: record for record in records}
    if len(by_id) != len(records):
        raise ProposalError("hashed record ids are duplicated")
    candidates: list[dict[str, Any]] = []

    def add(method: str, members: tuple[dict[str, Any], dict[str, Any]], **extra: Any) -> None:
        member_ids = [member["recordId"] for member in members]
        identifier = candidate_id(method, member_ids)
        review = decisions.get(identifier, {
            "decision": "unresolved",
            "rationale": "candidate has not been reviewed",
            "reviewer": "none",
        })
        candidates.append({
            "candidateId": identifier,
            "method": method,
            "members": [public_member(member) for member in sorted(members, key=lambda row: row["recordId"])],
            "crossSplit": members[0]["split"] != members[1]["split"],
            "review": review,
            **extra,
        })

    content_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        content_groups[record["contentSHA256"]].append(record)
        if record["sourceNameUsable"] and record["sourceNameToken"]:
            source_groups[record["sourceNameToken"]].append(record)
    for members in content_groups.values():
        for left, right in itertools.combinations(members, 2):
            add("exact_content", (left, right), automaticEvidence="same_bytes")
    for members in source_groups.values():
        for left, right in itertools.combinations(members, 2):
            add("normalized_source_name", (left, right), automaticEvidence="review_only")
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left["contentSHA256"] == right["contentSHA256"]:
                continue
            dhash_hamming = (left["dHash"] ^ right["dHash"]).bit_count()
            if dhash_hamming <= dhash_distance:
                add("perceptual_dhash", (left, right), hammingDistance=dhash_hamming, automaticEvidence="review_only")
            phash_hamming = (left["pHash"] ^ right["pHash"]).bit_count()
            if phash_hamming <= phash_distance:
                add("perceptual_phash", (left, right), hammingDistance=phash_hamming, automaticEvidence="review_only")
            central_phash_hamming = (left["centralPHash"] ^ right["centralPHash"]).bit_count()
            if central_phash_hamming <= central_phash_distance:
                add(
                    "central_crop_phash", (left, right),
                    hammingDistance=central_phash_hamming,
                    automaticEvidence="review_only",
                )
            for crop_name in DIRECTIONAL_PHASH_CROPS:
                directional_hamming = (
                    left["directionalPHashes"][crop_name]
                    ^ right["directionalPHashes"][crop_name]
                ).bit_count()
                if directional_hamming <= directional_phash_distance:
                    add(
                        f"directional_crop_phash_{crop_name}", (left, right),
                        hammingDistance=directional_hamming,
                        automaticEvidence="review_only",
                    )

    known_ids = {row["candidateId"] for row in candidates}
    unknown_decisions = sorted(set(decisions) - known_ids)
    if unknown_decisions:
        raise ProposalError("review decisions refer to unknown candidate ids")

    pair_rows: dict[tuple[str, str], dict[str, Any]] = {}
    dsu = DisjointSet(list(by_id))
    for row in candidates:
        member_ids = tuple(sorted(member["recordId"] for member in row["members"]))
        pair = pair_rows.setdefault(member_ids, {
            "pairId": digest_token("source-person-review-pair\0" + "\0".join(member_ids)),
            "members": row["members"],
            "methods": [],
            "distances": {},
            "crossSplit": row["crossSplit"],
            "reviewDecisions": [],
            "candidateIdsByMethod": {},
        })
        pair["methods"].append(row["method"])
        pair["candidateIdsByMethod"][row["method"]] = row["candidateId"]
        if "hammingDistance" in row:
            pair["distances"][row["method"]] = row["hammingDistance"]
        pair["reviewDecisions"].append(row["review"])
        decision = row["review"]["decision"]
        if row["method"] == "exact_content" or decision in {"same_source", "same_source_or_person"}:
            dsu.union(*member_ids)

    review_pairs: list[dict[str, Any]] = []
    for pair in pair_rows.values():
        pair["methods"] = sorted(set(pair["methods"]))
        decisions_for_pair = {row["decision"] for row in pair.pop("reviewDecisions")}
        if "same_source_or_person" in decisions_for_pair or "same_source" in decisions_for_pair:
            status = "confirmed_same_source_or_person"
        elif pair["methods"] == ["exact_content"]:
            status = "confirmed_exact_content"
        elif decisions_for_pair == {"different_source"}:
            status = "reviewed_different_source"
        else:
            status = "unresolved"
        pair["status"] = status
        pair["priority"] = (
            "cross_split" if pair["crossSplit"] else "within_split"
        )
        review_pairs.append(pair)
    review_pairs.sort(key=lambda row: (
        row["status"] != "unresolved",
        row["priority"] != "cross_split",
        row["pairId"],
    ))

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        components[dsu.find(record["recordId"])].append(record)
    groups: list[dict[str, Any]] = []
    reviewed_records: set[str] = set()
    for members in components.values():
        public = [public_member(member) for member in sorted(members, key=lambda row: row["recordId"])]
        confirmed = len(members) > 1
        if confirmed:
            reviewed_records.update(member["recordId"] for member in members)
        member_ids = [member["recordId"] for member in members]
        groups.append({
            "groupId": digest_token("coverage-proposal-group\0" + "\0".join(sorted(member_ids))),
            "members": public,
            "status": "confirmed_group" if confirmed else "unreviewed_singleton",
            "targetSplit": None,
        })
    groups.sort(key=lambda row: row["groupId"])
    unresolved = [row for row in review_pairs if row["status"] == "unresolved"]
    counts_by_method = Counter(row["method"] for row in candidates)
    return {
        "schemaVersion": "acne-group-coverage-proposal-v1",
        "dataset": {
            "archiveSHA256": archive_sha256,
            "images": len(records),
            "splits": {split: sum(record["split"] == split for record in records) for split in SPLITS},
        },
        "methods": {
            "exactContentSHA256": True,
            "usableNormalizedSourceName": True,
            "perceptualDHashMaxDistance": dhash_distance,
            "perceptualPHashMaxDistance": phash_distance,
            "centralCropPHashFraction": 0.8,
            "centralCropPHashMaxDistance": central_phash_distance,
            "directionalCropPHashBoxes": {
                name: list(crop) for name, crop in DIRECTIONAL_PHASH_CROPS.items()
            },
            "directionalCropPHashMaxDistance": directional_phash_distance,
            "perceptualMatchesAreReviewOnly": True,
        },
        "candidateCountsByMethod": {
            method: counts_by_method[method]
            for method in (
                "exact_content", "normalized_source_name", "perceptual_dhash",
                "perceptual_phash", "central_crop_phash",
                *(f"directional_crop_phash_{name}" for name in DIRECTIONAL_PHASH_CROPS),
            )
        },
        "reviewQueue": {
            "pairs": review_pairs,
            "totalPairs": len(review_pairs),
            "unresolvedPairs": len(unresolved),
            "unresolvedCrossSplitPairs": sum(row["crossSplit"] for row in unresolved),
            "unresolvedWithinSplitPairs": sum(not row["crossSplit"] for row in unresolved),
        },
        "coverageProposal": {
            "groups": groups,
            "groupsTotal": len(groups),
            "confirmedGroups": sum(group["status"] == "confirmed_group" for group in groups),
            "unreviewedSingletons": sum(group["status"] == "unreviewed_singleton" for group in groups),
            "reviewedRecords": len(reviewed_records),
            "unreviewedRecords": len(records) - len(reviewed_records),
            "allRecordsRepresentedExactlyOnce": sum(len(group["members"]) for group in groups) == len(records),
            "targetSplitsAssigned": False,
            "readyForGroupLockedSplit": False,
        },
        "decision": {
            "personOrSourceGroupCoverageEstablished": False,
            "trainingAuthorized": False,
            "reason": (
                "REVIEW_CANDIDATE_PAIRS_AND_SINGLETON_IDENTITIES_BEFORE_SPLIT"
                if unresolved else "REVIEW_SINGLETON_IDENTITIES_BEFORE_SPLIT"
            ),
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "recordIdsAreHashed": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-resolver-output", type=Path)
    parser.add_argument("--dhash-distance", type=int, default=8)
    parser.add_argument("--phash-distance", type=int, default=10)
    parser.add_argument("--central-phash-distance", type=int, default=10)
    parser.add_argument("--directional-phash-distance", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        result = build_proposal(
            args.dataset, args.archive_sha256, args.decisions,
            dhash_distance=args.dhash_distance,
            phash_distance=args.phash_distance,
            central_phash_distance=args.central_phash_distance,
            directional_phash_distance=args.directional_phash_distance,
        )
    except (ProposalError, ValueError) as exc:
        print(f"group coverage proposal blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.private_resolver_output:
        private = private_record_resolver(args.dataset)
        args.private_resolver_output.parent.mkdir(parents=True, exist_ok=True)
        args.private_resolver_output.write_text(
            json.dumps(private, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
