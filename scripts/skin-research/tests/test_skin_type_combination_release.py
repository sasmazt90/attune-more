import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "skin-research" / "check_skin_type_combination_release.py"
spec = importlib.util.spec_from_file_location("check_skin_type_combination_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _receipt():
    path = ROOT / "docs" / "skin" / "evidence" / "skin-type-combination-release-receipt-20261026-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _learned_method(role, method_id, regions, geometry):
    return {
        "role": role,
        "methodId": method_id,
        "kind": "learned-mask",
        "accepted": True,
        "truthSource": "expert-regional",
        "geometry": geometry,
        "regions": regions,
        "projectId": module.REGIONAL_PROJECT_ID,
        "datasetVersion": 2,
        "trainingId": f"training-{method_id}",
        "modelId": f"{module.REGIONAL_PROJECT_ID}-2-rfdetr-seg-small-{method_id}",
        "wholeFaceReplicationAllowed": False,
        "missingLabelMeansNormal": False,
        "modelPredictionIsExpertTruth": False,
        "sourcePersonGroupSplitIndependent": True,
        "thresholdsLockedBeforeFinalTest": True,
        "validationPassed": True,
        "untouchedFinalTestPassed": True,
        "physicalCameraPassed": True,
        "workingProductIntegrationPassed": True,
        "acceptanceEvidence": {
            "path": f"docs/skin/evidence/{method_id}.json",
            "sha256": "a" * 64,
        },
    }


def _ready_receipt():
    receipt = copy.deepcopy(_receipt())
    for field in receipt["preparation"]:
        receipt["preparation"][field] = True
    receipt["candidate"] = {
        "mode": "accepted-registry",
        "registryId": "skin-type-regional-registry-v1",
        "registryEvidence": {
            "path": "docs/skin/evidence/skin-type-regional-registry-v1.json",
            "sha256": "b" * 64,
        },
        "methods": [
            _learned_method("oily_t_zone", "oily-v2", ["forehead", "nose", "chin"], "polygon"),
            _learned_method("outside_dry", "dry-v2", ["leftCheek", "rightCheek"], "polygon"),
        ],
    }
    receipt["combinationValidation"] = {
        "methodIds": ["dry-v2", "oily-v2"],
        "policyLockedBeforeFinalTest": True,
        "validationPassed": True,
        "untouchedFinalTestPassed": True,
        "physicalCameraPassed": True,
        "lightingSkinTonePoseSlicesPassed": True,
        "workingProductIntegrationPassed": True,
        "coverageOverlapAndUnavailableControlsPassed": True,
        "historyWriteReadPassed": True,
        "acceptanceEvidence": {
            "path": "docs/skin/evidence/combination-v2-acceptance.json",
            "sha256": "c" * 64,
        },
    }
    return receipt


class SkinTypeCombinationReleaseTests(unittest.TestCase):
    def test_current_product_is_preserved_while_registry_is_empty(self):
        result = module.evaluate_release(_receipt())
        self.assertTrue(result["existingGlobalSkinTypeFlowPreserved"])
        self.assertTrue(result["existingConcreteResultFlowPreserved"])
        self.assertFalse(result["acceptedRegistryPresent"])
        self.assertFalse(result["researchTrainingAuthorized"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["combinationProductActivationAllowed"])
        self.assertIn("accepted_regional_method_registry_empty", result["testBlockers"])

    def test_booleans_alone_cannot_create_an_accepted_registry(self):
        receipt = _receipt()
        for field in receipt["preparation"]:
            receipt["preparation"][field] = True
        for field in receipt["combinationValidation"]:
            if field not in {"methodIds", "acceptanceEvidence"}:
                receipt["combinationValidation"][field] = True
        result = module.evaluate_release(receipt)
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertFalse(result["acceptedRegistryPresent"])
        self.assertFalse(result["finalTestEvaluationAuthorized"])
        self.assertFalse(result["combinationProductActivationAllowed"])

    def test_not_populated_registry_cannot_smuggle_method_identity(self):
        receipt = _receipt()
        receipt["candidate"]["registryId"] = "fake"
        with self.assertRaisesRegex(module.GateInputError, "cannot claim"):
            module.evaluate_release(receipt)

    def test_whole_face_box_missing_and_redness_contracts_are_pinned(self):
        mutations = (
            ("wholeFaceCopiedToRegionsAllowed", True, "whole-face"),
            ("boxesAsRegionalTruthAllowed", True, "Boxes|boxes"),
            ("missingLabelMeansNormal", True, "missing labels"),
            ("rednessMeansSensitivity", True, "sensitivity"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field):
                receipt = _receipt()
                receipt["combinationContract"][field] = value
                with self.assertRaisesRegex(module.GateInputError, message):
                    module.evaluate_release(receipt)

    def test_leaking_box_source_cannot_become_final_truth(self):
        receipt = _receipt()
        receipt["rejectedBoxSource"]["testEligibleForFinalAcceptance"] = True
        with self.assertRaisesRegex(module.GateInputError, "cannot become final"):
            module.evaluate_release(receipt)

    def test_known_rejected_model_cannot_enter_registry(self):
        receipt = _ready_receipt()
        method = receipt["candidate"]["methods"][0]
        method["datasetVersion"] = 1
        method["modelId"] = module.REJECTED_REGIONAL_MODEL_ID
        with self.assertRaisesRegex(module.GateInputError, "dataset version|rejected model"):
            module.evaluate_release(receipt)

    def test_t_zone_requires_forehead_nose_and_chin(self):
        receipt = _ready_receipt()
        receipt["candidate"]["methods"][0]["regions"] = ["forehead", "nose"]
        with self.assertRaisesRegex(module.GateInputError, "coverage incomplete"):
            module.evaluate_release(receipt)

    def test_outside_support_requires_both_cheeks(self):
        receipt = _ready_receipt()
        receipt["candidate"]["methods"][1]["regions"] = ["leftCheek"]
        with self.assertRaisesRegex(module.GateInputError, "coverage incomplete"):
            module.evaluate_release(receipt)

    def test_explicit_normal_must_be_uncoloured_evaluated_truth(self):
        receipt = _ready_receipt()
        receipt["candidate"]["methods"][1] = _learned_method(
            "outside_normal", "normal-v2", ["leftCheek", "rightCheek"], "polygon"
        )
        receipt["combinationValidation"]["methodIds"] = ["normal-v2", "oily-v2"]
        with self.assertRaisesRegex(module.GateInputError, "Normal requires explicit"):
            module.evaluate_release(receipt)

    def test_combination_validation_must_bind_exact_method_ids(self):
        receipt = _ready_receipt()
        receipt["combinationValidation"]["methodIds"] = ["oily-v2"]
        with self.assertRaisesRegex(module.GateInputError, "not bound"):
            module.evaluate_release(receipt)

    def test_evidence_hashes_are_required_not_mutable_labels(self):
        receipt = _ready_receipt()
        receipt["candidate"]["methods"][0]["acceptanceEvidence"]["sha256"] = "accepted"
        with self.assertRaisesRegex(module.GateInputError, "sha256"):
            module.evaluate_release(receipt)

    def test_complete_identity_bound_registry_can_pass(self):
        result = module.evaluate_release(_ready_receipt())
        self.assertEqual(result["decision"], "ready")
        self.assertEqual(result["acceptedMethodIds"], ["dry-v2", "oily-v2"])
        self.assertTrue(result["researchTrainingAuthorized"])
        self.assertTrue(result["finalTestEvaluationAuthorized"])
        self.assertTrue(result["combinationProductActivationAllowed"])


if __name__ == "__main__":
    unittest.main()
