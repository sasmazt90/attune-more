import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "audit_gate_pass_camera_package.py"
SPEC = importlib.util.spec_from_file_location("gate_audit", SCRIPT)
gate_audit = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate_audit)


def png(width=2, height=3):
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"rest"


def package(path, mutate=None):
    files = {}
    manifest_rows = []
    previous = {"subjects": []}
    model_hash = "f" * 64
    for index in range(6):
        person = f"{index + 1:02d}_subject"
        subject = {"subjectKey": person, "poses": {}}
        for pose, folder in (("FRONT", "front"), ("RIGHT", "side_1"), ("LEFT", "side_2")):
            image_path = f"{person}/{folder}.png"
            raw = png(2 + index, 3 + index) + pose.encode()
            digest = gate_audit._sha(raw)
            photo_id = gate_audit._sha((image_path + "rgba").encode())
            evidence = f"evidence/{person}/{folder}"
            preflight = {
                "personId": person,
                "pose": pose,
                "sourceWidth": 2 + index,
                "sourceHeight": 3 + index,
                "acquisitionAlignment": {"landmarks": [{}] * 478},
                "quality": {"isValid": True, "status": "OPTIMAL"},
                "staticPreflightAccepted": True,
                "matchesSkinAngle": True,
                "reasons": [],
                "geometryError": None,
                "physicalCameraAcceptance": False,
                "temporalStabilityStatus": "not_measured_still_image",
                "photoId": photo_id,
            }
            capture = {
                "version": gate_audit.CAPTURE_CHECK_VERSION,
                "modelHash": model_hash,
                "probability": 0.1,
                "status": "CLEAR",
                "frameToken": f"token-{index}-{pose}",
            }
            files[image_path] = raw
            files[f"{evidence}/preflight.json"] = json.dumps(preflight).encode()
            files[f"{evidence}/capture-check-response.json"] = json.dumps(capture).encode()
            manifest_rows.append(
                {
                    "personId": person,
                    "pose": pose,
                    "file": image_path,
                    "bytes": len(raw),
                    "sha256": digest,
                    "width": 2 + index,
                    "height": 3 + index,
                    "sourceKind": "fixture",
                    "staticPreflightAccepted": True,
                    "gateEvidence": evidence,
                    "measuredPhotoId": photo_id,
                }
            )
            if pose == "FRONT":
                subject["poses"]["front"] = {"sha256": digest}
        previous["subjects"].append(subject)
    manifest = {
        "personCount": 6,
        "imageCount": 18,
        "staticGatePassedCount": 18,
        "physicalCameraAcceptance": False,
        "fullV5SkinAnalysisCompletedForThisSet": False,
        "files": manifest_rows,
    }
    files["manifest.json"] = json.dumps(manifest).encode()
    files["README.txt"] = b"fixture"
    if mutate:
        mutate(files, manifest, previous)
        files["manifest.json"] = json.dumps(manifest).encode()
    checksums = [
        {"file": name, "bytes": len(raw), "sha256": gate_audit._sha(raw)}
        for name, raw in files.items()
    ]
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        archive.writestr("checksums.json", json.dumps(checksums))
    return previous


class GatePackageAuditTest(unittest.TestCase):
    def test_complete_package_passes_and_reuses_fronts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            previous = package(path)
            result = gate_audit.audit(path, previous, "libfile_fixture")
            self.assertEqual(result["gate"]["images"], 18)
            self.assertTrue(result["reuseDecision"]["frontHashSetMatchesSavedRoboflowInputs"])
            self.assertFalse(result["reuseDecision"]["repeatRoboflowInferenceRequired"])

    def test_tampered_checksum_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            previous = package(path)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("README.txt", b"tampered")
            with self.assertRaisesRegex(gate_audit.AuditError, "duplicate paths"):
                gate_audit.audit(path, previous)

    def test_failed_preflight_is_blocked(self):
        def mutate(files, _manifest, _previous):
            key = "evidence/01_subject/front/preflight.json"
            value = json.loads(files[key])
            value["staticPreflightAccepted"] = False
            files[key] = json.dumps(value).encode()

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            previous = package(path, mutate)
            with self.assertRaisesRegex(gate_audit.AuditError, "pose gate failed"):
                gate_audit.audit(path, previous)

    def test_changed_front_set_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            previous = package(path)
            previous["subjects"][0]["poses"]["front"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(gate_audit.AuditError, "FRONT image set changed"):
                gate_audit.audit(path, previous)

    def test_claimed_physical_camera_acceptance_is_blocked(self):
        def mutate(_files, manifest, _previous):
            manifest["physicalCameraAcceptance"] = True

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.zip"
            previous = package(path, mutate)
            with self.assertRaisesRegex(gate_audit.AuditError, "physical-camera"):
                gate_audit.audit(path, previous)


if __name__ == "__main__":
    unittest.main()
