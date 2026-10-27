#!/usr/bin/env python3
"""Measure the review set with the pinned upstream encoder, without synthesis.

Cosines are descriptive diagnostics, not calibrated speaker verification or a
substitute for native-language listening. Run in the isolated official runtime.
"""
import argparse
import itertools
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/core-api'))
from mental_neural_tts import load_configuration, verify_runtime_source, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    _, directory, reference, profile = load_configuration(args.config, 'en')
    if profile['id'] != 'female-calm-v1' or reference is None:
        raise ValueError('FEMALE_REVIEW_PROFILE_REQUIRED')
    verify_runtime_source()
    def offline(*a, **kw): raise OSError('REVIEW_NETWORK_DISABLED')
    socket.socket.connect = socket.socket.connect_ex = socket.socket.sendto = offline
    import librosa
    import numpy as np
    import torch
    from chatterbox.models.voice_encoder import VoiceEncoder
    torch.set_num_threads(2)
    encoder = VoiceEncoder()
    encoder.load_state_dict(torch.load(directory / 've.pt', map_location='cpu', weights_only=True))
    encoder.eval()
    public = ROOT / 'apps/vehicle-app/public'
    female = json.loads((public / 'audio/mental/v1/female-calm-v1-manifest.json').read_text())
    original = json.loads((public / 'audio/mental/v1/manifest.json').read_text())
    original_entries = {e['assetId']: e for e in original['entries']}
    baseline = json.loads((ROOT / 'docs/mental-structured/female-comparison-baseline.json').read_text())
    for name, expected in baseline['sha256'].items():
        if digest(ROOT / name) != expected: raise ValueError('ORIGINAL_COMPARISON_CHANGED')
    def embed(path):
        waveform, _ = librosa.load(path, sr=16000)
        value = encoder.embeds_from_wavs([waveform], sample_rate=16000)[0]
        return value / np.linalg.norm(value)
    ref = embed(reference)
    rows, vectors = [], {}
    for entry in (e for e in female['entries'] if (e['questionNodeId'],e['variantId']) in {('A','A-V01'),('B01','B01-V01'),('B02','B02-V01')}):
        path = public / entry['audioPath'].lstrip('/')
        if digest(path) != entry['sha256']: raise ValueError('GENERATED_SAMPLE_HASH_MISMATCH')
        vector = embed(path); vectors[(entry['language'], entry['variantId'])] = vector
        old = original_entries[entry['sourceAssetId']]
        old_vector = embed(public / old['audioPath'].lstrip('/'))
        rows.append({'language': entry['language'], 'variantId': entry['variantId'],
            'referenceCosine': round(float(vector @ ref), 6),
            'officialDefaultReferenceCosine': round(float(old_vector @ ref), 6),
            'durationMs': entry['durationMs'], 'officialDefaultDurationMs': old['durationMs'],
            'durationRatioToDefault': round(entry['durationMs'] / old['durationMs'], 4),
            'identityEvidence': 'very-short-acknowledgment-inconclusive' if entry['questionNodeId'] == 'A' else 'short-question-descriptive-only'})
    pairs = []
    for left, right in itertools.combinations(('tr', 'en', 'de'), 2):
        for a, b in itertools.product(('B01-V01', 'B02-V01'), repeat=2):
            pairs.append({'left': f'{left}/{a}', 'right': f'{right}/{b}',
                          'cosine': round(float(vectors[(left, a)] @ vectors[(right, b)]), 6)})
    output = {'profile': profile['id'], 'referenceSha256': digest(reference),
        'encoderSha256': digest(directory / 've.pt'), 'generation': profile['generation'],
        'generatedSpeechClips': 9, 'additionalSynthesis': 0,
        'originalComparisonFilesUnchanged': len(baseline['sha256']),
        'speakerConsistency': ('Owner accepted the representative recordings; independent biometric identity verification is not claimed.'
            if female.get('sampleApproval',{}).get('ownerApprovedAt') else 'Not verified. Owner listening approval pending.'),
        'limitations': ['Same conditioning hash verifies configuration, not perceptual identity.',
            'The upstream encoder is part of the generator, not an independent identity assessor.',
            'Cosines have no calibrated cross-language acceptance threshold for these short samples.',
            'Duration includes pauses; it does not alone establish a calm or slower delivery.',
            'Each asset has a deterministic seed; these are not seed-matched controlled A/B recordings.',
            'This measurement command synthesizes no new speech; real dynamic-closing proofs are documented separately.'],
        'samples': rows, 'crossLanguageQuestionPairs': pairs}
    target = ROOT / 'docs/mental-structured/listening-female-calm-v1/measurements.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'measurementFile': str(target), 'samples': len(rows), 'crossLanguagePairs': len(pairs), 'speakerConsistency': output['speakerConsistency']}))


if __name__ == '__main__': main()
