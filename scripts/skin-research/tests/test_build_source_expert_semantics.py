import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_expert_semantics.py"
SPEC = importlib.util.spec_from_file_location("build_source_expert_semantics", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
CURRENT_FACTS = REPO_ROOT / "docs/skin/evidence/source-expert-semantics-current-facts-20261028-v1.json"


def complete_manifest():
    manifest = {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "releaseRef": "release_1111111111111111",
        "sourceRegistryRef": "source_registry_2222222222222222",
        "targetsExpected": list(MODULE.TARGETS),
        "truthPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
        "mapContract": copy.deepcopy(MODULE.MAP_CONTRACT),
        "review": {
            "allTargetsReviewed": True,
            "expertAuthorizationConfirmed": True,
            "semanticDisagreementsResolved": True,
            "protocolsLockedBeforeDatasetRelease": True,
        },
        "targetSemantics": [],
    }
    for index, target in enumerate(MODULE.TARGETS, start=1):
        manifest["targetSemantics"].append({
            "target": target,
            "expertProtocolSHA256": f"{index:x}" * 64,
            "expertDefinitionLocked": True,
            "positiveExtentDefined": True,
            "evaluatedNegativeDefined": True,
            "unknownUnassessableDefined": True,
            "overlapPolicyDefined": True,
            "qualifiedHumanReviewRequired": True,
            "modelProposalsHiddenDuringReview": True,
            "sourceLabelsAcceptedAsExpertTruth": False,
        })
    return manifest


class SourceExpertSemanticsTest(unittest.TestCase):
    def test_committed_mapping_facts_stay_blocked(self):
        facts = json.loads(CURRENT_FACTS.read_text(encoding="utf-8"))
        result = MODULE.summarize_current_facts(facts)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["targets"], list(MODULE.TARGETS))
        self.assertFalse(result["perClassExpertSemanticsLocked"])
        self.assertFalse(result["mappingUsedAsExpertTruth"])
        self.assertEqual(result["mapContract"]["unknown"], "light-grey-never-normal")

    def test_complete_manifest_emits_gate_compatible_artifact(self):
        artifact = MODULE.build_release_artifact(complete_manifest())
        self.assertEqual(artifact["methodVersion"], MODULE.ARTIFACT_METHOD)
        self.assertEqual(artifact["targets"], list(MODULE.TARGETS))
        self.assertTrue(artifact["perClassExpertSemanticsLocked"])
        for field, expected in MODULE.SAFE_POLICY.items():
            self.assertEqual(artifact[field], expected)
        self.assertEqual(artifact["mapContract"]["dry"], "blue")
        self.assertEqual(artifact["mapContract"]["oily"], "green")

    def test_digest_is_deterministic_across_target_order(self):
        original = complete_manifest()
        reversed_manifest = copy.deepcopy(original)
        reversed_manifest["targetSemantics"].reverse()
        self.assertEqual(
            MODULE.build_release_artifact(original)["semanticsRegistryDigest"],
            MODULE.build_release_artifact(reversed_manifest)["semanticsRegistryDigest"],
        )

    def test_incomplete_template_is_blocked(self):
        template = {
            "schemaVersion": 1,
            "methodVersion": MODULE.INPUT_METHOD,
            "releaseRef": None,
            "sourceRegistryRef": None,
            "targetsExpected": list(MODULE.TARGETS),
            "truthPolicy": copy.deepcopy(MODULE.SAFE_POLICY),
            "mapContract": copy.deepcopy(MODULE.MAP_CONTRACT),
            "review": {
                "allTargetsReviewed": False,
                "expertAuthorizationConfirmed": False,
                "semanticDisagreementsResolved": False,
                "protocolsLockedBeforeDatasetRelease": False,
            },
            "targetSemantics": [],
        }
        result = MODULE.evaluate_private_manifest(template)
        self.assertIn("target_semantics_registry_empty", result["blockers"])
        with self.assertRaisesRegex(MODULE.SemanticsInputError, "expert semantics are incomplete"):
            MODULE.build_release_artifact(template)

    def test_unsafe_truth_promotions_fail_hard(self):
        for field, safe in MODULE.SAFE_POLICY.items():
            bad = complete_manifest()
            bad["truthPolicy"][field] = not safe
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.SemanticsInputError, "unsafe expert truth policy"):
                    MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["targetSemantics"][0]["sourceLabelsAcceptedAsExpertTruth"] = True
        with self.assertRaisesRegex(MODULE.SemanticsInputError, "source labels cannot substitute"):
            MODULE.evaluate_private_manifest(bad)

    def test_map_contract_changes_fail_hard(self):
        changes = {
            "dry": "green",
            "normal": "uncoloured-even-if-not-evaluated",
            "unknown": "normal",
            "mixedLayersAllowed": False,
            "combinationRequiresCoverageAndRuleValidation": False,
        }
        for field, value in changes.items():
            bad = complete_manifest()
            bad["mapContract"][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(MODULE.SemanticsInputError, "accepted map contract changed"):
                    MODULE.evaluate_private_manifest(bad)

    def test_incomplete_duplicate_or_unknown_target_is_blocked_or_rejected(self):
        bad = complete_manifest()
        bad["targetSemantics"].pop()
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("expert_target_inventory_incomplete", result["blockers"])
        bad = complete_manifest()
        bad["targetSemantics"][1]["target"] = bad["targetSemantics"][0]["target"]
        with self.assertRaisesRegex(MODULE.SemanticsInputError, "targets must be unique"):
            MODULE.evaluate_private_manifest(bad)
        bad = complete_manifest()
        bad["targetSemantics"][0]["expertDefinitionLocked"] = False
        result = MODULE.evaluate_private_manifest(bad)
        self.assertIn("target_semantic_0_expertDefinitionLocked_incomplete", result["blockers"])

    def test_private_semantics_and_model_payloads_fail_hard(self):
        for forbidden in ("definition", "reviewerId", "annotations", "polygons", "modelProposals"):
            bad = complete_manifest()
            bad["targetSemantics"][0][forbidden] = "private"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(MODULE.SemanticsInputError, "raw/private semantics or model payload"):
                    MODULE.evaluate_private_manifest(bad)


if __name__ == "__main__":
    unittest.main()
