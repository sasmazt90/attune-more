import copy
import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_nas_model_groups.py"
SPEC = importlib.util.spec_from_file_location("audit_nas_model_groups", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit)
FACTS = Path(__file__).parents[3] / "docs/skin/evidence/nas-model-group-facts-20261028-v1.json"
EVIDENCE = Path(__file__).parents[3] / "docs/skin/evidence/nas-model-group-audit-20261028-v1.json"


def facts():
    return json.loads(FACTS.read_text())


class NasModelGroupAuditTest(unittest.TestCase):
    def test_committed_evidence_replays_exactly(self):
        self.assertEqual(audit.audit_snapshot(facts()), json.loads(EVIDENCE.read_text()))

    def test_repository_snapshot_is_complete_and_fail_closed(self):
        result = audit.audit_snapshot(facts())
        rows = {row["project"]: row for row in result["projects"]}
        self.assertEqual(rows["attune-skin-acne-marks-pigmentation"]["inventory"]["children"], 89)
        self.assertEqual(rows["attune-skin-regional-skin-map"]["inventory"]["children"], 75)
        self.assertFalse(rows["attune-skin-acne-marks-pigmentation"]["evaluationCoverage"]["complete"])
        self.assertFalse(rows["attune-skin-regional-skin-map"]["decision"]["productActivationAllowed"])

    def test_observed_metric_leaders_are_not_recommended_flags(self):
        rows = {row["project"]: row for row in audit.audit_snapshot(facts())["projects"]}
        acne = rows["attune-skin-acne-marks-pigmentation"]
        regional = rows["attune-skin-regional-skin-map"]
        self.assertTrue(acne["observedAggregateLeaders"]["map50"]["modelId"].endswith("--929397"))
        self.assertTrue(acne["observedAggregateLeaders"]["map5095"]["modelId"].endswith("--754885"))
        self.assertTrue(regional["observedAggregateLeaders"]["map50"]["modelId"].endswith("--291700"))
        self.assertTrue(regional["observedAggregateLeaders"]["map5095"]["modelId"].endswith("--2c07ef"))
        self.assertFalse(acne["observedAggregateLeaders"]["releaseWinnerClaimed"])
        self.assertNotIn(acne["observedAggregateLeaders"]["map50"]["modelId"], acne["inventory"]["recommendedModelIds"])

    def test_fastest_hardware_observations_remain_non_release(self):
        rows = {row["project"]: row for row in audit.audit_snapshot(facts())["projects"]}
        for row in rows.values():
            fastest = row["observedAggregateLeaders"]["fastestByHardware"]
            self.assertTrue(fastest["T4"]["modelId"].endswith("--9602f1"))
            self.assertTrue(fastest["AI1"]["modelId"].endswith("--4f45e1"))
            self.assertFalse(row["interpretation"]["recommendedUsedAsHardwareWinner"])

    def test_truncated_or_partial_page_rejects(self):
        value = facts()
        value["projects"][0]["page"]["truncated"] = True
        with self.assertRaisesRegex(audit.AuditError, "not read completely"):
            audit.audit_snapshot(value)

    def test_duplicate_child_rejects(self):
        value = facts()
        value["projects"][0]["children"][1]["modelId"] = value["projects"][0]["children"][0]["modelId"]
        with self.assertRaisesRegex(audit.AuditError, "invalid or duplicated"):
            audit.audit_snapshot(value)

    def test_group_drift_rejects(self):
        value = facts()
        value["projects"][1]["children"][0]["group"] = "other-group"
        with self.assertRaisesRegex(audit.AuditError, "escaped"):
            audit.audit_snapshot(value)

    def test_sparse_optional_metrics_are_allowed_but_map50_is_required(self):
        result = audit.audit_snapshot(facts())
        self.assertEqual(len(result["projects"]), 2)
        value = facts()
        value["projects"][0]["children"][0]["metrics"]["map50"] = None
        with self.assertRaisesRegex(audit.AuditError, "must be numeric"):
            audit.audit_snapshot(value)

    def test_invalid_latency_and_recommended_semantics_reject(self):
        value = facts()
        value["projects"][0]["children"][0]["metrics"]["latency"]["T4"] = 0
        with self.assertRaisesRegex(audit.AuditError, "must be positive"):
            audit.audit_snapshot(value)
        value = facts()
        value["providerRecommendedSemantics"] = "winner"
        with self.assertRaisesRegex(audit.AuditError, "semantics"):
            audit.audit_snapshot(value)


if __name__ == "__main__":
    unittest.main()
