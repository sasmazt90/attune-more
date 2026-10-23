"""Build a conservative, source-photo-grouped under-eye research export.

Only explicit ``<source-id>_left`` / ``<source-id>_right`` filename pairs are
grouped. Short numeric stems and perceptual-hash proximity are deliberately not
used: on this source they collide across unrelated people. A pair already in
one split is left untouched; a pair spanning splits is moved wholly to train,
so validation/test do not contain the other crop of an exposed source photo.

The input ZIP is read-only. Image bytes, categories and annotation geometry are
preserved. COCO ids are regenerated because records can move between files.
The result remains research data: grouping a source photo does not establish
person independence, label correctness, consent, or individual-photo rights.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


SPLITS = ("train", "valid", "test")
PAIR_RE = re.compile(
    r"(?:^[0-9a-f]{8}-)?(?P<source_id>[0-9]{5,})_(?P<side>left|right)_jpg$",
    re.IGNORECASE,
)


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("UNSAFE_ARCHIVE_MEMBER")
    return path


def source_photo_pair(file_name):
    stem = PurePosixPath(file_name).stem.split(".rf.", 1)[0]
    match = PAIR_RE.fullmatch(stem)
    return match.group("source_id") if match else None


def read_source(path):
    rows = []
    categories = None
    readmes = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ZIP_MEMBER")
        for name in names:
            safe_member(name)
            if re.search(r"README.*\.txt$", name, re.IGNORECASE):
                readmes[name] = archive.read(name)
        for split in SPLITS:
            annotation_name = f"{split}/_annotations.coco.json"
            data = json.loads(archive.read(annotation_name))
            if categories is None:
                categories = data["categories"]
            elif categories != data["categories"]:
                raise ValueError("CATEGORY_DRIFT")
            by_image = collections.defaultdict(list)
            for annotation in data["annotations"]:
                by_image[annotation["image_id"]].append(annotation)
            for image in data["images"]:
                member = f"{split}/{safe_member(image['file_name'])}"
                payload = archive.read(member)
                rows.append({
                    "sourceSplit": split,
                    "fileName": image["file_name"],
                    "image": image,
                    "imageBytes": payload,
                    "imageSHA256": sha256_bytes(payload),
                    "annotations": by_image[image["id"]],
                    "sourcePhotoPair": source_photo_pair(image["file_name"]),
                })
    return rows, categories, readmes


def assign_splits(rows):
    pairs = collections.defaultdict(list)
    for index, row in enumerate(rows):
        if row["sourcePhotoPair"]:
            pairs[row["sourcePhotoPair"]].append(index)

    reviewed_pairs = []
    unpaired = []
    moved = []
    for pair_id, indices in sorted(pairs.items()):
        if len(indices) == 1:
            unpaired.append({
                "sourcePhotoPair": pair_id,
                "member": rows[indices[0]]["fileName"],
                "sourceSplit": rows[indices[0]]["sourceSplit"],
            })
            continue
        if len(indices) != 2:
            raise ValueError(f"UNEXPECTED_PAIR_SIZE:{pair_id}:{len(indices)}")
        sides = {
            re.search(r"_(left|right)_jpg", rows[index]["fileName"], re.IGNORECASE).group(1).lower()
            for index in indices
        }
        if sides != {"left", "right"}:
            raise ValueError(f"PAIR_SIDES_INVALID:{pair_id}")
        source_splits = sorted({rows[index]["sourceSplit"] for index in indices})
        cross_split = len(source_splits) > 1
        reviewed_pairs.append({
            "sourcePhotoPair": pair_id,
            "sourceSplits": source_splits,
            "crossSplit": cross_split,
            "members": [rows[index]["fileName"] for index in indices],
        })
        for index in indices:
            row = rows[index]
            row["assignedSplit"] = "train" if cross_split else row["sourceSplit"]
            if row["assignedSplit"] != row["sourceSplit"]:
                moved.append({
                    "fileName": row["fileName"],
                    "sourceSplit": row["sourceSplit"],
                    "assignedSplit": row["assignedSplit"],
                    "reason": "CROSS_SPLIT_SOURCE_PHOTO_PAIR_TO_TRAIN",
                    "sourcePhotoPair": pair_id,
                })
    for row in rows:
        row.setdefault("assignedSplit", row["sourceSplit"])
    return reviewed_pairs, unpaired, moved


def write_export(source, destination, rows, categories, readmes):
    buckets = {split: [] for split in SPLITS}
    for row in rows:
        buckets[row["assignedSplit"]].append(row)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name, payload in sorted(readmes.items()):
            output.writestr(name, payload)
        output.writestr(
            "README.attune.txt",
            "Research-only under-eye source export. Explicit left/right source-photo pairs are kept in one split; cross-split pairs are moved wholly to train. Image bytes and polygon geometry are preserved. This does not establish person independence, semantic approval, consent, or individual-photo rights.\n",
        )
        for split in SPLITS:
            images, annotations = [], []
            for image_id, row in enumerate(sorted(buckets[split], key=lambda item: item["fileName"])):
                image = dict(row["image"])
                image["id"] = image_id
                images.append(image)
                output.writestr(f"{split}/{row['fileName']}", row["imageBytes"])
                for annotation in row["annotations"]:
                    item = dict(annotation)
                    item["id"] = len(annotations)
                    item["image_id"] = image_id
                    annotations.append(item)
            output.writestr(
                f"{split}/_annotations.coco.json",
                json.dumps({"images": images, "annotations": annotations, "categories": categories}, separators=(",", ":")),
            )


def verify_export(path, source_rows):
    output_rows, categories, _ = read_source(path)
    source_by_name = {row["fileName"]: row for row in source_rows}
    output_by_name = {row["fileName"]: row for row in output_rows}
    if set(source_by_name) != set(output_by_name):
        raise ValueError("IMAGE_SET_CHANGED")
    for name, source in source_by_name.items():
        output = output_by_name[name]
        if source["imageSHA256"] != output["imageSHA256"]:
            raise ValueError("IMAGE_BYTES_CHANGED:" + name)
        source_shapes = sorted(
            (item["category_id"], item.get("bbox"), item.get("segmentation"), item.get("area"), item.get("iscrowd"))
            for item in source["annotations"]
        )
        output_shapes = sorted(
            (item["category_id"], item.get("bbox"), item.get("segmentation"), item.get("area"), item.get("iscrowd"))
            for item in output["annotations"]
        )
        if source_shapes != output_shapes:
            raise ValueError("ANNOTATION_GEOMETRY_CHANGED:" + name)
        if source["assignedSplit"] != output["sourceSplit"]:
            raise ValueError("SPLIT_ASSIGNMENT_MISMATCH:" + name)
    return output_rows, categories


def prepare(source, destination):
    rows, categories, readmes = read_source(source)
    reviewed_pairs, unpaired, moved = assign_splits(rows)
    write_export(source, destination, rows, categories, readmes)
    output_rows, _ = verify_export(destination, rows)
    image_counts = collections.Counter(row["sourceSplit"] for row in output_rows)
    class_names = {item["id"]: item["name"] for item in categories}
    class_counts = collections.Counter()
    for row in output_rows:
        for annotation in row["annotations"]:
            class_counts[(row["sourceSplit"], class_names[annotation["category_id"]])] += 1
    cross_pairs = [item for item in reviewed_pairs if item["crossSplit"]]
    return {
        "schemaVersion": 1,
        "methodVersion": "under-eye-source-photo-split-v1",
        "sourceArchive": Path(source).name,
        "sourceArchiveSHA256": sha256_file(source),
        "outputArchive": Path(destination).name,
        "outputArchiveSHA256": sha256_file(destination),
        "images": len(rows),
        "annotations": sum(len(row["annotations"]) for row in rows),
        "splits": dict(image_counts),
        "classCountsBySplit": {
            split: {label: class_counts[(split, label)] for label in sorted(class_names.values())}
            for split in SPLITS
        },
        "reviewedSourcePhotoPairs": reviewed_pairs,
        "unpairedExplicitCrops": unpaired,
        "crossSplitSourcePhotoPairs": len(cross_pairs),
        "movedToTrain": moved,
        "review": {
            "reviewerType": "assistant_visual_review_not_expert",
            "pairRule": "Only explicit left/right filenames visually consistent with the same source photo.",
            "rejectedAutomaticRules": [
                "dHash proximity: two cross-split candidates were visually different people/photos",
                "short numeric stem grouping: cross-split collisions included visibly unrelated people/photos",
            ],
        },
        "acceptance": {
            "sourceArchiveMutated": False,
            "imageBytesPreserved": True,
            "annotationGeometryPreserved": True,
            "explicitSourcePhotoPairsSplitSafe": True,
            "personIndependent": False,
            "expertReviewed": False,
            "cameraAccepted": False,
            "trainingAuthorizedByThisReceipt": True,
            "productAccepted": False,
        },
        "limitations": [
            "Grouping source-photo crops does not prove person-independent splits.",
            "Unrelated photos of the same person can remain across splits.",
            "Assistant visual review is not clinical or expert label approval.",
            "Publisher CC BY 4.0 metadata does not independently establish rights for each photo.",
            "The test split remains a source test, not an independent Attune camera benchmark.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.receipt.exists():
        parser.error("Output/receipt already exists; choose new versioned paths")
    receipt = prepare(args.source, args.output)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("images", "annotations", "splits", "crossSplitSourcePhotoPairs")}, sort_keys=True))


if __name__ == "__main__":
    main()
