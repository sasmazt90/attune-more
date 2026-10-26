"""Skin result screen on the real data path (approved result UI).

Camera (Chrome fake device fed by a y4m fixture) -> production MediaPipe capture of FRONT/RIGHT/LEFT -> POST
/api/local-health/skin per photo (saved models) -> POST /api/local-health/skin/regional-fuse -> general.findings ->
health record -> result screen -> reopened record (/skin?view=latest).

No pose, quality or model result is mocked. The fixture decides what is in the photos; it is NOT a physical camera.
Requirements: core-api on 127.0.0.1:8000 with the regional model bundle (ATTUNE_REGIONAL_V3_DIR), the built app on
127.0.0.1:3000, and a three-pose y4m (SKIN_E2E_Y4M, default audit-fixtures/three-angle.y4m: front, then each side).

Flags: --software-gpu (swiftshader), --chromium (bundled Chromium instead of the Chrome channel),
--skip-native-zoom (skip the Windows native 200% zoom capture; reported as not run in proof.json).
"""
import json, os, sys, time, math, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tests/e2e'))
from playwright.sync_api import sync_playwright, expect

OUT = Path(os.environ.get('SKIN_RESULT_AUDIT_DIR', 'audit-results/skin-real-path')); OUT.mkdir(parents=True, exist_ok=True)
Y4M = Path(os.environ.get('SKIN_E2E_Y4M', 'audit-fixtures/three-angle.y4m')).resolve()
assert Y4M.exists(), f'missing camera fixture {Y4M}'
NATIVE = '--skip-native-zoom' not in sys.argv
CHANNEL = {} if '--chromium' in sys.argv else {'channel': 'chrome'}
GPU = ['--use-gl=angle', '--use-angle=swiftshader'] if '--software-gpu' in sys.argv else []
# --use-fake-ui-for-media-stream answers the browser's own camera prompt (the app's consent is clicked below)
ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--use-file-for-fake-video-capture=' + str(Y4M), '--enable-unsafe-swiftshader', *GPU]
# Records every request/response of the skin endpoints (numbers only are kept by the app; photos stay in memory here).
HOOK = """window.skinCalls=[];const of=window.fetch;window.fetch=async(...a)=>{const url=String(a[0]);
const kind=url.endsWith('/api/local-health/skin')?'skin':url.endsWith('/api/local-health/skin/regional-fuse')?'fuse':null;
const body=kind&&a[1]&&a[1].body?JSON.parse(a[1].body):null;const r=await of(...a);
if(kind==='skin'&&window.__savePhotos)(window.skinPhotos=window.skinPhotos||[]).push({pose:body.pose,photo:body.photo,landmarks:body.landmarks});
if(kind){const j=r.ok?await r.clone().json():null;window.skinCalls.push(kind==='skin'
 ?{kind,status:r.status,pose:body.pose,photoId:body.photoId,noseToImageRight:body.landmarks&&+(body.landmarks[1].x-(body.landmarks[234].x+body.landmarks[454].x)/2).toFixed(3),general:j&&{findings:j.general&&j.general.findings},source:j&&[j.sourceWidth,j.sourceHeight],findingEvidence:j&&j.regionalSkinMap&&j.regionalSkinMap.findingEvidence,regionalSkinMap:j&&j.regionalSkinMap&&{evidence:Object.keys(j.regionalSkinMap.findingEvidence||{}),boxes:(j.regionalSkinMap.findingBoxes||[]).length,models:j.regionalSkinMap.models},status2:j&&j.regionalSkinMapStatus}
 :{kind,status:r.status,poses:Object.keys(body.maps||{}),response:j});}return r;};"""
VIEW_REGIONS = {'forehead': ['forehead', 'nose'], 'periorbital': ['periorbital'], 'rightCheek': ['rightCheek'], 'leftCheek': ['leftCheek'], 'chin': ['chin']}


def seen_ids(findings, regions=None):
    return sorted({f['id'] for f in findings if f['status'] == 'seen' and (regions is None or f['region'] in regions)})


def check_result(p, rec, shots, tag, photo=True, frame=lambda: None):
    """The result screen shows exactly what the record carries (approved UI elements only)."""
    general = rec['general']; fr = general['findings']; findings = fr['findings']
    expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
    ov = p.locator('[data-skin-overview-findings]')
    assert ov.get_attribute('data-skin-findings-state') == fr.get('status', 'measured') if fr.get('status') == 'unavailable' else ov.get_attribute('data-skin-findings-state') == 'measured'
    cards = sorted(p.locator('[data-skin-overview-finding]').evaluate_all('els=>els.map(e=>e.dataset.skinOverviewFinding)'))
    pages = max(1, math.ceil(len(seen_ids(findings)) / 4))
    for _ in range(pages - 1):   # the header arrows page the 2x2 grid
        p.get_by_role('button', name='Sonraki bulgular').click()
        cards += p.locator('[data-skin-overview-finding]').evaluate_all('els=>els.map(e=>e.dataset.skinOverviewFinding)')
    if pages > 1: p.get_by_role('button', name='Sonraki bulgular').click()
    assert sorted(set(cards)) == seen_ids(findings), (cards, seen_ids(findings))
    # every seen finding shows a number (score %, area %, count) - never just "seen"
    for c in set(cards):
        if p.locator(f'[data-skin-overview-finding="{c}"]').count():
            assert any(ch.isdigit() for ch in p.locator(f'[data-skin-overview-finding="{c}"]').first.inner_text()), c
    # nothing measured is never presented as a score: no bar/percentage without a value in the record
    if not any('severity' in f or 'areaPct' in f for f in findings):
        assert '%' not in p.locator('[data-skin-overview]').inner_text()
    if not cards:
        assert p.locator('[data-skin-findings-empty]').get_attribute('data-skin-findings-empty') == ('unavailable' if fr.get('status') == 'unavailable' else 'measured')
    pill = p.locator('[data-skin-findings-unmeasured]')
    assert int(pill.get_attribute('data-skin-findings-unmeasured')) == len(fr.get('unavailable', []))
    p.screenshot(path=str(OUT / f'{tag}-overview.png'), full_page=True); shots.append(f'{tag}-overview.png'); frame(); frame()
    pill.click()
    expect(p.locator('[data-skin-unmeasured-item]')).to_have_count(len(fr.get('unavailable', [])))
    p.screenshot(path=str(OUT / f'{tag}-unmeasured.png'), full_page=True); shots.append(f'{tag}-unmeasured.png'); p.keyboard.press('Escape')
    for card in cards[:1]:
        p.locator(f'[data-skin-overview-finding="{card}"]').first.click()
        if photo: assert p.locator('[data-face-panel]').bounding_box()['width'] >= 300
        p.screenshot(path=str(OUT / f'{tag}-overview-{card}.png'), full_page=True); shots.append(f'{tag}-overview-{card}.png')
        p.locator(f'[data-skin-overview-finding="{card}"]').first.click()
    for view, regions in VIEW_REGIONS.items():
        tab = p.locator(f'[data-skin-region-tab="{view}"]'); tab.click()
        want = seen_ids(findings, regions)
        badge = tab.inner_text().strip().split('\n')[-1]
        assert (badge.isdigit() and int(badge) == len(want)) or (not want and not badge.isdigit()), (view, badge, want)
        if want:
            expect(p.locator('[data-skin-finding-card]')).to_have_count(1)
            assert p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') in want
            # mole markers are only drawn on the photo of their own pose
            if p.locator('[data-skin-finding-card]').get_attribute('data-skin-finding-card') == 'mole':
                photo_pose = p.locator('[data-face-panel]').evaluate("e=>e.closest('[data-skin-result]')&&document.querySelector('[data-skin-snapshot]')?.getAttribute('data-snapshot-pose')")
                (OUT / f'{tag}-{view}-marker-pose.json').write_text(json.dumps({'photoPose': photo_pose}), 'utf8')
            p.get_by_role('button', name='Öneriler').click(); expect(p.locator('[data-skin-recommendations]')).to_have_count(1)
            # no measured score/count in this model version -> no band is chosen
            if not any(('severity' in f or 'areaPct' in f or 'countRange' in f) for f in findings):
                expect(p.locator('[data-skin-rec-unmeasured]')).to_have_count(1)
            p.screenshot(path=str(OUT / f'{tag}-{view}-recommendations.png'), full_page=True); shots.append(f'{tag}-{view}-recommendations.png'); p.keyboard.press('Escape')
        else:
            expect(p.locator('[data-skin-findings-empty]')).to_have_count(1)
        if photo:   # the photo of the page stays readable next to the labels (no squeezed photo column)
            assert p.locator('[data-face-panel]').bounding_box()['width'] >= 300, (view, p.locator('[data-face-panel]').bounding_box())
        p.screenshot(path=str(OUT / f'{tag}-{view}.png'), full_page=True); shots.append(f'{tag}-{view}.png'); frame(); frame()
    p.locator('[data-skin-region-tab="overview"]').click()


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=ARGS, **CHANNEL)
    # Video of the run. Default: time-lapse (one viewport frame every ~1.5 s, assembled with ffmpeg at the end) because
    # Playwright's live recording slowed the browser's own capture analysis enough to miss the pose gate on a slow CPU.
    # --video-full records Playwright's live video instead.
    FULL = '--video-full' in sys.argv
    c = b.new_context(permissions=['camera'], viewport={'width': 1600, 'height': 1000},
                      **(dict(record_video_dir=str(OUT / 'video'), record_video_size={'width': 1600, 'height': 1000}) if FULL else {}))
    FR = OUT / 'frames'; FR.mkdir(exist_ok=True); frame_no = [0]
    def frame():
        if FULL: return
        try:
            p.screenshot(path=str(FR / f'{frame_no[0]:05d}.jpg'), type='jpeg', quality=60); frame_no[0] += 1
        except Exception:
            pass
    c.add_init_script(HOOK)
    # SKIN_E2E_SAVE_PHOTOS=1 (diagnostics only, fixture photos): keeps the exact photo + landmarks the app sent
    if os.environ.get('SKIN_E2E_SAVE_PHOTOS') == '1': c.add_init_script('window.__savePhotos=true')
    p = c.new_page(); errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
    assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
    p.goto('http://127.0.0.1:3000/privacy'); p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check()
    p.goto('http://127.0.0.1:3000/skin')
    consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
    consent.wait_for(timeout=10000); consent.check(); p.get_by_role('button', name='İzin ver ve devam et').click()   # the user's service consent
    start = time.monotonic()
    p.get_by_role('button', name='Analizi Başlat', exact=True).click()
    deadline = time.monotonic() + float(os.environ.get('SKIN_E2E_TIMEOUT', '420')); trace = []
    while not p.locator('[data-skin-result]').count() and time.monotonic() < deadline:
        p.wait_for_timeout(1500); frame(); p.wait_for_timeout(1500); frame()
        trace.append(p.evaluate('({t:performance.now(),calls:window.skinCalls.map(c=>[c.kind,c.pose||c.poses,c.status]),body:document.body.innerText.slice(0,400)})'))
        (OUT / 'trace.json').write_text(json.dumps(trace, ensure_ascii=False, indent=1), 'utf8')
    if not p.locator('[data-skin-result]').count():
        p.screenshot(path=str(OUT / 'failure.png'), full_page=True)
        raise SystemExit('FAIL: no result screen; see trace.json / failure.png')
    seconds = time.monotonic() - start
    if os.environ.get('SKIN_E2E_SAVE_PHOTOS') == '1':
        import base64
        for x in p.evaluate('window.skinPhotos||[]'):
            (OUT / f"sent-{x['pose']}.png").write_bytes(base64.b64decode(x['photo'].split(',')[1]))
            (OUT / f"sent-{x['pose']}-landmarks.json").write_text(json.dumps(x['landmarks']), 'utf8')
    calls = p.evaluate('window.skinCalls'); (OUT / 'api-calls.json').write_text(json.dumps(calls, ensure_ascii=False, indent=1), 'utf8')
    skin = [x for x in calls if x['kind'] == 'skin' and x['status'] == 200]; fuse = [x for x in calls if x['kind'] == 'fuse']
    # three distinct photos, one per pose, each analysed by the saved models
    assert sorted(x['pose'] for x in skin[-3:]) == ['FRONT', 'LEFT', 'RIGHT'] and len({x['photoId'] for x in skin[-3:]}) == 3, skin
    for x in skin[-3:]:
        assert x['status2'] == 'OK' and x['regionalSkinMap']['evidence'], x
        assert all(len(h) == 64 for h in x['regionalSkinMap']['models'].values()), x['regionalSkinMap']['models']
    front = next(x for x in skin[-3:] if x['pose'] == 'FRONT')
    assert front['general']['findings']['status'] == 'unavailable' and front['general']['findings']['reason'] == 'REQUIRED_POSES_MISSING'
    # the three-angle result comes from the server fusion, once
    assert len(fuse) == 1 and fuse[0]['status'] == 200 and sorted(fuse[0]['poses']) == ['FRONT', 'LEFT', 'RIGHT'], fuse
    fused = fuse[0]['response']; assert fused['findings']['status'] == 'measured'
    rec = p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    hist = p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history"))')
    assert rec['comparisonScope'] == 'three-angle-v2' and rec['general']['analysisId'] == rec['id']
    # the record carries exactly the server's findings and regional map (no client rebuild)
    assert rec['general']['findings'] == fused['findings']
    assert rec['general']['regionalSkinMap'] == fused['regionalSkinMap']
    assert hist[0]['id'] == rec['id'] and hist[0]['general']['findings'] == fused['findings']
    if fused['regionalSkinMap'] and fused['regionalSkinMap']['skinType']['quality'] == 'valid':
        assert rec['general']['skinType']['value'] == fused['regionalSkinMap']['skinType']['value']
    else:
        assert rec['general']['skinType']['value'] is None
    assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
    shots = []
    check_result(p, rec, shots, 'result', frame=frame)
    # reopen the stored record (normal app route): same measurements on the approved result screen
    p.goto('http://127.0.0.1:3000/skin?view=latest')
    check_result(p, rec, shots, 'reopened', photo=False, frame=frame)   # numeric record only: photos are kept in memory / with separate consent
    native = None
    if NATIVE:
        from owned_window_capture import capture_owned_window
        saved = c.storage_state(); c.close(); b.close()
        profile = tempfile.TemporaryDirectory(prefix='attune-skin-result-zoom-')
        pref = Path(profile.name) / 'Default'; pref.mkdir(); (pref / 'Preferences').write_text(json.dumps({'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}}), 'utf8')
        c = pw.chromium.launch_persistent_context(profile.name, headless=False, no_viewport=True, args=['--window-size=1600,1000', *ARGS], **CHANNEL)
        c.add_init_script('if(location.origin==="http://127.0.0.1:3000"&&!sessionStorage.getItem("r")){for(const v of ' + json.dumps(saved['origins'][0]['localStorage']) + ')localStorage.setItem(v.name,v.value);sessionStorage.setItem("r","1");}')
        p = c.new_page(); p.goto('http://127.0.0.1:3000/skin?view=latest'); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
        native = p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,scroll:document.documentElement.scrollWidth})')
        assert native['dpr'] >= 2 and native['scroll'] <= native['innerWidth'], native
        capture_owned_window(p, profile.name, OUT / 'native200-overview.png'); profile.cleanup()
    assert not errors, errors
    proof = dict(status='PASS', camera='fake-device y4m fixture (not a physical camera)', fixture=str(Y4M.name), poseMock=False, qualityOverride=False,
                 modelInference='real (saved models via core-api)', seconds=round(seconds, 1), recordId=rec['id'],
                 findings=rec['general']['findings'], skinType=rec['general']['skinType'].get('value'),
                 nativeZoom=native if NATIVE else 'NOT RUN (--skip-native-zoom)', screenshots=shots, pageErrors=errors)
    video = None
    if not FULL and frame_no[0]:
        import subprocess
        video = str(OUT / 'run-timelapse.mp4')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '2', '-i', str(FR / '%05d.jpg'), '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', video], check=False)
    proof['video'] = video or 'playwright live video in video/'
    (OUT / 'proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), 'utf8'); c.close()
print('PASS: camera fixture -> /skin x3 -> /skin/regional-fuse -> record -> result screen -> reopened record carry the same findings')
