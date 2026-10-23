import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
from diagnose_detector_snapshot import analyze,CLASSES
LOCK={k:.3 for k in CLASSES}
def row(label,box,confidence=None):
    r={'class':label,'bbox':box}
    if confidence is not None:r['confidence']=confidence
    return r


def test_class_agnostic_confusion_does_not_hide_wrong_class():
    t={1:[row('Pimple',[0,0,10,10])]};p={1:[row('Post acne',[0,0,10,10],.9)]}
    r=analyze(t,p,LOCK)
    assert r['classAgnosticMatrix']['Pimple']['Post acne']==1
    assert r['sameClassBestOverlapOpportunities']['Pimple']['atFloorBestIoUAtLeast0.5']==0


def test_duplicate_prediction_cannot_claim_two_ground_truth_instances():
    t={1:[row('Pimple',[0,0,10,10])]};p={1:[row('Pimple',[0,0,10,10],s) for s in [.8,.9]]}
    r=analyze(t,p,LOCK)['classAgnosticMatrix']
    assert r['Pimple']['Pimple']==1 and r['background']['Pimple']==1


def test_loose_localization_is_an_opportunity_not_correct_detection():
    t={1:[row('Pimple',[0,0,10,10])]};p={1:[row('Pimple',[4,0,10,10],.9)]}
    r=analyze(t,p,LOCK)
    assert r['classAgnosticMatrix']['Pimple']['background']==1
    assert r['sameClassBestOverlapOpportunities']['Pimple']['atFloorBestIoUAtLeast0.3']==1
    assert r['sameClassBestOverlapOpportunities']['Pimple']['atFloorBestIoUAtLeast0.5']==0


def test_floor_only_prediction_does_not_enter_locked_threshold_matrix():
    t={1:[row('Pimple',[0,0,8,8])]};p={1:[row('Pimple',[0,0,8,8],.1)]}
    r=analyze(t,p,LOCK)
    assert r['classAgnosticMatrix']['Pimple']['background']==1
    assert r['sameClassBestOverlapOpportunities']['Pimple']['atFloorBestIoUAtLeast0.5']==1
    assert r['sourcePixelSizeCounts']['Pimple']['minEdgeAtMost8px']==1


def test_cross_class_truth_overlap_is_separate_from_prediction_errors():
    t={1:[row('Pimple',[0,0,8,8]),row('Post acne',[0,0,8,8])]}
    r=analyze(t,{1:[]},LOCK)
    assert r['crossClassTruthOverlaps']=={'Pimple / Post acne':1}
    assert not r['crossClassMatches']


def test_invalid_threshold_cannot_change_diagnostic_policy():
    with pytest.raises(ValueError):analyze({}, {}, {k:float('nan') for k in CLASSES})
