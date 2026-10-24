#!/usr/bin/env python3
"""Audit the self-contained Attune/Roboflow comparison HTML.

The input HTML contains face images, overlays, masks, and individual boxes.  The
JSON receipt written by this script is intentionally privacy-safe: it records
only hashes, aggregate counts, model identities, and acceptance blockers.

This comparison is a generated still-image replay.  It must never be promoted
to physical-camera evidence or expert-labelled accuracy evidence.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


EXPECTED_V5_SOURCE_SHA256 = (
    "02c49ba5cbda603ddac24a176b42b618f3a913fe2171beb4ab316b7899d70af5"
)
EXPECTED_PHOTOS = {
    "01_england": {
        "jpeg": "2945ce637fefa6099fcef31f9ae19a548f7c2cd13dc010eb967267830f429184",
        "photoId": "817fbb60fdd162891c084182d884c16948de9319aad0462eaf59fcacaa7b6a73",
    },
    "02_germany": {
        "jpeg": "a44fb454da79908755e47dec3bdd027088fda38c4328503fd1dfd517ecfef12f",
        "photoId": "8cc2eb89919701a5a83ed102a5ebeadd621fb661920e05869cb44cf396d7f73b",
    },
    "03_kenya": {
        "jpeg": "b95d5cfd087c4248e31aa3463de1f8d64b52302c6ab1e814d9aabe29b08275fb",
        "photoId": "7ca73025c6f7c07d4f3a58da1bd4cbf8999fcad1b7b44fd37b96fececf22ea1f",
    },
    "04_scotland": {
        "jpeg": "334202b493c1e15877f13531919c390fb397dccb137873330d7934073584a8c8",
        "photoId": "8b693b24213d9b268b371a9f6bc80dba498dcf7e3cf748b791619402035634b3",
    },
    "05_turkey": {
        "jpeg": "4efd376516e2bcba8cf737824adfb30508f173e04363fc822bab860a38a80326",
        "photoId": "ca81128f4b229ad231ec7e04a1e1e81b916d0f7631a9f54b5af5272cbf0c1632",
    },
    "06_usa": {
        "jpeg": "70e4b5c2a6ba874b07f824190f72799506b1c3949161ea1033d9fa95b8254bce",
        "photoId": "2aa4baefe40f59683868517fa01b5b4994fb9d3220e7fcd5cafc17985312fedc",
    },
}
EXPECTED_MODEL_KEYS = {f"m{i}" for i in range(1, 11)}
EXPECTED_V5_METRIC_ID = "experimental-step0-verifier-v5-local-preview-v1"
DISPLAY_THRESHOLDS = [7, 11, 30, 33, 50]
ACCEPTED_MAP_LABELS = {"Dry", "Oily", "Redness", "Normal", "Unknown"}


class AuditError(ValueError):
    """Raised for corrupt, inconsistent, or unexpected source evidence."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _extract_data(html: str) -> dict[str, Any]:
    match = re.search(
        r"<script[^>]+id=[\"']data[\"'][^>]*>(.*?)</script>", html, re.DOTALL
    )
    if not match:
        raise AuditError("embedded application data was not found")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise AuditError(f"embedded application data is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError("embedded application data must be an object")
    return value


def _decode_data_url(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
        raise AuditError(f"{label} is not an embedded image data URL")
    header, encoded = value.split(",", 1)
    if ";base64" not in header:
        raise AuditError(f"{label} is not base64 encoded")
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise AuditError(f"{label} base64 is invalid") from exc


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def audit(
    path: Path,
    *,
    expected_sha256: str | None = None,
    library_file_id: str | None = None,
) -> dict[str, Any]:
    raw = path.read_bytes()
    html_sha = _sha256(raw)
    if expected_sha256 and html_sha != expected_sha256:
        raise AuditError("HTML SHA-256 mismatch")
    data = _extract_data(raw.decode("utf-8"))

    if data.get("v5SourceSHA256") != EXPECTED_V5_SOURCE_SHA256:
        raise AuditError("V5 source archive identity mismatch")
    if data.get("thresholds") != DISPLAY_THRESHOLDS:
        raise AuditError("display threshold inventory mismatch")

    models = data.get("models")
    photos = data.get("photos")
    metrics = data.get("metrics")
    if not isinstance(models, list) or not isinstance(photos, list) or not isinstance(metrics, list):
        raise AuditError("model, photo, or metric inventory is missing")

    model_by_key: dict[str, dict[str, Any]] = {}
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("key"), str):
            raise AuditError("malformed model row")
        key = model["key"]
        if key in model_by_key:
            raise AuditError(f"duplicate model key: {key}")
        if not isinstance(model.get("model_id"), str) or not model.get("classes"):
            raise AuditError(f"model identity/classes missing: {key}")
        model_by_key[key] = model
    if set(model_by_key) != EXPECTED_MODEL_KEYS:
        raise AuditError("expected ten pinned model keys")

    prediction_totals: Counter[str] = Counter()
    prediction_classes: dict[str, Counter[str]] = defaultdict(Counter)
    capped_photos: dict[str, list[str]] = defaultdict(list)
    photo_receipts: list[dict[str, Any]] = []
    observed_map_labels: set[str] = set()
    unknown_pixels = 0
    outside_tinted = 0

    if {photo.get("id") for photo in photos if isinstance(photo, dict)} != set(EXPECTED_PHOTOS):
        raise AuditError("photo inventory does not match the six generated FRONT inputs")

    for photo in sorted(photos, key=lambda row: row["id"]):
        photo_id = photo["id"]
        expected = EXPECTED_PHOTOS[photo_id]
        if photo.get("sha256") != expected["jpeg"] or photo.get("photoId") != expected["photoId"]:
            raise AuditError(f"source identity mismatch: {photo_id}")
        embedded = _decode_data_url(photo.get("image"), f"{photo_id} image")
        if _sha256(embedded) != expected["jpeg"]:
            raise AuditError(f"embedded image hash mismatch: {photo_id}")
        if photo.get("combinedStatus") != "complete_static_replay":
            raise AuditError(f"unexpected replay status: {photo_id}")

        width, height = photo.get("width"), photo.get("height")
        if not _finite_number(width) or not _finite_number(height) or width <= 0 or height <= 0:
            raise AuditError(f"invalid image dimensions: {photo_id}")
        predictions = photo.get("predictions")
        caps = photo.get("cap")
        if not isinstance(predictions, dict) or set(predictions) != EXPECTED_MODEL_KEYS:
            raise AuditError(f"prediction inventory mismatch: {photo_id}")
        if not isinstance(caps, dict) or set(caps) != EXPECTED_MODEL_KEYS:
            raise AuditError(f"cap inventory mismatch: {photo_id}")

        per_model: dict[str, int] = {}
        for model_key in sorted(EXPECTED_MODEL_KEYS):
            rows = predictions[model_key]
            if not isinstance(rows, list):
                raise AuditError(f"predictions are not a list: {photo_id}/{model_key}")
            cap = caps[model_key]
            if not isinstance(cap, dict) or cap.get("count") != len(rows):
                raise AuditError(f"cap count mismatch: {photo_id}/{model_key}")
            if len(rows) == 300:
                capped_photos[model_key].append(photo_id)
            allowed_classes = set(model_by_key[model_key]["classes"])
            per_model[model_key] = len(rows)
            prediction_totals[model_key] += len(rows)
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or row.get("cls") not in allowed_classes:
                    raise AuditError(f"unknown prediction class: {photo_id}/{model_key}/{index}")
                score = row.get("score")
                if not _finite_number(score) or not 0 <= score <= 1:
                    raise AuditError(f"invalid score: {photo_id}/{model_key}/{index}")
                box = [row.get(name) for name in ("x", "y", "w", "h")]
                if not all(_finite_number(value) for value in box):
                    raise AuditError(f"invalid box: {photo_id}/{model_key}/{index}")
                x, y, box_width, box_height = box
                if (
                    box_width < 0
                    or box_height < 0
                    or x - box_width / 2 < -1
                    or y - box_height / 2 < -1
                    or x + box_width / 2 > width + 1
                    or y + box_height / 2 > height + 1
                ):
                    raise AuditError(f"out-of-bounds box: {photo_id}/{model_key}/{index}")
                prediction_classes[model_key][row["cls"]] += 1

        skinmap = photo.get("skinmap")
        if not isinstance(skinmap, dict) or skinmap.get("validation") != "valid":
            raise AuditError(f"skin-map validation missing: {photo_id}")
        totals = skinmap.get("totals")
        anatomy_pixels = skinmap.get("anatomyPixels")
        if not isinstance(totals, dict) or not all(
            isinstance(value, int) and value >= 0 for value in totals.values()
        ):
            raise AuditError(f"skin-map totals invalid: {photo_id}")
        if sum(totals.values()) != anatomy_pixels:
            raise AuditError(f"skin-map pixel conservation failed: {photo_id}")
        if skinmap.get("outsideSkinTinted") != 0:
            raise AuditError(f"skin-map colors outside anatomy: {photo_id}")
        observed_map_labels.update(totals)
        unknown_pixels += totals.get("Unknown", 0)
        outside_tinted += skinmap["outsideSkinTinted"]
        photo_receipts.append(
            {
                "profile": photo_id,
                "jpegSha256": expected["jpeg"],
                "decodedRgbaSha256": expected["photoId"],
                "embeddedImageVerified": True,
                "predictionCounts": per_model,
                "skinMapTotals": totals,
                "skinMapPixelConservation": True,
            }
        )

    metrics_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    v5_metric_rows: list[dict[str, Any]] = []
    for row in metrics:
        if not isinstance(row, dict):
            raise AuditError("malformed metric row")
        if row.get("model") == "v5":
            if (
                row.get("modelId") != EXPECTED_V5_METRIC_ID
                or row.get("split") != "no-independent-test"
            ):
                raise AuditError("unexpected V5 metric scope")
            v5_metric_rows.append(row)
            continue
        if row.get("model") not in model_by_key:
            raise AuditError("metric row references an unknown model")
        model_key = row["model"]
        if row.get("modelId") != model_by_key[model_key]["model_id"]:
            raise AuditError(f"metric model identity mismatch: {model_key}")
        metrics_by_model[model_key].append(row)

    model_receipts: list[dict[str, Any]] = []
    for key in sorted(model_by_key):
        model = model_by_key[key]
        rows = metrics_by_model[key]
        evaluated = [row for row in rows if row.get("split") == "test"]
        model_receipts.append(
            {
                "key": key,
                "modelId": model["model_id"],
                "project": model.get("project"),
                "version": model.get("version"),
                "architecture": model.get("architecture"),
                "classes": model["classes"],
                "evaluationId": model.get("eval_id"),
                "metricSplits": sorted({row.get("split") for row in rows}),
                "testMetrics": [
                    {
                        "class": row.get("cls"),
                        "precision": row.get("precision"),
                        "recall": row.get("recall"),
                        "f1": row.get("f1"),
                        "threshold": row.get("testThreshold"),
                    }
                    for row in evaluated
                ],
                "predictionCountAtExplorationFloor": prediction_totals[key],
                "predictionCountsByClass": dict(sorted(prediction_classes[key].items())),
                "cappedProfiles": capped_photos[key],
            }
        )

    v5_evaluation = data.get("v5Evaluation")
    if not isinstance(v5_evaluation, dict):
        raise AuditError("V5 evaluation scope is missing")
    independent_test = v5_evaluation.get("independentUnusedFinalTest", {})
    current_images = v5_evaluation.get("current18GeneratedImages", {})
    physical_camera = False
    expert_truth = bool(current_images.get("groundTruthAvailable"))
    independent_final_test = bool(independent_test.get("available"))
    map_contract_matches = observed_map_labels.issubset(ACCEPTED_MAP_LABELS) and (
        "Sensitive" not in observed_map_labels
    )
    cap_hit_count = sum(len(items) for items in capped_photos.values())

    blockers = [
        "source_is_generated_still_image_replay_not_physical_camera",
        "current_six_profiles_have_no_expert_ground_truth",
        "no_independent_unused_final_test_metric_artifact",
    ]
    if cap_hit_count:
        blockers.append("exploration_inference_hit_300_prediction_cap")
    if not map_contract_matches:
        blockers.append("regional_map_uses_sensitive_label_instead_of_independent_redness_layer")
    if any(not receipt["testMetrics"] for receipt in model_receipts):
        blockers.append("some_selected_nas_variants_have_no_bound_test_evaluation")

    return {
        "schemaVersion": 1,
        "artifact": {
            "name": path.name,
            "sha256": html_sha,
            "bytes": len(raw),
            "libraryFileId": library_file_id,
        },
        "source": {
            "v5ResultArchiveSha256": EXPECTED_V5_SOURCE_SHA256,
            "sourceType": "generated-still-image-replay",
            "frontProfiles": len(photo_receipts),
            "frontHashesMatchAuditedV5Package": True,
            "physicalCameraAcceptance": physical_camera,
            "expertGroundTruth": expert_truth,
        },
        "integrity": {
            "embeddedImagesVerified": len(photo_receipts),
            "modelIdentitiesPinned": len(model_receipts),
            "boundingBoxesValid": True,
            "classesBoundToModels": True,
            "skinMapPixelConservation": True,
            "outsideSkinTintedPixels": outside_tinted,
        },
        "exploration": {
            "inferenceFloor": 0.05,
            "displayThresholdPercentages": DISPLAY_THRESHOLDS,
            "models": model_receipts,
            "cappedProfileModelPairs": cap_hit_count,
            "capValue": 300,
            "completeRecallClaimAllowed": False,
        },
        "regionalMap": {
            "acceptedContract": {
                "Dry": "blue",
                "Oily": "green",
                "Redness": "independent red contour/hatch",
                "Normal": "uncolored only when evaluated",
                "Unknown": "light gray and never normal",
            },
            "observedLabels": sorted(observed_map_labels),
            "unknownPixels": unknown_pixels,
            "unknownPreserved": unknown_pixels > 0,
            "contractMatches": map_contract_matches,
            "sensitiveMayStandInForRedness": False,
        },
        "evaluation": {
            "metricRowsBoundToExactModelId": True,
            "v5RowsWithoutIndependentTest": len(v5_metric_rows),
            "independentUnusedFinalTest": independent_final_test,
            "currentProfilesHaveGroundTruth": expert_truth,
            "accuracyMeasuredOnCurrentProfiles": False,
            "thresholdSelectionAuthorized": False,
            "productionActivationAuthorized": False,
        },
        "photos": photo_receipts,
        "acceptance": {
            "passed": False,
            "blockers": blockers,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--library-file-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = audit(
            args.html,
            expected_sha256=args.expected_sha256,
            library_file_id=args.library_file_id,
        )
    except (AuditError, OSError, UnicodeDecodeError) as exc:
        print(f"audit blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        "audit complete:",
        f"{receipt['source']['frontProfiles']} generated FRONT profiles,",
        f"{receipt['exploration']['cappedProfileModelPairs']} capped model/profile pairs,",
        "product acceptance blocked",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
