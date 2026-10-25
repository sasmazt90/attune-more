import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "check_regional_improvement_release.py"
SPEC = importlib.util.spec_from_file_location("regional_improvement_release", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)


def diagnosis():
    return {
        "schemaVersion": "regional-mask-model-diagnosis-v1",
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
        "dataset": {
            "archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
            "images": gate.EXPECTED_IMAGES,
        },
        "decision": {
            "modelAccepted": False,
            "activationAllowed": False,
            "rednessIndependentLayer": True,
            "nextExperimentPolicy": "one_change_validation_only_after_release_gate",
        },
    }


def group_split():
    return {
        "schemaVersion": "regional-mask-group-split-v1",
        "source": {
            "archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
            "images": gate.EXPECTED_IMAGES,
        },
        "replacementDatasetVersion": "regional-group-locked-v2",
        "complete": True,
        "sourcePersonGroupingComplete": True,
        "sourcePersonOverlapAcrossSplits": 0,
        "testUntouched": True,
    }


def source_audit():
    return {
        "schemaVersion": "regional-mask-source-group-audit-v1",
        "source": {
            "sourceArchiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
            "providerExportSHA256": gate.EXPECTED_PROVIDER_EXPORT_SHA256,
            "versionNumber": 1,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "resolverCommitted": False,
        },
        "inventory": {
            "images": gate.EXPECTED_IMAGES,
            "uniqueSourceIds": gate.EXPECTED_IMAGES,
            "annotations": gate.EXPECTED_ANNOTATIONS,
            "polygonAnnotations": gate.EXPECTED_ANNOTATIONS,
            "nonPolygonAnnotations": 0,
            "invalidPolygonAnnotations": 0,
        },
        "coverage": {"allRecordsRepresented": True},
        "decision": {
            "trainingAuthorized": False,
            "replacementSplitReady": False,
            "testEligibleForFinalAcceptance": False,
        },
    }


def mask_protocol(redness_independent=True):
    return {
        "schemaVersion": "regional-mask-expert-protocol-v1",
        "archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
        "reviewer": "expert_review",
        "rednessIndependentLayer": redness_independent,
        "missingMaskMeansNormal": False,
        "modelPredictionAcceptedAsTruth": False,
        "classes": [
            {
                "name": name,
                "expertReviewed": True,
                "maskExtentPolicyLocked": True,
                "hardNegativePolicyLocked": True,
                "ambiguousCasePolicyLocked": True,
                "reviewedItemIds": [f"reviewed-{name}"],
            }
            for name in gate.CLASSES
        ],
    }


def experiment(changes=None, redness_independent=True):
    return {
        "schemaVersion": "regional-mask-validation-experiment-v1",
        "replacementDatasetVersion": "regional-group-locked-v2",
        "selectionSplit": "valid",
        "testUsedForSelection": False,
        "rednessIndependentLayer": redness_independent,
        "changes": changes
        if changes is not None
        else [{"type": "mask_extent_standardization"}],
    }


def final_test(images=50, overlap=0):
    return {
        "schemaVersion": "regional-mask-untouched-final-test-v1",
        "archiveSHA256": gate.EXPECTED_ARCHIVE_SHA256,
        "replacementDatasetVersion": "regional-group-locked-v2",
        "images": images,
        "isUntouched": True,
        "frozenBeforeTraining": True,
        "sourcePersonGroupingComplete": True,
        "overlapWithPreviouslyExposedTestImages": overlap,
        "independentProductCameraHoldoutReserved": True,
        "productCameraHoldoutImages": 12,
    }


class RegionalImprovementReleaseGateTest(unittest.TestCase):
    def test_repository_receipt_fails_closed_with_expected_blockers(self):
        root = Path(__file__).parents[3]
        current = json.loads(
            (root / "docs/skin/evidence/regional-rfdetr-seg-small-t2-diagnosis-20261025-v1.json").read_text()
        )
        root_audit = json.loads(
            (root / "docs/skin/evidence/regional-mask-source-group-audit-20261025-v1.json").read_text()
        )
        result = gate.build_gate(current, source_audit=root_audit)
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(
            result["decision"]["blockedReasons"],
            [
                "SOURCE_PERSON_GROUP_LOCKED_REPLACEMENT_SPLIT_MISSING",
                "EXPERT_MASK_AND_NEGATIVE_PROTOCOL_MISSING",
                "VALIDATION_ONLY_ONE_CHANGE_EXPERIMENT_MISSING",
                "NEW_UNTOUCHED_50_IMAGE_FINAL_TEST_AND_CAMERA_HOLDOUT_MISSING",
            ],
        )

    def test_complete_receipts_authorize_one_validation_training_only(self):
        result = gate.build_gate(
            diagnosis(), source_audit(), group_split(), mask_protocol(), experiment(), final_test()
        )
        self.assertTrue(result["decision"]["trainingAuthorized"])
        self.assertFalse(result["decision"]["testEvaluationAuthorized"])
        self.assertFalse(result["decision"]["activationAllowed"])

    def test_multiple_or_untargeted_changes_are_rejected(self):
        result = gate.build_gate(
            diagnosis(),
            source_audit(),
            group_split(),
            mask_protocol(),
            experiment([
                {"type": "mask_extent_standardization"},
                {"type": "augmentation_change"},
            ]),
            final_test(),
        )
        self.assertIn(
            "EXACTLY_ONE_EXPERIMENT_CHANGE_REQUIRED",
            result["decision"]["blockedReasons"],
        )
        result = gate.build_gate(
            diagnosis(),
            source_audit(),
            group_split(),
            mask_protocol(),
            experiment([{"type": "augmentation_change"}]),
            final_test(),
        )
        self.assertIn(
            "EXPERIMENT_CHANGE_NOT_TARGETED_TO_CONFIRMED_PROBLEM",
            result["decision"]["blockedReasons"],
        )

    def test_redness_must_remain_independent(self):
        result = gate.build_gate(
            diagnosis(),
            source_audit(),
            group_split(),
            mask_protocol(redness_independent=False),
            experiment(),
            final_test(),
        )
        self.assertIn(
            "REGIONAL_SEMANTIC_INVARIANTS_NOT_LOCKED",
            result["decision"]["blockedReasons"],
        )
        result = gate.build_gate(
            diagnosis(),
            source_audit(),
            group_split(),
            mask_protocol(),
            experiment(redness_independent=False),
            final_test(),
        )
        self.assertIn(
            "REDNESS_INDEPENDENT_LAYER_REQUIRED",
            result["decision"]["blockedReasons"],
        )

    def test_small_or_exposed_final_test_is_rejected(self):
        result = gate.build_gate(
            diagnosis(), source_audit(), group_split(), mask_protocol(), experiment(), final_test(images=49)
        )
        self.assertIn("FINAL_TEST_BELOW_50_IMAGES", result["decision"]["blockedReasons"])
        result = gate.build_gate(
            diagnosis(),
            source_audit(),
            group_split(),
            mask_protocol(),
            experiment(),
            final_test(overlap=1),
        )
        self.assertIn(
            "FINAL_TEST_NOT_UNTOUCHED_GROUP_SAFE_OR_CAMERA_RESERVED",
            result["decision"]["blockedReasons"],
        )

    def test_identity_and_privacy_mismatch_raise(self):
        value = diagnosis()
        value["modelIdentity"]["evalId"] = "wrong"
        with self.assertRaisesRegex(gate.GateError, "binding"):
            gate.build_gate(value)
        value = diagnosis()
        value["privacy"]["containsFilenames"] = True
        with self.assertRaisesRegex(gate.GateError, "privacy safe"):
            gate.build_gate(value)

    def test_source_audit_is_required_and_cannot_masquerade_as_group_split(self):
        result = gate.build_gate(diagnosis())
        self.assertIn(
            "FROZEN_PROVIDER_EXPORT_AUDIT_MISSING",
            result["decision"]["blockedReasons"],
        )
        with self.assertRaisesRegex(gate.GateError, "group split schema"):
            gate.build_gate(diagnosis(), source_audit(), source_audit())

        value = source_audit()
        value["privacy"]["resolverCommitted"] = True
        with self.assertRaisesRegex(gate.GateError, "privacy safe"):
            gate.build_gate(diagnosis(), value)


if __name__ == "__main__":
    unittest.main()
