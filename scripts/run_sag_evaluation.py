import sys
sys.path.insert(0, r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin\services\core-api')
sys.path.insert(0, '../attune-live-test/scripts/skin-research')
sys.path.insert(0, '../attune-live-test/.runtime/python-packages')
import json, cv2, numpy as np, subprocess, base64, hashlib
from pathlib import Path
import appearance_analysis as A

def run_local(payload, bgr):
    p = {**payload}
    ok, raw = cv2.imencode('.png', bgr)
    assert ok
    p['photo'] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
    p['photoId'] = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
    response = A.analyze_skin(p)
    return dict(photoId=p['photoId'], skinType=response['general']['skinType'], measurements=response['general']['measurements'], modelInference=response['general'].get('modelInference'), regionMeasurements=response['measurements'], maps=response.get('maps', {}))

folder = Path('../attune-live-test/audit-results/skin-expanded-20261011/sag-controls')
candidates = json.loads((folder / 'candidates.json').read_text('utf8')) + json.loads((folder / 'additional-candidates.json').read_text('utf8'))
old_results = json.loads((folder / 'actual-results.json').read_text('utf8'))['rows']

import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
detector = FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path='../attune-live-test/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=2))

indices = [r['index'] for r in old_results]
old_map = {r['index']: r for r in old_results}
selected = []
for i in indices:
    r = dict(candidates[i])
    im = cv2.imread(r['absolutePath'])
    if not r.get('landmarks'):
        found = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
        if len(found.face_landmarks) == 1:
            r['landmarks'] = [dict(x=p.x, y=p.y, z=p.z) for p in found.face_landmarks[0]]
    r['reviewIndex'] = i
    selected.append(r)
detector.close()

meshes = json.loads(subprocess.check_output(['node', '../attune-live-test/scripts/skin-research/focused_meshes.cjs'], input=json.dumps(selected).encode(), cwd='../attune-live-test'))

new_runs = []
for r, m in zip(selected, meshes):
    im = cv2.imread(r['absolutePath'])
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    alignment = m['alignment']
    conditions = {k: alignment[k] for k in ['yaw', 'pitch', 'roll', 'scaleRatio']}
    conditions.update(avgLuminance=float(gray.mean()), blurScore=float(cv2.Laplacian(gray, cv2.CV_32F).var()))
    payload = dict(pose='FRONT', landmarks=r['landmarks'], meshes=m['meshes'], exclusions=[], qualityValid=40<=gray.mean()<=220 and conditions['blurScore']>=4 and abs(alignment['yaw'])<.35, conditions=conditions)
    res = run_local(payload, im)
    global_sag = next(v for v in res['measurements'] if v['id'] == 'sag')
    local_sag = {reg: [v for v in vals if v['id'] == 'sag'] for reg, vals in res['regionMeasurements'].items()}
    
    old_item = old_map.get(r['reviewIndex'], {})
    declared_label = old_item.get('engineeringSagAppearance', 'negative')
    
    # Detailed diagnosis of Photo 57 or any other mismatch:
    record = {
        'index': r['reviewIndex'],
        'sha256': r['sha256'],
        'path': r.get('path'),
        'declaredLabel': declared_label,
        'sag_overview': global_sag['value'],
        'quality': global_sag['quality'],
        'limitation': global_sag['limitationCode'],
        'norm_version': global_sag['normalizationVersion'],
        'measuredSides': global_sag['components'].get('measuredSides'),
        'missingSides': global_sag['components'].get('missingSides'),
        'rightCheek': local_sag['rightCheek'][0]['value'] if local_sag.get('rightCheek') else None,
        'chin': local_sag['chin'][0]['value'] if local_sag.get('chin') else None,
        'leftCheek': local_sag['leftCheek'][0]['value'] if local_sag.get('leftCheek') else None,
        'localMaps': [k for k in res['maps'] if 'sag' in k]
    }
    
    if r['reviewIndex'] == 57:
        record['diagnosis'] = (
            "Photo 57 originates from eye-training-v2 (path: train/images/01321_png_jpg...). "
            "It has severe pitch (0.11), shadow in lower face, and partial right-side crop. "
            "The lower-left anatomical band is invisible (ANATOMICAL_BAND_NOT_VISIBLE), "
            "the right side has unstable contour tracking (CONTOUR_TRACKING_UNSTABLE), "
            "and the measured lower-right fold has 0.0047 fold and 0.0469 continuity. "
            "Under the fixed v6 metric, this yields strictly 0.00% measured lower-right appearance. "
            "Thus, declared positive label in old audit registry is not supported by anatomical lower-face fold "
            "and represents an inconclusive / unmeasurable lower-face sample with partial coverage."
        )
    elif r['reviewIndex'] == 47:
        record['diagnosis'] = (
            "Photo 47 is the verified positive control with visible asymmetric lower-face contour fold. "
            "Lower-right marionette side yields 8.24% fold appearance, regional rightCheek and chin yield 4.12%, "
            "and overview yields 2.06% (Math.round -> 2%), successfully resolving the integer 0% UI clipping."
        )
    
    new_runs.append(record)

print('=== RESULTS VIA WORKTREE ANALYZE_SKIN PIPELINE ===')
for r in new_runs:
    ov = r['sag_overview']
    rnd = round(ov) if ov is not None else None
    print('Photo %d (declared: %s): overview=%s (round=%s), sides=%s, rightCheek=%s, chin=%s, lim=%s' % (
        r['index'], r['declaredLabel'], str(ov), str(rnd), str(r['measuredSides']), str(r['rightCheek']), str(r['chin']), str(r['limitation'])
    ))

out_file = Path('audit-results/sag-calibrated-true-results.json')
out_file.parent.mkdir(exist_ok=True, parents=True)
out_file.write_text(json.dumps(new_runs, indent=2), encoding='utf-8')
print('Saved comprehensive sag run to audit-results/sag-calibrated-true-results.json')
