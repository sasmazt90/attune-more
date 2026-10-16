import numpy as np
import relabel_compare as R


def lab(points):
    return dict(points=[dict(id=f'P{i}', x=x, y=y, cat=c) for i, (x, y, c) in enumerate(points)])


def box(x, y, s=4): return [x - s, y - s, x + s, y + s]


def run(points, preds, mask=None, oval=None, r=10.):
    if mask is None: mask = np.zeros((200, 200), bool); mask[50:150, 50:150] = True
    if oval is None: oval = np.zeros((200, 200), bool); oval[20:180, 20:180] = True
    return R.score_photo(lab(points), [box(*p) for p in preds], mask, oval, r)


def test_one_prediction_one_target():
    x = run([(100, 100, 'TARGET'), (104, 100, 'TARGET')], [(102, 100)])
    assert x['hits'] == 1


def test_second_prediction_on_same_target_is_duplicate():
    x = run([(100, 100, 'TARGET')], [(100, 100), (103, 100)])
    assert x['hits'] == 1 and x['classes'].count('duplicate') == 1


def test_tolerance_is_inclusive_and_not_exceeded():
    assert run([(100, 100, 'TARGET')], [(110, 100)])['hits'] == 1
    assert run([(100, 100, 'TARGET')], [(110.5, 100)])['hits'] == 0


def test_max_cardinality_over_nearest():
    # prediction A is nearest to target 1 but is the only one in reach of target 2
    x = run([(100, 100, 'TARGET'), (112, 100, 'TARGET')], [(104, 100), (93, 100)])
    assert x['hits'] == 2


def test_class_order_other_uncertain_false_unreviewed_outside():
    pts = [(60, 60, 'MOLE'), (80, 80, 'UNCERTAIN')]
    x = run(pts, [(60, 62), (80, 82), (120, 120), (30, 30), (190, 190)])
    assert x['classes'] == ['onOther:MOLE', 'onUncertain', 'falseReviewed', 'unreviewedInOval', 'outsideOval']


def test_empty_mask_photo_never_gives_false_or_outside():
    x = run([(100, 100, 'TARGET')], [(100, 100), (150, 20), (5, 5)], mask=np.zeros((200, 200), bool))
    assert x['hits'] == 1 and x['classes'][1:] == ['unreviewedPhoto', 'unreviewedPhoto']


def test_uncertain_and_unreviewed_never_counted_false():
    x = run([(120, 120, 'UNCERTAIN')], [(121, 121), (30, 100)])
    assert 'falseReviewed' not in x['classes']
