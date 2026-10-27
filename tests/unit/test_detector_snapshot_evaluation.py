import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts/skin-research'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('snapshot_eval', SCRIPTS / 'evaluate_detector_snapshot.py')
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def fixture(tmp_path, split='valid', predictions=None):
    coco = dict(info={}, images=[dict(id=1, width=32, height=32, file_name='one.jpg')],
                categories=[dict(id=i + 1, name=k) for i, k in enumerate(E.CLASSES)],
                annotations=[dict(id=1, image_id=1, category_id=2, bbox=[4, 4, 8, 8], area=64, iscrowd=0)])
    archive = tmp_path / ('data-' + split + '.zip')
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(split + '/_annotations.coco.json', json.dumps(coco))
    folder = tmp_path / split; folder.mkdir()
    row = dict(source=dict(id='remote-image', cocoImageId=1), split=split, status='ok',
               requestedModel='pinned-model', resolvedModel=dict(model_id='pinned-model', model_package_id='package'),
               inferenceId='real-inference-receipt', image=dict(width=32, height=32), confidenceFloor=.05,
               predictions=predictions if predictions is not None else
               [dict(x=8, y=8, width=8, height=8, confidence=.9, **{'class': 'Pimple'})])
    path = folder / 'one.json'; path.write_text(json.dumps(row))
    return archive, folder, row, path


def test_iou_and_confidence_ordered_matching_do_not_double_count_truth():
    truth = {1: [dict(bbox=[0, 0, 10, 10], **{'class': 'Pimple'})]}
    predictions = {1: [dict(bbox=[0, 0, 10, 10], confidence=s, **{'class': 'Pimple'}) for s in [.2, .9]]}
    events, total = E.match_events(truth, predictions, 'Pimple')
    assert events == [(.9, True), (.2, False)] and total == 1
    assert E.point(events, total, .1)['tp'] == 1 and E.point(events, total, .1)['fp'] == 1
    assert E.iou([0, 0, 10, 10], [10, 10, 10, 10]) == 0


def test_wrong_class_cannot_match_correct_location():
    truth = {1: [dict(bbox=[0, 0, 10, 10], **{'class': 'Pimple'})]}
    predictions = {1: [dict(bbox=[0, 0, 10, 10], confidence=.9, **{'class': 'Post acne'})]}
    points = E.operating_points(truth, predictions, 'valid')
    assert points['Pimple']['tp'] == 0 and points['Pimple']['fn'] == 1


def test_test_split_must_not_choose_its_own_threshold():
    with pytest.raises(ValueError, match='TEST_REQUIRES'):
        E.operating_points({}, {}, 'test')
    points = E.operating_points({1: []}, {1: []}, 'test', {k: .3 for k in E.CLASSES})
    assert all(p['threshold'] == .3 for p in points.values())


def test_exact_box_ap_and_validation_lock(tmp_path):
    archive, folder, _, _ = fixture(tmp_path)
    result = E.evaluate(archive, folder, 'valid')
    assert result['coco'][0]['map50'] == pytest.approx(1)
    assert result['operatingPoints']['Pimple']['tp'] == 1
    assert result['lockedThresholds']['Pimple'] == .9
    assert not result['modelAccepted'] and not result['lockedTestIndependent']


def test_no_predictions_is_zero_ap_not_success_or_crash(tmp_path):
    archive, folder, _, _ = fixture(tmp_path, predictions=[])
    result = E.evaluate(archive, folder, 'valid')
    assert result['coco'][0]['map50'] == 0
    assert result['operatingPoints']['Pimple']['fn'] == 1


@pytest.mark.parametrize('bad', ['dimensions', 'model', 'floor', 'split', 'missing', 'class', 'nan'])
def test_invalid_or_incomplete_prediction_snapshot_is_rejected(tmp_path, bad):
    archive, folder, row, path = fixture(tmp_path)
    if bad == 'dimensions': row['image']['width'] = 16
    elif bad == 'model': row['resolvedModel']['model_id'] = 'fallback-model'
    elif bad == 'floor': row['confidenceFloor'] = .5
    elif bad == 'split': row['split'] = 'test'
    elif bad == 'class': row['predictions'][0]['class'] = 'Mole'
    elif bad == 'nan': row['predictions'][0]['x'] = float('nan')
    path.write_text(json.dumps(row))
    if bad == 'missing': path.unlink()
    with pytest.raises(ValueError): E.read_snapshot(archive, folder, 'valid')


def test_test_identity_must_match_frozen_validation_lock(tmp_path):
    archive, folder, _, _ = fixture(tmp_path, split='test')
    lock = dict(thresholdSelectionSplit='valid', modelIdentity=dict(modelId='wrong', modelPackageId='package'),
                lockedThresholds={k: .3 for k in E.CLASSES})
    with pytest.raises(ValueError, match='MATCHING_VALIDATION_LOCK'):
        E.evaluate(archive, folder, 'test', lock)


def test_lossless_gzip_snapshot_replay_preserves_receipts_and_metrics(tmp_path):
    archive, folder, _, path = fixture(tmp_path)
    raw = path.read_text()
    bundle = tmp_path / 'snapshot.json.gz'
    bundle.write_bytes(gzip.compress(json.dumps(dict(records=[dict(name=path.name, split='valid', rawJSON=raw)])).encode(), mtime=0))
    original = E.evaluate(archive, folder, 'valid')
    replay = E.evaluate(archive, bundle, 'valid')
    assert replay == original
