import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_acne_validation_expert_review.py"
SPEC = importlib.util.spec_from_file_location("build_acne_validation_expert_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
QUEUE = json.loads((REPO_ROOT / "docs/skin/evidence/acne-validation-failure-review-queue-20261028-v1.json").read_text())


def complete_manifest():
    decisions = []
    for class_name, record_ref in MODULE.validate_queue(QUEUE):
        decisions.append({
            "className": class_name,
            "recordRef": record_ref,
            "truthStatus": "positive_target",
            "rootCause": "model_only_failure",
            "expertDecisionIndependent": True,
        })
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "queueDigest": MODULE.EXPECTED_QUEUE_DIGEST,
        "evalId": MODULE.EXPECTED_EVAL_ID,
        "modelId": MODULE.EXPECTED_MODEL_ID,
        "split": "valid",
        "confidenceThreshold": 0.3,
        "testSplitRead": False,
        "thresholdSelectedHere": False,
        "reviewRef": "review_1111111111111111",
        "reviewAuthorityRef": "authority_2222222222222222",
        "expertProtocolSHA256": "3" * 64,
        "reviewPolicy": {
            "qualifiedHumanReviewConfirmed": True,
            "modelProposalHiddenUntilIndependentDecision": True,
            "nativeResolutionSourceViewed": True,
            "classDefinitionsLockedBeforeReview": True,
            "missingLabelNotNegativeOrNormal": True,
            "modelProposalNotExpertTruth": True,
            "reviewDoesNotAuthorizeRelabel": True,
            "reviewDoesNotAuthorizeTraining": True,
            "testExcluded": True,
        },
        "decisions": decisions,
    }


class AcneValidationExpertReviewTest(unittest.TestCase):
    def test_committed_queue_is_exactly_bound(self):
        expected = MODULE.validate_queue(QUEUE)
        self.assertEqual(len(expected), 45)
        self.assertEqual(len(set(expected)), 45)

    def test_complete_review_emits_only_aggregate_evidence(self):
        artifact = MODULE.build_artifact(QUEUE, complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertTrue(artifact["expertReviewComplete"])
        self.assertTrue(artifact["targetedRemediationPlanningAllowed"])
        self.assertFalse(artifact["datasetMutationAuthorized"])
        self.assertFalse(artifact["trainingAuthorized"])
        self.assertFalse(artifact["finalTestEvaluationAuthorized"])
        self.assertFalse(artifact["productActivationAllowed"])
        self.assertNotIn("decisions", artifact)
        self.assertNotIn("recordRef", json.dumps(artifact))
        self.assertEqual(artifact["reviewedDecisions"], 45)

    def test_output_is_deterministic_across_decision_order(self):
        first = complete_manifest()
        second = copy.deepcopy(first)
        second["decisions"].reverse()
        self.assertEqual(
            MODULE.build_artifact(QUEUE, first)["aggregateDigest"],
            MODULE.build_artifact(QUEUE, second)["aggregateDigest"],
        )

    def test_incomplete_template_stays_blocked(self):
        value = complete_manifest()
        value["reviewRef"] = None
        value["reviewAuthorityRef"] = None
        value["expertProtocolSHA256"] = None
        value["decisions"] = []
        preflight = MODULE.evaluate_manifest(QUEUE, value)
        self.assertEqual(preflight["decision"], "blocked")
        self.assertFalse(preflight["expertReviewComplete"])
        self.assertIn("expert_decisions_incomplete", preflight["blockers"])
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "review is incomplete"):
            MODULE.build_artifact(QUEUE, value)

    def test_missing_duplicate_and_extra_decisions_fail_closed(self):
        value = complete_manifest()
        value["decisions"].pop()
        self.assertIn("expert_decisions_incomplete", MODULE.evaluate_manifest(QUEUE, value)["blockers"])
        value = complete_manifest()
        value["decisions"][-1] = copy.deepcopy(value["decisions"][0])
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "duplicate"):
            MODULE.evaluate_manifest(QUEUE, value)
        value = complete_manifest()
        value["decisions"][0]["recordRef"] = "f" * 64
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "locked queue"):
            MODULE.evaluate_manifest(QUEUE, value)

    def test_model_proposal_cannot_become_expert_truth(self):
        value = complete_manifest()
        value["reviewPolicy"]["modelProposalNotExpertTruth"] = False
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "policy changed"):
            MODULE.evaluate_manifest(QUEUE, value)
        value = complete_manifest()
        value["decisions"][0]["expertDecisionIndependent"] = False
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "independent"):
            MODULE.evaluate_manifest(QUEUE, value)

    def test_test_or_threshold_use_fails_hard(self):
        value = complete_manifest()
        value["split"] = "test"
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "validation@0.30"):
            MODULE.evaluate_manifest(QUEUE, value)
        value = complete_manifest()
        value["confidenceThreshold"] = 0.35
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "validation@0.30"):
            MODULE.evaluate_manifest(QUEUE, value)
        value = complete_manifest()
        value["testSplitRead"] = True
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "cannot use test"):
            MODULE.evaluate_manifest(QUEUE, value)

    def test_queue_identity_or_payload_mutation_fails_hard(self):
        value = copy.deepcopy(QUEUE)
        value["queueDigest"] = "0" * 64
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "queue digest changed"):
            MODULE.validate_queue(value)
        value = copy.deepcopy(QUEUE)
        value["classes"]["Pimple"]["reviewItems"][0]["priorityScore"] += 1
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "no longer matches"):
            MODULE.validate_queue(value)

    def test_private_identity_media_and_geometry_fields_fail_hard(self):
        for key in ("filename", "imageId", "reviewerName", "polygons", "predictions"):
            value = complete_manifest()
            value[key] = "private"
            with self.subTest(key=key):
                with self.assertRaisesRegex(MODULE.ExpertReviewError, "raw/private"):
                    MODULE.evaluate_manifest(QUEUE, value)

    def test_unsupported_decision_codes_fail_hard(self):
        value = complete_manifest()
        value["decisions"][0]["truthStatus"] = "normal_by_absence"
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "unsupported"):
            MODULE.evaluate_manifest(QUEUE, value)
        value = complete_manifest()
        value["decisions"][0]["rootCause"] = "recommended_model"
        with self.assertRaisesRegex(MODULE.ExpertReviewError, "unsupported"):
            MODULE.evaluate_manifest(QUEUE, value)


if __name__ == "__main__":
    unittest.main()
