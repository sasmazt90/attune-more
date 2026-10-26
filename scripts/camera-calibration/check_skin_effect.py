"""Effect of a camera colour cast and of the fitted calibration profile on the skin findings (no training, local models).

For each person: the three source photos are (a) analysed as they are, (b) with a simulated camera colour cast,
(c) with the same cast corrected by a profile fitted from a synthetic photo of the Attune chart taken under that cast.
Geometry (landmarks) is identical in all three, so differences come from colour only. Synthetic photos and a simulated
cast: this shows the mechanism, not real-camera accuracy.

usage: ATTUNE_REGIONAL_V3_DIR=... python scripts/camera-calibration/check_skin_effect.py PHOTO_ROOT OUT.json K-217 [K-...]
PHOTO_ROOT/<id>/<id>-{front,side_1,side_2}.png
"""
import json, sys
from pathlib import Path
import cv2, numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api')); sys.path.insert(0, str(ROOT / 'tests/unit'))
import camera_color as CC, camera_calibration as CAL, regional_skin_v3 as R
from regional_attach import fuse_regional
from test_camera_color import synthetic_chart_photo
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

D = np.array([[1.08, .06, -.02], [.03, .95, .04], [-.04, .08, .86]]); GAIN, OFF = 0.92, np.array([.004, .003, .006])
def cast(bgr):
    lin = CC.srgb_to_linear(bgr[..., ::-1] / 255.) @ D.T * GAIN + OFF
    return (CC.linear_to_srgb(lin) * 255 + .5).astype(np.uint8)[..., ::-1]
profile, report = CAL.fit_profile([CAL.measure_chart(synthetic_chart_photo(D, GAIN, OFF))], 'simulated-cast', yuv={'matrix': 'bt601', 'fullRange': False})
assert profile, report
LM = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')), num_faces=1))
root, out = Path(sys.argv[1]), Path(sys.argv[2])

def summary(findings):
    rows = {}
    for f in findings['findings']:
        if f['status'] == 'seen':
            v = {k: f[k] for k in ('count', 'severity', 'areaPct', 'toneDiff') if k in f}
            rows[f"{f['id']}/{f['region']}"] = v
    return rows

result = {'cast': {'matrix': D.tolist(), 'gain': GAIN, 'offset': OFF.tolist()}, 'calibration': report['fit'], 'persons': {}}
for kid in sys.argv[3:]:
    photos = {p: cv2.imread(str(root / kid / f'{kid}-{f}.png')) for p, f in (('FRONT', 'front'), ('LEFT', 'side_1'), ('RIGHT', 'side_2'))}
    lms = {p: [{'x': q.x, 'y': q.y, 'z': q.z} for q in LM.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(b, cv2.COLOR_BGR2RGB))).face_landmarks[0]] for p, b in photos.items()}
    person = {}
    for name, fn in (('original', lambda b: b), ('cast', cast), ('castCorrected', lambda b: CC.apply_ccm(cast(b), profile))):
        imgs = {p: fn(b) for p, b in photos.items()}
        maps = {p: R.analyze_photo(imgs[p], lms[p], pose=p) for p in imgs}
        person[name] = {'seen': summary(fuse_regional(maps)['findings']),
                        'faceMeanAbsDiffVsOriginal': round(float(np.abs(imgs['FRONT'].astype(int) - photos['FRONT']).mean()), 2)}
    o = set(person['original']['seen'])
    for name in ('cast', 'castCorrected'):
        s = set(person[name]['seen']); person[name]['lost'] = sorted(o - s); person[name]['added'] = sorted(s - o)
    result['persons'][kid] = person
    print(kid, {n: (len(person[n]['seen']), person[n].get('lost'), person[n].get('added')) for n in person}, flush=True)
out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
