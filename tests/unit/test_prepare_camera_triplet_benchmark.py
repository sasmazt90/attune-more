import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "skin-research"
    / "prepare_camera_triplet_benchmark.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_camera_triplet_benchmark", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ManifestError = MODULE.ManifestError
build_manifest = MODULE.build_manifest


def _jpeg(width: int, height: int, salt: int) -> bytes:
    # Minimal stream sufficient for deterministic metadata parsing. The salt
    # prevents the fixtures from accidentally becoming byte-identical.
    sof = bytes(
        [
            0xFF,
            0xC0,
            0x00,
            0x11,
            0x08,
            (height >> 8) & 0xFF,
            height & 0xFF,
            (width >> 8) & 0xFF,
            width & 0xFF,
            0x03,
            0x01,
            0x11,
            0x00,
            0x02,
            0x11,
            0x00,
            0x03,
            0x11,
            salt,
        ]
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _triplet(root: Path, subject: str = "1.England") -> None:
    for index, pose in enumerate(("front", "side_1", "side_2"), start=1):
        (root / f"{subject}_{pose}.jpg").write_bytes(_jpeg(2048, 1529, index))


class CameraTripletManifestTests(unittest.TestCase):
    def test_complete_generated_triplet_is_smoke_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _triplet(root)
            manifest = build_manifest(root, declared_generated=True)
        self.assertTrue(manifest["capturePackage"]["completeTriplets"])
        self.assertTrue(manifest["eligibility"]["captureAndIntegrationSmokeTest"])
        self.assertFalse(manifest["eligibility"]["precisionRecallF1"])
        self.assertFalse(manifest["eligibility"]["realCameraAcceptance"])
        self.assertFalse(manifest["source"]["rawImagesCommitted"])

    def test_missing_pose_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _triplet(root)
            (root / "1.England_side_2.jpg").unlink()
            with self.assertRaisesRegex(ManifestError, "incomplete triplets"):
                build_manifest(root, declared_generated=True)

    def test_duplicate_image_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _triplet(root)
            front = (root / "1.England_front.jpg").read_bytes()
            (root / "1.England_side_2.jpg").write_bytes(front)
            with self.assertRaisesRegex(ManifestError, "duplicate image bytes"):
                build_manifest(root, declared_generated=True)

    def test_unexpected_jpeg_filename_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _triplet(root)
            (root / "unscoped.jpg").write_bytes(_jpeg(10, 10, 7))
            with self.assertRaisesRegex(ManifestError, "unexpected filenames"):
                build_manifest(root, declared_generated=True)


if __name__ == "__main__":
    unittest.main()
