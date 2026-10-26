"""Extra checks: (1) decide() on the 80 test persons from cached features = research person decisions;
(2) redness: effect of the research-only row filter (region must also exist in redness_feats.json) which production cannot apply;
(3) region-level precision/recall of decide()'s 'seen' regions on the test persons (information only)."""
import sys, json, numpy as np, re
sys.argv = ['x']; exec(open('export_det.py').read().split("def main():")[0])
sys.path.insert(0, f'{REPO}/services/core-api'); import skin_findings_det as SFD
MD = f'{S}/rv3model'; SP = SFD.specs(MD)
for fid in ('acne', 'redness'):
    J = SP[fid]
    for nofilter in ((False, True) if fid == 'redness' else (False,)):
        if nofilter:
            RF.clear(); RF.update({str(i): {g: 1 for g in APP} for i in range(0, 10**6)})   # disable the filter
        rows, _ = build_rows(fid)
        tep = sorted({r['kid'] for r in rows if r['kid'] in test and r['src'] in TR})
        lab = (lambda k: st[k]['acne'] != 'yok') if fid == 'acne' else (lambda k: st[k]['sens'] != 'yok')
        regl = (lambda k: set(st[k]['acneRegions'])) if fid == 'acne' else (lambda k: set(st[k]['sensRegions']) if st[k]['sens'] != 'yok' else set())
        tp = fp = fn = 0; rtp = rfp = rfn = 0; nrows = 0
        for k in tep:
            by = {}
            for r in rows:
                if r['kid'] != k or r['src'] not in TR: continue
                nrows += 1; pose = {'front': 'FRONT', 'pos': 'LEFT', 'neg': 'RIGHT'}[r['view']]
                ex = dict(bare={r['reg']: {'c_red': r['f'].get('c_red')}}, color={r['reg']: {'cv_red': r['f'].get('cv_red'), 'cv_redp90': r['f'].get('cv_redp90')}}, ita=r['f'].get('ita'))
                by.setdefault(pose, {fid: {}})[fid].update(SFD.photo_scores({r['reg']: r['f']}, ex, r['view'], MD, folds=True)[fid])
            d = SFD.decide(by, J); seen = {e['region'] for e in d if e['status'] == 'seen'}; y = lab(k)
            tp += bool(seen) and y; fp += bool(seen) and not y; fn += (not seen) and y
            g = regl(k); rtp += len(seen & g); rfp += len(seen - g); rfn += len(g - seen)
        print(fid, 'nofilter' if nofilter else 'research rows', f'test persons {len(tep)} rows {nrows}: person TP {tp} FP {fp} FN {fn}; region TP {rtp} FP {rfp} FN {rfn} P {rtp/max(rtp+rfp,1):.2f} R {rtp/max(rtp+rfn,1):.2f}')
