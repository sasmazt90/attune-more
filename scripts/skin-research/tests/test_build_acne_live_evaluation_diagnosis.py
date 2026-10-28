import copy
import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_acne_live_evaluation_diagnosis.py"
SPEC = importlib.util.spec_from_file_location("acne_live_diagnosis", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)
FACTS = Path(__file__).parents[3] / "docs/skin/evidence/acne-live-evaluation-facts-20261028-v1.json"


def facts():
    return json.loads(FACTS.read_text())


class AcneLiveEvaluationDiagnosisTest(unittest.TestCase):
    def test_repository_facts_remain_fail_closed(self):
        result = gate.build_diagnosis(facts())
        self.assertEqual(result["evaluationCoverage"], {
            "expectedModels": 90, "evaluatedModels": 2,
            "missingEvaluations": 88, "complete": False,
        })
        self.assertEqual(result["observedMetricLeader"]["evalId"], "7s06OfIzx78XzATqr5oA")
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertFalse(result["decision"]["productActivationAllowed"])

    def test_recommended_flag_does_not_override_metrics(self):
        result = gate.build_diagnosis(facts())
        self.assertEqual(result["providerRecommendedFlag"]["evalId"], "0xMgfVLFzMyNEOhN1baC")
        self.assertFalse(result["providerRecommendedFlag"]["usedAsAccuracyOrHardwareWinner"])
        self.assertNotEqual(result["providerRecommendedFlag"]["evalId"], result["observedMetricLeader"]["evalId"])

    def test_class_findings_are_separate_and_rejected(self):
        result = gate.build_diagnosis(facts())
        self.assertEqual(set(result["classes"]), set(gate.CLASSES))
        self.assertTrue(all(not row["accepted"] for row in result["classes"].values()))
        self.assertIn("tone proxy", " ".join(result["classes"]["Pigmentation"]["actions"]))

    def test_missing_evaluation_rejects(self):
        value = facts()
        value["evaluations"].pop()
        with self.assertRaisesRegex(gate.DiagnosisError, "both known evaluations"):
            gate.build_diagnosis(value)

    def test_unknown_or_missing_class_rejects(self):
        value = facts()
        value["evaluations"][0]["perClass"]["test"][0]["className"] = "Acne"
        with self.assertRaisesRegex(gate.DiagnosisError, "all three classes"):
            gate.build_diagnosis(value)

    def test_invalid_confusion_matrix_rejects(self):
        value = facts()
        value["evaluations"][0]["confusion"]["matrix"][0].pop()
        with self.assertRaisesRegex(gate.DiagnosisError, "4x4"):
            gate.build_diagnosis(value)

    def test_invalid_metric_rejects(self):
        value = facts()
        value["evaluations"][0]["summary"]["map50_95"] = float("nan")
        with self.assertRaisesRegex(gate.DiagnosisError, "finite"):
            gate.build_diagnosis(value)

    def test_receipt_cannot_clear_exposed_test(self):
        value = copy.deepcopy(facts())
        value["releaseControls"]["existingTestExposed"] = False
        with self.assertRaisesRegex(gate.DiagnosisError, "exposure fact"):
            gate.build_diagnosis(value)


if __name__ == "__main__":
    unittest.main()
