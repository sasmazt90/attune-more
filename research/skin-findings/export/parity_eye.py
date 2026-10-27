"""Feature parity: production skin_findings_eye features (from photo + MediaPipe landmarks as list of dicts) vs the
cached research features (eye_pose_rows.npz 'col' front rows, sag_geo.json, eye_fair_emb.npz) and the research light.py.
Usage: python3 parity_eye.py K-181 K-190 ...   (prints JSON lines + a summary)"""
import sys, json, time, numpy as np, cv2, collections, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); import light
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api'); import skin_findings_eye as SE
from scipy.spatial import Delaunay

class Embedder:   # same code as regional_skin_v3.KClassifier.embed (local dinov2-small, local_files_only)
    def __init__(self, d):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        self.torch = torch; self.proc = AutoImageProcessor.from_pretrained(d, local_files_only=True); self.dm = AutoModel.from_pretrained(d, local_files_only=True).eval()
    def embed(self, crops):
        from PIL import Image
        with self.torch.no_grad():
            o = self.dm(**self.proc(images=[Image.fromarray(c) for c in crops], return_tensors='pt')).last_hidden_state
            return self.torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy()

emb = Embedder(f'{S}/rv3model/dinov2-small')
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
rows = list(np.load(f'{S}/rf/eye_pose_rows.npz', allow_pickle=True)['rows'])
COL = collections.defaultdict(list)
for r in rows:
    if r['pose'] == 'front': COL[r['kid']].append(r['col'])
sg = json.load(open(f'{S}/rf/sag_geo.json')); EMB = np.load(f'{S}/rf/eye_fair_emb.npz', allow_pickle=True)['E'].item()
MD = f'{S}/rv3model'; sp = SE.specs(MD)
out = []
for kid in sys.argv[1:]:
    img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); h, w = img.shape[:2]
    r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    L = [dict(x=q.x, y=q.y, z=q.z) for q in r.face_landmarks[0]]
    t0 = time.time(); X = SE.features(img, L, emb); dt = time.time() - t0
    # research references
    col_ref = np.mean(COL[kid], 0)
    geo_ref = np.array(list(sg[kid]['f'].values()))
    lid_ref = (EMB[kid]['lid_L'] + EMB[kid]['lid_R']) / 2; cor_ref = (EMB[kid]['corner_L'] + EMB[kid]['corner_R']) / 2
    # triangulation check: cv2.Subdiv2D vs scipy Delaunay on the same 400-px-face points
    P = np.array([[q['x'] * w, q['y'] * h] for q in L[:468]]); fw = P[:, 0].max() - P[:, 0].min(); sc = 400 / fw
    P2 = (P - [P[:, 0].min() - .15 * fw, P[:, 1].min() - .15 * fw]) * sc
    tri_cv = {tuple(sorted(t)) for t in SE._delaunay(P2, 0, 0).tolist()}; tri_sp = {tuple(sorted(t)) for t in Delaunay(P2).simplices.tolist()}
    # research light.py on the same landmarks (scipy) -> colour, to separate port error from landmark/cache drift
    class Q:  # attribute access like Python MediaPipe
        def __init__(s, d): s.x, s.y, s.z = d['x'], d['y'], d['z']
    R = light.analyze(img, [Q(d) for d in L]); Rp = SE.light_analyze(img, L)
    d = dict(kid=kid, secs=round(dt, 2), tri_cv=len(tri_cv), tri_scipy=len(tri_sp), tri_same=tri_cv == tri_sp,
             corr_maxabs_vs_lightpy=float(np.abs(R['corr'] - Rp['corr']).max()),
             col=X['darkCircles'][:3].tolist() if 'darkCircles' in X else None, col_ref=col_ref.tolist(),
             col_maxabs=float(np.abs(X['darkCircles'][:3] - col_ref).max()) if 'darkCircles' in X else None,
             geo_maxabs=float(np.abs(X['hoodedEyelids'][:7] - geo_ref).max()),
             lid_emb_maxabs=float(np.abs(X['hoodedEyelids'][7:] - lid_ref).max()), corner_emb_maxabs=float(np.abs(X['downturnedCorners'][7:] - cor_ref).max()))
    # probabilities: production features vs cached features
    ref = {'darkCircles': np.concatenate([col_ref, [1, 0]]), 'hoodedEyelids': np.concatenate([geo_ref, lid_ref]), 'downturnedCorners': np.concatenate([geo_ref, cor_ref])}
    for fid in SE.FINDINGS:
        if fid in X:
            pp, pr = SE.predict_proba(sp[fid], X[fid]), SE.predict_proba(sp[fid], ref[fid])
            d[f'p_{fid}'] = [round(pp, 5), round(pr, 5)]; d[f'flip_{fid}'] = SE.decide(pp, sp[fid]) != SE.decide(pr, sp[fid])
    # photo_scores entry point + missing z / side view behaviour
    d['photo_scores'] = SE.photo_scores(img, L, 'front', emb, MD)
    d['no_z'] = SE.photo_scores(img, [dict(x=q['x'], y=q['y']) for q in L], 'front', emb, MD)
    d['side_view'] = SE.photo_scores(img, L, 'pos', emb, MD)
    print(json.dumps(d), flush=True); out.append(d)
def agg(k):
    v = np.array([o[k] for o in out if o.get(k) is not None]); return dict(max=float(v.max()), median=float(np.median(v)), n=len(v))
summ = {k: agg(k) for k in ('col_maxabs', 'geo_maxabs', 'lid_emb_maxabs', 'corner_emb_maxabs', 'corr_maxabs_vs_lightpy')}
for fid in SE.FINDINGS:
    dp = np.array([abs(o[f'p_{fid}'][0] - o[f'p_{fid}'][1]) for o in out if f'p_{fid}' in o])
    summ[f'prob_absdiff_{fid}'] = dict(max=float(dp.max()), median=float(np.median(dp)), n=len(dp), flips=int(sum(o.get(f'flip_{fid}', False) for o in out)))
summ['triangulation_identical'] = f"{sum(o['tri_same'] for o in out)}/{len(out)}"
summ['secs_median'] = float(np.median([o['secs'] for o in out]))
print('SUMMARY', json.dumps(summ, indent=1))
json.dump(dict(persons=out, summary=summ), open(f'{S}/v2/parity_eye.json', 'w'), indent=1)
