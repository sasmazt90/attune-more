"""Belirginlik (visibility severity, 0-100) for findings that the DINOv2-crop classifiers marked as seen.

Saved models: <model_dir>/findings-v2/severity/<findingId>.json, exported by the severity export script
(research recipe: research/skin-findings/scripts/sev_final.py + sev_bands.py; see CODEX_HANDOFF.md §5-6).

Per finding: mean of the DINOv2-small crop embeddings (CLS ++ mean patch, 768) over the listed (view, crop) rows ->
StandardScaler + Ridge -> raw prediction -> midrank percentile among the stored out-of-fold predictions of the rated
positives (0 = mildest, 100 = most visible). This is a relative visibility rank among synthetic positive faces rated
blind by Claude (1-3); it is not a clinical severity and is only meaningful when the finding was detected.

Inputs: emb_by_pose_crop maps (view, crop) -> np.ndarray[768] where view is the skin_findings_dino view name
('front', 'pos' = LEFT pose, 'neg' = RIGHT pose) or the API pose ('FRONT', 'LEFT', 'RIGHT'); crops are
skin_findings_dino.CROPS names cut by skin_findings_dino.crops_of(). numpy only."""
from __future__ import annotations
import glob, hashlib, json, os, threading
import numpy as np

VIEW_OF_POSE = {'FRONT': 'front', 'LEFT': 'pos', 'RIGHT': 'neg', 'front': 'front', 'pos': 'pos', 'neg': 'neg'}
_lock = threading.Lock(); _cache: dict = {}


def specs(model_dir: str) -> dict:
    with _lock:
        if model_dir not in _cache:
            d = {}
            for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', 'severity', '*.json'))):
                if os.path.basename(p).startswith('REPORT'):
                    continue
                s = json.load(open(p))
                if str(s.get('version', '')).startswith('skin-findings-v2-severity'):
                    s['_ref'] = np.asarray(s['reference']['sortedOOF'], np.float64)
                    d[s['id']] = s
            _cache[model_dir] = d
        return _cache[model_dir]


def _embedding(spec: dict, emb_by_pose_crop: dict, allow_partial: bool):
    rows = {}
    for (pose, crop), v in (emb_by_pose_crop or {}).items():
        view = VIEW_OF_POSE.get(pose)
        if view is not None and v is not None:
            rows[(view, crop)] = np.asarray(v, np.float64).reshape(-1)
    want = [tuple(r) for r in spec['inputs']['embedding']['expectedRows']]
    have = [r for r in want if r in rows]
    if not have:
        return None
    if len(have) < len(want):
        # research persons always had every row; partial input is allowed only on request and needs the front crops
        front = [r for r in want if r[0] == 'front']
        if not allow_partial or not all(r in rows for r in front):
            return None
    x = np.mean([rows[r] for r in have], 0)
    return x if x.shape[0] == spec['inputs']['embedding']['dim'] and np.all(np.isfinite(x)) else None


def raw_prediction(spec: dict, x_emb: np.ndarray, x_extra=None):
    m = spec['model']; b0 = m['blocks'][0]
    z = [(x_emb - np.asarray(b0['mean'])) / np.asarray(b0['scale'])]
    if len(m['blocks']) > 1:                                            # extra (non-embedding) block, if a model has one
        if x_extra is None:
            return None
        b = m['blocks'][1]; z.append(b['weight'] * (np.asarray(x_extra, np.float64) - np.asarray(b['mean'])) / np.asarray(b['scale']))
    return float(np.concatenate(z) @ np.asarray(m['coef']) + m['intercept'])


def severity(finding_id: str, emb_by_pose_crop: dict, extra: dict | None, model_dir: str, allow_partial: bool = False):
    """0-100 percentile (float) or None when there is no model for this finding or the inputs are missing."""
    spec = specs(model_dir).get(finding_id)
    if spec is None:
        return None
    x = _embedding(spec, emb_by_pose_crop, allow_partial)
    if x is None:
        return None
    xe = None
    names = [e['name'] for e in spec['inputs'].get('extra', [])]
    if names:
        vals = [(extra or {}).get(n) for n in names]
        if any(v is None or not np.isfinite(float(v)) for v in vals):
            return None
        xe = np.array(vals, np.float64)
    p = raw_prediction(spec, x, xe)
    if p is None or not np.isfinite(p):
        return None
    ref = spec['_ref']
    return float(100.0 * (np.searchsorted(ref, p, 'left') + 0.5 * (np.searchsorted(ref, p, 'right') - np.searchsorted(ref, p, 'left'))) / len(ref))


def needed_crops(model_dir: str) -> set:
    return {c for s in specs(model_dir).values() for c in s['inputs']['embedding']['crops']}


def manifest(model_dir: str) -> dict:
    return {os.path.relpath(p, model_dir): hashlib.sha256(open(p, 'rb').read()).hexdigest()
            for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', 'severity', '*.json')))
            if not os.path.basename(p).startswith('REPORT')}


# ---- per-photo form (numbers only cross the API): the Ridge prediction is linear in the row mean, so
#      prediction = mean over expected rows of coef·((row - mean)/scale) + intercept. Each photo sends its row terms.
def row_terms(view: str, emb_by_crop: dict, model_dir: str) -> dict:
    """{finding id: {'<view>:<crop>': term}} for the expected rows this photo provides (embedding-only models)."""
    out = {}
    for fid, spec in specs(model_dir).items():
        if len(spec['model']['blocks']) != 1:
            continue
        b0 = spec['model']['blocks'][0]; coef = np.asarray(spec['model']['coef']); terms = {}
        for v, crop in (tuple(r) for r in spec['inputs']['embedding']['expectedRows']):
            if v == VIEW_OF_POSE.get(view) and crop in emb_by_crop:
                z = (np.asarray(emb_by_crop[crop], np.float64) - np.asarray(b0['mean'])) / np.asarray(b0['scale'])
                terms[f'{v}:{crop}'] = round(float(coef @ z), 8)
        if terms:
            out[fid] = terms
    return out


def from_terms(finding_id: str, terms: dict, model_dir: str):
    """0-100 percentile from the row terms of all photos; None unless every expected row is present (research rule)."""
    spec = specs(model_dir).get(finding_id)
    if spec is None:
        return None
    want = [f'{v}:{c}' for v, c in spec['inputs']['embedding']['expectedRows']]
    if any(k not in terms for k in want):
        return None
    p = float(np.mean([terms[k] for k in want]) + spec['model']['intercept'])
    ref = spec['_ref']
    return float(100.0 * (np.searchsorted(ref, p, 'left') + 0.5 * (np.searchsorted(ref, p, 'right') - np.searchsorted(ref, p, 'left'))) / len(ref))
