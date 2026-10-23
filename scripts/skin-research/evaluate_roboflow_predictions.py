"""Reproduce held-out COCO metrics from saved Roboflow MCP inference JSON.

No API calls, training, threshold fitting, or changes to production acceptance.
Input is a list of {suffix, image: {filename, id}, response: {result: ...}}.
All frozen split images must appear exactly once for each model. Predictions
remain in original source pixels; category names, not ordinal IDs, are joined.
"""
import argparse
import contextlib
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


def identity(name):
    match = re.match(r"^[0-9a-f]{64}", name)
    if not match:
        raise ValueError("Missing immutable source filename identity")
    return match[0]


def evaluate(archive, rows, split):
    if not isinstance(rows, list) or not rows:
        raise ValueError("No inference records; empty input is not an evaluation")
    with zipfile.ZipFile(archive) as source:
        truth = json.loads(source.read(f"{split}/_annotations.coco.json"))
    used_categories = {a["category_id"] for a in truth["annotations"]}
    truth["categories"] = [c for c in truth["categories"] if c["id"] in used_categories]
    names = {c["name"]: c["id"] for c in truth["categories"]}
    images = {identity(im["file_name"]): im for im in truth["images"]}
    if len(images) != len(truth["images"]):
        raise ValueError("Duplicate source identity in frozen split")
    report = {"split": split, "images": len(images), "annotations": len(truth["annotations"]),
              "exportSHA256": hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
              "metric": "pycocotools COCOeval bbox, maxDets=[1,10,100], IoU=.50:.05:.95",
              "inference": {"confidenceFloor": .05, "overlap": .5, "serverCandidateCap": 300},
              "scope": "Publisher annotations; not clinical accuracy or camera-domain acceptance",
              "models": {}}
    for model in sorted({r["suffix"] for r in rows}):
        records = [r for r in rows if r["suffix"] == model]
        seen, detections, capped, packages = set(), [], 0, set()
        for row in records:
            key = identity(row["image"]["filename"])
            if key not in images or key in seen:
                raise ValueError("Unexpected or duplicate split image")
            seen.add(key)
            result = row.get("response", {}).get("result")
            if not result or "error" in row:
                raise ValueError("Inference failed; incomplete evaluations cannot pass")
            image, measured = images[key], result["image"]
            if measured != {"width": image["width"], "height": image["height"]}:
                raise ValueError("Source/export dimensions differ; implicit rescaling prohibited")
            packages.add(result["resolved_model"]["model_package_id"])
            capped += len(result["predictions"]) >= 300
            for p in result["predictions"]:
                if p["class"] not in names:
                    raise ValueError("Unknown category; silent remapping prohibited")
                values = [p[k] for k in ("x", "y", "width", "height", "confidence")]
                if not np.isfinite(values).all() or p["width"] <= 0 or p["height"] <= 0:
                    raise ValueError("Invalid prediction geometry/score")
                detections.append({"image_id": image["id"], "category_id": names[p["class"]],
                                   "bbox": [p["x"]-p["width"]/2, p["y"]-p["height"]/2,
                                            p["width"], p["height"]], "score": p["confidence"]})
        if seen != set(images):
            raise ValueError("Missing frozen split images")
        if not detections:
            raise ValueError("No detections; do not silently produce an empty COCO result")
        with contextlib.redirect_stdout(io.StringIO()):
            gt = COCO(); gt.dataset = truth; gt.createIndex()
            evaluator = COCOeval(gt, gt.loadRes(detections), "bbox")
            evaluator.evaluate(); evaluator.accumulate(); evaluator.summarize()
        precision = evaluator.eval["precision"]
        per_class = []
        for k, category_id in enumerate(evaluator.params.catIds):
            values = precision[:, :, k, 0, -1]
            at50 = values[0]
            per_class.append({"class": next(n for n, i in names.items() if i == category_id),
                              "AP50": float(at50[at50 >= 0].mean()),
                              "AP50to95": float(values[values >= 0].mean())})
        report["models"][model] = {"AP50": float(evaluator.stats[1]),
                                    "AP50to95": float(evaluator.stats[0]),
                                    "AP75": float(evaluator.stats[2]),
                                    "APSmall": float(evaluator.stats[3]),
                                    "APMedium": float(evaluator.stats[4]),
                                    "APLarge": float(evaluator.stats[5]),
                                    "predictionCount": len(detections),
                                    "imagesAtServerCandidateCap": int(capped),
                                    "resolvedPackages": sorted(packages),
                                    "classes": per_class}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--split", choices=["valid", "test"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = evaluate(args.export, json.loads(Path(args.predictions).read_text()), args.split)
    Path(args.out).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"split": args.split, "models": {m: {k: v for k, v in r.items() if k != "classes"}
                                                     for m, r in output["models"].items()}}, indent=2))
