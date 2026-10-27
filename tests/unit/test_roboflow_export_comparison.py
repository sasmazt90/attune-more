import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

from PIL import Image
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts/skin-research'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('export_comparison', SCRIPTS / 'verify_roboflow_export.py')
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def archive(tmp, name, *, remote=False, split='test', shift=0, colour='white', duplicate=False, polygon=False, mask_shift=0):
    path = tmp / name
    filename = 'sample_png_jpg.rf.new.jpg' if remote else 'sample_png.rf.original.jpg'
    image = dict(id=7 if remote else 1, width=16, height=16, file_name=filename)
    ann = dict(id=9 if remote else 1, image_id=image['id'], category_id=2 if remote else 1,
               bbox=[1 + shift, 2, 3, 4], segmentation=[[1+mask_shift,2,4,2,4,6,1,6]] if polygon else [], iscrowd=0)
    data = dict(images=[image], annotations=[ann],
                categories=[dict(id=ann['category_id'], name='Pimple')])
    if duplicate:
        other = copy.deepcopy(image)
        other['id'] += 1
        other['file_name'] = 'sample_png.rf.another.jpg'
        second = copy.deepcopy(ann)
        second['image_id'] = other['id']
        data['images'].append(other)
        data['annotations'].append(second)
    out = io.BytesIO()
    Image.new('RGB', (16, 16), colour).save(out, format='PNG')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(split + '/_annotations.coco.json', json.dumps(data))
        for row in data['images']:
            z.writestr(split + '/' + row['file_name'], out.getvalue())
    return path


def test_reassigned_ids_order_and_export_suffix_do_not_hide_exact_match(tmp_path):
    result = E.compare(archive(tmp_path, 'a.zip'), archive(tmp_path, 'b.zip', remote=True))
    assert result['pairedImages'] == 1 and result['metadataAndGeometryMatched']
    assert result['splitsUnchanged'] and result['allDimensionsVerified']
    assert result['exactPhotoIdentityVerified'] and result['decodedIdenticalImages'] == 1


def test_geometry_changes_are_not_silently_rounded_or_accepted(tmp_path):
    result = E.compare(archive(tmp_path, 'a.zip'), archive(tmp_path, 'b.zip', remote=True, shift=.00001))
    assert not result['metadataAndGeometryMatched']
    assert len(result['missing']) == len(result['extra']) == 1


def test_split_drift_is_separate_from_matching_geometry(tmp_path):
    result = E.compare(archive(tmp_path, 'a.zip'), archive(tmp_path, 'b.zip', remote=True, split='train'))
    assert result['metadataAndGeometryMatched'] and not result['splitsUnchanged']


def test_matching_annotation_cannot_establish_matching_photo_pixels(tmp_path):
    result = E.compare(archive(tmp_path, 'a.zip'), archive(tmp_path, 'b.zip', remote=True, colour='black'))
    assert result['metadataAndGeometryMatched'] and not result['exactPhotoIdentityVerified']
    assert result['rows'][0]['meanAbsoluteChannelError'] == 255


def test_ambiguous_original_names_and_geometry_are_never_arbitrarily_paired(tmp_path):
    result = E.compare(archive(tmp_path, 'a.zip', duplicate=True), archive(tmp_path, 'b.zip', remote=True))
    assert len(result['ambiguous']) == 1 and result['pairedImages'] == 0
    assert not result['metadataAndGeometryMatched'] and not result['exactPhotoIdentityVerified']


def test_empty_archive_is_rejected(tmp_path):
    empty = tmp_path / 'empty.zip'
    with zipfile.ZipFile(empty, 'w'):
        pass
    with pytest.raises(ValueError, match='NO_COCO_IMAGES'):
        E.compare(empty, archive(tmp_path, 'a.zip'))


def test_exact_polygon_policy_reports_recomputed_boxes_separately(tmp_path):
    a=archive(tmp_path,'a.zip',polygon=True)
    b=archive(tmp_path,'b.zip',remote=True,polygon=True,shift=.13)
    assert not E.compare(a,b)['metadataAndGeometryMatched']
    result=E.compare(a,b,'segmentation')
    assert result['metadataAndGeometryMatched'] and result['splitsUnchanged']
    assert not result['fullGeometryUnchanged'] and result['changedBoxGeometryImages']==1


def test_polygon_drift_is_never_rounded_away(tmp_path):
    a=archive(tmp_path,'a.zip',polygon=True)
    b=archive(tmp_path,'b.zip',remote=True,polygon=True,mask_shift=.00001)
    assert not E.compare(a,b,'segmentation')['metadataAndGeometryMatched']


def test_boxes_cannot_pass_polygon_verification(tmp_path):
    with pytest.raises(ValueError,match='POLYGON_TRUTH'):
        E.compare(archive(tmp_path,'a.zip'),archive(tmp_path,'b.zip',remote=True),'segmentation')
