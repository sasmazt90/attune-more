import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_acne_concern_release.py"
spec = importlib.util.spec_from_file_location("check_acne_concern_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "acne-per-class-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_training_prerequisites(receipt):
    for field in (
        "rightsReviewed",
        "expertPerClassPositiveNegativeAndAmbiguityProtocolComplete",
        "personIndependentGroupingComplete",
        "groupLockedReplacementSplitVerified",
        "newUntouchedFinalTestReserved",
        "independentCameraHoldoutReserved",
        "oneChangeValidationExperimentSpecified",
        "qualityPolicyLockedBeforeValidation",
    ):
        receipt["candidate"][field] = True


def _install_distinct_candidate(receipt):
    candidate = receipt["candidate"]
    candidate["mode"] = "new-model"
    candidate["modelId"] = "tolgar-sasmaz/attune-skin-acne-marks-pigmentation-2-rfdetr-small-t1"
    candidate["trainingId"] = "future-training-id"
    candidate["datasetVersion"] = 2
    candidate["trainedFromGroupLockedReplacementSplit"] = True
    candidate["candidateChangeMatchesPreRegisteredExperiment"] = True
    candidate["thresholdsLockedBeforeFinalTest"] = True


class AcneConcernReleaseTests(unittest.TestCase):
    def test_current_classes_and_known_models_are_blocked(self):
        result = module.evaluate_release(_receipt())
        self.assertFalse(result["researchModelAccepted"])
        self.assertFalse(result["knownNasChildrenAccepted"])
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertFalse(result["blindRetrainingAllowed"])
        for class_name in ("Pimple", "Post acne", "Pigmentation"):
            self.assertFalse(result["classDecisions"][class_name]["productActivationAllowed"])

    def test_classes_cannot_be_collapsed(self):
        receipt = _receipt()
        receipt["semanticContract"]["classesRemainSeparate"] = False
        with self.assertRaisesRegex(module.GateInputError, "remain separate"):
            module.evaluate_release(receipt)

    def test_tone_cannot_populate_localized_pigmentation(self):
        receipt = _receipt()
        receipt["semanticContract"]["pigmentationPopulatedByToneProxy"] = True
        with self.assertRaisesRegex(module.GateInputError, "tone cannot populate"):
            module.evaluate_release(receipt)

    def test_missing_label_and_medical_claims_are_rejected(self):
        receipt = _receipt()
        receipt["semanticContract"]["missingClassMeansNegative"] = True
        with self.assertRaisesRegex(module.GateInputError, "negative truth"):
            module.evaluate_release(receipt)
        receipt = _receipt()
        receipt["semanticContract"]["medicalDiagnosisInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "medical diagnoses"):
            module.evaluate_release(receipt)

    def test_class_metrics_cannot_be_merged_or_hidden(self):
        receipt = _receipt()
        receipt["researchModel"]["classMetrics"]["Pigmentation"]["diagnosticTest"]["f1"] = 0.322
        with self.assertRaisesRegex(module.GateInputError, "per-class"):
            module.evaluate_release(receipt)

    def test_partial_grouping_cannot_become_person_independent(self):
        receipt = _receipt()
        receipt["source"]["personIndependent"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become person-independent"):
            module.evaluate_release(receipt)

    def test_known_rejected_model_cannot_be_relabelled_as_candidate(self):
        receipt = _receipt()
        receipt["candidate"].update({
            "mode": "new-model",
            "modelId": module.REJECTED_RESEARCH_MODEL_ID,
            "trainingId": "fake-new-training",
            "datasetVersion": 2,
        })
        with self.assertRaisesRegex(module.GateInputError, "cannot be relabelled"):
            module.evaluate_release(receipt)

    def test_completed_pre_model_evidence_authorizes_only_targeted_training(self):
        receipt = _receipt()
        _complete_training_prerequisites(receipt)
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctCandidatePresent"])
        self.assertFalse(result["classDecisions"]["Pimple"]["finalTestEvaluationAuthorized"])
        self.assertFalse(result["roadmapAccepted"])

    def test_one_distinct_future_class_can_pass_without_promoting_others(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for field in receipt["candidate"]["classes"]["Pimple"]:
            receipt["candidate"]["classes"]["Pimple"][field] = True
        result = module.evaluate_release(receipt)
        self.assertTrue(result["distinctCandidatePresent"])
        self.assertTrue(result["classDecisions"]["Pimple"]["productActivationAllowed"])
        self.assertFalse(result["classDecisions"]["Post acne"]["productActivationAllowed"])
        self.assertFalse(result["classDecisions"]["Pigmentation"]["productActivationAllowed"])
        self.assertFalse(result["roadmapAccepted"])

    def test_complete_distinct_future_candidate_can_pass_all_classes(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for class_name in ("Pimple", "Post acne", "Pigmentation"):
            for field in receipt["candidate"]["classes"][class_name]:
                receipt["candidate"]["classes"][class_name][field] = True
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["decision"], "ready")


if __name__ == "__main__":
    unittest.main()
