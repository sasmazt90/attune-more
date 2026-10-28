#!/usr/bin/env python3
"""Build the source-geometry release artifact without promoting weak truth.

Two inputs are intentionally separate:

* the committed source-mapping receipt produces a public, blocked preflight
  from the geometry that has actually been observed; and
* a private opaque manifest can produce ``skin-source-geometry-audit-v1``
  only after every selected archive is enumerated and its release-eligible
  geometry has zero unresolved issues.

Archive names, paths, URLs, raw annotation payloads, model proposals and
reviewer identities are never accepted in the private manifest or emitted in
the public artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


INPUT_METHOD = "skin-source-geometry-audit-input-v1"
PREFLIGHT_METHOD = "skin-source-geometry-audit-preflight-v1"
ARTIFACT_METHOD = "skin-source-geometry-audit-v1"
SOURCE_RECEIPT_METHOD = "source-mapping-release-receipt-v2"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "path", "url", "uri", "archive", "archiveName",
    "archivePath", "image", "images", "annotation", "annotations",
    "polygon", "polygons", "bbox", "mask", "reviewer", "reviewerId",
    "prediction", "predictions", "modelProposal", "modelProposals",
}
ALLOWED_SAFETY_KEYS = {
    "boxesAcceptedAsPixelTruth",
    "rectanglePolygonsAcceptedAsPixelTruth",
    "modelGeometryAcceptedAsExpertTruth",
    "missingLabelsAcceptedAsNegativeOrNormal",
}


class GeometryInputError(ValueError):
    """Raised when geometry evidence violates the release contract."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None and value != "0" * 64


def _is_opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE_RE.fullmatch(value) is not None


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GeometryInputError(f"{field} must be a nonnegative integer")
    return value


def _reject_private_payload(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS and key not in ALLOWED_SAFETY_KEYS:
                raise GeometryInputError(f"{location} contains private or proposal payload fields")
            _reject_private_payload(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_payload(child, f"{location}[{index}]")


def summarize_committed_facts(receipt: dict[str, Any]) -> dict[str, Any]:
    """Turn the current committed audits into a truthful blocked preflight."""
    if receipt.get("schemaVersion") != 2 or receipt.get("methodVersion") != SOURCE_RECEIPT_METHOD:
        raise GeometryInputError("source mapping receipt identity changed")
    facts = receipt.get("auditFacts")
    if not isinstance(facts, dict):
        raise GeometryInputError("source mapping audit facts are missing")
    clean3 = facts.get("clean3", {})
    acquisition = facts.get("acquisition", {})
    review = facts.get("sourceReview", {})
    under_eye = facts.get("underEye", {})
    clean_geometry = clean3.get("geometry", {})
    try:
        box_only = sum(int(clean_geometry[label]["box"]) for label in ("Dry-Skin", "Oily-Skin", "Skin-Redness"))
        clean_valid = sum(int(clean_geometry[label]["validPolygon"]) for label in ("Dry-Skin", "Oily-Skin", "Skin-Redness"))
        known_invalid = int(acquisition["geometryIssueCount"])
        rectangle = int(acquisition["redness"]["rectanglePolygon"])
        acquisition_valid = int(acquisition["redness"]["validPolygon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeometryInputError("committed geometry facts are incomplete") from exc
    blockers = [
        "selected_archive_geometry_coverage_incomplete",
        "known_invalid_geometry_present",
        "box_only_annotations_ineligible_for_pixel_truth",
        "rectangle_polygons_ineligible_for_pixel_truth",
        "expert_semantic_geometry_review_incomplete",
    ]
    if clean3.get("apiExportCountDiscrepancyUnresolved") is True:
        blockers.append("clean3_api_export_count_discrepancy_unresolved")
    if under_eye.get("sourcePersonCoverageComplete") is not True:
        blockers.append("under_eye_source_person_coverage_incomplete")
    if review.get("expertReviewed") is not True:
        blockers.append("selected_pair_expert_review_incomplete")
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "sourceFactsMethodVersion": SOURCE_RECEIPT_METHOD,
        "selectedArchiveCount": 0,
        "knownAuditedImages": int(acquisition.get("images", 0)) + int(clean3.get("actualImages", 0)) + int(under_eye.get("images", 0)),
        "knownValidPolygonCount": acquisition_valid + clean_valid + int(under_eye.get("darkcirclePolygons", 0)) + int(under_eye.get("eyebagPolygons", 0)),
        "knownInvalidGeometryIssueCount": known_invalid,
        "knownBoxOnlyAnnotationCount": box_only,
        "knownRectanglePolygonCount": rectangle,
        "allGeometryAudited": False,
        "boxesAcceptedAsPixelTruth": False,
        "rectanglePolygonsAcceptedAsPixelTruth": False,
        "modelGeometryAcceptedAsExpertTruth": False,
        "missingLabelsAcceptedAsNegativeOrNormal": False,
        "readyForReleaseArtifact": False,
        "decision": "blocked",
        "blockers": sorted(blockers),
    }


def evaluate_private_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate an opaque private manifest and return a public preflight."""
    if not isinstance(manifest, dict):
        raise GeometryInputError("manifest must be a JSON object")
    _reject_private_payload(manifest)
    if manifest.get("schemaVersion") not in (None, 1):
        raise GeometryInputError("private manifest schema changed")
    if manifest.get("methodVersion") not in (None, INPUT_METHOD):
        raise GeometryInputError("private manifest method changed")
    blockers: list[str] = []
    release_ref = manifest.get("releaseRef")
    registry_ref = manifest.get("sourceRegistryRef")
    if not _is_opaque(release_ref):
        blockers.append("release_ref_missing_or_invalid")
    if not _is_opaque(registry_ref):
        blockers.append("source_registry_ref_missing_or_invalid")
    expected_count = manifest.get("selectedArchiveCountExpected")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
        expected_count = None
        blockers.append("selected_archive_count_expected_missing")
    entries = manifest.get("selectedArchives", [])
    if not isinstance(entries, list):
        raise GeometryInputError("selectedArchives must be a list")
    if not entries:
        blockers.append("selected_archive_geometry_registry_empty")
    if expected_count is not None and len(entries) != expected_count:
        blockers.append("selected_archive_count_mismatch")

    opaque_ids: list[str] = []
    evidence_hashes: list[str] = []
    canonical: list[dict[str, Any]] = []
    total_images = 0
    total_annotations = 0
    total_polygons = 0
    total_invalid = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise GeometryInputError(f"selected archive {index} must be an object")
        allowed = {
            "opaqueId", "geometryEvidenceSHA256", "imageCount", "annotationCount",
            "releaseEligiblePolygonCount", "releaseEligibleInvalidGeometryIssueCount",
            "allImagesAndAnnotationsEnumerated", "actualGeometryAudited",
            "expertSemanticsBound", "rightsApprovedForGeometryReview",
            "boxesAcceptedAsPixelTruth", "rectanglePolygonsAcceptedAsPixelTruth",
            "modelGeometryAcceptedAsExpertTruth", "missingLabelsAcceptedAsNegativeOrNormal",
        }
        if set(entry) - allowed:
            raise GeometryInputError(f"selected archive {index} contains unsupported fields")
        opaque_id = entry.get("opaqueId")
        evidence_hash = entry.get("geometryEvidenceSHA256")
        if not _is_opaque(opaque_id):
            blockers.append(f"selected_archive_{index}_opaque_id_invalid")
        if not _is_sha256(evidence_hash):
            blockers.append(f"selected_archive_{index}_evidence_sha256_invalid")
        counts = {
            "imageCount": _nonnegative_int(entry.get("imageCount"), f"selected archive {index} imageCount"),
            "annotationCount": _nonnegative_int(entry.get("annotationCount"), f"selected archive {index} annotationCount"),
            "releaseEligiblePolygonCount": _nonnegative_int(entry.get("releaseEligiblePolygonCount"), f"selected archive {index} releaseEligiblePolygonCount"),
            "releaseEligibleInvalidGeometryIssueCount": _nonnegative_int(entry.get("releaseEligibleInvalidGeometryIssueCount"), f"selected archive {index} releaseEligibleInvalidGeometryIssueCount"),
        }
        total_images += counts["imageCount"]
        total_annotations += counts["annotationCount"]
        total_polygons += counts["releaseEligiblePolygonCount"]
        total_invalid += counts["releaseEligibleInvalidGeometryIssueCount"]
        for field in ("allImagesAndAnnotationsEnumerated", "actualGeometryAudited", "expertSemanticsBound", "rightsApprovedForGeometryReview"):
            if entry.get(field) is not True:
                blockers.append(f"selected_archive_{index}_{field}_incomplete")
        for field in ALLOWED_SAFETY_KEYS:
            if entry.get(field) is not False:
                raise GeometryInputError(f"unsafe geometry truth policy: {field}")
        if counts["releaseEligibleInvalidGeometryIssueCount"] != 0:
            blockers.append(f"selected_archive_{index}_invalid_geometry_present")
        if counts["imageCount"] == 0 or counts["annotationCount"] == 0:
            blockers.append(f"selected_archive_{index}_geometry_inventory_empty")
        if _is_opaque(opaque_id):
            opaque_ids.append(opaque_id)
        if _is_sha256(evidence_hash):
            evidence_hashes.append(evidence_hash)
        if _is_opaque(opaque_id) and _is_sha256(evidence_hash):
            canonical.append({"opaqueId": opaque_id, "geometryEvidenceSHA256": evidence_hash, **counts})
    if len(opaque_ids) != len(set(opaque_ids)):
        raise GeometryInputError("selected archive opaque IDs must be unique")
    if len(evidence_hashes) != len(set(evidence_hashes)):
        raise GeometryInputError("geometry evidence hashes must be unique")
    blockers = sorted(set(blockers))
    digest = hashlib.sha256(_canonical_bytes(sorted(canonical, key=lambda item: item["opaqueId"]))).hexdigest() if canonical else None
    return {
        "schemaVersion": 1,
        "methodVersion": PREFLIGHT_METHOD,
        "releaseRef": release_ref if _is_opaque(release_ref) else None,
        "sourceRegistryRef": registry_ref if _is_opaque(registry_ref) else None,
        "selectedArchiveCount": len(entries),
        "imageCount": total_images,
        "annotationCount": total_annotations,
        "releaseEligiblePolygonCount": total_polygons,
        "releaseEligibleInvalidGeometryIssueCount": total_invalid,
        "geometryRegistryDigest": digest,
        "allGeometryAudited": not blockers,
        "boxesAcceptedAsPixelTruth": False,
        "rectanglePolygonsAcceptedAsPixelTruth": False,
        "modelGeometryAcceptedAsExpertTruth": False,
        "missingLabelsAcceptedAsNegativeOrNormal": False,
        "readyForReleaseArtifact": not blockers,
        "decision": "ready" if not blockers else "blocked",
        "blockers": blockers,
    }


def build_release_artifact(manifest: dict[str, Any]) -> dict[str, Any]:
    preflight = evaluate_private_manifest(manifest)
    if not preflight["readyForReleaseArtifact"]:
        raise GeometryInputError("geometry audit is incomplete: " + ", ".join(preflight["blockers"]))
    return {
        "schemaVersion": 1,
        "methodVersion": ARTIFACT_METHOD,
        "releaseRef": preflight["releaseRef"],
        "sourceRegistryRef": preflight["sourceRegistryRef"],
        "selectedArchiveCount": preflight["selectedArchiveCount"],
        "geometryRegistryDigest": preflight["geometryRegistryDigest"],
        "imageCount": preflight["imageCount"],
        "annotationCount": preflight["annotationCount"],
        "releaseEligiblePolygonCount": preflight["releaseEligiblePolygonCount"],
        "allGeometryAudited": True,
        "invalidGeometryIssueCount": 0,
        "boxesAcceptedAsPixelTruth": False,
        "rectanglePolygonsAcceptedAsPixelTruth": False,
        "modelGeometryAcceptedAsExpertTruth": False,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-mapping-receipt", type=Path)
    source.add_argument("--private-manifest", type=Path)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if args.source_mapping_receipt is not None:
        receipt = json.loads(args.source_mapping_receipt.read_text(encoding="utf-8"))
        preflight = summarize_committed_facts(receipt)
        if args.artifact_output is not None:
            raise GeometryInputError("committed partial facts cannot emit a release artifact")
    else:
        manifest = json.loads(args.private_manifest.read_text(encoding="utf-8"))
        preflight = evaluate_private_manifest(manifest)
        if args.artifact_output is not None:
            _write_json(args.artifact_output, build_release_artifact(manifest))
    _write_json(args.preflight_output, preflight)
    return 0 if preflight["readyForReleaseArtifact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
