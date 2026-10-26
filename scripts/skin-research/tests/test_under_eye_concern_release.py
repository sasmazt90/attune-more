import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_under_eye_concern_release.py"
spec = importlib.util.spec_from_file_location("check_under_eye_concern_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "under-eye-per-class-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_training_prerequisites(receipt):
    for field in (
        "exactArchiveAuthorized",
        "groupedImportVerified",
        "augmentationFreeGroupedVersionVerified",
        "rightsReviewed",
        "expertPerClassMaskNegativeAndAmbiguityProtocolComplete",
        "personIndependentGroupedSplitLocked",
        "newUntouchedFinalTestReserved",
        "independentCameraHoldoutReserved",
        "qualityPolicyLockedBeforeValidation",
    ):
        receipt["candidate"][field] = True


def _install_distinct_candidate(receipt):
    candidate = receipt["candidate"]
    candidate["mode"] = "new-model"
    candidate["projectId"] = module.EXPECTED_GROUPED_PROJECT_ID
    candidate["modelId"] = f"{module.EXPECTED_GROUPED_PROJECT_ID}-1-rfdetr-seg-small-t1"
    candidate["trainingId"] = "future-grouped-training-id"
    candidate["datasetVersion"] = 1
    candidate["trainedFromAuthorizedGroupedArchive"] = True
    candidate["candidateChangeMatchesPreRegisteredExperiment"] = True
    candidate["thresholdsLockedBeforeFinalTest"] = True


class UnderEyeConcernReleaseTests(unittest.TestCase):
    def test_current_classes_are_independently_blocked(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertTrue(result["classesRemainSeparate"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctGroupedCandidatePresent"])
        self.assertFalse(result["blindRetrainingAllowed"])
        self.assertFalse(result["classDecisions"]["darkcircle"]["productActivationAllowed"])
        self.assertFalse(result["classDecisions"]["eyebag"]["productActivationAllowed"])

    def test_classes_cannot_be_collapsed(self):
        receipt = _receipt()
        receipt["semanticContract"]["classesRemainSeparate"] = False
        with self.assertRaisesRegex(module.GateInputError, "remain separate"):
            module.evaluate_release(receipt)

    def test_medical_cause_claims_are_rejected(self):
        receipt = _receipt()
        receipt["semanticContract"]["darkcircleMedicalCauseInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "medical causes"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["semanticContract"]["eyebagEdemaOrFluidRetentionInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "edema"):
            module.evaluate_release(receipt)

    def test_missing_label_cannot_become_negative_truth(self):
        receipt = _receipt()
        receipt["semanticContract"]["missingClassMeansNegative"] = True
        with self.assertRaisesRegex(module.GateInputError, "negative truth"):
            module.evaluate_release(receipt)

    def test_class_metrics_cannot_be_merged_or_hidden(self):
        receipt = _receipt()
        receipt["ungroupedModel"]["classMetrics"]["darkcircle"]["diagnosticTest"]["f1"] = 0.568
        with self.assertRaisesRegex(module.GateInputError, "per-class"):
            module.evaluate_release(receipt)

    def test_partial_grouping_cannot_become_person_independent(self):
        receipt = _receipt()
        receipt["source"]["personIndependent"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become person-independent"):
            module.evaluate_release(receipt)

    def test_known_ungrouped_model_cannot_be_relabelled_as_grouped_candidate(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": module.EXPECTED_GROUPED_PROJECT_ID,
            "modelId": module.REJECTED_UNGROUPED_MODEL_ID,
            "trainingId": "fake-new-training",
            "datasetVersion": 1,
        })
        with self.assertRaisesRegex(module.GateInputError, "cannot be relabelled"):
            module.evaluate_release(receipt)

    def test_candidate_must_belong_to_grouped_research_project(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "projectId": "tolgar-sasmaz/attune-skin-under-eye-pilot",
            "modelId": "tolgar-sasmaz/attune-skin-under-eye-pilot-2-rfdetr-seg-small-t2",
            "trainingId": "future-training",
            "datasetVersion": 2,
        })
        with self.assertRaisesRegex(module.GateInputError, "grouped research project"):
            module.evaluate_release(receipt)

    def test_completed_pre_model_evidence_authorizes_only_targeted_training(self):
        receipt = _receipt()
        _complete_training_prerequisites(receipt)
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctGroupedCandidatePresent"])
        self.assertFalse(result["roadmapAccepted"])

    def test_one_future_class_can_pass_without_promoting_the_other(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for field in receipt["candidate"]["classes"]["darkcircle"]:
            receipt["candidate"]["classes"]["darkcircle"][field] = True
        result = module.evaluate_release(receipt)
        self.assertTrue(result["classDecisions"]["darkcircle"]["productActivationAllowed"])
        self.assertFalse(result["classDecisions"]["eyebag"]["productActivationAllowed"])
        self.assertFalse(result["roadmapAccepted"])

    def test_complete_future_candidate_can_pass_both_classes(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for class_name in ("darkcircle", "eyebag"):
            for field in receipt["candidate"]["classes"][class_name]:
                receipt["candidate"]["classes"][class_name][field] = True
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["decision"], "ready")


if __name__ == "__main__":
    unittest.main()
