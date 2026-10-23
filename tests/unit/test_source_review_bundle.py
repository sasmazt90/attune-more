"""Behavioural checks for review-only source preparation, without model training."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

from PIL import Image
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts' / 'skin-research'
sys.path.insert(0, str(SCRIPTS))
from audit_roadmap_archives import audit_sources
from prepare_source_review_bundle import build_bundle, choose_review_rows


def source(tmp_path):
    pixels = io.BytesIO()
    Image.new('RGB', (16, 16), (63, 70, 90)).save(pixels, format='PNG')
    image = {'id': 7, 'file_name': 'face.png', 'width': 16, 'height': 16}
    raw = {'id': 19, 'image_id': 7, 'category_id': 3, 'bbox': [1, 1, 12, 12],
           'segmentation': [[1, 1, 13, 1, 11, 13, 1, 10]], 'iscrowd': 0}
    doc = {'images': [image], 'annotations': [raw], 'categories': [{'id': 3, 'name': 'normal'}],
           'licenses': [{'id': 1, 'name': 'CC BY 4.0'}]}
    path = tmp_path / 'source.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('train/_annotations.coco.json', json.dumps(doc))
        z.writestr('train/face.png', pixels.getvalue())
        z.writestr('README.dataset.txt', 'Source fixture; CC BY 4.0')
    audit = audit_sources({'SOURCE': path})
    anns = {'SOURCE:train/face.png': [{'sourceLabel': 'normal', 'raw': raw}]}
    return path, audit, anns, raw, pixels.getvalue()


def test_original_pairs_and_unreviewed_normal_survive(tmp_path):
    path, audit, _, raw, pixels = source(tmp_path)
    out = tmp_path / 'review.zip'
    result = build_bundle(audit, {'SOURCE': path}, [], [['SOURCE', 'normal', 'mask', 1]],
                          {'SOURCE': {'license': 'CC BY 4.0'}}, out)
    assert result['commercialTrainingAccepted'] is False
    assert result['personIndependent'] is False
    assert result['images'][0]['reviewStatus'] == 'pending'
    assert result['images'][0]['expertReviewed'] is False
    with zipfile.ZipFile(out) as z:
        assert z.read('SOURCE/train/face.png') == pixels
        doc = json.loads(z.read('SOURCE/train/_annotations.coco.json'))
        assert doc['annotations'] == [raw]
        assert doc['categories'][0]['name'] == 'normal'
        assert z.read('SOURCE/source-documents/README.dataset.txt').endswith(b'CC BY 4.0')


@pytest.mark.parametrize('reason', ['valid', 'test', 'exact-cross-split', 'near-cross-split', 'known-existing'])
def test_holdout_candidates_and_known_existing_pixels_are_excluded(tmp_path, reason):
    _, audit, anns, _, _ = source(tmp_path)
    row = audit['images'][0]
    previous = []
    if reason in ('valid', 'test'):
        row['split'] = reason
    elif reason == 'exact-cross-split':
        audit['exactGroups'].append({'crossSplit': True, 'members': [row['key']]})
    elif reason == 'near-cross-split':
        audit['perceptualCandidates'].append({'crossSplit': True, 'left': row['key'], 'right': 'other'})
    else:
        previous = [{**row, 'key': 'old:train/photo.jpg'}]
    selected, _, shortfalls = choose_review_rows(audit, previous, anns, [['SOURCE', 'normal', 'mask', 1]])
    assert selected == []
    assert shortfalls[0]['availableSelected'] == 0


def test_rectangle_cannot_satisfy_mask_quota(tmp_path):
    _, audit, anns, _, _ = source(tmp_path)
    anns['SOURCE:train/face.png'][0]['raw']['segmentation'] = [[1, 1, 13, 1, 13, 13, 1, 13]]
    selected, _, _ = choose_review_rows(audit, [], anns, [['SOURCE', 'normal', 'mask', 1]])
    assert selected == []
    selected, _, _ = choose_review_rows(audit, [], anns, [['SOURCE', 'normal', 'box', 1]])
    assert selected[0]['selectionSupervision'] == 'box'


def test_no_photo_is_counted_twice_for_multiple_targets(tmp_path):
    _, audit, anns, raw, _ = source(tmp_path)
    anns['SOURCE:train/face.png'].append({'sourceLabel': 'oily', 'raw': copy.deepcopy(raw)})
    chosen, _, shortfalls = choose_review_rows(audit, [], anns,
        [['SOURCE', 'normal', 'mask', 1], ['SOURCE', 'oily', 'mask', 1]])
    assert len(chosen) == 1
    assert shortfalls[0]['target'] == 'oily'


def test_archive_drift_and_overwrite_are_rejected(tmp_path):
    path, audit, _, _, _ = source(tmp_path)
    out = tmp_path / 'review.zip'
    build_bundle(audit, {'SOURCE': path}, [], [], {}, out)
    with pytest.raises(FileExistsError):
        build_bundle(audit, {'SOURCE': path}, [], [], {}, out)
    with path.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='SOURCE_ARCHIVE_HASH_MISMATCH'):
        build_bundle(audit, {'SOURCE': path}, [], [], {}, tmp_path / 'different.zip')


def test_replay_is_byte_identical(tmp_path):
    path, audit, _, _, _ = source(tmp_path)
    first = build_bundle(audit, {'SOURCE': path}, [], [['SOURCE', 'normal', 'mask', 1]], {}, tmp_path / 'a.zip')
    second = build_bundle(audit, {'SOURCE': path}, [], [['SOURCE', 'normal', 'mask', 1]], {}, tmp_path / 'b.zip')
    assert first['bundleSHA256'] == second['bundleSHA256']
