import copy
import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build_regional_mask_expert_protocol.py"
SPEC = importlib.util.spec_from_file_location("regional_mask_expert_protocol", SCRIPT)
protocol = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(protocol)


def queue():
    items = []
    for name, count in protocol.EXPECTED_CLASS_COUNTS.items():
        for index in range(count):
            items.append({
                "reviewItemId": f"{len(items):024x}",
                "className": name,
                "split": "train" if index % 2 == 0 else "valid",
                "missingClassIsNegative": False,
            })
    return {
        "schemaVersion": "regional-mask-expert-review-queue-v1",
        "source": {
            "sourceArchiveSHA256": protocol.EXPECTED_ARCHIVE_SHA256,
            "providerExportSHA256": protocol.EXPECTED_PROVIDER_EXPORT_SHA256,
            "versionNumber": 1,
        },
        "privacy": {
            "containsImageBytes": False,
            "containsFilenames": False,
            "containsRawSourceNames": False,
            "containsProviderImageIds": False,
            "resolverCommitted": False,
        },
        "selection": {
            "allowedSplits": ["train", "valid"],
            "testImagesRead": 0,
            "testImagesSelected": 0,
            "selectedUniqueImages": protocol.EXPECTED_ITEMS,
        },
        "reviewPolicy": {
            "reviewerRequired": "expert_review",
            "rednessIndependentLayer": True,
            "missingMaskMeansNormal": False,
            "missingClassIsNegative": False,
            "modelPredictionAcceptedAsTruth": False,
        },
        "items": items,
    }


def completed_decisions(template):
    value = copy.deepcopy(template)
    value["reviewer"] = "expert_review"
    for row in value["classPolicies"]:
        row["maskExtentPolicyLocked"] = True
        row["hardNegativePolicyLocked"] = True
        row["ambiguousCasePolicyLocked"] = True
    for row in value["items"]:
        row["expertReviewed"] = True
        row["assessability"] = "assessable"
        row["maskExtentDecision"] = "correct"
        row["semanticDecision"] = "keep"
    return value


class RegionalMaskExpertProtocolTests(unittest.TestCase):
    def test_template_is_fail_closed_and_privacy_safe(self):
        value = protocol.build_template(queue(), protocol.EXPECTED_QUEUE_SHA256)
        self.assertEqual(len(value["items"]), protocol.EXPECTED_ITEMS)
        self.assertTrue(all(row["expertReviewed"] is False for row in value["items"]))
        self.assertFalse(value["decision"]["maskProtocolReady"])
        rendered = json.dumps(value).lower()
        self.assertNotIn(".jpg", rendered)
        self.assertFalse(value["privacy"]["containsFilenames"])

    def test_complete_exact_review_builds_protocol_without_authorizing_training(self):
        source = queue()
        template = protocol.build_template(source, protocol.EXPECTED_QUEUE_SHA256)
        result = protocol.build_protocol(
            source,
            protocol.EXPECTED_QUEUE_SHA256,
            completed_decisions(template),
        )
        self.assertTrue(result["decision"]["maskProtocolReady"])
        self.assertFalse(result["decision"]["trainingAuthorized"])
        self.assertEqual(
            {row["name"]: len(row["reviewedItemIds"]) for row in result["classes"]},
            protocol.EXPECTED_CLASS_COUNTS,
        )

    def test_pending_duplicate_and_wrong_binding_are_rejected(self):
        source = queue()
        template = protocol.build_template(source, protocol.EXPECTED_QUEUE_SHA256)
        with self.assertRaisesRegex(protocol.ProtocolError, "reviewer"):
            protocol.build_protocol(source, protocol.EXPECTED_QUEUE_SHA256, template)
        value = completed_decisions(template)
        value["items"][1]["reviewItemId"] = value["items"][0]["reviewItemId"]
        with self.assertRaisesRegex(protocol.ProtocolError, "unknown or duplicated"):
            protocol.build_protocol(source, protocol.EXPECTED_QUEUE_SHA256, value)
        value = completed_decisions(template)
        value["items"][0]["className"] = "Redness"
        with self.assertRaisesRegex(protocol.ProtocolError, "binding"):
            protocol.build_protocol(source, protocol.EXPECTED_QUEUE_SHA256, value)

    def test_non_assessable_and_bad_extent_cannot_be_kept(self):
        source = queue()
        template = protocol.build_template(source, protocol.EXPECTED_QUEUE_SHA256)
        value = completed_decisions(template)
        value["items"][0].update({
            "assessability": "ambiguous",
            "maskExtentDecision": "not_assessable",
            "semanticDecision": "keep",
        })
        with self.assertRaisesRegex(protocol.ProtocolError, "must be excluded"):
            protocol.build_protocol(source, protocol.EXPECTED_QUEUE_SHA256, value)
        value = completed_decisions(template)
        value["items"][0].update({
            "maskExtentDecision": "too_broad",
            "semanticDecision": "keep",
        })
        with self.assertRaisesRegex(protocol.ProtocolError, "cannot be kept"):
            protocol.build_protocol(source, protocol.EXPECTED_QUEUE_SHA256, value)

    def test_queue_digest_and_test_isolation_are_enforced(self):
        with self.assertRaisesRegex(protocol.ProtocolError, "digest"):
            protocol.build_template(queue(), "0" * 64)
        value = queue()
        value["selection"]["testImagesRead"] = 1
        with self.assertRaisesRegex(protocol.ProtocolError, "test isolated"):
            protocol.build_template(value, protocol.EXPECTED_QUEUE_SHA256)


if __name__ == "__main__":
    unittest.main()
