import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "check_acne_improvement_release.py"
SPEC = importlib.util.spec_from_file_location("acne_improvement_release", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)


def diagnosis():
    return {
        "schemaVersion": "acne-model-diagnosis-v1",
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
        },
        "modelIdentity": {
            "modelId": gate.EXPECTED_MODEL_ID,
            "trainingId": gate.EXPECTED_TRAINING_ID,
            "evalId": gate.EXPECTED_EVAL_ID,
            "versionNumber": 1,
        },
        "dataset": {"archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256},
        "decision": {
            "modelAccepted": False,
            "activationAllowed": False,
            "nextExperimentPolicy": "one_change_validation_only_after_release_gate",
        },
    }


def split_gate(ready=True):
    return {
        "schemaVersion": "acne-split-release-gate-v1",
        "dataset": {"archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256, "records": 800},
        "replacementSplit": {"complete": ready},
        "semanticNegativeReview": {"complete": ready},
        "decision": {"readyToGenerateReplacementSplit": ready},
    }


def semantics(complete=True):
    return {
        "schemaVersion": "acne-semantic-negative-review-v1",
        "datasetArchiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
        "reviewer": "expert_review" if complete else None,
        "classes": [{
            "name": name,
            "expertReviewed": complete,
            "positiveDefinitionLocked": complete,
            "hardNegativePolicyLocked": complete,
            "ambiguousCasePolicyLocked": complete,
            "reviewedItemIds": [f"reviewed-{name}"] if complete else [],
        } for name in gate.CLASSES],
    }


def experiment(changes=None):
    return {
        "schemaVersion": "acne-validation-experiment-v1",
        "replacementDatasetVersion": "group-locked-v2",
        "selectionSplit": "valid",
        "testUsedForSelection": False,
        "changes": changes if changes is not None else [{"type": gate.ALLOWED_EXPERIMENT_CHANGE}],
    }


def final_test(overlap=0):
    return {
        "schemaVersion": "acne-untouched-final-test-v1",
        "archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
        "replacementDatasetVersion": "group-locked-v2",
        "images": 80,
        "isUntouched": True,
        "frozenBeforeTraining": True,
        "sourcePersonGroupingComplete": True,
        "overlapWithPreviouslyExposedTestImages": overlap,
    }


class AcneImprovementReleaseGateTest(unittest.TestCase):
    def test_repository_receipts_fail_closed_with_expected_blockers(self):
        root = Path(__file__).parents[3]
        current_diagnosis = json.loads((root / "docs/skin/evidence/acne-rfdetr-small-t2-diagnosis-20261025-v1.json").read_text())
        current_split = json.loads((root / "docs/skin/evidence/acne-split-release-gate-20261024-v1.json").read_text())
        current_semantics = json.loads((root / "docs/skin/evidence/acne-semantic-negative-review-20261024-v1.json").read_text())
        result = gate.build_gate(current_diagnosis, current_split, current_semantics)
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(result["decision"]["blockedReasons"], [
            "SOURCE_PERSON_GROUP_LOCKED_REPLACEMENT_SPLIT_MISSING",
            "EXPERT_SEMANTIC_NEGATIVE_POLICY_MISSING",
            "VALIDATION_ONLY_ONE_CHANGE_EXPERIMENT_MISSING",
            "NEW_UNTOUCHED_FINAL_TEST_MISSING",
        ])

    def test_complete_receipts_authorize_one_validation_training_only(self):
        result = gate.build_gate(
            diagnosis(), split_gate(), semantics(), experiment(), final_test()
        )
        self.assertTrue(result["decision"]["trainingAuthorized"])
        self.assertFalse(result["decision"]["testEvaluationAuthorized"])
        self.assertFalse(result["decision"]["activationAllowed"])

    def test_multiple_changes_are_rejected(self):
        proposal = experiment([
            {"type": gate.ALLOWED_EXPERIMENT_CHANGE},
            {"type": "augmentation_change"},
        ])
        result = gate.build_gate(
            diagnosis(), split_gate(), semantics(), proposal, final_test()
        )
        self.assertIn("EXACTLY_ONE_EXPERIMENT_CHANGE_REQUIRED", result["decision"]["blockedReasons"])

    def test_exposed_test_or_version_mismatch_is_rejected(self):
        result = gate.build_gate(
            diagnosis(), split_gate(), semantics(), experiment(), final_test(overlap=1)
        )
        self.assertIn("FINAL_TEST_NOT_UNTOUCHED_OR_GROUP_SAFE", result["decision"]["blockedReasons"])
        mismatched = final_test()
        mismatched["replacementDatasetVersion"] = "group-locked-v3"
        result = gate.build_gate(
            diagnosis(), split_gate(), semantics(), experiment(), mismatched
        )
        self.assertIn("EXPERIMENT_FINAL_TEST_VERSION_MISMATCH", result["decision"]["blockedReasons"])

    def test_identity_and_privacy_mismatch_raise(self):
        value = diagnosis()
        value["modelIdentity"]["evalId"] = "wrong"
        with self.assertRaisesRegex(gate.GateError, "binding"):
            gate.build_gate(value, split_gate())
        value = diagnosis()
        value["privacy"]["containsFilenames"] = True
        with self.assertRaisesRegex(gate.GateError, "privacy safe"):
            gate.build_gate(value, split_gate())


if __name__ == "__main__":
    unittest.main()
