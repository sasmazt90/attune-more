import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_attune_v5_results_package.py"
SPEC = importlib.util.spec_from_file_location("attune_v5_audit", SCRIPT)
audit_module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit_module)


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


def fixture_zip(path):
    files = {}
    source_rows = []
    summary_rows = []
    verification_rows = []
    for person_index, person in enumerate(audit_module.PEOPLE):
        for pose_index, pose in enumerate(audit_module.POSES):
            source_hash = hashlib.sha256(f"{person}/{pose}".encode()).hexdigest()
            photo_id = hashlib.sha256(f"rgba/{person}/{pose}".encode()).hexdigest()
            width, height = 20, 10
            source_rows.append({
                "personId": person, "pose": pose, "file": f"{person}/fixture.jpg",
                "sha256": source_hash, "width": width, "height": height,
                "sourceType": "generated-still-image-replay", "staticPreflightAccepted": True,
                "measuredPhotoId": photo_id,
            })
            summary_rows.append({
                "personId": person, "pose": pose, "inputSHA256": source_hash,
                "analysisStatus": "completed", "httpStatus": 200,
                "productAttachmentSucceeded": True, "measurementCount": 9,
                "measured": 9, "unavailable": 0,
            })
            verification_rows.append({
                "personId": person, "pose": pose,
                "checks": {"sourceFileHashMatches": True, "actualHTTP200": True},
            })
            measurements = ({name: {} for name in audit_module.REGIONS} if pose == "FRONT" else {"leftCheek": {}})
            response = {
                "photoId": photo_id, "sourceWidth": width, "sourceHeight": height,
                "storage": "volatile-memory-only", "measurements": measurements,
                "maps": {}, "contours": {},
            }
            if pose == "FRONT":
                response["general"] = {
                    "measurements": [{"id": name, "quality": "valid", "value": 1.0} for name in audit_module.CRITERIA],
                    "skinType": {"quality": "valid", "value": "normal"},
                }
            prefix = f"{person}/{pose}"
            files[f"{prefix}/response.json"] = encoded(response)
            files[f"{prefix}/request-metadata.json"] = encoded({"photoId": photo_id})
            files[f"{prefix}/http.json"] = encoded({"url": f"http://127.0.0.1:1{audit_module.ENDPOINT}", "httpStatus": 200})
            files[f"{prefix}/request-transport.json"] = encoded({"url": f"http://127.0.0.1:1{audit_module.ENDPOINT}", "method": "POST"})

    files["run-manifest.json"] = encoded({
        "status": "finished", "sourceType": "generated-still-image-replay",
        "physicalCameraAcceptance": False, "temporalSamples": 0,
        "temporalStability": "not_measured", "productOrModelOrThresholdChanges": False,
        "protectedFilesUnchanged": True, "counts": {"completed": 18, "failed": 0},
        "git": {"baseCommit": audit_module.BASE_COMMIT, "localRevisionSHA256": "a" * 64},
    })
    files["input-manifest.json"] = encoded({
        "personCount": 6, "imageCount": 18, "physicalCameraAcceptance": False, "files": source_rows,
    })
    files["summary.json"] = encoded({"expectedInputs": 18, "completedInputs": 18, "inputs": summary_rows})
    files["artifact-verification.json"] = encoded({
        "passed": True, "verifiedInputs": 18, "verifiedCompletePeople": 6, "inputChecks": verification_rows,
    })
    checksums = [
        {"file": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        for name, payload in sorted(files.items())
    ]
    files["checksums.json"] = encoded(checksums)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in files.items():
            zf.writestr(name, payload)


class AttuneV5AuditTest(unittest.TestCase):
    def test_complete_package_exports_six_fronts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            fixture_zip(path)
            bundle, evidence = audit_module.audit(path)
        self.assertEqual(len(bundle["captures"]), 6)
        self.assertEqual(evidence["completedInputs"], 18)
        self.assertFalse(evidence["claims"]["accuracyMeasured"])

    def test_archive_hash_mismatch_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            fixture_zip(path)
            with self.assertRaisesRegex(audit_module.AuditError, "archive SHA-256 mismatch"):
                audit_module.audit(path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
