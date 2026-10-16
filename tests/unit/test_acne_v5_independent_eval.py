"""The v5 evaluation's model input, tiles and predictions must not depend on annotations."""
import copy, inspect, json, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research')]
import eval_acne_v5_independent as ev


def test_preprocessing_and_inference_take_no_labels():
    for fn in (ev.plan, ev.infer):
        assert not ({'positive', 'boxes', 'annotations', 'truth', 'targets', 'side'} & set(inspect.signature(fn).parameters))
    src = inspect.getsource(ev.plan) + inspect.getsource(ev.infer) + inspect.getsource(ev.run_photo)
    for word in ("['positive']", "photo_scale", "['ignore']", "negativeBoxes"): assert word not in src


def test_changing_annotations_changes_nothing_before_metrics():
    rp_path = ev.OUT / 'replay.jsonl'
    if not rp_path.exists() or not (ev.D / 'manifest-v4.json').exists(): pytest.skip('local evaluation data not present')
    v2 = ev.setup(); import torch
    rp = {json.loads(l)['sha256']: json.loads(l) for l in rp_path.read_text().splitlines()}
    p = next(x for x in ev.photos() if x['kind'] == 'positive-photo' and rp[x['sha256']].get('gatePassedWithoutEyewear') and len(x['positive']) >= 2)
    q = copy.deepcopy(p); q['positive'] = [dict(b, box=[v * 0.5 for v in b['box']]) for b in q['positive'][:1]]; q['ignore'] = []; q['negativeBoxes'] = []
    torch.set_num_threads(2); net = v2.build_net(ev.TOGG).eval()
    a = ev.run_photo(net, p, rp[p['sha256']]); b = ev.run_photo(net, q, rp[q['sha256']])
    for k in ('status', 'rects', 'final', 'rawAfterNMS', 'confidenceCandidates', 'tiles'): assert a[k] == b[k], k
    # metrics DO change with annotations (the only place labels enter)
    ma = ev.metrics([a], [p]); mb = ev.metrics([b], [q])
    assert ma['pos']['targets'] != mb['pos']['targets']
