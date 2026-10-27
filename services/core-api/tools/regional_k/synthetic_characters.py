"""Attune synthetic in-car skin profiles: plan -> generate (front + 2 side poses, same identity) -> review -> approve.

Commands
  plan N            add N balanced character plans (K-031, K-032, ...)
  next              generate the next planned character into pending/<id>/ and STOP for review
  approve ID        move pending/<id>/ into approved/ and append the Excel row
  reject ID "why"   discard images, keep the plan, log the reason (it will be regenerated on `next`)
  status            counts + spend so far

The API key is read from a local .env (OPENAI_API_KEY) and never printed.
Identity check: OpenCV SFace (Apache-2.0) cosine between front and each side pose; < SIM_MIN -> regenerate that pose.
"""
import os, sys, json, random, re, base64, time, io, shutil
import numpy as np, cv2

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, 'state.json')
PENDING, APPROVED = os.path.join(ROOT, 'pending'), os.path.join(ROOT, 'approved')
XLSX = os.path.join(ROOT, 'otomatik_karakter_profilleri.xlsx')
ENV = os.environ.get('ATTUNE_GEN_ENV', os.path.join(os.path.dirname(ROOT), '.oa_env'))
FACEREC = os.path.join(os.path.dirname(ROOT), 'facerec')
MODEL = os.environ.get('ATTUNE_IMAGE_MODEL', 'gpt-image-2.5-flare')
SIZE, QUALITY = '1024x1536', os.environ.get('ATTUNE_IMAGE_QUALITY', 'high')
SIM_MIN, MAX_TRIES = 0.45, 3
PRICE_OUT, PRICE_IN_IMG, PRICE_IN_TXT = 30e-6, 8e-6, 5e-6   # USD per token (model page)

REGIONS = [('forehead', 'Alın', 'forehead'), ('nose', 'Burun', 'nose'), ('rightCheek', 'Sağ yanak', "the cheek on the LEFT side of the image (the person's own right cheek)"),
           ('leftCheek', 'Sol yanak', "the cheek on the RIGHT side of the image (the person's own left cheek)"), ('chin', 'Çene', 'chin')]
TR_TYPE = {'oily': 'yağlı', 'dry': 'kuru', 'normal': 'normal'}
FST = {'I': 'very fair, pale skin (Fitzpatrick I)', 'II': 'fair skin (Fitzpatrick II)', 'III': 'light olive / wheatish skin (Fitzpatrick III)',
       'IV': 'olive-brown skin (Fitzpatrick IV)', 'V': 'brown skin (Fitzpatrick V)', 'VI': 'deep dark brown skin (Fitzpatrick VI)'}
FST_TR = {'I': 'I (çok açık)', 'II': 'II (açık)', 'III': 'III (buğday)', 'IV': 'IV (esmer)', 'V': 'V (koyu)', 'VI': 'VI (çok koyu)'}
# region patterns: weighted toward the cases the model fails on (mixed faces, normal skin, oily cheeks)
PATTERNS = [
    ('T-yağlı / yanak normal', dict(forehead='oily', nose='oily', rightCheek='normal', leftCheek='normal', chin='normal'), 4),
    ('T-yağlı / yanak kuru', dict(forehead='oily', nose='oily', rightCheek='dry', leftCheek='dry', chin='normal'), 3),
    ('tümü normal', dict(forehead='normal', nose='normal', rightCheek='normal', leftCheek='normal', chin='normal'), 4),
    ('tümü yağlı', dict(forehead='oily', nose='oily', rightCheek='oily', leftCheek='oily', chin='oily'), 3),
    ('yanak yağlı / T normal', dict(forehead='normal', nose='normal', rightCheek='oily', leftCheek='oily', chin='oily'), 2),
    ('tümü kuru', dict(forehead='dry', nose='dry', rightCheek='dry', leftCheek='dry', chin='dry'), 2),
    ('yanak kuru / geri kalan normal', dict(forehead='normal', nose='normal', rightCheek='dry', leftCheek='dry', chin='normal'), 3),
    ('alın-burun yağlı / çene kuru', dict(forehead='oily', nose='oily', rightCheek='normal', leftCheek='normal', chin='dry'), 2),
]
LOOK = {'oily': 'clearly visible greasy shine and oily sheen', 'dry': 'clearly dry, matte skin with visible fine flaking and rough texture',
        'normal': 'healthy normal skin: no shine, no flaking, natural soft matte finish'}
# subtle rendering (closer to how real mild oiliness/dryness looks in a car selfie)
LOOK_SUBTLE = {'oily': 'mild oiliness: a subtle, slight natural sheen that catches the light, not greasy or dripping',
               'dry': 'mildly dry skin: slightly dull and less supple, faint fine texture and only a few tiny barely visible flakes on close look',
               'normal': LOOK['normal']}

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return dict(next_id=31, plans=[], spend_usd=0.0, log=[])

def save_state(s):
    json.dump(s, open(STATE, 'w'), ensure_ascii=False, indent=1)

def sample(rng, kid):
    tone = rng.choices(list(FST), weights=[1, 1.5, 2, 2.5, 3, 3])[0]
    sex = rng.choice(['erkek', 'kadın'])
    age = rng.choices(['18-25', '26-35', '36-45', '46-55', '56-65', '66+'], weights=[3, 3, 2.5, 2, 1.5, 1])[0]
    beard = rng.choices(['yok', 'sinek kaydı', 'kısa sakal — koyu', 'kısa sakal — kır', 'uzun sakal — kır'], weights=[4, 2, 2, 1, 1])[0] if sex == 'erkek' else 'yok'
    if beard.endswith('kır') and age in ('18-25', '26-35'):
        beard = 'kısa sakal — koyu'
    name, regions, _ = rng.choices(PATTERNS, weights=[p[2] for p in PATTERNS])[0]
    sens = rng.choices(['yok', 'kızarıklık', 'rozasea', 'egzama', 'sedef'], weights=[6, 2, 1.5, 1.5, 0.5])[0]
    sens_regions = []
    if sens == 'rozasea':
        sens_regions = ['rightCheek', 'leftCheek'] + (['nose'] if rng.random() < .5 else [])
    elif sens != 'yok':
        sens_regions = rng.sample([r[0] for r in REGIONS], rng.choice([1, 2]))
    acne = 'yok'
    if any(v == 'oily' for v in regions.values()) and age in ('18-25', '26-35') and rng.random() < .55:
        acne = rng.choice(['az (1-3)', 'orta (4-10)'])
    acne_regions = [r for r, v in regions.items() if v == 'oily'][:2] if acne != 'yok' else []
    extras = []
    if age in ('46-55', '56-65', '66+'):
        extras += rng.sample(['kaz ayağı', 'alın kırışıklığı', 'göz altı torbası', 'güneş lekesi'], 2)
    if rng.random() < .2:
        extras.append(rng.choice(['ben (yanakta)', 'melazma (yanaklarda)', 'dudakta uçuk']))
    return dict(id=f'K-{kid:03d}', tone=tone, sex=sex, age=age, beard=beard, pattern=name, regions=regions,
                sens=sens, sensRegions=sens_regions, acne=acne, acneRegions=acne_regions, extras=extras, status='planned', tries=0,
                intensity=('hafif' if rng.random() < float(os.environ.get('ATTUNE_SUBTLE', '0')) else 'belirgin'))

def region_en(rid):
    return next(r[2] for r in REGIONS if r[0] == rid)

def front_prompt(p):
    sex_en = 'man' if p['sex'] == 'erkek' else 'woman'
    beard = {'yok': 'clean-shaven' if p['sex'] == 'erkek' else '', 'sinek kaydı': 'with light stubble',
             'kısa sakal — koyu': 'with a short dark beard', 'kısa sakal — kır': 'with a short grey beard',
             'uzun sakal — kır': 'with a long grey beard'}[p['beard']]
    lines = [f"Photorealistic smartphone-quality selfie taken by the in-car driver-facing camera of a parked car. A {sex_en} aged {p['age'].replace('+',' or older')} {beard}, {FST[p['tone']]}.",
             "Front pose: looking straight into the camera, neutral relaxed expression, mouth closed, no glasses, hair away from the forehead, whole face fully visible.",
             "Even, natural daylight through the windshield; no makeup, no filter, no retouching, no beauty glow; realistic pores and skin texture."]
    by_type = {}
    for rid, t in p['regions'].items():
        by_type.setdefault(t, []).append(region_en(rid))
    for t, regs in by_type.items():
        lines.append(f"Skin on {', '.join(regs)}: {(LOOK_SUBTLE if p.get('intensity') == 'hafif' else LOOK)[t]}.")
    if 'oily' in by_type:
        verb = 'have a slight sheen' if p.get('intensity') == 'hafif' else 'shine'
        lines.append(f"Only the {', '.join(by_type['oily'])} {verb}; all other areas have no shine at all.")
    else:
        lines.append("No shine anywhere on the face.")
    if p['sens'] != 'yok':
        what = {'kızarıklık': 'visible diffuse redness', 'rozasea': 'rosacea: persistent redness with fine visible capillaries',
                'egzama': 'eczema patches: red, dry, slightly scaly', 'sedef': 'psoriasis plaques: well-defined red patches with silvery scale'}[p['sens']]
        lines.append(f"{what} on {', '.join(region_en(r) for r in p['sensRegions'])}.")
    if p['acne'] != 'yok':
        n = '2-3' if p['acne'].startswith('az') else '5-8'
        lines.append(f"{n} small inflamed acne papules and a few blackheads on {', '.join(region_en(r) for r in p['acneRegions'])}.")
    ex = {'kaz ayağı': "crow's feet", 'alın kırışıklığı': 'forehead lines', 'göz altı torbası': 'under-eye bags', 'güneş lekesi': 'a few sun spots',
          'ben (yanakta)': 'one small mole on a cheek', 'melazma (yanaklarda)': 'melasma patches on both cheeks', 'dudakta uçuk': 'a cold sore on the lip'}
    if p['extras']:
        lines.append('Also: ' + ', '.join(ex[e] for e in p['extras']) + '.')
    lines.append("Portrait orientation, head and shoulders, car interior softly visible behind.")
    return ' '.join(lines)

def side_prompt(p, side):
    turn = ('so that the nose points toward the RIGHT side of the image (the person turns their head to their own left)' if side == 1
            else 'so that the nose points toward the LEFT side of the image (the person turns their head to their own right)')
    return (f"This is character {p['id']} from the reference photo. Generate the SAME person, same identity, same face, same age, same hair, "
            f"same clothing, same skin tone and exactly the same skin condition in every region as the reference (same shine, dryness, redness, "
            f"spots and lesions in the same places). Same in-car setting and lighting. Only change the head pose: head turned about 20 degrees {turn}, "
            f"eyes looking where the head points, neutral expression. Photorealistic, no makeup, no retouching.")

def client():
    from openai import OpenAI
    key = re.search(r'OPENAI_API_KEY\s*=\s*(\S+)', open(ENV, encoding='utf-8-sig').read()).group(1).strip('"\'')
    return OpenAI(api_key=key)

def cost(usage):
    if usage is None:
        return 0.0
    u = usage if isinstance(usage, dict) else usage.model_dump()
    det = u.get('input_tokens_details') or {}
    return u.get('output_tokens', 0) * PRICE_OUT + det.get('image_tokens', 0) * PRICE_IN_IMG + det.get('text_tokens', 0) * PRICE_IN_TXT

_fr = None
def face_feat(path):
    global _fr
    if _fr is None:
        _fr = (cv2.FaceDetectorYN.create(os.path.join(FACEREC, 'yunet.onnx'), '', (320, 320), 0.6),
               cv2.FaceRecognizerSF.create(os.path.join(FACEREC, 'sface.onnx'), ''))
    det, rec = _fr
    im = cv2.imread(path); h, w = im.shape[:2]; det.setInputSize((w, h)); _, f = det.detect(im)
    if f is None:
        return None
    f = f[np.argmax(f[:, 2] * f[:, 3])]
    return rec.feature(rec.alignCrop(im, f))

_lm = None
def yaw(path):
    global _lm
    import math, mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    if _lm is None:
        _lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=os.path.join(os.path.dirname(ROOT), 'repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task')), output_facial_transformation_matrixes=True, num_faces=1))
    im = cv2.imread(path); r = _lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks:
        return None
    m = np.array(r.facial_transformation_matrixes[0]).T.flatten(); return round(math.degrees(math.atan2(m[8], m[10])), 1)

def similarity(a, b):
    fa, fb = face_feat(a), face_feat(b)
    if fa is None or fb is None:
        return -1.0
    return float(_fr[1].match(fa, fb, cv2.FaceRecognizerSF_FR_COSINE))

def cmd_plan(n):
    s = load_state(); rng = random.Random(1000 + s['next_id'])
    for _ in range(n):
        s['plans'].append(sample(rng, s['next_id'])); s['next_id'] += 1
    save_state(s); print('planned', n, '->', s['plans'][-1]['id'])

def cmd_next():
    s = load_state()
    p = next((x for x in s['plans'] if x['status'] in ('planned', 'rejected')), None)
    if p is None:
        print('no plans left'); return
    if sum(x['status'] == 'pending' for x in s['plans']) >= int(os.environ.get('ATTUNE_MAX_PENDING', '1')):
        print('waiting for review:', [x['id'] for x in s['plans'] if x['status'] == 'pending']); return
    c = client(); d = os.path.join(PENDING, p['id']); os.makedirs(d, exist_ok=True); spent = 0.0
    fp = front_prompt(p)
    r = c.images.generate(model=MODEL, prompt=fp, size=SIZE, quality=QUALITY, n=1)
    spent += cost(getattr(r, 'usage', None))
    front = os.path.join(d, f"{p['id']}-front.png"); open(front, 'wb').write(base64.b64decode(r.data[0].b64_json))
    sims = {}
    for side in (1, 2):
        best = None
        for t in range(MAX_TRIES):
            with open(front, 'rb') as fh:
                r = c.images.edit(model=MODEL, image=[fh], prompt=side_prompt(p, side), size=SIZE, quality=QUALITY, n=1)
            spent += cost(getattr(r, 'usage', None))
            out = os.path.join(d, f"{p['id']}-side_{side}.png"); tmp = out + f'.try{t}.png'
            open(tmp, 'wb').write(base64.b64decode(r.data[0].b64_json))
            sim = similarity(front, tmp); y = yaw(tmp)
            good_pose = y is not None and abs(y) > 10.5 and (y > 0) == (side == 1)
            score = sim + (1.0 if good_pose else 0.0)
            if best is None or score > best[0]:
                best = (score, tmp, sim, y)
            if sim >= SIM_MIN and good_pose:
                break
        shutil.move(best[1], out)
        for f in os.listdir(d):
            if '.try' in f:
                os.remove(os.path.join(d, f))
        sims[f'side_{side}'] = round(best[2], 3); sims[f'yaw_{side}'] = best[3]
    p.update(status='pending', tries=p['tries'] + 1, similarity=sims, prompts=dict(front=fp, side_1=side_prompt(p, 1), side_2=side_prompt(p, 2)), cost_usd=round(spent, 4))
    s['spend_usd'] = round(s['spend_usd'] + spent, 4); save_state(s)
    print(json.dumps(dict(id=p['id'], similarity=sims, identityOK=all(v >= SIM_MIN for k, v in sims.items() if k.startswith('side')), cost_usd=round(spent, 4), total_usd=s['spend_usd'], folder=d), ensure_ascii=False))

def cmd_redo_side(kid, side):
    s = load_state(); p = next(x for x in s['plans'] if x['id'] == kid); c = client(); d = os.path.join(PENDING, kid)
    front = os.path.join(d, f"{kid}-front.png"); spent = 0.0; best = None
    for t in range(MAX_TRIES):
        with open(front, 'rb') as fh:
            r = c.images.edit(model=MODEL, image=[fh], prompt=side_prompt(p, side), size=SIZE, quality=QUALITY, n=1)
        spent += cost(getattr(r, 'usage', None)); tmp = os.path.join(d, f'redo{t}.png'); open(tmp, 'wb').write(base64.b64decode(r.data[0].b64_json))
        sim = similarity(front, tmp); y = yaw(tmp); good = y is not None and abs(y) > 10.5 and (y > 0) == (side == 1)
        if best is None or sim + good > best[0]: best = (sim + good, tmp, sim, y)
        if sim >= SIM_MIN and good: break
    shutil.move(best[1], os.path.join(d, f"{kid}-side_{side}.png"))
    for f in os.listdir(d):
        if f.startswith('redo'): os.remove(os.path.join(d, f))
    p['similarity'][f'side_{side}'] = round(best[2], 3); p['similarity'][f'yaw_{side}'] = best[3]; p['cost_usd'] = round(p.get('cost_usd', 0) + spent, 4)
    s['spend_usd'] = round(s['spend_usd'] + spent, 4); save_state(s); print(kid, 'side', side, 'sim', round(best[2], 3), 'yaw', best[3], 'cost', round(spent, 4))

def excel_row(p):
    reg = '; '.join(f"{tr}: {TR_TYPE[p['regions'][rid]]}" for rid, tr, _ in REGIONS)
    look = []
    if 'oily' in p['regions'].values(): look.append('Yağlı görünüm: belirgin yağlı parlama')
    if 'dry' in p['regions'].values(): look.append('Kuru görünüm: belirgin pullanma')
    trn = {r[0]: r[1].lower() for r in REGIONS}
    sens = {k: 'yok' for k in ('Kızarıklık', 'Rozasea', 'Egzama / atopik', 'Sedef')}
    key = {'kızarıklık': 'Kızarıklık', 'rozasea': 'Rozasea', 'egzama': 'Egzama / atopik', 'sedef': 'Sedef'}.get(p['sens'])
    if key: sens[key] = ('belirgin' if key == 'Kızarıklık' else 'var') + ' — ' + ', '.join(trn[r] for r in p['sensRegions'])
    parts = [f"Yaş: {p['age']}", f"Cinsiyet: {p['sex']}", f"Ten tonu (Fitzpatrick): {FST_TR[p['tone']]}", f"Sakal: {p['beard']}",
             f"Bölge bazında cilt tipi: {reg}", *look, *(f"{k}: {v}" for k, v in sens.items()),
             f"Uçuk: {'var' if 'dudakta uçuk' in p['extras'] else 'yok'}",
             f"Sivilce: {p['acne']}" + (' — ' + ', '.join(trn[r] for r in p['acneRegions']) if p['acneRegions'] else ''),
             f"Diğer: {', '.join(p['extras']) if p['extras'] else 'yok'}", f"Desen: {p['pattern']} ({p.get('intensity','belirgin')})"]
    return '• ' + ' • '.join(parts)

def cmd_approve(kid):
    import openpyxl
    s = load_state(); p = next(x for x in s['plans'] if x['id'] == kid)
    assert p['status'] == 'pending', p['status']
    dst = os.path.join(APPROVED, kid); shutil.rmtree(dst, ignore_errors=True); shutil.move(os.path.join(PENDING, kid), dst)
    if os.path.exists(XLSX):
        wb = openpyxl.load_workbook(XLSX); ws = wb.active
    else:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Karakter Profilleri'; ws.append(['Kimlik No', 'Diğer Bilgiler'])
    ws.append([kid, excel_row(p)]); wb.save(XLSX)
    p['status'] = 'approved'; s['log'].append(dict(t=time.time(), id=kid, action='approve')); save_state(s); print('approved', kid)

def cmd_reject(kid, why):
    s = load_state(); p = next(x for x in s['plans'] if x['id'] == kid)
    shutil.rmtree(os.path.join(PENDING, kid), ignore_errors=True)
    p['status'] = 'rejected'; p.setdefault('rejections', []).append(why); s['log'].append(dict(t=time.time(), id=kid, action='reject', why=why)); save_state(s)
    print('rejected', kid, why)

def cmd_status():
    s = load_state(); from collections import Counter
    print(dict(Counter(x['status'] for x in s['plans'])), 'spend_usd', s['spend_usd'])

if __name__ == '__main__':
    a = sys.argv[1:]
    {'plan': lambda: cmd_plan(int(a[1])), 'next': cmd_next, 'approve': lambda: cmd_approve(a[1]), 'reject': lambda: cmd_reject(a[1], a[2] if len(a) > 2 else ''),
     'status': cmd_status, 'redo': lambda: cmd_redo_side(a[1], int(a[2])), 'prompt': lambda: print(front_prompt(next(x for x in load_state()['plans'] if x['id'] == a[1]))),
     'row': lambda: print(excel_row(next(x for x in load_state()['plans'] if x['id'] == a[1])))}[a[0]]()
