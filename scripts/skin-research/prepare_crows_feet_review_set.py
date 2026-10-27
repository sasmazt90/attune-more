"""Build a clean, group-safe *review* package for the crows_feet source.

This intentionally does not declare a train-ready dataset. Images without a
``crows_feet`` annotation are not copied because the source has not established
that absence means an evaluated negative. Invalid polygons are quarantined, not
repaired, and source-photo groups are kept in a single split.
"""
import argparse
import collections
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from PIL import Image

from audit_roadmap_archives import file_digest, geometry, safe_member


SPLITS = ("train", "valid", "test")
METHOD = "crows-feet-positive-review-package-v1"


def source_stem(file_name):
    """Remove Roboflow's transform fingerprint, retaining the source-name hint."""
    stem = PurePosixPath(file_name).stem
    return re.sub(r"\.rf\.[0-9a-f]{8,}$", "", stem, flags=re.IGNORECASE)


def decoded_hash(data):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        rgb = image.convert("RGB")
        header = f"RGB:{rgb.width}:{rgb.height}:".encode()
        return hashlib.sha256(header + rgb.tobytes()).hexdigest()


class Groups:
    def __init__(self, count):
        self.parent = list(range(count))

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def assign_splits(group_ids):
    """Deterministic 70/15/15 assignment by groups, never by transformed image."""
    ordered = sorted(group_ids, key=lambda value: hashlib.sha256(value.encode()).hexdigest())
    count = len(ordered)
    train_end = round(count * .70)
    valid_end = train_end + round(count * .15)
    return {value: ("train" if index < train_end else
                    "valid" if index < valid_end else "test")
            for index, value in enumerate(ordered)}


def prepare(source, output_zip):
    source = Path(source)
    output_zip = Path(output_zip)
    if output_zip.exists():
        raise FileExistsError("OUTPUT_EXISTS")
    source_before = file_digest(source)
    rows = []
    quarantined = []
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            safe_member(name)
        for split in SPLITS:
            data = json.loads(archive.read(f"{split}/_annotations.coco.json"))
            categories = {item["id"]: item["name"] for item in data["categories"]}
            class_ids = {item for item, name in categories.items() if name == "crows_feet"}
            if len(class_ids) != 1:
                raise ValueError("CROWS_FEET_CLASS_MISSING_OR_AMBIGUOUS")
            images = {item["id"]: item for item in data["images"]}
            annotations = collections.defaultdict(list)
            for annotation in data["annotations"]:
                if annotation["category_id"] in class_ids:
                    annotations[annotation["image_id"]].append(annotation)
            for image_id, candidates in annotations.items():
                image = images[image_id]
                name = f"{split}/{image['file_name']}"
                raw = archive.read(name)
                valid = []
                for annotation in candidates:
                    status = geometry(annotation, image["width"], image["height"])
                    if status["validMask"]:
                        valid.append(annotation)
                    else:
                        quarantined.append({
                            "sourceSplit": split,
                            "fileName": image["file_name"],
                            "annotationId": annotation["id"],
                            "reason": status.get("maskReason", status["kind"]),
                        })
                if valid:
                    rows.append({
                        "sourceSplit": split,
                        "image": image,
                        "annotations": valid,
                        "bytes": raw,
                        "sourceStem": source_stem(image["file_name"]),
                        "decodedSHA256": decoded_hash(raw),
                    })

    groups = Groups(len(rows))
    for field in ("sourceStem", "decodedSHA256"):
        seen = {}
        for index, row in enumerate(rows):
            value = row[field]
            if value in seen:
                groups.union(index, seen[value])
            else:
                seen[value] = index
    members = collections.defaultdict(list)
    for index in range(len(rows)):
        members[groups.find(index)].append(index)
    group_ids = {}
    for root, indices in members.items():
        identity = "\n".join(sorted(
            f"{rows[index]['sourceStem']}:{rows[index]['decodedSHA256']}" for index in indices
        ))
        group_ids[root] = hashlib.sha256(identity.encode()).hexdigest()
    allocation = assign_splits(group_ids.values())

    outputs = {split: {"images": [], "annotations": [],
                       "categories": [{"id": 1, "name": "crows_feet", "supercategory": "none"}]}
               for split in SPLITS}
    source_group_splits = collections.defaultdict(set)
    annotation_id = collections.Counter()
    image_id = collections.Counter()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as target:
        for index, row in enumerate(rows):
            group_id = group_ids[groups.find(index)]
            split = allocation[group_id]
            source_group_splits[group_id].add(split)
            image_id[split] += 1
            new_image_id = image_id[split]
            output_name = f"{row['sourceSplit']}__{row['image']['file_name']}"
            target.writestr(f"{split}/{output_name}", row["bytes"])
            outputs[split]["images"].append({
                **row["image"], "id": new_image_id, "file_name": output_name,
            })
            for annotation in row["annotations"]:
                annotation_id[split] += 1
                outputs[split]["annotations"].append({
                    **annotation, "id": annotation_id[split],
                    "image_id": new_image_id, "category_id": 1,
                })
        for split, data in outputs.items():
            target.writestr(f"{split}/_annotations.coco.json",
                            json.dumps(data, ensure_ascii=False, separators=(",", ":")))

        receipt = {
            "schemaVersion": 1,
            "methodVersion": METHOD,
            "sourceArchive": source.name,
            "sourceArchiveSHA256": source_before,
            "class": "crows_feet",
            "scope": "positive-only annotation review; not a train-ready negative-complete dataset",
            "validImages": len(rows),
            "validAnnotations": sum(len(row["annotations"]) for row in rows),
            "quarantinedAnnotations": len(quarantined),
            "quarantinedImages": len({(row["sourceSplit"], row["fileName"])
                                      for row in quarantined}),
            "quarantineReasons": dict(sorted(collections.Counter(
                row["reason"] for row in quarantined).items())),
            "sourceGroups": len(members),
            "splits": {split: {"images": len(outputs[split]["images"]),
                                "annotations": len(outputs[split]["annotations"]),
                                "groups": len({group_ids[groups.find(index)] for index, row in enumerate(rows)
                                               if allocation[group_ids[groups.find(index)]] == split})}
                       for split in SPLITS},
            "crossSplitGroupsAfter": sum(len(value) > 1 for value in source_group_splits.values()),
            "sourceBytesUnchanged": file_digest(source) == source_before,
            "trainingAuthorized": False,
            "negativeCompletenessVerified": False,
            "expertSemanticReview": False,
            "cameraAccepted": False,
            "productAccepted": False,
            "quarantine": quarantined,
            "limitations": [
                "Only images with at least one valid crows_feet polygon are included.",
                "Unlabelled images are not converted into negative examples.",
                "Filename stems and exact decoded pixels are grouping evidence, not person identity.",
                "A valid polygon does not replace expert semantic review.",
            ],
        }
        target.writestr("REVIEW_MANIFEST.json",
                        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    receipt["outputArchive"] = output_zip.name
    receipt["outputArchiveSHA256"] = file_digest(output_zip)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error("receipt exists; choose a new versioned path")
    receipt = prepare(args.source, args.output_zip)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in
                      ("validImages", "validAnnotations", "quarantinedAnnotations",
                       "sourceGroups", "splits", "trainingAuthorized")}, sort_keys=True))


if __name__ == "__main__":
    main()
