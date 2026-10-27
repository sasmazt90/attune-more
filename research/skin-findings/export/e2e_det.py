"""End-to-end test of the analyze_photo snippet (REPORT_det.md) WITHOUT editing regional_skin_v3.py: the snippet is
inserted into an in-memory copy of analyze_photo; source photos (3 poses) -> photo_result -> decide()."""
import os, sys, json, inspect, textwrap, cv2, numpy as np
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'; sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R, skin_findings_det as SFD
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
SNIPPET = open(f'{S}/v2/analyze_photo_snippet.py').read()
src = textwrap.dedent(inspect.getsource(R.analyze_photo))
anchor = '    import skin_findings_v1 as SF\n'
assert src.count(anchor) == 1
src = src.replace(anchor, textwrap.indent(SNIPPET, '    ') + anchor)
src = src.replace('findingScores=finding_scores,', 'findingScores=finding_scores, findingDet=finding_det,')
exec(compile(src, 'analyze_photo_patched', 'exec'), R.__dict__)
LM = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans']}
for kid in sys.argv[1:]:
    maps = {}
    for pose, f in (('FRONT', 'front'), ('LEFT', 'side_1'), ('RIGHT', 'side_2')):
        bgr = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png')
        L = [{'x': q.x, 'y': q.y, 'z': q.z} for q in LM.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
        maps[pose] = R.analyze_photo(bgr, L, pose=pose)
        json.dumps(maps[pose]['findingDet'])   # must be JSON-serialisable
    d = SFD.decide({p: m['findingDet'] for p, m in maps.items()}, R.MODEL_DIR)
    p = st[kid]
    print(kid, 'labels: acne', p['acne'], p.get('acneRegions'), '| sens', p['sens'], p.get('sensRegions'), '| source', {q: m['findingDet']['landmarkSource'] for q, m in maps.items()})
    for e in d:
        if e['status'] == 'seen':
            print('   SEEN', e)
    print('   notSeen:', [(e['id'], e['region'], e['probability']) for e in d if e['status'] != 'seen'])
print('manifest', SFD.manifest(R.MODEL_DIR))
