import copy
from contextlib import contextmanager
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
    path = ROOT / "docs" / "skin" / "evidence" / "under-eye-per-class-release-receipt-20261029-v6.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _grouped_gate(training_ready=False):
    path = ROOT / "docs" / "skin" / "evidence" / "under-eye-grouped-release-gate-20261029-v5.json"
    gate = json.loads(path.read_text(encoding="utf-8"))
    if training_ready:
        gate["providerProjectSummaryConsistent"] = True
        gate["versionGenerationAuthorized"] = True
        gate["augmentationFreeGroupedVersionVerified"] = True
        gate["providerExportIdentityVerified"] = True
        gate["researchTrainingAuthorized"] = True
        gate["blockers"] = [
            "independent_camera_holdout_missing",
            "working_product_integration_evidence_missing",
        ]
    return gate


@contextmanager
def _accept_grouped_gate(gate):
    original = module.EXPECTED_GROUPED_GATE_CANONICAL_SHA256
    module.EXPECTED_GROUPED_GATE_CANONICAL_SHA256 = module._canonical_sha(gate)
    try:
        yield
    finally:
        module.EXPECTED_GROUPED_GATE_CANONICAL_SHA256 = original


def _queue():
    path = ROOT / "docs" / "skin" / "evidence" / "under-eye-expert-review-queue-20261027-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_protocol(queue):
    return {
        "schemaVersion": "under-eye-expert-semantic-protocol-v1",
        "candidateArchiveSHA256": module.EXPECTED_GROUPED_ARCHIVE_SHA256,
        "reviewQueueCanonicalSHA256": module.EXPECTED_REVIEW_QUEUE_CANONICAL_SHA256,
        "reviewerRole": "expert_review",
        "classes": [{
            "name": name,
            "expertReviewed": True,
            "positiveDefinitionLocked": True,
            "maskExtentPolicyLocked": True,
            "hardNegativePolicyLocked": True,
            "ambiguousCasePolicyLocked": True,
            "reviewedItemIds": sorted(
                row["reviewItemId"] for row in queue["items"] if row["targetClass"] == name
            ),
        } for name in ("darkcircle", "eyebag")],
        "semanticInvariants": queue["reviewPolicy"],
        "decision": {
            "expertReviewComplete": True,
            "semanticProtocolReady": True,
            "personIndependentSplitReady": False,
            "trainingAuthorized": False,
            "testEvaluationAuthorized": False,
            "activationAllowed": False,
        },
    }


def _complete_training_prerequisites(receipt):
    for field in (
        "rightsReviewed",
        "expertPerClassMaskNegativeAndAmbiguityProtocolComplete",
        "personIndependentGroupedSplitLocked",
        "newUntouchedFinalTestReserved",
        "independentCameraHoldoutReserved",
        "qualityPolicyLockedBeforeValidation",
    ):
        receipt["candidate"][field] = True
    receipt["candidate"]["exactArchiveAuthorized"] = True
    receipt["candidate"]["groupedImportVerified"] = True
    receipt["candidate"]["providerUploadEvidenceVerified"] = True
    receipt["candidate"]["providerProjectSummaryConsistent"] = True
    receipt["candidate"]["versionGenerationAuthorized"] = True
    receipt["candidate"]["augmentationFreeGroupedVersionVerified"] = True
    receipt["candidate"]["providerExportIdentityVerified"] = True


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
        result = module.evaluate_release(_receipt(), _grouped_gate(), _queue())
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertTrue(result["classesRemainSeparate"])
        self.assertTrue(result["expertReviewQueueVerified"])
        self.assertFalse(result["expertSemanticProtocolVerified"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertTrue(result["groupedImportVerified"])
        self.assertTrue(result["providerUploadEvidenceVerified"])
        self.assertFalse(result["providerProjectSummaryConsistent"])
        self.assertFalse(result["versionGenerationAuthorized"])
        self.assertNotIn("grouped_import_verification_missing", result["sharedTrainingBlockers"])
        self.assertIn("provider_project_summary_inconsistent", result["sharedTrainingBlockers"])
        self.assertFalse(result["providerExportIdentityVerified"])
        self.assertFalse(result["distinctGroupedCandidatePresent"])
        self.assertFalse(result["blindRetrainingAllowed"])
        self.assertFalse(result["classDecisions"]["darkcircle"]["productActivationAllowed"])
        self.assertFalse(result["classDecisions"]["eyebag"]["productActivationAllowed"])

    def test_classes_cannot_be_collapsed(self):
        receipt = _receipt()
        receipt["semanticContract"]["classesRemainSeparate"] = False
        with self.assertRaisesRegex(module.GateInputError, "remain separate"):
            module.evaluate_release(receipt, _grouped_gate())

    def test_medical_cause_claims_are_rejected(self):
        receipt = _receipt()
        receipt["semanticContract"]["darkcircleMedicalCauseInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "medical causes"):
            module.evaluate_release(receipt, _grouped_gate())
        receipt = _receipt()
        receipt["semanticContract"]["eyebagEdemaOrFluidRetentionInferred"] = True
        with self.assertRaisesRegex(module.GateInputError, "edema"):
            module.evaluate_release(receipt, _grouped_gate())

    def test_missing_label_cannot_become_negative_truth(self):
        receipt = _receipt()
        receipt["semanticContract"]["missingClassMeansNegative"] = True
        with self.assertRaisesRegex(module.GateInputError, "negative truth"):
            module.evaluate_release(receipt, _grouped_gate())

    def test_class_metrics_cannot_be_merged_or_hidden(self):
        receipt = _receipt()
        receipt["ungroupedModel"]["classMetrics"]["darkcircle"]["diagnosticTest"]["f1"] = 0.568
        with self.assertRaisesRegex(module.GateInputError, "per-class"):
            module.evaluate_release(receipt, _grouped_gate())

    def test_partial_grouping_cannot_become_person_independent(self):
        receipt = _receipt()
        receipt["source"]["personIndependent"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become person-independent"):
            module.evaluate_release(receipt, _grouped_gate())

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
            module.evaluate_release(receipt, _grouped_gate())

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
            module.evaluate_release(receipt, _grouped_gate())

    def test_completed_pre_model_evidence_authorizes_only_targeted_training(self):
        receipt = _receipt()
        _complete_training_prerequisites(receipt)
        queue = _queue()
        gate = _grouped_gate(training_ready=True)
        with _accept_grouped_gate(gate):
            result = module.evaluate_release(receipt, gate, queue, _complete_protocol(queue))
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["distinctGroupedCandidatePresent"])
        self.assertFalse(result["roadmapAccepted"])

    def test_one_future_class_can_pass_without_promoting_the_other(self):
        receipt = copy.deepcopy(_receipt())
        _complete_training_prerequisites(receipt)
        _install_distinct_candidate(receipt)
        for field in receipt["candidate"]["classes"]["darkcircle"]:
            receipt["candidate"]["classes"]["darkcircle"][field] = True
        queue = _queue()
        gate = _grouped_gate(training_ready=True)
        with _accept_grouped_gate(gate):
            result = module.evaluate_release(receipt, gate, queue, _complete_protocol(queue))
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
        queue = _queue()
        gate = _grouped_gate(training_ready=True)
        with _accept_grouped_gate(gate):
            result = module.evaluate_release(receipt, gate, queue, _complete_protocol(queue))
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["roadmapAccepted"])
        self.assertEqual(result["decision"], "ready")

    def test_boolean_protocol_claim_without_bound_protocol_is_rejected(self):
        receipt = _receipt()
        receipt["candidate"]["expertPerClassMaskNegativeAndAmbiguityProtocolComplete"] = True
        with self.assertRaisesRegex(module.GateInputError, "not bound"):
            module.evaluate_release(receipt, _grouped_gate(), _queue())

    def test_review_queue_tampering_is_rejected(self):
        queue = _queue()
        queue["dataset"]["testSelectedForReview"] = 1
        with self.assertRaisesRegex(module.GateInputError, "queue content changed"):
            module.evaluate_release(_receipt(), _grouped_gate(), queue)

    def test_protocol_must_cover_every_frozen_queue_item(self):
        receipt = _receipt()
        receipt["candidate"]["expertPerClassMaskNegativeAndAmbiguityProtocolComplete"] = True
        queue = _queue()
        protocol = _complete_protocol(queue)
        protocol["classes"][0]["reviewedItemIds"].pop()
        with self.assertRaisesRegex(module.GateInputError, "cover the frozen queue"):
            module.evaluate_release(receipt, _grouped_gate(), queue, protocol)

    def test_receipt_booleans_cannot_promote_current_grouped_gate(self):
        receipt = _receipt()
        receipt["candidate"]["providerProjectSummaryConsistent"] = True
        receipt["candidate"]["versionGenerationAuthorized"] = True
        receipt["candidate"]["augmentationFreeGroupedVersionVerified"] = True
        receipt["candidate"]["providerExportIdentityVerified"] = True
        with self.assertRaisesRegex(module.GateInputError, "not bound"):
            module.evaluate_release(receipt, _grouped_gate(), _queue())

    def test_completed_import_disables_repeat_upload_but_not_version_gate(self):
        receipt = _receipt()
        gate = _grouped_gate()
        result = module.evaluate_release(receipt, gate, _queue())
        self.assertTrue(result["groupedImportVerified"])
        self.assertTrue(result["providerUploadEvidenceVerified"])
        self.assertFalse(result["providerProjectSummaryConsistent"])
        self.assertFalse(result["versionGenerationAuthorized"])
        self.assertFalse(result["researchTrainingAuthorized"])

    def test_revoked_or_reusable_stale_upload_gate_is_rejected(self):
        gate = _grouped_gate()
        gate["authorizedArchiveSHA256"] = module.REVOKED_GROUPED_ARCHIVE_SHA256
        with self.assertRaisesRegex(module.GateInputError, "content changed"):
            module.evaluate_release(_receipt(), gate, _queue())
        gate = _grouped_gate()
        gate["existingUploadTaskReusable"] = True
        with self.assertRaisesRegex(module.GateInputError, "content changed"):
            module.evaluate_release(_receipt(), gate, _queue())


if __name__ == "__main__":
    unittest.main()


