"""Severity input parity: production crop (skin_findings_dino.crops_of) + production embedder (regional_skin_v3.KClassifier.embed)
vs the research cache (rf/finding_angle4_emb.npz) used by export_sev.py, for rated persons; then severity() end to end.
Usage: cd $S && python3 v2/sev_parity.py K-xxx K-yyy ..."""
import sys, json, collections, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import skin_findings_dino as SD, skin_findings_severity as SV
from regional_skin_v3 import KClassifier
emb = KClassifier({}, f'{S}/rv3model/dinov2-small')
MD = f'{S}/rv3model'
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
z = np.load(f'{S}/rf/finding_angle4_emb.npz', allow_pickle=True); E = z['E']; M = z['meta']
idx = collections.defaultdict(list)
for i, m in enumerate(M): idx[(m['kid'], m['crop'], m['src'])].append(i)
K = json.load(open(f'{S}/rate/key.json')); IDS = {'torba': 'eyeBags', 'morluk': 'darkCircles', 'kapak': 'hoodedEyelids', 'kaz': 'crowsFeet', 'alin': 'foreheadLines', 'akneizi': 'acneMarks'}
need = SV.needed_crops(MD); worst = 0.0; out = {}
for kid in sys.argv[1:]:
    prod, cache = {}, {}
    for f, view, srcn in (('front', 'front', 'front'), ('side_1', 'pos', 's20'), ('side_2', 'neg', 's20')):
        img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png')
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        lmk = [dict(x=q.x, y=q.y) for q in r.face_landmarks[0]]
        crops = SD.crops_of(img, lmk, view, need); names = list(crops)
        for n, v in zip(names, emb.embed([crops[n] for n in names])):
            prod[(view, n)] = v
            ii = idx.get((kid, n, srcn), [])
            # s20 holds both side photos; the side rule leaves one row per (kid, crop) for L/R crops, two for centre crops
            d = min(float(np.abs(E[i] - v).max()) for i in ii); worst = max(worst, d)
            j = min(ii, key=lambda i: np.abs(E[i] - v).max()); cache[(view, n)] = E[j]
    sev = {}
    for f, fid in IDS.items():
        if kid in K[f]:
            sev[fid] = (round(SV.severity(fid, prod, {}, MD), 4), round(SV.severity(fid, cache, {}, MD), 4))
    out[kid] = dict(rows=len(prod), maxAbsDiff=max(float(np.abs(prod[k] - cache[k]).max()) for k in prod), severity_prod_vs_cache=sev)
    print(kid, json.dumps(out[kid]), flush=True)
print('WORST max|diff| over all crops:', worst)
json.dump(dict(persons=out, worstMaxAbsDiff=worst), open(f'{S}/v2/sev_parity.json', 'w'), indent=1)
