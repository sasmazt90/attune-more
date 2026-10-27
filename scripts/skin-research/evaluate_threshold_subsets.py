#!/usr/bin/env python3
"""Summarise one detector response at several confidence thresholds.

The lowest-threshold response is reused so threshold comparisons do not trigger
additional hosted inference calls or mix predictions from different model runs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _iou(a: dict, b: dict) -> float:
    ax0, ay0 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
    ax1, ay1 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
    bx0, by0 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
    bx1, by1 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    intersection = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(
        0.0, min(ay1, by1) - max(ay0, by0)
    )
    union = a["width"] * a["height"] + b["width"] * b["height"] - intersection
    return intersection / union if union > 0 else 0.0


def summarise(predictions: list[dict], thresholds: list[float]) -> dict:
    ordered = sorted(set(thresholds))
    if not ordered or ordered[0] < 0 or ordered[-1] > 1:
        raise ValueError("thresholds must be within [0, 1]")
    result = {}
    for threshold in ordered:
        rows = [row for row in predictions if float(row["confidence"]) >= threshold]
        result[f"{threshold:.2f}"] = {
            "total": len(rows),
            "byClass": dict(sorted(Counter(row["class"] for row in rows).items())),
        }
    conflicts = []
    for index, first in enumerate(predictions):
        for second in predictions[index + 1 :]:
            if first["class"] == second["class"]:
                continue
            overlap = _iou(first, second)
            if overlap >= 0.9:
                conflicts.append(
                    {
                        "classes": sorted([first["class"], second["class"]]),
                        "iou": overlap,
                        "confidences": [first["confidence"], second["confidence"]],
                    }
                )
    return {"thresholds": result, "nearIdenticalCrossClassBoxes": conflicts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--thresholds", default="0.08,0.15,0.20,0.30,0.50")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text("utf-8"))
    result = payload.get("result", payload)
    summary = summarise(
        result.get("predictions", []),
        [float(value) for value in args.thresholds.split(",")],
    )
    summary["model"] = result.get("resolved_model")
    summary["inferenceId"] = result.get("inference_id")
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, "utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
