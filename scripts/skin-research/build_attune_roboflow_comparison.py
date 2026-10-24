#!/usr/bin/env python3
"""Build a fail-closed Attune/Roboflow comparison receipt.

The tool deliberately does not run either system.  It accepts independently
captured, source-bound results and refuses to emit a comparison unless the six
generated FRONT inputs and the current merged Attune contract are complete.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


CURRENT_PRODUCT_COMMIT = "7463eef112c5a40f7cd01192b6d1f4e9fa6ab285"
CURRENT_ENDPOINT = "/api/local-health/skin"
CURRENT_CRITERIA = (
    "tone",
    "oil",
    "redness",
    "acne",
    "sag",
    "dry",
    "lines",
    "dark",
    "bags",
)
REGIONS = (
    "forehead",
    "rightCheek",
    "leftCheek",
    "nose",
    "chin",
    "periorbital",
)
THRESHOLDS = (0.08, 0.15, 0.20, 0.30, 0.50)
ROBOFLOW_CLASSES = ("akne", "gozenek", "kirisiklik", "kizariklik", "pul")
ROBOFLOW_PACKAGE = "7ee34fce76456d9ff4cfe6e7049aad1e"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when evidence cannot support a comparison."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ContractError(f"{label} must be a lowercase SHA-256 hex string")
    return value


def _front_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = manifest.get("source", {})
    package = manifest.get("capturePackage", {})
    if source.get("declaredGenerated") is not True:
        raise ContractError("capture source is not declared generated")
    if source.get("expertGroundTruth") is not False:
        raise ContractError("generated package must not claim expert ground truth")
    if source.get("realCameraCapture") is not False:
        raise ContractError("generated package must not claim real-camera evidence")
    if package.get("subjects") != 6 or package.get("images") != 18:
        raise ContractError("capture package must contain six complete triplets")
    if package.get("completeTriplets") is not True:
        raise ContractError("capture package is incomplete")

    rows: dict[str, dict[str, Any]] = {}
    subjects = manifest.get("subjects")
    if not isinstance(subjects, list) or len(subjects) != 6:
        raise ContractError("manifest must list exactly six subjects")
    for subject in subjects:
        if not isinstance(subject, dict) or not isinstance(subject.get("subjectKey"), str):
            raise ContractError("manifest subject is malformed")
        key = subject["subjectKey"]
        front = subject.get("poses", {}).get("front")
        if key in rows or not isinstance(front, dict):
            raise ContractError(f"missing or duplicate FRONT manifest row for {key}")
        row = {
            "filename": front.get("filename"),
            "sha256": _sha(front.get("sha256"), f"{key} FRONT sha256"),
            "width": front.get("width"),
            "height": front.get("height"),
        }
        if not isinstance(row["filename"], str):
            raise ContractError(f"{key} FRONT filename is missing")
        if not all(isinstance(row[name], int) and row[name] > 0 for name in ("width", "height")):
            raise ContractError(f"{key} FRONT dimensions are invalid")
        rows[key] = row
    return rows


def _threshold_counts(predictions: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    kept = [row for row in predictions if float(row.get("confidence", -1)) >= threshold]
    classes = Counter(row.get("class") for row in kept)
    unknown = sorted(str(value) for value in classes if value not in ROBOFLOW_CLASSES)
    if unknown:
        raise ContractError(f"unknown Roboflow classes: {', '.join(unknown)}")
    return {
        "total": len(kept),
        "byClass": {name: classes[name] for name in ROBOFLOW_CLASSES if classes[name]},
    }


def _validate_roboflow(
    evidence: dict[str, Any], fronts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    model = evidence.get("model", {})
    resolved = model.get("resolvedModel", {})
    if model.get("requestedModelId") != "ciltanalizi-rfa8m/12":
        raise ContractError("unexpected Roboflow model ID")
    if resolved.get("model_package_id") != ROBOFLOW_PACKAGE:
        raise ContractError("Roboflow model package is not the pinned package")
    if float(model.get("requestedConfidence", -1)) != 0.08:
        raise ContractError("Roboflow evidence was not captured at the 8% review floor")
    if evidence.get("source", {}).get("expertGroundTruth") is not False:
        raise ContractError("Roboflow generated-image evidence cannot be ground truth")

    by_subject: dict[str, dict[str, Any]] = {}
    calls = evidence.get("calls")
    if not isinstance(calls, list) or len(calls) != len(fronts):
        raise ContractError("Roboflow evidence must contain one call per FRONT image")
    filename_to_subject = {row["filename"]: key for key, row in fronts.items()}
    aggregate = {str(value): {"total": 0, "byClass": Counter()} for value in THRESHOLDS}
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("input"), dict):
            raise ContractError("malformed Roboflow call")
        input_row = call["input"]
        key = filename_to_subject.get(input_row.get("filename"))
        if key is None or key in by_subject:
            raise ContractError("Roboflow input is unknown or duplicated")
        expected = fronts[key]
        if input_row.get("sha256") != expected["sha256"]:
            raise ContractError(f"Roboflow input hash mismatch for {key}")
        if (input_row.get("width"), input_row.get("height")) != (
            expected["width"],
            expected["height"],
        ):
            raise ContractError(f"Roboflow input dimensions mismatch for {key}")
        predictions = call.get("predictions")
        if not isinstance(predictions, list):
            raise ContractError(f"Roboflow predictions missing for {key}")
        counts: dict[str, Any] = {}
        for threshold in THRESHOLDS:
            label = str(threshold)
            derived = _threshold_counts(predictions, threshold)
            reported = call.get("thresholdCounts", {}).get(label)
            if reported != derived:
                raise ContractError(f"Roboflow threshold counts do not recompute for {key} at {label}")
            counts[label] = derived
            aggregate[label]["total"] += derived["total"]
            aggregate[label]["byClass"].update(derived["byClass"])
        by_subject[key] = counts

    reported_aggregate = evidence.get("aggregateThresholdCounts", {})
    for threshold in THRESHOLDS:
        label = str(threshold)
        derived = {
            "total": aggregate[label]["total"],
            "byClass": {
                name: aggregate[label]["byClass"][name]
                for name in ROBOFLOW_CLASSES
                if aggregate[label]["byClass"][name]
            },
        }
        if reported_aggregate.get(label) != derived:
            raise ContractError(f"Roboflow aggregate does not recompute at {label}")
    return by_subject


def _measurement_summary(general: dict[str, Any], subject: str) -> tuple[dict[str, Any], dict[str, Any]]:
    measurements = general.get("measurements")
    if not isinstance(measurements, list):
        raise ContractError(f"Attune general.measurements missing for {subject}")
    by_id: dict[str, Any] = {}
    for row in measurements:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ContractError(f"Attune measurement malformed for {subject}")
        if row["id"] in by_id:
            raise ContractError(f"duplicate Attune criterion {row['id']} for {subject}")
        by_id[row["id"]] = row
    if set(by_id) != set(CURRENT_CRITERIA):
        raise ContractError(f"Attune criterion inventory mismatch for {subject}")

    summary = {}
    for criterion in CURRENT_CRITERIA:
        row = by_id[criterion]
        quality = row.get("quality")
        value = row.get("value")
        if quality not in ("valid", "insufficient"):
            raise ContractError(f"invalid Attune quality for {subject}/{criterion}")
        if quality == "valid" and not isinstance(value, (int, float)):
            raise ContractError(f"valid Attune value missing for {subject}/{criterion}")
        if quality == "insufficient" and value is not None:
            raise ContractError(f"insufficient Attune value must be null for {subject}/{criterion}")
        summary[criterion] = {
            "quality": quality,
            "value": value,
            "limitationCode": row.get("limitationCode"),
            "methodVersion": row.get("methodVersion"),
        }

    skin_type = general.get("skinType")
    if not isinstance(skin_type, dict):
        raise ContractError(f"separate Attune skin type missing for {subject}")
    if skin_type.get("quality") not in ("valid", "insufficient"):
        raise ContractError(f"invalid Attune skin type quality for {subject}")
    return summary, {
        "quality": skin_type.get("quality"),
        "value": skin_type.get("value"),
        "confidence": skin_type.get("confidence"),
        "limitationCode": skin_type.get("limitationCode"),
        "methodVersion": skin_type.get("methodVersion"),
    }


def _validate_attune(
    bundle: dict[str, Any], fronts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if bundle.get("sourceCommit") != CURRENT_PRODUCT_COMMIT:
        raise ContractError("Attune bundle is not pinned to the current merged product commit")
    if bundle.get("endpoint") != CURRENT_ENDPOINT:
        raise ContractError("Attune bundle endpoint mismatch")
    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        raise ContractError("Attune execution provenance is missing")
    if provenance.get("sourceType") != "generated-still-image-replay":
        raise ContractError("Attune evidence is not the declared generated replay")
    if provenance.get("baseCommit") != CURRENT_PRODUCT_COMMIT:
        raise ContractError("Attune provenance base commit mismatch")
    if provenance.get("productOrModelOrThresholdChanges") is not False:
        raise ContractError("Attune execution changed product/model/threshold behavior")
    if not SHA256_RE.fullmatch(str(provenance.get("localRevisionSHA256", ""))):
        raise ContractError("Attune local execution revision is unidentified")
    captures = bundle.get("captures")
    if not isinstance(captures, list) or len(captures) != len(fronts):
        raise ContractError("Attune bundle must contain all six FRONT responses")

    result: dict[str, dict[str, Any]] = {}
    hash_to_subject = {row["sha256"]: key for key, row in fronts.items()}
    for capture in captures:
        if not isinstance(capture, dict):
            raise ContractError("malformed Attune capture")
        input_row = capture.get("input")
        if not isinstance(input_row, dict):
            raise ContractError("Attune input is missing")
        jpeg_hash = input_row.get("jpegSha256")
        subject = hash_to_subject.get(jpeg_hash)
        if subject is None or subject in result:
            raise ContractError("Attune FRONT hash is unknown or duplicated")
        if capture.get("pose") != "FRONT":
            raise ContractError(f"Attune capture is not FRONT for {subject}")
        response = capture.get("response")
        if not isinstance(response, dict):
            raise ContractError(f"Attune input/response missing for {subject}")
        expected = fronts[subject]
        if not isinstance(input_row.get("filename"), str):
            raise ContractError(f"Attune filename missing for {subject}")
        if jpeg_hash != expected["sha256"]:
            raise ContractError(f"Attune JPEG identity mismatch for {subject}")
        rgba_hash = _sha(input_row.get("decodedRgbaSha256"), f"{subject} decoded RGBA sha256")
        if response.get("photoId") != rgba_hash:
            raise ContractError(f"Attune photoId mismatch for {subject}")
        if (response.get("sourceWidth"), response.get("sourceHeight")) != (
            expected["width"],
            expected["height"],
        ):
            raise ContractError(f"Attune source dimensions mismatch for {subject}")
        if response.get("storage") != "volatile-memory-only":
            raise ContractError(f"unexpected Attune analyzer storage receipt for {subject}")
        regional = response.get("measurements")
        if not isinstance(regional, dict) or not all(name in regional for name in REGIONS):
            raise ContractError(f"Attune regional inventory incomplete for {subject}")
        if not isinstance(response.get("maps"), dict) or not isinstance(response.get("contours"), dict):
            raise ContractError(f"Attune map/contour contract missing for {subject}")
        general = response.get("general")
        if not isinstance(general, dict):
            raise ContractError(f"Attune FRONT overview missing for {subject}")
        criteria, skin_type = _measurement_summary(general, subject)
        result[subject] = {
            "captureLabel": capture.get("subjectKey") or capture.get("personId"),
            "captureFilename": input_row["filename"],
            "photoId": rgba_hash,
            "methodVersion": response.get("methodVersion"),
            "criteria": criteria,
            "skinType": skin_type,
            "regionalInventory": list(REGIONS),
            "mapCount": len(response["maps"]),
            "contourCount": len(response["contours"]),
        }
    return result


def _markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Attune current-product / Roboflow proposal comparison",
        "",
        "This receipt compares source-bound outputs; it is not an accuracy score.",
        "Generated images are integration/proposal-review evidence only, not real-camera or expert truth.",
        "",
        "| Subject | Attune valid / 9 | Skin type | Roboflow 8% | Roboflow 50% |",
        "| --- | ---: | --- | ---: | ---: |",
    ]
    for row in receipt["subjects"]:
        valid = sum(1 for value in row["attune"]["criteria"].values() if value["quality"] == "valid")
        skin_type = row["attune"]["skinType"]
        skin_label = skin_type["value"] if skin_type["quality"] == "valid" else "not evaluated"
        lines.append(
            f"| {row['subjectKey']} | {valid} | {skin_label} | "
            f"{row['roboflow']['0.08']['total']} | {row['roboflow']['0.5']['total']} |"
        )
    lines.extend(
        [
            "",
            "Attune values retain their per-criterion quality and limitation receipts in the JSON output.",
            "Roboflow counts are proposals recomputed from the single 8% response per image.",
            "Neither system's output is treated as ground truth for the other.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_value(row: dict[str, Any]) -> str:
    if row.get("quality") != "valid":
        return "—"
    value = row.get("value")
    return f"{value:.2f}" if isinstance(value, (int, float)) else "—"


def _html(receipt: dict[str, Any]) -> str:
    criteria_headers = "".join(f"<th>{html.escape(name)}</th>" for name in CURRENT_CRITERIA)
    attune_rows = []
    rf_rows = []
    for item in receipt["subjects"]:
        subject = html.escape(item["subjectKey"])
        criteria = "".join(
            f'<td title="{html.escape(str(item["attune"]["criteria"][name].get("limitationCode") or "valid"))}">'
            f'{_format_value(item["attune"]["criteria"][name])}</td>'
            for name in CURRENT_CRITERIA
        )
        skin = item["attune"]["skinType"]
        skin_label = skin.get("value") if skin.get("quality") == "valid" else "—"
        attune_rows.append(f"<tr><th>{subject}</th>{criteria}<td>{html.escape(str(skin_label))}</td></tr>")
        threshold_cells = []
        for threshold in THRESHOLDS:
            summary = item["roboflow"][str(threshold)]
            detail = ", ".join(f"{name}: {count}" for name, count in summary["byClass"].items()) or "none"
            threshold_cells.append(f'<td title="{html.escape(detail)}">{summary["total"]}</td>')
        rf_rows.append(f"<tr><th>{subject}</th>{''.join(threshold_cells)}</tr>")
    provenance = receipt["attuneExecutionProvenance"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Attune / Roboflow source-bound comparison</title>
<style>body{{font:14px system-ui,sans-serif;margin:2rem;color:#172033}}h1,h2{{line-height:1.2}}.note{{max-width:80rem;padding:1rem;background:#f4f6f8;border-left:4px solid #64748b}}.wrap{{overflow:auto;margin:1rem 0 2rem}}table{{border-collapse:collapse;min-width:60rem}}th,td{{border:1px solid #cbd5e1;padding:.5rem;text-align:right;white-space:nowrap}}thead th,tbody th{{background:#f8fafc}}tbody th{{text-align:left}}code{{font-size:.85em}}</style>
</head><body><h1>Attune / Roboflow source-bound comparison</h1>
<p class="note"><strong>Not an accuracy score.</strong> These are generated replay images without expert ground truth or physical-camera acceptance. Attune values and Roboflow proposal counts are different outputs and are not directly comparable.</p>
<p>Attune base commit: <code>{receipt['sourceCommit']}</code><br>Execution revision: <code>{html.escape(str(provenance['localRevisionSHA256']))}</code><br>Endpoint: <code>{html.escape(receipt['endpoint'])}</code></p>
<h2>Attune current-product outputs</h2><div class="wrap"><table><thead><tr><th>Profile</th>{criteria_headers}<th>skin type</th></tr></thead><tbody>{''.join(attune_rows)}</tbody></table></div>
<h2>Roboflow proposal counts by confidence floor</h2><div class="wrap"><table><thead><tr><th>Profile</th><th>8%</th><th>15%</th><th>20%</th><th>30%</th><th>50%</th></tr></thead><tbody>{''.join(rf_rows)}</tbody></table></div>
<p>Hover a Roboflow count to see its class breakdown. A lower confidence floor surfaces more review proposals; it does not make those proposals correct.</p>
</body></html>"""


def build(manifest: dict[str, Any], roboflow: dict[str, Any], attune: dict[str, Any]) -> dict[str, Any]:
    fronts = _front_manifest(manifest)
    rf = _validate_roboflow(roboflow, fronts)
    current = _validate_attune(attune, fronts)
    return {
        "schemaVersion": 1,
        "comparisonReady": True,
        "sourceCommit": CURRENT_PRODUCT_COMMIT,
        "endpoint": CURRENT_ENDPOINT,
        "attuneExecutionProvenance": attune["provenance"],
        "subjects": [
            {"subjectKey": key, "attune": current[key], "roboflow": rf[key]}
            for key in sorted(fronts)
        ],
        "claims": {
            "accuracyMeasured": False,
            "expertGroundTruth": False,
            "realCameraAcceptance": False,
            "thresholdCalibrationAuthorized": False,
            "productionActivationAuthorized": False,
            "crossSystemScoresDirectlyComparable": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--roboflow", type=Path, required=True)
    parser.add_argument("--attune", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--output-html", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = build(_load(args.manifest), _load(args.roboflow), _load(args.attune))
    except ContractError as exc:
        print(f"comparison blocked: {exc}", file=sys.stderr)
        return 2
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_md.write_text(_markdown(receipt), encoding="utf-8")
    if args.output_html is not None:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(_html(receipt), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
