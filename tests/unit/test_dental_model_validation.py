import importlib.util
from pathlib import Path
import pytest


def module():
    path=Path(__file__).resolve().parents[2]/'scripts/dental_model_validation.py'
    spec=importlib.util.spec_from_file_location('dental_validation',path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded


def test_duplicate_detections_are_false_positives_and_missing_class_is_not_calibrated():
    diagnostic=module().retained_detection_calibration(
        [{'boxes':[[0,0,0,10,10]]}],
        [[[0,0,10,10,1,.9,0],[0,0,10,10,1,.8,0],[50,50,60,60,1,.1,1]]], .2, ['D','d'])
    first, second=diagnostic['classes']
    assert first['retainedPredictions']==2
    assert first['Brier']==pytest.approx((.1**2+.8**2)/2)
    assert first['ECE']==pytest.approx(.45)
    assert second['retainedPredictions']==0 and second['Brier'] is None and second['ECE'] is None


def test_correct_class_without_localization_is_not_a_positive():
    result=module().retained_detection_calibration(
        [{'boxes':[[0,0,0,10,10]]}], [[[50,50,60,60,1,.9,0]]], .2, ['D'])['classes'][0]
    assert result['Brier']==pytest.approx(.81)
    assert result['bins'][0]['localizedPrecision']==0


def test_group_intervals_keep_duplicate_predictions_and_class_absence_explicit():
    rows=[{'group':'A','boxes':[[0,0,0,10,10]]},{'group':'B','boxes':[[1,0,0,10,10]]}]
    predictions=[[[0,0,10,10,1,.9,0],[0,0,10,10,1,.8,0]],[[0,0,10,10,1,.9,1],[0,0,10,10,1,.8,1]]]
    result=module().group_f1_intervals(rows,predictions,.2,['D','d'])
    assert result['groups']==2 and result['draws']==200
    assert result['macroF1_95CI']==pytest.approx([1/3,2/3])
    assert result['classF1_95CI'][0]==pytest.approx([0,2/3])
    assert result['classF1_95CI'][1]==pytest.approx([0,2/3])
    assert result==module().group_f1_intervals(rows,predictions,.2,['D','d'])


def test_validation_stopping_rule_requires_minimum_epochs_and_plateau():
    path=Path(__file__).resolve().parents[2]/'scripts/watch_dental_training.py'
    spec=importlib.util.spec_from_file_location('dental_stopping',path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    constant=lambda count:[{'validation':{'macroF1':.4}} for _ in range(count)]
    assert not loaded.decision(constant(7))
    assert loaded.decision(constant(8))
    assert not loaded.decision([{'validation':{'macroF1':value}} for value in [.1,.2,.3,.4,.5,.6,.7,.8]])
    assert not loaded.decision([{'validation':{'macroF1':value}} for value in [.1,.2,.3,.4,.4,.4,.4,.41]])
