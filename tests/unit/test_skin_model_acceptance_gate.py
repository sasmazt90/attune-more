import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'scripts/skin-research/skin_model_acceptance_gate.py'
SPEC = importlib.util.spec_from_file_location('skin_model_acceptance_gate', PATH)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def complete_receipt():
    metrics = {'precision': .91, 'recall': .88, 'f1': .895}
    return {
        'target': 'fixture-only',
        'modelIdentity': {'modelId': 'fixture/model/1', 'immutableId': 'a' * 64},
        'provenance': {
            'sourceArchiveSHA256': 'b' * 64,
            'rightsReviewed': True,
            'expertLabelProtocolVerified': True,
            'personIndependentSplits': True,
            'negativeCoverageReviewed': True,
            'lockedTestUntouchedDuringSelection': True,
        },
        'evaluation': {
            'thresholdSelectionSplit': 'validation',
            'thresholdsLockedBeforeTest': True,
            'qualityGateEvidence': 'docs/fixture-evaluation.json',
            'classes': {
                'fixture': {
                    'threshold': .4,
                    'validation': metrics,
                    'test': metrics,
                    'passed': True,
                }
            },
        },
        'camera': {
            'independentFromTrainingSources': True,
            'sameCaptureContractAsProduct': True,
            'skinToneLightingPoseSlicesReviewed': True,
            'passed': True,
            'evidence': 'docs/fixture-camera.json',
        },
        'integration': {
            'api': True,
            'productContract': True,
            'unavailableFallback': True,
            'privacyAndConsent': True,
            'historyCompatibility': True,
            'regressionTests': True,
            'evidence': 'docs/fixture-integration.json',
        },
    }


def test_complete_receipt_passes_without_mutation():
    receipt = complete_receipt()
    before = copy.deepcopy(receipt)
    verdict = GATE.evaluate(receipt)
    assert verdict['accepted'] and verdict['activationAllowed']
    assert verdict['reasons'] == []
    assert receipt == before


def test_finished_training_and_metrics_alone_do_not_pass():
    receipt = complete_receipt()
    receipt['provenance'].update(
        expertLabelProtocolVerified=False,
        personIndependentSplits=False,
        negativeCoverageReviewed=False,
    )
    receipt['camera'] = {'passed': False}
    receipt['integration'] = {}
    verdict = GATE.evaluate(receipt)
    assert not verdict['accepted'] and not verdict['activationAllowed']
    assert 'PROVENANCE_EXPERTLABELPROTOCOLVERIFIED_REQUIRED' in verdict['reasons']
    assert 'PROVENANCE_PERSONINDEPENDENTSPLITS_REQUIRED' in verdict['reasons']
    assert 'CAMERA_PASSED_REQUIRED' in verdict['reasons']
    assert 'INTEGRATION_API_REQUIRED' in verdict['reasons']


def test_each_class_requires_validation_locked_test_and_explicit_pass():
    receipt = complete_receipt()
    receipt['evaluation']['thresholdSelectionSplit'] = 'test'
    receipt['evaluation']['thresholdsLockedBeforeTest'] = False
    receipt['evaluation']['classes']['fixture']['test'] = None
    receipt['evaluation']['classes']['fixture']['passed'] = False
    verdict = GATE.evaluate(receipt)
    assert 'THRESHOLD_NOT_SELECTED_ON_VALIDATION' in verdict['reasons']
    assert 'THRESHOLDS_NOT_LOCKED_BEFORE_TEST' in verdict['reasons']
    assert 'CLASS_fixture_TEST_METRICS_INVALID' in verdict['reasons']
    assert 'CLASS_fixture_QUALITY_GATE_FAILED' in verdict['reasons']


def test_truthy_strings_and_unpinned_identities_fail_closed():
    receipt = complete_receipt()
    receipt['modelIdentity']['immutableId'] = 'package-name'
    receipt['provenance']['sourceArchiveSHA256'] = 'archive-name'
    receipt['provenance']['rightsReviewed'] = 'yes'
    receipt['camera']['passed'] = 1
    verdict = GATE.evaluate(receipt)
    assert 'IMMUTABLE_MODEL_ID_INVALID' in verdict['reasons']
    assert 'SOURCE_ARCHIVE_ID_INVALID' in verdict['reasons']
    assert 'PROVENANCE_RIGHTSREVIEWED_REQUIRED' in verdict['reasons']
    assert 'CAMERA_PASSED_REQUIRED' in verdict['reasons']
