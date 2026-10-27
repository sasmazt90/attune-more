import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "reconcile_excluded_archive_inventory.py"
SPEC = importlib.util.spec_from_file_location("reconcile_excluded_archive_inventory", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
REPO_ROOT = MODULE_PATH.resolve().parents[2]
RECEIPT = REPO_ROOT / "docs/skin/evidence/excluded-archive-inventory-receipt-20261026-v1.json"


def receipt():
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def entry(index):
    return {
        "opaqueId": f"excluded-{index:012x}",
        "archiveSHA256": f"{index + 1:064x}",
        "disposition": "user_excluded",
        "accessed": False,
        "mutated": False,
        "uploaded": False,
        "usedForTraining": False,
        "usedForProductTruth": False,
    }


class ExcludedArchiveInventoryTest(unittest.TestCase):
    def test_current_public_receipt_is_preserved_but_not_reconciled(self):
        result = MODULE.evaluate_inventory(receipt())
        self.assertTrue(result["preservationPolicyEnforced"])
        self.assertFalse(result["inventoryReconciled"])
        self.assertEqual(result["candidateArchiveCount"], 0)

    def test_three_entries_never_satisfy_four_archive_policy(self):
        current = receipt()
        current["privateInventoryCandidate"]["entries"] = [entry(i) for i in range(3)]
        current["privateInventoryCandidate"]["completePrivateInventoryReviewed"] = True
        result = MODULE.evaluate_inventory(current)
        self.assertFalse(result["inventoryReconciled"])
        self.assertIn("four_opaque_archive_hashes_not_recorded", result["blockers"])

    def test_public_name_path_or_selected_source_overlap_fails_hard(self):
        current = receipt()
        named = entry(0)
        named["filename"] = "private.zip"
        current["privateInventoryCandidate"]["entries"] = [named]
        with self.assertRaisesRegex(MODULE.ReconciliationError, "names, paths or URLs"):
            MODULE.evaluate_inventory(current)
        current = receipt()
        current["privateInventoryCandidate"]["selectedSourceHashOverlap"] = ["a" * 64]
        with self.assertRaisesRegex(MODULE.ReconciliationError, "overlaps"):
            MODULE.evaluate_inventory(current)

    def test_duplicate_identity_or_mutation_fails_hard(self):
        current = receipt()
        current["privateInventoryCandidate"]["entries"] = [entry(0), entry(0)]
        with self.assertRaisesRegex(MODULE.ReconciliationError, "unique"):
            MODULE.evaluate_inventory(current)
        current = receipt()
        changed = entry(0)
        changed["mutated"] = True
        current["privateInventoryCandidate"]["entries"] = [changed]
        with self.assertRaisesRegex(MODULE.ReconciliationError, "mutated"):
            MODULE.evaluate_inventory(current)

    def test_four_unique_private_hashes_can_reconcile_without_public_names(self):
        future = copy.deepcopy(receipt())
        future["privateInventoryCandidate"]["entries"] = [entry(i) for i in range(4)]
        future["privateInventoryCandidate"]["completePrivateInventoryReviewed"] = True
        result = MODULE.evaluate_inventory(future)
        self.assertTrue(result["inventoryReconciled"])
        self.assertTrue(result["sourceReleaseContributionAllowed"])
        self.assertFalse(result["publicNamesOrPathsStored"])


if __name__ == "__main__":
    unittest.main()
