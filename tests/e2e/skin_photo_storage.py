"""Three-pose skin photo storage on real persisted records (IndexedDB 'attune-skin-photos' + localStorage records).

 (a) consent on: a REAL three-pose camera scan stores FRONT, LEFT and RIGHT; every stored photoId is the sha256 of
     the decoded RGBA pixels of its own PNG, pose and size match the PNG, only FRONT carries the overview.
 (b) after a browser relaunch (no in-memory frames) /skin?view=latest and /skin?view=record&id=<A> show record A's
     own stored photos (data-snapshot-photoid and the <image> href of the face panel), per pose (overview -> FRONT,
     rightCheek -> LEFT, leftCheek -> RIGHT).
 (c) an OLDER record B (numeric copy of A with a new id/older timestamp, its own photos written with the app's own
     saveSkinPhotos) opens with B's photos and never A's.
 (d) consent off: withdrawing it on /privacy removes every stored photo and nothing is loaded; with consent off the
     app's writer stores nothing; deleting a record on /profile removes its stored photos, other rows stay.

Isolated temporary Chrome profile: never touches the user's profile. Photos never leave the temp profile except as
audit files under audit-results/ (git-ignored). Nothing about pose, quality or models is mocked.

Requirements: built app on 127.0.0.1:3000, core-api on 127.0.0.1:8000, Chrome, a three-pose y4m
(SKIN_E2E_Y4M; build one with tests/e2e/make_skin_y4m.py FRONT.png SIDE_A.png SIDE_B.png out.y4m).
usage: SKIN_E2E_Y4M=/path/three-angle.y4m python tests/e2e/skin_photo_storage.py [--chromium] [--software-gpu]
Every check runs and is reported (proof.json); exit code 1 if any check fails.
"""
import base64, hashlib, io, json, os, subprocess, sys, tempfile, time, traceback
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
APP = 'http://127.0.0.1:3000'
OUT = Path(os.environ.get('SKIN_PHOTO_STORAGE_AUDIT_DIR', ROOT / 'audit-results/skin-photo-storage')); OUT.mkdir(parents=True, exist_ok=True)
Y4M = Path(os.environ.get('SKIN_E2E_Y4M', ROOT / 'audit-fixtures/three-angle.y4m')).resolve()
assert Y4M.exists(), f'missing camera fixture {Y4M}'
CHANNEL = {} if '--chromium' in sys.argv else {'channel': 'chrome'}
GPU = ['--use-gl=angle', '--use-angle=swiftshader'] if '--software-gpu' in sys.argv else []
ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--use-file-for-fake-video-capture=' + str(Y4M), '--enable-unsafe-swiftshader', *GPU]
PHOTO_CONSENT = 'Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla'
NUMERIC_CONSENT = 'Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla'
REGION_POSE = {'overview': 'FRONT', 'rightCheek': 'LEFT', 'leftCheek': 'RIGHT'}
# What the app sent to /api/local-health/skin (pose, photoId, photo) - used only to build the older record's photos.
HOOK = """window.sentPhotos=[];const of=window.fetch;window.fetch=async(...a)=>{const url=String(a[0]);
if(url.endsWith('/api/local-health/skin')&&a[1]&&a[1].body){const b=JSON.parse(a[1].body);window.sentPhotos.push({pose:b.pose,photoId:b.photoId,photo:b.photo});}
return of(...a);};"""
# The app's own photo store module (actual source, transpiled), loaded into a page of the app's origin.
STORE_JS = subprocess.check_output(['node', '-e', "const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/skinPhotoHistory.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText);"], cwd=ROOT, text=True)

results = []


def check(name, fn):
    try:
        detail = fn(); results.append({'check': name, 'status': 'PASS', **({'detail': detail} if detail is not None else {})}); print('PASS', name, flush=True)
    except Exception as e:  # every check is reported; the run fails at the end
        results.append({'check': name, 'status': 'FAIL', 'error': f'{type(e).__name__}: {e}'}); print('FAIL', name, '-', e, flush=True); traceback.print_exc()


def rows(p):
    return p.evaluate("()=>new Promise((resolve,reject)=>{const q=indexedDB.open('attune-skin-photos');q.onupgradeneeded=()=>q.result.createObjectStore('records',{keyPath:'id'});q.onsuccess=()=>{const db=q.result,t=db.transaction('records');const r=t.objectStore('records').getAll();r.onsuccess=()=>resolve(r.result);t.oncomplete=()=>db.close();t.onerror=()=>reject(t.error);};q.onerror=()=>reject(q.error);})")


def row(p, rid):
    found = [r for r in rows(p) if r['id'] == rid]
    return json.loads(found[0]['payload']) if found else None


def rgba_sha(data_url):
    return hashlib.sha256(Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1]))).convert('RGBA').tobytes()).hexdigest()


def png_size(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1]))).size


def load_store(p):
    p.evaluate('(js)=>{window.photoStore={};new Function("exports",js)(window.photoStore);}', STORE_JS)


def shown(p, url):
    """Opens a result route and returns {region: (photoId, href sha256)} of the face panel for overview/rightCheek/leftCheek."""
    p.goto(APP + url); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
    out = {}
    for region in REGION_POSE:
        p.locator(f'[data-skin-region-tab="{region}"]').click()
        snap = p.locator('[data-skin-snapshot]')
        try:
            expect(snap).to_have_count(1, timeout=8000)
        except AssertionError:
            out[region] = None; continue
        href = snap.locator('image').first.get_attribute('href') or ''
        out[region] = (snap.get_attribute('data-snapshot-photoid'), hashlib.sha256(href.encode()).hexdigest())
    p.locator('[data-skin-region-tab="overview"]').click()
    return out


def expected(frames):
    return {region: (frames[pose]['photoId'], hashlib.sha256(frames[pose]['dataUrl'].encode()).hexdigest()) for region, pose in REGION_POSE.items()}


with tempfile.TemporaryDirectory(prefix='attune-skin-photo-storage-') as profile, sync_playwright() as pw:
    def launch():
        c = pw.chromium.launch_persistent_context(profile, headless=True, viewport={'width': 1600, 'height': 1000}, permissions=['camera'], args=ARGS, **CHANNEL)
        c.add_init_script(HOOK); p = c.pages[0] if c.pages else c.new_page(); p.on('pageerror', lambda e: errors.append(str(e))); return c, p
    errors = []
    c, p = launch()
    assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
    p.goto(APP + '/privacy'); p.get_by_label(NUMERIC_CONSENT).check()
    photo = p.get_by_label(PHOTO_CONSENT)
    if not photo.is_checked(): photo.click()
    expect(photo).to_be_checked()
    p.goto(APP + '/skin')
    consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
    consent.wait_for(timeout=15000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()
    p.get_by_role('button', name='Analizi Başlat', exact=True).click(); start = time.monotonic()
    deadline = start + float(os.environ.get('SKIN_E2E_TIMEOUT', '420'))
    while not p.locator('[data-skin-result]').count() and time.monotonic() < deadline:
        p.wait_for_timeout(3000)
    if not p.locator('[data-skin-result]').count():
        p.screenshot(path=str(OUT / 'failure.png'), full_page=True); raise SystemExit('FAIL: the real scan produced no result screen (see failure.png)')
    p.wait_for_timeout(1500)
    seconds = round(time.monotonic() - start, 1)
    rec = p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))'); A = rec['id']
    sent = {x['pose']: x for x in p.evaluate('window.sentPhotos')}
    notice = p.get_by_text('Cilt fotoğrafı kaydedilemedi. Sayısal sonuçlar korunuyor.', exact=True).count()
    stored_a = row(p, A)

    def a_three_poses():
        assert rec['comparisonScope'] == 'three-angle-v2', rec.get('comparisonScope')
        assert not notice, 'the app showed "Cilt fotoğrafı kaydedilemedi" after the scan'
        assert stored_a is not None, f'no IndexedDB row for record {A}; rows={[r["id"] for r in rows(p)]}'
        assert sorted(stored_a) == ['FRONT', 'LEFT', 'RIGHT'], sorted(stored_a)
        entry = next(r for r in rows(p) if r['id'] == A)
        assert hashlib.sha256(entry['payload'].encode()).hexdigest() == entry['sha256']
        ids = {}
        for pose, f in stored_a.items():
            assert f['angle'] == pose and f['dataUrl'].startswith('data:image/png;base64,'), pose
            assert rgba_sha(f['dataUrl']) == f['photoId'], (pose, 'photoId != sha256(decoded RGBA)')
            assert png_size(f['dataUrl']) == (f['width'], f['height']), (pose, png_size(f['dataUrl']), f['width'], f['height'])
            assert rec['captures'][pose] == {'captureId': f['photoId'], 'pose': pose, 'sourceWidth': f['width'], 'sourceHeight': f['height']}, (pose, rec['captures'].get(pose))
            for m in (f.get('localMaps') or {}).values():
                assert m['photoId'] == f['photoId'] and m['pose'] == pose and m['sourceWidth'] == f['width'] and m['sourceHeight'] == f['height'], pose
            ids[pose] = f['photoId']
        assert len(set(ids.values())) == 3, ids
        g = stored_a['FRONT'].get('general')
        assert g and g['captureId'] == ids['FRONT'] and g['pose'] == 'FRONT' and g['analysisId'] == A
        assert 'general' not in stored_a['LEFT'] and 'general' not in stored_a['RIGHT']
        assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))'), 'pixels in localStorage'
        return {'recordId': A, 'photoIds': ids, 'bytes': entry['bytes'], 'scanSeconds': seconds}
    check('(a) consent on: real scan stores FRONT/LEFT/RIGHT with own photoId=sha256(RGBA)/pose/size', a_three_poses)

    # Older record B: numeric copy of A (new id, one day older, appended after A) + its own photos (A's sent
    # photos with inverted colours), written with the app's own saveSkinPhotos under the app's origin.
    p.goto(APP + '/privacy'); load_store(p)
    B = p.evaluate('''async({rec,sent})=>{
      const id=crypto.randomUUID(),ts=new Date(Date.parse(rec.timestamp)-86400000).toISOString();
      const frames={},captures={};
      for(const pose of ['FRONT','LEFT','RIGHT']){
        const img=new Image();img.src=sent[pose].photo;await img.decode();
        const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const ctx=c.getContext('2d');
        ctx.filter='invert(1)';ctx.drawImage(img,0,0);ctx.filter='none';
        const px=ctx.getImageData(0,0,c.width,c.height).data;
        const photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',px))).map(v=>v.toString(16).padStart(2,'0')).join('');
        frames[pose]={angle:pose,photoId,dataUrl:c.toDataURL('image/png'),width:c.width,height:c.height,meshes:{},rois:[],exclusions:[],faceContour:[],contours:{},crop:{x:0,y:0,width:1,height:1}};
        captures[pose]={captureId:photoId,pose,sourceWidth:c.width,sourceHeight:c.height};
      }
      const general=rec.general?{...rec.general,captureId:frames.FRONT.photoId,analysisId:id,sourceTransform:{...rec.general.sourceTransform,sourceWidth:frames.FRONT.width,sourceHeight:frames.FRONT.height}}:undefined;
      if(general)frames.FRONT.general=general;
      const older={...rec,id,analysisId:id,timestamp:ts,captures,general};
      const history=JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]');history.push(older);
      localStorage.setItem('togg_health_skin_history',JSON.stringify(history));
      const saved=await window.photoStore.saveSkinPhotos(id,frames);
      return {id,saved,photoIds:Object.fromEntries(Object.entries(frames).map(([k,f])=>[k,f.photoId]))};
    }''', {'rec': rec, 'sent': sent})
    stored_b = row(p, B['id'])
    def b_setup():
        assert B['saved'] is True and stored_b and sorted(stored_b) == ['FRONT', 'LEFT', 'RIGHT'], B
        assert all(rgba_sha(f['dataUrl']) == f['photoId'] for f in stored_b.values()), 'B photoId != sha256(RGBA)'
        return B['photoIds']
    check('(c-setup) older record B stored through the app\'s saveSkinPhotos', b_setup)
    (OUT / 'records.json').write_text(json.dumps({'A': A, 'B': B, 'rowsAfterSetup': [r['id'] for r in rows(p)]}, indent=1), 'utf8')

    # (b)/(c): relaunch the browser (no in-memory frames), open the routes
    c.close(); c, p = launch()
    p.goto(APP + '/privacy')
    want_a = expected(stored_a) if stored_a else {r: (rec['captures'][pose]['captureId'], None) for r, pose in REGION_POSE.items()}
    want_b = expected(stored_b) if stored_b else None
    a_photo_ids = {v[0] for v in want_a.values()}

    def b_latest():
        got = shown(p, '/skin?view=latest'); p.screenshot(path=str(OUT / 'reopened-latest.png'), full_page=True)
        assert got == want_a, {'shown': got, 'expected (record A)': want_a}
        got = shown(p, f'/skin?view=record&id={A}')
        assert got == want_a, {'shown': got, 'expected (record A)': want_a}
        return got
    check('(b) after relaunch view=latest and view=record&id=A show A\'s own FRONT/LEFT/RIGHT photos', b_latest)

    def c_older():
        got = shown(p, f'/skin?view=record&id={B["id"]}'); p.screenshot(path=str(OUT / 'reopened-older.png'), full_page=True)
        assert all(v is None or v[0] not in a_photo_ids for v in got.values()), {'shown': got, 'newest record photoIds': sorted(a_photo_ids)}
        assert got == want_b, {'shown': got, 'expected (record B)': want_b}
        return got
    check('(c) opening the OLDER record B shows B\'s photos, never the newest record A\'s', c_older)

    # (d) withdrawal on /privacy clears the store; nothing loads; consent-off writer stores nothing
    p.goto(APP + '/privacy'); photo = p.get_by_label(PHOTO_CONSENT); expect(photo).to_be_checked(); photo.click(); expect(photo).not_to_be_checked(); p.wait_for_timeout(800)

    def d_withdraw():
        left = [r['id'] for r in rows(p)]
        assert left == [], left
        assert len(p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history"))')) == 2, 'numeric records must stay'
        got = shown(p, '/skin?view=latest')
        assert all(v is None for v in got.values()), got
        p.goto(APP + '/privacy'); load_store(p)
        saved = p.evaluate('async(id)=>window.photoStore.saveSkinPhotos(id,{FRONT:{angle:"FRONT",photoId:"a".repeat(64),dataUrl:"data:image/png;base64,AA==",width:32,height:32}})', A)
        assert saved is False and rows(p) == [], (saved, rows(p))
        return {'rowsAfterWithdrawal': left}
    check('(d) withdrawing photo consent removes all stored photos; nothing is loaded or written while off', d_withdraw)

    def d_delete():
        p.goto(APP + '/privacy'); photo = p.get_by_label(PHOTO_CONSENT); photo.click(); expect(photo).to_be_checked(); load_store(p)
        assert stored_b, 'record B photos unavailable'
        for rid, frames in ((B['id'], stored_b), (A, stored_a)):
            if frames: assert p.evaluate('async([id,f])=>window.photoStore.saveSkinPhotos(id,f)', [rid, frames]) is True
        before = sorted(r['id'] for r in rows(p))
        p.goto(APP + '/profile'); r = p.locator(f'[data-record-id="{B["id"]}"]'); expect(r).to_have_count(1, timeout=20000)
        r.locator('button[aria-label*="kaydını sil"]').click(); p.get_by_role('button', name='Evet, sil', exact=True).click(); expect(r).to_have_count(0, timeout=15000)
        after = sorted(x['id'] for x in rows(p))
        assert B['id'] not in after and not any(i.startswith('delete-backup:') for i in after), after
        assert after == sorted(set(before) - {B['id']}), (before, after)
        return {'before': before, 'after': after}
    check('(d) deleting a record on /profile removes its stored photos; other rows stay', d_delete)
    c.close()

failed = [r for r in results if r['status'] == 'FAIL']
proof = {'status': 'FAIL' if failed else 'PASS', 'camera': f'fake-device y4m fixture {Y4M.name} (not a physical camera)', 'poseMock': False,
         'qualityOverride': False, 'buildId': (ROOT / 'apps/vehicle-app/.next/BUILD_ID').read_text().strip() if (ROOT / 'apps/vehicle-app/.next/BUILD_ID').exists() else None,
         'results': results, 'pageErrors': errors}
(OUT / 'proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), 'utf8')
print(json.dumps({'status': proof['status'], 'failed': [r['check'] for r in failed], 'proof': str(OUT / 'proof.json')}, ensure_ascii=False))
sys.exit(1 if failed else 0)
