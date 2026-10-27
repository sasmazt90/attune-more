"""Fail-closed acceptance gate for learned skin-model candidates.

This is an offline promotion check.  It does not train, infer, activate a
model, or turn predictions into truth.  Existing analytic appearance methods
are outside this gate; learned candidates must present every required proof.
"""
import argparse
import json
import re
from pathlib import Path

VERSION = 'skin-model-acceptance-gate-v1'
IMMUTABLE_ID = re.compile(r'^(?:[0-9a-f]{32}|[0-9a-f]{64})$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')

PROVENANCE_FLAGS = (
    'rightsReviewed',
    'expertLabelProtocolVerified',
    'personIndependentSplits',
    'negativeCoverageReviewed',
    'lockedTestUntouchedDuringSelection',
)
CAMERA_FLAGS = (
    'independentFromTrainingSources',
    'sameCaptureContractAsProduct',
    'skinToneLightingPoseSlicesReviewed',
    'passed',
)
INTEGRATION_FLAGS = (
    'api',
    'productContract',
    'unavailableFallback',
    'privacyAndConsent',
    'historyCompatibility',
    'regressionTests',
)


def _true(section, key):
    return isinstance(section, dict) and section.get(key) is True


def _text(section, key):
    value = section.get(key) if isinstance(section, dict) else None
    return isinstance(value, str) and bool(value.strip())


def _metric_block(value):
    if not isinstance(value, dict):
        return False
    required = ('precision', 'recall', 'f1')
    return all(
        isinstance(value.get(key), (int, float))
        and not isinstance(value.get(key), bool)
        and 0 <= value[key] <= 1
        for key in required
    )


def evaluate(receipt):
    """Return a deterministic verdict without mutating the candidate receipt."""
    reasons = []
    identity = receipt.get('modelIdentity') if isinstance(receipt, dict) else None
    if not _text(receipt, 'target'):
        reasons.append('TARGET_MISSING')
    if not isinstance(identity, dict) or not _text(identity, 'modelId'):
        reasons.append('MODEL_ID_MISSING')
    immutable = identity.get('immutableId') if isinstance(identity, dict) else None
    if not isinstance(immutable, str) or not IMMUTABLE_ID.fullmatch(immutable):
        reasons.append('IMMUTABLE_MODEL_ID_INVALID')

    provenance = receipt.get('provenance') if isinstance(receipt, dict) else None
    source_hash = provenance.get('sourceArchiveSHA256') if isinstance(provenance, dict) else None
    if not isinstance(source_hash, str) or not SHA256.fullmatch(source_hash):
        reasons.append('SOURCE_ARCHIVE_ID_INVALID')
    for flag in PROVENANCE_FLAGS:
        if not _true(provenance, flag):
            reasons.append('PROVENANCE_' + flag.upper() + '_REQUIRED')

    evaluation = receipt.get('evaluation') if isinstance(receipt, dict) else None
    if not isinstance(evaluation, dict):
        reasons.append('EVALUATION_MISSING')
    else:
        if evaluation.get('thresholdSelectionSplit') != 'validation':
            reasons.append('THRESHOLD_NOT_SELECTED_ON_VALIDATION')
        if not _true(evaluation, 'thresholdsLockedBeforeTest'):
            reasons.append('THRESHOLDS_NOT_LOCKED_BEFORE_TEST')
        if not _text(evaluation, 'qualityGateEvidence'):
            reasons.append('QUALITY_GATE_EVIDENCE_MISSING')
        classes = evaluation.get('classes')
        if not isinstance(classes, dict) or not classes:
            reasons.append('PER_CLASS_EVALUATION_MISSING')
        else:
            for name in sorted(classes):
                row = classes[name]
                if not isinstance(row, dict):
                    reasons.append(f'CLASS_{name}_EVALUATION_INVALID')
                    continue
                threshold = row.get('threshold')
                if (not isinstance(threshold, (int, float)) or isinstance(threshold, bool)
                        or not 0 <= threshold <= 1):
                    reasons.append(f'CLASS_{name}_THRESHOLD_INVALID')
                if not _metric_block(row.get('validation')):
                    reasons.append(f'CLASS_{name}_VALIDATION_METRICS_INVALID')
                if not _metric_block(row.get('test')):
                    reasons.append(f'CLASS_{name}_TEST_METRICS_INVALID')
                if row.get('passed') is not True:
                    reasons.append(f'CLASS_{name}_QUALITY_GATE_FAILED')

    camera = receipt.get('camera') if isinstance(receipt, dict) else None
    for flag in CAMERA_FLAGS:
        if not _true(camera, flag):
            reasons.append('CAMERA_' + flag.upper() + '_REQUIRED')
    if not _text(camera, 'evidence'):
        reasons.append('CAMERA_EVIDENCE_MISSING')

    integration = receipt.get('integration') if isinstance(receipt, dict) else None
    for flag in INTEGRATION_FLAGS:
        if not _true(integration, flag):
            reasons.append('INTEGRATION_' + flag.upper() + '_REQUIRED')
    if not _text(integration, 'evidence'):
        reasons.append('INTEGRATION_EVIDENCE_MISSING')

    return {
        'gateVersion': VERSION,
        'target': receipt.get('target') if isinstance(receipt, dict) else None,
        'modelIdentity': identity if isinstance(identity, dict) else None,
        'accepted': not reasons,
        'reasons': reasons,
        'activationAllowed': not reasons,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.receipt.read_text('utf8'))),
                     indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
