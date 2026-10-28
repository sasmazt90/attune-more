import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_source_mapping_release_candidate.py"
SPEC = importlib.util.spec_from_file_location("build_source_mapping_release_candidate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/source-mapping-release-receipt-20261028-v2.json"
GATE_TEST_PATH = Path(__file__).with_name("test_check_source_mapping_release.py")
GATE_TEST_SPEC = importlib.util.spec_from_file_location("source_mapping_gate_fixture_for_builder", GATE_TEST_PATH)
GATE_TEST = importlib.util.module_from_spec(GATE_TEST_SPEC)
sys.modules[GATE_TEST_SPEC.name] = GATE_TEST
GATE_TEST_SPEC.loader.exec_module(GATE_TEST)


def base_receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def empty_manifest():
    return {
        "schemaVersion": 1,
        "methodVersion": MODULE.INPUT_METHOD,
        "artifacts": {name: None for name in MODULE.ARTIFACT_NAMES},
    }


def complete_fixture(root):
    future = base_receipt()
    GATE_TEST._install_complete_artifacts(future["acceptanceCandidate"], root)
    manifest = empty_manifest()
    manifest["artifacts"] = {
        name: identity["path"]
        for name, identity in future["acceptanceCandidate"]["artifacts"].items()
    }
    return manifest


class SourceMappingReleaseCandidateBuilderTest(unittest.TestCase):
    def test_empty_manifest_stays_blocked(self):
        result = MODULE.evaluate_manifest(base_receipt(), empty_manifest())
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["artifactCount"], 0)
        self.assertEqual(len(result["blockers"]), 8)
        self.assertFalse(result["trainingDataReleaseAuthorized"])

    def test_complete_registry_emits_gate_accepted_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = complete_fixture(root)
            receipt = MODULE.build_candidate_receipt(base_receipt(), manifest, root)
            gate = MODULE.build_gate_output(base_receipt(), manifest, root)
        self.assertTrue(gate["evidenceRegistryComplete"])
        self.assertTrue(gate["trainingDataReleaseAuthorized"])
        self.assertTrue(gate["productTruthAuthorized"])
        self.assertEqual(set(receipt["acceptanceCandidate"]["artifacts"]), set(MODULE.ARTIFACT_NAMES))

    def test_registry_sha_and_receipt_sha_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = complete_fixture(root)
            reverse = copy.deepcopy(manifest)
            reverse["artifacts"] = dict(reversed(list(reverse["artifacts"].items())))
            first = MODULE.evaluate_manifest(base_receipt(), manifest, root)
            second = MODULE.evaluate_manifest(base_receipt(), reverse, root)
        self.assertEqual(first["artifactRegistrySHA256"], second["artifactRegistrySHA256"])
        self.assertEqual(first["candidateReceiptSHA256"], second["candidateReceiptSHA256"])

    def test_path_traversal_and_non_registry_path_fail_hard(self):
        for path in ("../private.json", "/tmp/private.json", "private.json"):
            manifest = empty_manifest()
            manifest["artifacts"]["excludedArchiveInventory"] = path
            with self.subTest(path=path):
                with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "outside the public source evidence registry"):
                    MODULE.evaluate_manifest(base_receipt(), manifest)

    def test_method_mismatch_fails_before_receipt_emission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = complete_fixture(root)
            path = root / manifest["artifacts"]["excludedArchiveInventory"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["methodVersion"] = "wrong"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "method identity changed"):
                MODULE.evaluate_manifest(base_receipt(), manifest, root)

    def test_mixed_release_identities_fail_hard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = complete_fixture(root)
            path = root / manifest["artifacts"]["cameraReservation"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["releaseRef"] = "release_9999999999999999"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "release identities disagree"):
                MODULE.evaluate_manifest(base_receipt(), manifest, root)

    def test_missing_artifact_cannot_emit_receipt_or_gate(self):
        manifest = empty_manifest()
        with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "candidate is incomplete"):
            MODULE.build_candidate_receipt(base_receipt(), manifest)
        with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "candidate is incomplete"):
            MODULE.build_gate_output(base_receipt(), manifest)

    def test_manifest_inventory_and_fields_are_exact(self):
        bad = empty_manifest()
        bad["privateNotes"] = "not allowed"
        with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "fields changed"):
            MODULE.evaluate_manifest(base_receipt(), bad)
        bad = empty_manifest()
        bad["artifacts"].pop("cameraReservation")
        with self.assertRaisesRegex(MODULE.SourceMappingCandidateInputError, "inventory is incomplete"):
            MODULE.evaluate_manifest(base_receipt(), bad)


if __name__ == "__main__":
    unittest.main()
