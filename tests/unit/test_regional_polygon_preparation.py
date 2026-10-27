import copy
import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts/skin-research'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('regional_prep', SCRIPTS / 'prepare_regional_polygons.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


def source():
    return dict(images=[dict(id=1, file_name='face.jpg', width=20, height=20)],
                categories=[dict(id=1, name='Oily'), dict(id=2, name='Acne')],
                annotations=[dict(id=1, image_id=1, category_id=1,
                                  bbox=[1, 1, 8, 8], segmentation=[[1, 1, 9, 2, 7, 9]])])


def test_original_geometry_and_image_are_preserved_without_normal_truth():
    data = source(); original = copy.deepcopy(data)
    selected, excluded = P.select(data, 'train', 'v11', set())
    assert selected['annotations'] == data['annotations'] and selected['images'] == data['images']
    assert [c['name'] for c in selected['categories']] == ['Oily'] and not excluded
    assert data == original


def test_unsupported_target_annotation_quarantines_whole_image():
    data = source(); data['annotations'].append(dict(id=2, image_id=1, category_id=1, bbox=[2, 2, 3, 3], segmentation=[]))
    selected, excluded = P.select(data, 'train', 'v11', set())
    assert not selected['images'] and not selected['annotations']
    assert excluded[0]['reasons'] == ['UNSUPPORTED_TARGET_GEOMETRY']


def test_candidate_quarantine_does_not_assert_person_identity_or_change_source():
    data = source(); original = copy.deepcopy(data)
    selected, excluded = P.select(data, 'test', 'v11', {'v11:test/face.jpg'})
    assert not selected['images'] and 'CROSS_SPLIT_CANDIDATE_QUARANTINE' in excluded[0]['reasons']
    assert data == original


def test_absent_target_annotations_do_not_create_normal_examples():
    data = source(); data['annotations'][0]['category_id'] = 2
    selected, excluded = P.select(data, 'valid', 'v11', set())
    assert not selected['images'] and excluded[0]['reasons'] == ['NO_TARGET_POSITIVES_NOT_NORMAL_TRUTH']
