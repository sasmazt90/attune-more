"""Render a deterministic, mask-aware review board from a COCO ZIP.

The board is evidence for human semantic review.  It never promotes polygon
geometry, filename similarity, or a source class name to expert truth.
"""
import argparse
import collections
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from PIL import Image, ImageDraw, ImageFont


SPLITS = ("train", "valid", "test")
RF_SUFFIX = re.compile(r"\.rf\.[^.]+$", re.IGNORECASE)


def source_stem(file_name):
    """Return the pre-Roboflow filename stem used only as a review hint."""
    return RF_SUFFIX.sub("", PurePosixPath(file_name).stem)


def polygon_area(values):
    points = list(zip(values[::2], values[1::2]))
    if len(points) < 3:
        return 0.0
    return abs(sum(a[0] * b[1] - a[1] * b[0]
                   for a, b in zip(points, points[1:] + points[:1]))) / 2


def load_rows(path, class_name):
    rows = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or "\\" in name or ":" in name:
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
        for split in SPLITS:
            data = json.loads(archive.read(f"{split}/_annotations.coco.json"))
            images = {item["id"]: item for item in data["images"]}
            categories = {item["id"]: item["name"] for item in data["categories"]}
            grouped = collections.defaultdict(list)
            for annotation in data["annotations"]:
                if categories[annotation["category_id"]] == class_name:
                    grouped[annotation["image_id"]].append(annotation)
            for image_id, annotations in grouped.items():
                image = images[image_id]
                area = 0.0
                for annotation in annotations:
                    segmentation = annotation.get("segmentation") or []
                    if isinstance(segmentation, list):
                        area += sum(polygon_area(part) for part in segmentation)
                rows.append({
                    "split": split,
                    "fileName": image["file_name"],
                    "path": f"{split}/{image['file_name']}",
                    "width": image["width"],
                    "height": image["height"],
                    "sourceStem": source_stem(image["file_name"]),
                    "annotations": annotations,
                    "annotationCount": len(annotations),
                    "maskAreaRatio": area / (image["width"] * image["height"]),
                })
    return rows


def choose_rows(rows, limit):
    by_stem = collections.defaultdict(list)
    for row in rows:
        by_stem[row["sourceStem"]].append(row)
    selected = []
    reasons = {}
    for stem, members in sorted(by_stem.items()):
        splits = {row["split"] for row in members}
        if len(splits) > 1:
            for row in sorted(members, key=lambda item: (item["split"], item["fileName"]))[:2]:
                if row["path"] not in reasons:
                    selected.append(row)
                    reasons[row["path"]] = "cross-split-filename-candidate"
            if len(selected) >= min(limit, 8):
                break
    buckets = (
        ("small-mask", lambda value: value <= .002),
        ("medium-mask", lambda value: .002 < value <= .02),
        ("large-mask", lambda value: value > .02),
    )
    for label, predicate in buckets:
        candidates = sorted((row for row in rows if predicate(row["maskAreaRatio"])),
                            key=lambda item: (item["split"], item["maskAreaRatio"], item["fileName"]))
        if not candidates:
            continue
        indexes = sorted({0, len(candidates) // 3, 2 * len(candidates) // 3, len(candidates) - 1})
        for index in indexes:
            row = candidates[index]
            if row["path"] not in reasons:
                selected.append(row)
                reasons[row["path"]] = label
            if len(selected) >= limit:
                return selected, reasons
    return selected[:limit], reasons


def render(path, rows, reasons, output, columns=4, tile=320):
    rows_count = (len(rows) + columns - 1) // columns
    board = Image.new("RGB", (columns * tile, rows_count * tile), "#101827")
    font = ImageFont.load_default()
    with zipfile.ZipFile(path) as archive:
        for index, row in enumerate(rows):
            image = Image.open(io.BytesIO(archive.read(row["path"]))).convert("RGB")
            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for annotation in row["annotations"]:
                segmentation = annotation.get("segmentation") or []
                if isinstance(segmentation, list):
                    for part in segmentation:
                        points = list(zip(part[::2], part[1::2]))
                        if len(points) >= 3:
                            draw.polygon(points, fill=(255, 45, 85, 70), outline=(255, 45, 85, 255), width=2)
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
            image.thumbnail((tile, tile - 52), Image.Resampling.LANCZOS)
            x = (index % columns) * tile
            y = (index // columns) * tile
            board.paste(image, (x + (tile - image.width) // 2, y))
            label = (f"{row['split']} | {reasons[row['path']]} | "
                     f"n={row['annotationCount']} area={row['maskAreaRatio']:.3f}\n"
                     f"{row['fileName'][:46]}")
            ImageDraw.Draw(board).multiline_text((x + 4, y + tile - 48), label,
                                                 font=font, fill="white", spacing=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output, quality=92)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--class-name", default="wrinkles")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.output.exists() or args.selection.exists():
        parser.error("output exists; choose new versioned outputs")
    rows = load_rows(args.source, args.class_name)
    selected, reasons = choose_rows(rows, args.limit)
    render(args.source, selected, reasons, args.output)
    receipt = {
        "schemaVersion": 1,
        "methodVersion": "wrinkle-source-review-board-v1",
        "sourceArchive": args.source.name,
        "class": args.class_name,
        "selectionIsExpertTruth": False,
        "rows": [{key: row[key] for key in
                  ("split", "fileName", "sourceStem", "annotationCount", "maskAreaRatio")}
                 | {"reason": reasons[row["path"]]} for row in selected],
        "limitations": [
            "Filename grouping is a leakage-review hint, not a person identity claim.",
            "The board does not establish clinical label validity or camera performance.",
        ],
    }
    args.selection.parent.mkdir(parents=True, exist_ok=True)
    args.selection.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected": len(selected), "board": str(args.output)}))


if __name__ == "__main__":
    main()
