import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "skin-research"
    / "audit_original_photo_model_comparison.py"
)
EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "skin"
    / "evidence"
    / "original-photo-model-comparison-audit-20261024.json"
)
SPEC = importlib.util.spec_from_file_location("comparison_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fixture(*, bad_image=False, map_label="Sensitive", capped=True):
    photos = []
    for index, (profile, identity) in enumerate(MODULE.EXPECTED_PHOTOS.items()):
        image = bytes([index + 1])
        identity["jpeg"] = MODULE._sha256(image)
        predictions = {f"m{i}": [] for i in range(1, 11)}
        if capped and index == 0:
            predictions["m1"] = [
                {"x": 5, "y": 5, "w": 2, "h": 2, "score": 0.1, "cls": "Class1"}
                for _ in range(300)
            ]
        caps = {
            key: {
                "count": len(rows),
                "minimum": min((row["score"] for row in rows), default=None),
            }
            for key, rows in predictions.items()
        }
        totals = {"Dry": 0, "Oily": 0, map_label: 0, "Unknown": 100}
        photos.append(
            {
                "id": profile,
                "sha256": identity["jpeg"],
                "photoId": identity["photoId"],
                "image": "data:image/jpeg;base64,"
                + base64.b64encode(image + (b"x" if bad_image and index == 0 else b"")).decode(),
                "combinedStatus": "complete_static_replay",
                "width": 10,
                "height": 10,
                "predictions": predictions,
                "cap": caps,
                "skinmap": {
                    "validation": "valid",
                    "totals": totals,
                    "anatomyPixels": 100,
                    "outsideSkinTinted": 0,
                },
            }
        )
    models = [
        {
            "key": f"m{i}",
            "model_id": f"workspace/model-{i}",
            "project": f"model-{i}",
            "version": 1,
            "architecture": "test",
            "classes": [f"Class{i}"],
            "eval_id": None,
        }
        for i in range(1, 11)
    ]
    payload = {
        "v5SourceSHA256": MODULE.EXPECTED_V5_SOURCE_SHA256,
        "thresholds": MODULE.DISPLAY_THRESHOLDS,
        "models": models,
        "photos": photos,
        "metrics": [
            {
                "model": f"m{i}",
                "modelId": f"workspace/model-{i}",
                "split": "none",
            }
            for i in range(1, 11)
        ],
        "v5Evaluation": {
            "independentUnusedFinalTest": {"available": False},
            "current18GeneratedImages": {"groundTruthAvailable": False},
        },
    }
    return '<html><script id="data" type="application/json">' + json.dumps(payload) + "</script></html>"


class OriginalPhotoModelComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.original_photos = json.loads(json.dumps(MODULE.EXPECTED_PHOTOS))

    def tearDown(self):
        MODULE.EXPECTED_PHOTOS.clear()
        MODULE.EXPECTED_PHOTOS.update(self.original_photos)

    def _audit(self, html):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comparison.html"
            path.write_text(html, encoding="utf-8")
            return MODULE.audit(path, library_file_id="fixture")

    def test_privacy_safe_receipt_blocks_product_acceptance(self):
        receipt = self._audit(fixture())
        self.assertEqual(6, receipt["source"]["frontProfiles"])
        self.assertEqual(10, receipt["integrity"]["modelIdentitiesPinned"])
        self.assertFalse(receipt["source"]["physicalCameraAcceptance"])
        self.assertFalse(receipt["evaluation"]["accuracyMeasuredOnCurrentProfiles"])
        self.assertFalse(receipt["acceptance"]["passed"])
        self.assertIn(
            "regional_map_uses_sensitive_label_instead_of_independent_redness_layer",
            receipt["acceptance"]["blockers"],
        )
        self.assertEqual(1, receipt["exploration"]["cappedProfileModelPairs"])

    def test_tampered_embedded_image_is_rejected(self):
        with self.assertRaisesRegex(MODULE.AuditError, "embedded image hash mismatch"):
            self._audit(fixture(bad_image=True))

    def test_accepted_redness_label_removes_map_contract_blocker(self):
        receipt = self._audit(fixture(map_label="Redness", capped=False))
        self.assertTrue(receipt["regionalMap"]["contractMatches"])
        self.assertNotIn(
            "regional_map_uses_sensitive_label_instead_of_independent_redness_layer",
            receipt["acceptance"]["blockers"],
        )

    def test_committed_receipt_preserves_fail_closed_gates(self):
        receipt = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            "83def109c93c2ca5b16580cee9f61ddb5ba08dd18f8f86e214aa9bb00139752e",
            receipt["artifact"]["sha256"],
        )
        self.assertEqual(6, receipt["integrity"]["embeddedImagesVerified"])
        self.assertEqual(15, receipt["exploration"]["cappedProfileModelPairs"])
        self.assertFalse(receipt["regionalMap"]["contractMatches"])
        self.assertFalse(receipt["evaluation"]["productionActivationAuthorized"])
        self.assertFalse(receipt["acceptance"]["passed"])


if __name__ == "__main__":
    unittest.main()
