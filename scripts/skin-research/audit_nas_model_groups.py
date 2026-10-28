#!/usr/bin/env python3
"""Audit complete RF-DETR NAS groups without treating recommended as a winner.

The input is a privacy-safe provider snapshot.  The audit requires a complete
single page for each frozen modelGroup, validates sparse NAS metrics and
reports aggregate metric/latency leaders as observations only.  It cannot
authorize training, final-test evaluation, a per-class decision or activation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "nas-model-group-facts-v1"
RECOMMENDED_SEMANTICS = "flattened_union_only_not_accuracy_or_hardware_winner"
EXPECTED = {
    "attune-skin-acne-marks-pigmentation": {
        "version": 1,
        "trainingId": "5b632a5c12b76fcfe703",
        "modelGroup": "032w7Kc1N3tGyX43O8TN-5b632a5c12b76fcfe703-rfdetrNasGroup",
        "taskType": "object-detection",
        "modelType": "rfdetr-nas",
        "records": 89,
        "uniqueChildren": 89,
        "duplicateModelIds": [],
        "providerEvaluations": 2,
        "evaluatedNasChildren": 1,
    },
    "attune-skin-regional-skin-map": {
        "version": 1,
        "trainingId": "3485f8c67f957a1b850d",
        "modelGroup": "k3CenVIV6eguGn8fSMdT-3485f8c67f957a1b850d-rfdetrNasGroup",
        "taskType": "instance-segmentation",
        "modelType": "rfdetr-nas-seg",
        "records": 75,
        "uniqueChildren": 74,
        "duplicateModelIds": ["tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-nas-seg-t1--e79545"],
        "providerEvaluations": 2,
        "evaluatedNasChildren": 1,
    },
}


class AuditError(ValueError):
    """Raised when a model-group snapshot is incomplete or inconsistent."""


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuditError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise AuditError(f"{label} must be finite")
    if positive and result <= 0:
        raise AuditError(f"{label} must be positive")
    if not positive and not 0 <= result <= 100:
        raise AuditError(f"{label} must be between 0 and 100")
    return result


def _metric_leader(children: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    rows = [row for row in children if isinstance(row["metrics"].get(metric), (int, float))]
    if not rows:
        raise AuditError(f"{metric} has no observations")
    leader = min(rows, key=lambda row: (-float(row["metrics"][metric]), row["modelId"]))
    return {"modelId": leader["modelId"], "value": float(leader["metrics"][metric])}


def _fastest(children: list[dict[str, Any]]) -> dict[str, Any]:
    hardware = sorted({
        target
        for row in children
        for target in (row["metrics"].get("latency") or {})
    })
    if not hardware:
        raise AuditError("NAS snapshot has no hardware latency observations")
    output: dict[str, Any] = {}
    for target in hardware:
        rows = [
            row for row in children
            if isinstance((row["metrics"].get("latency") or {}).get(target), (int, float))
        ]
        winner = min(rows, key=lambda row: (
            float(row["metrics"]["latency"][target]), row["modelId"]
        ))
        output[target] = {
            "modelId": winner["modelId"],
            "latencyMs": float(winner["metrics"]["latency"][target]),
        }
    return output


def _validate_project(value: dict[str, Any]) -> dict[str, Any]:
    project = value.get("project")
    if project not in EXPECTED:
        raise AuditError("unexpected NAS project")
    expected = EXPECTED[project]
    for field in ("version", "trainingId", "modelGroup"):
        if value.get(field) != expected[field]:
            raise AuditError(f"{project} {field} binding changed")
    if value.get("expectedTaskType") != expected["taskType"]:
        raise AuditError(f"{project} task type changed")
    if value.get("expectedModelType") != expected["modelType"]:
        raise AuditError(f"{project} model type changed")

    page = value.get("page")
    if not isinstance(page, dict):
        raise AuditError(f"{project} page metadata missing")
    if page != {
        "offset": 0,
        "limit": 200,
        "total": expected["records"],
        "returned": expected["records"],
        "truncated": False,
    }:
        raise AuditError(f"{project} modelGroup was not read completely in one page")

    children = value.get("children")
    if not isinstance(children, list) or len(children) != expected["records"]:
        raise AuditError(f"{project} child inventory is incomplete")
    model_ids = [row.get("modelId") for row in children if isinstance(row, dict)]
    if len(model_ids) != len(children) or any(not isinstance(item, str) or not item for item in model_ids):
        raise AuditError(f"{project} child identities are invalid")
    duplicate_model_ids = sorted({
        model_id for model_id in model_ids if model_ids.count(model_id) > 1
    })
    if len(set(model_ids)) != expected["uniqueChildren"] or duplicate_model_ids != expected["duplicateModelIds"]:
        raise AuditError(f"{project} provider record duplication changed")

    normalized: list[dict[str, Any]] = []
    for row in children:
        model_id = row["modelId"]
        if row.get("group") != expected["modelGroup"]:
            raise AuditError(f"{project} child escaped the frozen modelGroup")
        if row.get("status") != "finished":
            raise AuditError(f"{project} contains an unfinished child")
        if row.get("taskType") != expected["taskType"] or row.get("modelType") != expected["modelType"]:
            raise AuditError(f"{project} child task/model type changed")
        if not isinstance(row.get("recommended"), bool):
            raise AuditError(f"{project} recommended flag must be boolean")
        metrics = row.get("metrics")
        if not isinstance(metrics, dict):
            raise AuditError(f"{project} child metrics missing")
        _number(metrics.get("map50"), f"{model_id}.map50")
        if metrics.get("map5095") is not None:
            _number(metrics["map5095"], f"{model_id}.map5095")
        latency = metrics.get("latency")
        if latency is not None:
            if not isinstance(latency, dict) or not latency:
                raise AuditError(f"{model_id}.latency must be a non-empty map or null")
            for target, measurement in latency.items():
                if not isinstance(target, str) or not target:
                    raise AuditError(f"{model_id} has an invalid hardware key")
                _number(measurement, f"{model_id}.latency.{target}", positive=True)
        pareto = metrics.get("paretoOptimalFor")
        if pareto is not None and (
            not isinstance(pareto, list)
            or any(not isinstance(item, str) or ":" not in item for item in pareto)
        ):
            raise AuditError(f"{model_id}.paretoOptimalFor is invalid")
        normalized.append(row)

    evaluations = value.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != expected["providerEvaluations"]:
        raise AuditError(f"{project} provider evaluation inventory changed")
    eval_ids = [row.get("evalId") for row in evaluations if isinstance(row, dict)]
    if len(eval_ids) != len(set(eval_ids)) or any(row.get("status") != "done" for row in evaluations):
        raise AuditError(f"{project} evaluations are duplicated or unfinished")
    child_set = set(model_ids)
    evaluated_children = sorted({
        row.get("modelId") for row in evaluations if row.get("modelId") in child_set
    })
    if len(evaluated_children) != expected["evaluatedNasChildren"]:
        raise AuditError(f"{project} evaluated NAS child coverage changed")

    recommended = sorted({row["modelId"] for row in normalized if row["recommended"]})
    return {
        "project": project,
        "version": expected["version"],
        "trainingId": expected["trainingId"],
        "modelGroup": expected["modelGroup"],
        "inventory": {
            "modelRecords": len(normalized),
            "uniqueChildren": len(child_set),
            "duplicateModelIds": duplicate_model_ids,
            "complete": True,
            "finishedModelRecords": len(normalized),
            "recommendedFlaggedUniqueChildren": len(recommended),
            "recommendedModelIds": recommended,
        },
        "observedAggregateLeaders": {
            "map50": _metric_leader(normalized, "map50"),
            "map5095": _metric_leader(normalized, "map5095"),
            "fastestByHardware": _fastest(normalized),
            "releaseWinnerClaimed": False,
        },
        "evaluationCoverage": {
            "providerEvaluations": len(evaluations),
            "evaluatedNasChildren": len(evaluated_children),
            "evaluatedNasModelIds": evaluated_children,
            "missingUniqueNasChildEvaluations": len(child_set) - len(evaluated_children),
            "complete": len(evaluated_children) == len(child_set),
        },
        "interpretation": {
            "recommendedUsedAsAccuracyWinner": False,
            "recommendedUsedAsHardwareWinner": False,
            "paretoMembershipUsedAsRecommendation": False,
            "aggregateMetricsUsedAsPerClassEvidence": False,
        },
        "decision": {
            "perClassAcceptanceAllowed": False,
            "trainingAuthorized": False,
            "finalTestEvaluationAuthorized": False,
            "productActivationAllowed": False,
            "blindRetrainingAllowed": False,
            "reason": "PER_CLASS_AND_INDEPENDENT_ACCEPTANCE_EVIDENCE_REQUIRED",
        },
    }


def audit_snapshot(facts: dict[str, Any]) -> dict[str, Any]:
    if facts.get("schemaVersion") != SCHEMA:
        raise AuditError("facts schema changed")
    if facts.get("providerRecommendedSemantics") != RECOMMENDED_SEMANTICS:
        raise AuditError("provider recommended semantics changed")
    if facts.get("accessibleProjects") != 20:
        raise AuditError("accessible project inventory changed")
    projects = facts.get("projects")
    if not isinstance(projects, list) or len(projects) != len(EXPECTED):
        raise AuditError("both NAS projects are required")
    audited = [_validate_project(value) for value in projects]
    if {value["project"] for value in audited} != set(EXPECTED):
        raise AuditError("NAS project inventory is incomplete")
    return {
        "schemaVersion": "nas-model-group-audit-v1",
        "observedAt": facts.get("observedAt"),
        "accessibleProjects": facts["accessibleProjects"],
        "projects": sorted(audited, key=lambda value: value["project"]),
        "providerRecommendedSemantics": {
            "flattenedUnionOnly": True,
            "accuracyWinnerClaimAllowed": False,
            "hardwareWinnerClaimAllowed": False,
            "authoritativeRecommendedByHardwarePresent": False,
        },
        "crossProjectControls": {
            "modelsComparedOnlyInsideTheirOwnProjectAndTask": True,
            "perClassEvidenceRequiredSeparately": True,
            "physicalCameraEvidenceRequiredSeparately": True,
            "roadmapAccepted": False,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsProviderImageIds": False,
            "containsAnnotationsOrGeometry": False,
            "containsExcludedArchiveDetails": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_snapshot(json.loads(args.facts.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
