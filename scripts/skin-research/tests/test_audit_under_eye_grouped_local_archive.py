import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "audit_under_eye_grouped_local_archive.py"
SPEC = importlib.util.spec_from_file_location("audit_under_eye_grouped_local_archive", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _archive(path: Path, *, bad_polygon: bool = False, duplicate_content: bool = False) -> None:
    image_bytes = {"train": b"a", "valid": b"b", "test": b"c"}
    if duplicate_content:
        image_bytes["valid"] = image_bytes["train"]
    with zipfile.ZipFile(path, "w") as archive:
        for split, payload in image_bytes.items():
            archive.writestr(f"{split}/sample.jpg", payload)
            ring = [0, 0, 1, 0, 1, 1] if not bad_polygon else [0, 0, 1, 1]
            archive.writestr(f"{split}/_annotations.coco.json", json.dumps({
                "images": [{"id": 1, "file_name": "sample.jpg", "width": 2, "height": 2}],
                "categories": [{"id": 1, "name": "darkcircle"}, {"id": 2, "name": "eyebag"}],
                "annotations": [{
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1 if split != "test" else 2,
                    "segmentation": [ring],
                    "bbox": [0, 0, 1, 1],
                    "area": 0.5,
                    "iscrowd": 0,
                }],
            }))


def _relax_contract(monkeypatch: pytest.MonkeyPatch, archive: Path) -> None:
    monkeypatch.setattr(MODULE, "AUTHORIZED_SHA256", MODULE._sha256_file(archive))
    monkeypatch.setattr(MODULE, "EXPECTED_BYTES", archive.stat().st_size)
    monkeypatch.setattr(MODULE, "EXPECTED_IMAGES", {"train": 1, "valid": 1, "test": 1})
    monkeypatch.setattr(MODULE, "EXPECTED_ANNOTATIONS", {"train": 1, "valid": 1, "test": 1})
    monkeypatch.setattr(MODULE, "EXPECTED_CLASSES", {"darkcircle": 2, "eyebag": 1})


def test_accepts_exact_polygon_archive_without_identifiers(tmp_path, monkeypatch):
    archive = tmp_path / "grouped.zip"
    _archive(archive)
    _relax_contract(monkeypatch, archive)
    receipt = MODULE.audit_archive(archive, observed_at="2026-10-28T22:08:15Z")
    assert receipt["images"] == 3
    assert receipt["crossSplitDuplicateImageBytes"] == 0
    assert receipt["polygonGeometryVerified"] is True
    assert receipt["uploadPerformed"] is False
    assert receipt["researchTrainingAuthorized"] is False
    assert "sample.jpg" not in json.dumps(receipt)


def test_rejects_wrong_archive_hash(tmp_path):
    archive = tmp_path / "grouped.zip"
    _archive(archive)
    with pytest.raises(MODULE.ArchiveAuditError, match="SHA256"):
        MODULE.audit_archive(archive, observed_at="2026-10-28T22:08:15Z")


def test_rejects_box_like_or_degenerate_segmentation(tmp_path, monkeypatch):
    archive = tmp_path / "grouped.zip"
    _archive(archive, bad_polygon=True)
    _relax_contract(monkeypatch, archive)
    with pytest.raises(MODULE.ArchiveAuditError, match="polygon"):
        MODULE.audit_archive(archive, observed_at="2026-10-28T22:08:15Z")


def test_rejects_duplicate_bytes_across_splits(tmp_path, monkeypatch):
    archive = tmp_path / "grouped.zip"
    _archive(archive, duplicate_content=True)
    _relax_contract(monkeypatch, archive)
    with pytest.raises(MODULE.ArchiveAuditError, match="duplicate image bytes"):
        MODULE.audit_archive(archive, observed_at="2026-10-28T22:08:15Z")
