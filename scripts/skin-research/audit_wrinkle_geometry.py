"""Audit one COCO class without turning broad/rectangular regions into creases.

This is a geometry/provenance audit, not clinical annotation review. Normalized
area thresholds describe source masks only; they do not define severity or a
product operating threshold.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path, PurePosixPath
import statistics
import zipfile


SPLITS = ("train", "valid", "test")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def polygon_area(values):
    points = list(zip(values[::2], values[1::2]))
    if points and points[-1] == points[0]:
        points.pop()
    if len(points) < 3:
        return 0.0, points
    return abs(sum(a[0] * b[1] - a[1] * b[0]
                   for a, b in zip(points, points[1:] + points[:1]))) / 2, points


def is_axis_rectangle(points):
    return (len(points) == 4 and len({point[0] for point in points}) == 2
            and len({point[1] for point in points}) == 2)


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return {}
    def value(fraction):
        return ordered[round((len(ordered) - 1) * fraction)]
    return {name: value(fraction) for name, fraction in
            (("min", 0), ("p25", .25), ("median", .5), ("p75", .75),
             ("p90", .9), ("max", 1))}


def audit(path, class_name):
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
            for annotation in data["annotations"]:
                if categories[annotation["category_id"]] != class_name:
                    continue
                image = images[annotation["image_id"]]
                segmentation = annotation.get("segmentation") or []
                if not isinstance(segmentation, list):
                    geometry = "rle"
                    mask_area = None
                    points = 0
                else:
                    parts = [polygon_area(part) for part in segmentation]
                    rectangle = any(is_axis_rectangle(part_points) for _, part_points in parts)
                    geometry = "rectangle-polygon" if rectangle else "polygon"
                    mask_area = sum(area for area, _ in parts)
                    points = sum(len(part_points) for _, part_points in parts)
                x, y, width, height = annotation["bbox"]
                image_area = image["width"] * image["height"]
                rows.append({
                    "split": split,
                    "fileName": image["file_name"],
                    "annotationId": annotation["id"],
                    "geometry": geometry,
                    "polygonPoints": points,
                    "maskAreaRatio": None if mask_area is None else mask_area / image_area,
                    "bboxAreaRatio": width * height / image_area,
                    "centroid": [(x + width / 2) / image["width"],
                                 (y + height / 2) / image["height"]],
                })
    polygons = [row for row in rows if row["geometry"] == "polygon"]
    areas = [row["maskAreaRatio"] for row in polygons]
    bbox_areas = [row["bboxAreaRatio"] for row in polygons]
    point_counts = [row["polygonPoints"] for row in polygons]
    split_counts = collections.Counter(row["split"] for row in rows)
    image_counts = collections.Counter(row["split"] for row in
                                        {(row["split"], row["fileName"]): row for row in rows}.values())
    bins = collections.Counter()
    for row in polygons:
        x_bin = min(2, int(row["centroid"][0] * 3))
        y_bin = min(2, int(row["centroid"][1] * 3))
        bins[f"x{x_bin}-y{y_bin}"] += 1
    return {
        "schemaVersion": 1,
        "methodVersion": "wrinkle-source-geometry-audit-v1",
        "sourceArchive": Path(path).name,
        "sourceArchiveSHA256": sha256_file(path),
        "class": class_name,
        "annotations": len(rows),
        "imagesWithClass": len({(row["split"], row["fileName"]) for row in rows}),
        "annotationsBySplit": dict(split_counts),
        "imagesBySplit": dict(image_counts),
        "geometry": dict(collections.Counter(row["geometry"] for row in rows)),
        "nonRectanglePolygonAreaRatio": quantiles(areas),
        "nonRectanglePolygonBBoxAreaRatio": quantiles(bbox_areas),
        "nonRectanglePolygonPointCount": quantiles(point_counts),
        "descriptiveBuckets": {
            "maskAreaAtMost2Percent": sum(value <= .02 for value in areas),
            "maskAreaAtLeast8Percent": sum(value >= .08 for value in areas),
            "maskAreaAtLeast40Percent": sum(value >= .40 for value in areas),
            "bboxAreaAtLeast25Percent": sum(value >= .25 for value in bbox_areas),
        },
        "normalizedCentroidBins": dict(sorted(bins.items())),
        "filenameContext": {
            "annotationsOnWrinkleNamedImages": sum("wrinkle_skin" in row["fileName"].lower() for row in rows),
            "annotationsOnOtherNamedImages": sum("wrinkle_skin" not in row["fileName"].lower() for row in rows),
        },
        "rows": rows,
        "acceptance": {
            "geometryAudited": True,
            "crowsFeetDefinitionSupported": False,
            "specializedCrowsFeetTrainingAuthorized": False,
            "genericWrinkleTrainingAuthorized": False,
            "expertSemanticReview": False,
            "cameraAccepted": False,
            "productAccepted": False,
        },
        "limitations": [
            "Image-normalized mask location is not facial anatomy without landmarks.",
            "A valid polygon can still be a broad skin region rather than wrinkle/crease truth.",
            "Axis-aligned rectangle polygons are box supervision, not exact wrinkle masks.",
            "The source class does not distinguish crow's feet from forehead, under-eye, cheek or mouth lines.",
            "No expression, pose, person-independence or native Attune camera acceptance is established.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--class-name", default="wrinkles")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; choose a new versioned receipt")
    result = audit(args.source, args.class_name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("annotations", "imagesWithClass", "annotationsBySplit", "geometry")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
