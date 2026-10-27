import json
import unittest
from collections import Counter
from pathlib import Path


EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "skin"
    / "evidence"
    / "generated-front-roboflow-20261024-v1.json"
)


class GeneratedFrontRoboflowEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_inference_identity_and_scope_are_pinned(self) -> None:
        calls = self.evidence["calls"]
        self.assertEqual(6, len(calls))
        self.assertEqual(6, len({call["inferenceId"] for call in calls}))
        self.assertEqual(
            "7ee34fce76456d9ff4cfe6e7049aad1e",
            self.evidence["model"]["resolvedModel"]["model_package_id"],
        )
        self.assertTrue(self.evidence["source"]["frontImagesSentToRoboflow"])
        self.assertFalse(self.evidence["source"]["sideImagesSentToRoboflow"])

    def test_threshold_counts_are_derived_from_single_eight_percent_run(self) -> None:
        thresholds = (0.08, 0.15, 0.2, 0.3, 0.5)
        predictions = [
            prediction
            for call in self.evidence["calls"]
            for prediction in call["predictions"]
        ]
        for threshold in thresholds:
            retained = [
                prediction
                for prediction in predictions
                if prediction["confidence"] >= threshold
            ]
            expected = self.evidence["aggregateThresholdCounts"][str(threshold)]
            self.assertEqual(len(retained), expected["total"])
            self.assertEqual(
                dict(sorted(Counter(item["class"] for item in retained).items())),
                expected["byClass"],
            )

    def test_no_accuracy_or_activation_claim_is_allowed(self) -> None:
        eligibility = self.evidence["metricEligibility"]
        self.assertFalse(eligibility["precision"])
        self.assertFalse(eligibility["recall"])
        self.assertFalse(eligibility["f1"])
        self.assertFalse(self.evidence["interpretation"]["thresholdSelectionAuthorized"])
        self.assertFalse(self.evidence["interpretation"]["productionActivationAuthorized"])


if __name__ == "__main__":
    unittest.main()
