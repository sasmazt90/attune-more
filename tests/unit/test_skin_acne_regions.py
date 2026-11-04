"""Acne counting rules on synthetic geometry. Real-photo results are in docs/qa/QA-25-ACNE-TRACE.md."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
cv2 = pytest.importorskip('cv2')
import skin_findings_v1 as SF  # noqa: E402


def square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Five regions in a 1024 crop, and a mesh that puts the face oval around them and the eyes and lips in known places.
POLYS = {'forehead': square(300, 200, 700, 330), 'nose': square(450, 420, 570, 640),
         'cheek_imgL': square(240, 520, 400, 750), 'cheek_imgR': square(620, 520, 780, 750), 'chin': square(380, 800, 640, 920)}


def mesh():
    points = np.full((478, 2), 512.0)
    ring = np.linspace(0, 2 * np.pi, len(SF.FACE_OVAL), endpoint=False)
    points[SF.FACE_OVAL, 0] = 512 + 310 * np.cos(ring)
    points[SF.FACE_OVAL, 1] = 540 + 400 * np.sin(ring)

    def place(indices, x0, y0, x1, y1):
        turn = np.linspace(0, 2 * np.pi, len(indices), endpoint=False)
        points[indices, 0] = (x0 + x1) / 2 + (x1 - x0) / 2 * np.cos(turn)
        points[indices, 1] = (y0 + y1) / 2 + (y1 - y0) / 2 * np.sin(turn)
    place(SF.NOT_SKIN[0], 340, 380, 430, 430)
    place(SF.NOT_SKIN[1], 590, 380, 680, 430)
    place(SF.NOT_SKIN[2], 320, 340, 440, 370)
    place(SF.NOT_SKIN[3], 580, 340, 700, 370)
    place(SF.NOT_SKIN[4], 430, 700, 590, 780)
    return points


@pytest.mark.parametrize('x, y, region', [
    (500, 260, 'forehead'),      # inside a region stays there
    (500, 180, 'forehead'),      # hairline, above the region
    (510, 345, 'forehead'),      # between the brows
    (320, 790, 'rightCheek'),    # jaw, below the cheek
    (420, 790, 'chin'),          # beside the lips, nearest the chin
])
def test_a_lesion_on_the_face_goes_to_a_region(x, y, region):
    assert SF.lesion_region(POLYS, x, y, mesh()) == region


@pytest.mark.parametrize('x, y', [
    (385, 405),                  # on an eye
    (380, 355),                  # on a brow
    (510, 740),                  # on the lips
    (980, 100),                  # background, far outside the face
])
def test_nothing_outside_facial_skin_is_counted(x, y):
    assert SF.lesion_region(POLYS, x, y, mesh()) is None


def test_without_a_mesh_only_the_research_regions_count():
    assert SF.lesion_region(POLYS, 500, 260) == 'forehead'
    assert SF.lesion_region(POLYS, 500, 180) is None


def box(region, pose, n):
    return [dict(finding='acne', region=region, pose=pose, type='papule', x=i, y=i, r=5, score=.5) for i in range(n)]


def maps(front=(), left=(), right=()):
    return {'FRONT': {'findingBoxes': list(front)}, 'LEFT': {'findingBoxes': list(left)}, 'RIGHT': {'findingBoxes': list(right)}}


POSES = ['FRONT', 'LEFT', 'RIGHT']


def rows(**status):
    return [dict(id='acne', region=region, status=value, pose='FRONT') for region, value in status.items()]


def test_a_positive_person_shows_a_region_with_several_marked_lesions():
    found = rows(forehead='seen', chin='notSeen')
    SF._show_regions_with_marked_lesions(found, maps(front=box('chin', 'FRONT', 4)), POSES)
    assert found[1]['status'] == 'seen' and found[1]['decidedBy'] == 'markedLesions' and found[1]['pose'] == 'FRONT'
    assert 'decidedBy' not in found[0]


def test_one_box_alone_does_not_show_a_region():
    found = rows(forehead='seen', nose='notSeen')
    SF._show_regions_with_marked_lesions(found, maps(front=box('nose', 'FRONT', 1), left=box('nose', 'LEFT', 1)), POSES)
    assert found[1]['status'] == 'notSeen'


def test_boxes_never_make_a_person_positive():
    found = rows(forehead='notSeen', chin='notSeen')
    SF._show_regions_with_marked_lesions(found, maps(front=box('chin', 'FRONT', 6) + box('forehead', 'FRONT', 6)), POSES)
    assert [f['status'] for f in found] == ['notSeen', 'notSeen']


def test_an_unreadable_region_stays_unreadable():
    found = rows(forehead='seen', chin='inconclusive')
    SF._show_regions_with_marked_lesions(found, maps(front=box('chin', 'FRONT', 5)), POSES)
    assert found[1]['status'] == 'inconclusive'


def test_lesions_are_counted_from_one_photo_only():
    row = dict(id='acne', region='forehead', status='seen', pose='LEFT')
    SF._attach_count(row, maps(front=box('forehead', 'FRONT', 2), left=box('forehead', 'LEFT', 3), right=box('forehead', 'RIGHT', 1)), POSES, fallback_pose='LEFT')
    assert row['count'] == 3 and row['countPose'] == 'LEFT'
    assert {m['pose'] for m in row['markers']} == {'LEFT'}


def test_a_tie_keeps_the_photo_facing_the_region():
    row = dict(id='acne', region='forehead', status='seen', pose='LEFT')
    SF._attach_count(row, maps(front=box('forehead', 'FRONT', 2), left=box('forehead', 'LEFT', 2)), POSES, fallback_pose='LEFT')
    assert row['countPose'] == 'FRONT'


def test_other_findings_keep_their_counting_rule():
    marks = [dict(finding='coldSore', region='chin', pose=p, x=1, y=1, r=1, score=.5) for p in ('LEFT', 'LEFT', 'FRONT')]
    row = dict(id='coldSore', region='chin', status='seen')
    SF._attach_count(row, maps(front=marks[2:], left=marks[:2]), POSES)
    assert row['count'] == 1 and row['countPose'] == 'FRONT'
